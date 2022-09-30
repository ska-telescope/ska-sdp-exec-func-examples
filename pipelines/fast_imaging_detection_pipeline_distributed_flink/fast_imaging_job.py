################################################################################
#  Licensed to the Apache Software Foundation (ASF) under one
#  or more contributor license agreements.  See the NOTICE file
#  distributed with this work for additional information
#  regarding copyright ownership.  The ASF licenses this file
#  to you under the Apache License, Version 2.0 (the
#  "License"); you may not use this file except in compliance
#  with the License.  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
# limitations under the License.
################################################################################
import torch
import sys
from pyflink.common import Row, Configuration
from pyflink.common.typeinfo import Types
from pyflink.common.restart_strategy import RestartStrategies
from pyflink.datastream import StreamExecutionEnvironment, FlatMapFunction, RuntimeContext
from pyflink.table import StreamTableEnvironment, DataTypes, Schema
from pyflink.datastream.checkpointing_mode import CheckpointingMode
from pyflink.util.java_utils import get_j_env_configuration

try:
    import cupy
except ImportError:
    cupy = None
    print("ERROR: no cupy!")
    sys.exit()

from pipeline_functions import serialize_object, deserialize_object, process_ms_slice, read_hadoop, write_hadoop

class FastImagingPipeline(FlatMapFunction):
    # Class used to obtain a dirty image from a measurement set
    def flat_map(self, value):
        createTime = value[0]
        sliceIndex = value[1]
        try:
            data_in = read_hadoop("in",sliceIndex)
            data_out = process_ms_slice(data_in)
            write_hadoop(data_out, "out", sliceIndex)
            print("Hadoop Written")
        except Exception:
            pass
        yield Row(createTime, sliceIndex)


def FIP_processing():
    env = StreamExecutionEnvironment.get_execution_environment()
    # start a checkpoint every 1000 ms
    env.enable_checkpointing(1000)

    # set mode to exactly-once (this is the default)
    env.get_checkpoint_config().set_checkpointing_mode(CheckpointingMode.EXACTLY_ONCE)

    # make sure 500 ms of progress happen between checkpoints
    env.get_checkpoint_config().set_min_pause_between_checkpoints(500)

    # checkpoints have to complete within one minute, or are discarded
    env.get_checkpoint_config().set_checkpoint_timeout(2000000)

    # only two consecutive checkpoint failures are tolerated
    env.get_checkpoint_config().set_tolerable_checkpoint_failure_number(5)

    # allow only one checkpoint to be in progress at the same time
    env.get_checkpoint_config().set_max_concurrent_checkpoints(1)

    env.get_checkpoint_config().enable_unaligned_checkpoints()
    env.set_restart_strategy(RestartStrategies.fixed_delay_restart(restart_attempts=60,
                                                                   delay_between_attempts=int(2 * 1e3)))  # delay in ms
    t_env = StreamTableEnvironment.create(stream_execution_environment=env)
    t_env.get_config().get_configuration().set_string("pipeline.name",
                                                      "Prototype \"Fast\" Imaging Pipeline")
    config = Configuration(j_configuration=get_j_env_configuration(env._j_stream_execution_environment))
    config.set_boolean("python.fn-execution.memory.managed", True)
    config.set_boolean("python.profile.enabled", True)
    config.set_integer("python.fn-execution.bundle.time", 1000)
    config.set_integer("python.fn-execution.bundle.size", 2)

    # This is so that no downstream process waits for watermarks which kafka does not provide.
    # Without this the pipeline fails when parallelism is greater than 4.
    # I am not sure how kafka topic partitions work, but they are apparently used to generate watermarks at the source.
    t_env.get_config().get_configuration().set_string("table.exec.source.idle-timeout", "1 s")

    create_kafka_source_ddl = """
            CREATE TABLE kafka_source (
                createTime VARCHAR,
                sliceIndex STRING
            ) WITH (
              'connector' = 'kafka',
              'sink.partitioner' = 'round-robin',
              'topic' = 'signal_in',
              'properties.bootstrap.servers' = 'kafka:9092',
              'properties.group.id' = 'test_3',
              'scan.startup.mode' = 'latest-offset',
              'value.format' = 'json'
            )
            """

    create_kafka_sink_ddl = """
            CREATE TABLE kafka_sink (
                createTime VARCHAR,
                sliceIndex STRING
            ) WITH (
              'connector' = 'kafka',
              'sink.partitioner' = 'round-robin',
              'topic' = 'signal_out',
              'properties.bootstrap.servers' = 'kafka:9092',
              'properties.group.id' = 'test_3',
              'scan.startup.mode' = 'latest-offset',
              'value.format' = 'json'
            )
            """
    # Sets up Table API calls
    t_env.execute_sql(create_kafka_source_ddl)
    t_env.execute_sql(create_kafka_sink_ddl)

    # Create Table using the source
    table = t_env.from_path("kafka_source")

    # Convert Table to Datastream
    ds = t_env.to_data_stream(table)


    # Datastream which records the current flag in the baseline
    ds_out = ds.rebalance().flat_map(FastImagingPipeline(), output_type=Types.ROW([Types.STRING(), Types.STRING()]))
    # Convert the datastream to a table so it can be written using table sinks.
    table_out = t_env.from_data_stream(ds_out,
                                                  Schema.new_builder()
                                                  .column("f0", DataTypes.STRING())
                                                  .column("f1", DataTypes.STRING())
                                                  .build()
                                                  ).alias("createTime, sliceIndex")

    # To have multiple sinks in a job we use statement sets
    # create a statement set
    statement_set = t_env.create_statement_set()
    statement_set.add_insert("kafka_sink", table_out)
    statement_set.execute()
    print(env.get_execution_plan())
    # Prints the execution plan for illustrative purposes, remove the -d option to see the output.
    # The output can be visualised using steps here:
    # https://nightlies.apache.org/flink/flink-docs-release-1.13/docs/dev/execution/execution_plans/
    print("To confirm the cuda flink image is built correctly...")
    print("Flink job manager sees the following GPU on its node:")
    print(torch.cuda.get_device_name(0))

if __name__ == '__main__':
    FIP_processing()