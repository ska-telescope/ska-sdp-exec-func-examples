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
import time
from json import dumps
from time import sleep

import logging
from optparse import OptionParser

import confluent_kafka

from pipeline_functions import serialize_object, producer_open_ms, producer_send_slice, write_hadoop, read_hadoop
logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')


def write_data(producer, args, do_single, epsilon, do_w_stacking, im_size, pixel_size_arcsec):
    topic = "signal_in_src"
    # Generate sine wave and random data interspersed
    ms_data = producer_open_ms(args, do_single, epsilon, do_w_stacking, im_size, pixel_size_arcsec)
    mstime_unique = ms_data["mstime_unique"]

    for i in range(1, len(mstime_unique)): #do not send the first slice when finding sources as there is no preceeding slice

        # Add timestamp and send data
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        cur_data = {"createTime": ts, "sliceIndex": i}
        logging.info("Sending message with topic: " + str(topic))
        logging.info("Starting send")

        # send slice using Kafka
        producer.produce(topic, value=dumps(cur_data).encode('utf-8'))
        producer.poll(0)
        logging.info("Sent message with topic: " + str(topic))
        sleep(message_interval)
    producer.flush()

def create_producer():
    print("Connecting to Kafka brokers")
    for i in range(0, 6):
        try:
            conf = {'bootstrap.servers': 'kafka:9092', 'message.max.bytes': '524288000',
                    'batch.size': '524288000'}
            producer = confluent_kafka.Producer(**conf)
            print("Connected to Kafka")
            return producer
        except Exception as e:
            print("Waiting for brokers to become available")
            sleep(10)

    raise RuntimeError("Failed to connect to brokers within 60 seconds")

if __name__ == '__main__':
    ## This is a bit of a bodge, the only parameter which does anything is the measurement set file.
    producer = create_producer()
    parser = OptionParser(usage='%prog [options] msname')
    parser.add_option('--im_size', dest='im_size', default=1024, help='Image size (default = 1024)')
    parser.add_option('--pixel_size_arcsec', dest='pixel_size_arcsec', default=1.0,
                      help='Pixel size (default = 1.0 arcsec)')
    parser.add_option('--do_single', dest='do_single', default=False,
                      help='Make inverts in a single precision (default = False)')
    parser.add_option('--epsilon', dest='epsilon', default=1e-12,
                      help='Accuracy parameter (default = 1e-12 for FP64, should be 1e-5 for FP32)')
    parser.add_option('--do_w_stacking', dest='do_w_stacking', default=True,
                      help='To perform w-stacking gridding (default = True)')
    parser.add_option('--message_interval', dest='message_interval', default=0.1,
                      help='The interval at which messages are sent')
    (options, args) = parser.parse_args()
    do_single = bool(options.do_single)
    epsilon = float(options.epsilon)
    do_w_stacking = bool(options.do_w_stacking)
    im_size = int(options.im_size)
    pixel_size_arcsec = float(options.pixel_size_arcsec)
    message_interval = float(options.message_interval)

    write_data(producer, args, do_single, epsilon, do_w_stacking, im_size, pixel_size_arcsec)

