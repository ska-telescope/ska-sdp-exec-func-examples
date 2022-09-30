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

from kafka import KafkaConsumer
from kafka import errors 
from json import loads
from time import sleep
import logging

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')
try:
    import cPickle as pickle
except:
    import pickle

from pipeline_functions import deserialize_object, consumer_write_slice, read_hadoop

def write_data(producer):
    # Generate sine wave and random data interspersed
    for message in producer:
        #print("%s key=%s value=%s" % (message.topic, message.key, message.value))
        logging.info("Kafka message received")
        value = message.value
        bytes_out_b64 = value["serialData"]
        sources_out = deserialize_object(bytes_out_b64)

        fits_image_filename = "./catfits/" + str(sources_out["i"]) + "_" + str(
            sources_out["im_size"]) + "p.cat.fits"
        f = open(fits_image_filename, "wb")
        f.write(sources_out["in_memory_cat_file"])
        f.close()
        logging.info("written to file")

def create_consumer():
    print("Connecting to Kafka brokers")
    topic = "signal_out_src"
    for i in range(0, 6):
        try:
            consumer = KafkaConsumer(topic, bootstrap_servers=['kafka:9092'],
                            value_deserializer=lambda x: loads(x), max_partition_fetch_bytes=524288000)
            print("Connected to Kafka")
            return consumer
        except errors.NoBrokersAvailable:
            print("Waiting for brokers to become available")
            sleep(10)

    raise RuntimeError("Failed to connect to brokers within 60 seconds")

if __name__ == '__main__':
    producer = create_consumer()
    write_data(producer)
