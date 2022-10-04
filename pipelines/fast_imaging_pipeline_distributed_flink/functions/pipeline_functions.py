import sys

try:
    import cupy
except ImportError:
    cupy = None
    print("ERROR: no cupy installed! Cupy is only needed for the processing")

import numpy as np
import os

try:
    import cPickle as pickle
except:
    import pickle
import io
import pybase64
import casacore.tables.table as Table

try:
    from ska_sdp_func import Gridder
except ImportError:
    cupy = None
    print("ERROR: ska_sdp_func (Gridder) not installed! This is only needed for the processing")


from astropy.io import fits
from astropy import wcs


def deserialize_object(object_in):
    pickled_object = pybase64.b64decode(object_in)
    deserialized_object = pickle.loads(pickled_object)
    return deserialized_object


def serialize_object(object_in):
    pickled_object = pickle.dumps(object_in, protocol=4)
    serialized_object = pybase64.b64encode(pickled_object).decode('utf-8')
    return serialized_object


def run_ms2dirty(do_single, do_w_stacking, vis, model, freqs, uvw, weight, flags, im_size, pixel_size_arcsec,
                 epsilon=1e-12):
    """Runs ms2dirty to invert visibility slice."""
    # Credit for this function belongs to Vlad Stolyarov

    print(" ")  # just for separation of debug output
    print(" ")

    vis = vis - model
    vis[np.where(flags > 0)] = 0  # Apply flags.
    vis = vis[:, :, 0] + vis[:, :, 3]

    if do_single:
        vis = vis.astype(np.complex64)
        freqs = freqs.astype(np.float32)
        uvw = uvw.astype(np.float32)
        weight = weight.astype(np.float32)

    pixel_size_rad = pixel_size_arcsec / 3600. * np.pi / 180.0

    # Run gridder test on GPU, using cupy arrays.
    if cupy:
        vis_gpu = cupy.asarray(vis)
        freqs_gpu = cupy.asarray(freqs)
        uvw_gpu = cupy.asarray(uvw)
        weight_gpu = cupy.asarray(weight)
        dirty_image_gpu = cupy.zeros([im_size, im_size], uvw.dtype)

        # Create gridder
        gridder = Gridder(
            uvw_gpu,
            freqs_gpu,
            vis_gpu,
            weight_gpu,
            dirty_image_gpu,
            pixel_size_rad,
            pixel_size_rad,
            epsilon,
            do_w_stacking,
        )

        # Run gridder
        gridder.ms2dirty(
            uvw_gpu, freqs_gpu, vis_gpu, weight_gpu, dirty_image_gpu
        )

        # Copy dirty image from GPU to CPU memory
        dirty_image = cupy.asnumpy(dirty_image_gpu)

    return dirty_image


def process_ms_slice(data_in):
    # Extract input sent from generator
    i = data_in["i"]
    do_single = data_in["do_single"]
    do_w_stacking = data_in["do_w_stacking"]
    vis_snap = data_in["vis_snap"]
    model_snap = data_in["model_snap"]
    freqs = data_in["freqs"]
    uvw_snap = data_in["uvw_snap"]
    weight_snap = data_in["weight_snap"]
    flags_snap = data_in["flags_snap"]
    im_size = data_in["im_size"]
    pixel_size_arcsec = data_in["pixel_size_arcsec"]
    epsilon = data_in["epsilon"]
    mstime_unique = data_in["mstime_unique"]

    # Process the data using the SKA Processing Function Library
    dirty_image = run_ms2dirty(do_single, do_w_stacking, vis_snap, model_snap, freqs, uvw_snap, weight_snap,
                               flags_snap, im_size, pixel_size_arcsec, epsilon=epsilon)

    # Write the results into the data cube FITS file data(ntimes, im_size, im_size)

    # Create a new WCS object.  The number of axes must be set
    # from the start
    w = wcs.WCS(naxis=3)

    # Create fits file header
    nx = im_size
    ny = im_size
    cdelt = pixel_size_arcsec / 3600.
    tstart1 = mstime_unique[0]
    ntime1 = mstime_unique.shape[0]
    tdelt1 = (mstime_unique[-1] - tstart1) / (ntime1 - 1)
    w.wcs.crpix = [nx, ny, 1.0]
    w.wcs.cdelt = np.array([-cdelt, cdelt, tdelt1])
    w.wcs.crval = [180., 0.0, tstart1]
    w.wcs.ctype = ["RA---TAN", "DEC--TAN", "TIME"]
    w.wcs.cunit = ["deg", "deg", "s"]
    header = w.to_header()
    hdumodel = fits.PrimaryHDU(data=dirty_image.astype(np.float32), header=header)
    hdumodel.header['BUNIT'] = 'K'

    in_memory_fits_file = io.BytesIO()
    hdumodel.writeto(in_memory_fits_file, overwrite=True)

    # Package output to be sent to consumer
    data_out = {"i": i,
                "im_size": im_size,
                "in_memory_fits_file": in_memory_fits_file.getvalue()}

    return data_out


