import sys
sys.path.insert(0, '../functions')
from pipeline_functions import serialize_object, deserialize_object, process_ms_slice, producer_open_ms, \
    producer_send_slice, consumer_write_slice
from optparse import OptionParser

if __name__ == '__main__':
    """This file illustrates how the the FLink Fast Imaging Pipeline work by using the same function locally in Python"""

    # The following is done by the Generator
    # Parse input arguments to select measurement set
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
    (options, args) = parser.parse_args()
    do_single = bool(options.do_single)
    epsilon = float(options.epsilon)
    do_w_stacking = bool(options.do_w_stacking)
    im_size = int(options.im_size)
    pixel_size_arcsec = float(options.pixel_size_arcsec)

    ms_data = producer_open_ms(args, do_single, epsilon, do_w_stacking, im_size, pixel_size_arcsec)
    mstime_unique = ms_data["mstime_unique"]

    for i in range(len(mstime_unique)):
        slice_data = producer_send_slice(i, ms_data)

        # For use in Flink serialise data and send via Kafka
        # Serialisation is not needed for this example, but it is included as it features in the Flink Pipeline
        serial_data_in = serialize_object(slice_data)

        # Here Kafka is used in the pipeline to transport the data to Flink, using the Flink Kafka Source

        # Done in the Flink Job
        data_in = deserialize_object(serial_data_in)
        data_out = process_ms_slice(data_in)
        serial_data_out = serialize_object(data_out)

        # Here Kafka is used in the pipeline to transport the data from Flink, using the Flink Kafka Sink

        # Done by the Consumer
        slice_data_out = deserialize_object(serial_data_out)
        consumer_write_slice(slice_data_out)
