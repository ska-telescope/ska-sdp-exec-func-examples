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

import multiprocessing

def sourcefinding(fits_tmp, fits_prev, i):
    import io
    from astropy.io import fits
    from astropy import wcs
    from smart_open import open
    import os
    import numpy as np
    try:
        import bdsf
    except ImportError:
        import scipy.signal.signaltools

        def _centered(arr, newsize):
            # Return the center newsize portion of the array.
            newsize = np.asarray(newsize)
            currsize = np.array(arr.shape)
            startind = (currsize - newsize) // 2
            endind = startind + newsize
            myslice = [slice(startind[k], endind[k]) for k in range(len(endind))]
            return arr[tuple(myslice)]

        scipy.signal.signaltools._centered = _centered
        import bdsf

    from tempfile import NamedTemporaryFile
    from copy import deepcopy
    import warnings
    warnings.filterwarnings("ignore")
    np.warnings.filterwarnings('ignore', category=np.VisibleDeprecationWarning)
    import logging.config
    logging.config.dictConfig({
        'version': 1,
        # Other configs ...
        'disable_existing_loggers': True
    })
    # Extract input sent from generator
    bmaj = float(0.01)
    bmin = float(0.01)
    bpa = float(0.0)
    freq = float(1.2e9)
    thresh_isl = float(3.0)
    thresh_pix = float(5.0)

    h = fits.open(io.BytesIO(fits_tmp))
    print("h type: ", type(h))
    h[0].header['BPA'] = bpa  # stupid Miriad
    h[0].header['BMAJ'] = bmaj  # deg
    h[0].header['BMIN'] = bmin  # deg
    # Check if the central frequency is included into the header.
    # Add the keyword if required
    try:
        freq1 = h[0].header['FREQ']
    except KeyError:
        h[0].header['FREQ'] = freq  # Hz

    hc = deepcopy(h)  # get a copy to use as template
    print("hc info 0 ", hc.info())
    data_tmp = h[0].data
    print("Data shape:", data_tmp.shape)

    cdelt3 = hc[0].header['CDELT3']
    crval3 = hc[0].header['CRVAL3']
    print("CDELT3=", cdelt3, "sec")
    print("CRVAL3=", crval3, "sec")

    data_tmp = h[0].data[:, :]
    data_prev = fits.open(io.BytesIO(fits_prev))[0].data[:, :]
    # Process find possible sources in the difference of the images
    image = data_tmp - data_prev
    hc[0].data = image
    print("Any entry in image NAN?: ", np.isnan(image).any())

    hc[0].header["CRVAL3"] = crval3 + i * cdelt3
    catprefix = 'image-%04i' % i
    print(catprefix)
    folder_cat = "./BDSF_result"
    try:
        os.mkdir(folder_cat)
        os.chmod(folder_cat, 0o777)
    except FileExistsError:
        print(folder_cat, "exists")
    print("Made folder")
    catprefix = os.path.join(folder_cat, catprefix)
    filename = catprefix + '.fits'
    hc.writeto(filename, overwrite=True)
    os.chmod(filename, 0o777)

    img = bdsf.process_image(filename, thresh_isl=thresh_isl, thresh_pix=thresh_pix, rms_box=(160, 50), rms_map=True,
                             mean_map='zero', ini_method='intensity', adaptive_rms_box=True, adaptive_thresh=150,
                             rms_box_bright=(60, 15), group_by_isl=False, group_tol=10.0, flagging_opts=True,
                             flag_maxsize_fwhm=0.5, advanced_opts=True, ncores=16, blank_limit=None, quiet=True)
    cat_file_name = catprefix + '.cat.fits'
    img.write_catalog(outfile=cat_file_name, catalog_type='srl', format='fits', correct_proj='True',
                      clobber='True')
    print("Written to catalogue file")
    # Extract bytes from the temporary results file
    if os.path.exists(cat_file_name) == True:
        print("Cat file exists, i: ", i)
        with open(cat_file_name, 'rb') as fin:
            in_memory_cat_file = io.BytesIO(fin.read())
    else:
        print("No cat file for i: ", i)
        in_memory_cat_file = io.BytesIO()

    print("Extract temp results")
    # Package output to be sent to consumer
    data_out = {"i": i,
                "im_size": data_tmp.shape[0],
                "in_memory_cat_file": in_memory_cat_file.getvalue()}
    if os.path.exists(cat_file_name) == False:
        os.remove(filename)
    return data_out

class FastImagingPipeline(FlatMapFunction):
    # Class used to obtain a dirty image from a measurement set
    def flat_map(self, value):
        createTime = value[0]
        sliceIndex = value[1]

        obj_tmp = read_hadoop("out", int(sliceIndex))
        fits_tmp = obj_tmp["in_memory_fits_file"]
        obj_prev = read_hadoop("out", int(sliceIndex)-1)
        fits_prev = obj_prev["in_memory_fits_file"]
        print("fits_prev type: ", type(fits_prev))
        data_out = sourcefinding(fits_tmp, fits_prev, int(sliceIndex))
        serialData = serialize_object(data_out)
        print("Data Serialised")
        yield Row(createTime, sliceIndex, serialData)


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
                                                      "Prototype \"Source Finder\" Pipeline")
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
              'topic' = 'signal_in_src',
              'properties.bootstrap.servers' = 'kafka:9092',
              'properties.group.id' = 'test_3',
              'scan.startup.mode' = 'latest-offset',
              'value.format' = 'json'
            )
            """

    create_kafka_sink_ddl = """
            CREATE TABLE kafka_sink (
                createTime VARCHAR,
                sliceIndex STRING,
                serialData STRING
            ) WITH (
              'connector' = 'kafka',
              'sink.partitioner' = 'round-robin',
              'topic' = 'signal_out_src',
              'properties.max.request.size' = '524288000',
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
    ds_out = ds.rebalance().flat_map(FastImagingPipeline(), output_type=Types.ROW([Types.STRING(), Types.STRING(), Types.STRING()]))
    # Convert the datastream to a table so it can be written using table sinks.
    table_out = t_env.from_data_stream(ds_out,
                                                  Schema.new_builder()
                                                  .column("f0", DataTypes.STRING())
                                                  .column("f1", DataTypes.STRING())
                                                  .column("f2", DataTypes.STRING())
                                                  .build()
                                                  ).alias("createTime, sliceIndex, serialData")

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