def producer_open_ms(args, do_single, epsilon, do_w_stacking, im_size, pixel_size_arcsec):
    """ Reads a measurement set and then return each time slice individually """
    if len(args) != 1:
        print('Please specify a Measurement Set')
        sys.exit()
    else:
        MSfile = args[0].rstrip('/')

    MSname = os.path.basename(MSfile)

    print(MSfile)

    table_all = Table(MSfile)
    ColNames = table_all.colnames()

    for col in ColNames:
        print(col)

    # Read the frequencies
    table_freq = Table(MSfile + "/SPECTRAL_WINDOW")
    for col in table_freq.colnames():
        print(col)

    freqs = table_freq.getcol("CHAN_FREQ")[0]

    # Find unique times and their indices
    mstime = table_all.getcol("TIME")
    mstime_unique, time_idx = np.unique(mstime, return_index=True)

    # Loop over unique times and send each slice
    ms_data = {"time_idx": time_idx, "mstime_unique": mstime_unique, "mstime": mstime, "table_all": table_all,
               "do_single": do_single, "do_w_stacking": do_w_stacking, "freqs": freqs, "im_size": im_size,
               "pixel_size_arcsec": pixel_size_arcsec, "epsilon": epsilon}

    return ms_data


def producer_send_slice(i, ms_data):
    """ Send a specified slice of a measurement set """
    # Extract data about the measurement set analysed (required to send a slice)
    time_idx = ms_data["time_idx"]
    mstime_unique = ms_data["mstime_unique"]
    mstime = ms_data["mstime"]
    table_all = ms_data["table_all"]
    do_single = ms_data["do_single"]
    do_w_stacking = ms_data["do_w_stacking"]
    freqs = ms_data["freqs"]
    im_size = ms_data["im_size"]
    pixel_size_arcsec = ms_data["pixel_size_arcsec"]
    epsilon = ms_data["epsilon"]

    # Find start and end indices for each snapshot
    istart = time_idx[i]
    if i != len(mstime_unique) - 1:
        iend = time_idx[i + 1] - 1
    else:
        iend = len(mstime) - 1
    number_of_rows_to_read = iend - istart + 1
    vis_snap = table_all.getcol("DATA", istart, number_of_rows_to_read).astype(np.complex128)

    try:
        model_snap = table_all.getcol("MODEL_DATA", istart, number_of_rows_to_read).astype(np.complex128)
    except:
        model_snap = np.zeros(vis_snap.shape)

    uvw_snap = table_all.getcol("UVW", istart, number_of_rows_to_read)
    weight_snap = np.ones(vis_snap.shape)
    flags_snap = table_all.getcol("FLAG", istart, number_of_rows_to_read)
    # weight_snap = table_all.getcol("WEIGHT_SPECTRUM", istart, number_of_rows_to_read)

    print("\n", i, mstime_unique[i], istart, iend, number_of_rows_to_read, vis_snap.shape, freqs.shape,
          uvw_snap.shape, "\n")

    slice_data_out = {"i": i,
                      "do_single": do_single,
                      "do_w_stacking": do_w_stacking,
                      "vis_snap": vis_snap,
                      "model_snap": model_snap,
                      "freqs": freqs,
                      "uvw_snap": uvw_snap,
                      "weight_snap": weight_snap,
                      "flags_snap": flags_snap,
                      "im_size": im_size,
                      "pixel_size_arcsec": pixel_size_arcsec,
                      "epsilon": epsilon,
                      "mstime_unique": mstime_unique,
                      }
    return slice_data_out


def consumer_write_slice(slice_data_in):
    """ Writes the output of the processing function to a file"""
    fits_image_filename = "./fits/" + str(slice_data_in["i"]) + "_" + str(slice_data_in["im_size"]) + "p.fits"
    f = open(fits_image_filename, "wb")
    f.write(slice_data_in["in_memory_fits_file"])
    f.close()
