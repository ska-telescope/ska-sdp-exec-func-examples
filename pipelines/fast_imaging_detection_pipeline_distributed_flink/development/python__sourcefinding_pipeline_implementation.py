import sys
sys.path.insert(0, '../functions')
from pipeline_functions import serialize_object, deserialize_object, process_ms_slice, producer_open_ms, \
    producer_send_slice, consumer_write_slice, write_fs, read_fs
from optparse import OptionParser
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
                             flag_maxsize_fwhm=0.5, advanced_opts=True, ncores=64, blank_limit=None, debug=True)
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
                "im_size": im_size,
                "in_memory_cat_file": in_memory_cat_file.getvalue()}
    if os.path.exists(cat_file_name) == False:
        os.remove(filename)
    return data_out
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

        # Here Kafka is used in the pipeline to transport the data to Flink, using the Flink Kafka Source

        # Done in the Flink Job
        data_out = process_ms_slice(slice_data)
        write_fs(data_out, "out", int(i))
        # Here Kafka is used in the pipeline to transport the data from Flink, using the Flink Kafka Sink

        # Done by the Consumer
        consumer_write_slice(data_out)
        
        if i > 0:
            obj_tmp = read_fs("out", int(i))
            fits_tmp = obj_tmp["in_memory_fits_file"]
            obj_prev = read_fs("out", int(i) - 1)
            fits_prev = obj_prev["in_memory_fits_file"]
                
            sources_out = sourcefinding(fits_tmp, fits_prev, i)
            fits_image_filename = "./catfits/" + str(sources_out["i"]) + "_" + str(
                sources_out["im_size"]) + "p.cat.fits"
            f = open(fits_image_filename, "wb")
            f.write(sources_out["in_memory_cat_file"])
            f.close()