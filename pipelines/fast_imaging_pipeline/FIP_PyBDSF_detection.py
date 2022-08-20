#!/usr/bin/env python
# coding: utf-8

import sys
from optparse import OptionParser

import numpy as np
from astropy.io import fits
from copy import deepcopy
import time
import os
import glob

# If SciPy is too new for PyBDSF version installed, then apply this fix
try:
    import bdsf
except ImportError:
    import  scipy.signal.signaltools

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


def main():

    parser = OptionParser(usage="%prog [options] fitsname")
    parser.add_option(
        "--folder_cat", 
        dest="folder_cat", 
        default="BDSF_result", 
        help="A folder to keep the catalogs (default = ./BDSF_result)"
    )
    parser.add_option(
        "--bmaj",
        dest="bmaj",
        default=0.01,
        help="Beam major FWHM size (default = 0.01 deg)",
    )
    parser.add_option(
        "--bmin",
        dest="bmin",
        default=0.01,
        help="Beam minor FWHM size (default = 0.01 deg)",
    )
    parser.add_option(
        "--bpa",
        dest="bpa",
        default=0.0,
        help="Beam position angle (default = 0 deg)",
    )
    parser.add_option(
        "--freq",
        dest="freq",
        default=1.2e9,
        help="central frequency, Hz (default = 1.2e9 Hz)",
    )
    parser.add_option(
        "--thresh_isl",
        dest="thresh_isl",
        default=3.0,
        help="A threshdold for the pixel islands, in noise rms units (PyBDSF parameter, default = 3.0)",
    )
    parser.add_option(
        "--thresh_pix",
        dest="thresh_pix",
        default=5.0,
        help="A threshdold for the source detection, in noise rms units (PyBDSF parameter, default = 5.0)",
    )

    (options, args) = parser.parse_args()
    folder_cat = options.folder_cat
    bmaj = float(options.bmaj)
    bmin = float(options.bmin)
    bpa = float(options.bpa)
    freq = float(options.freq)
    thresh_isl = float(options.thresh_isl)
    thresh_pix = float(options.thresh_pix)

    if len(args) != 1:
        print("Please specify the FITS file for point source detection")
        sys.exit()
    else:
        fitsfile = args[0].rstrip("/")

    print("Starting point source detection in the frame differences in ", os.path.basename(fitsfile))

    try:
        os.mkdir(folder_cat)
    except FileExistsError:
        print(folder_cat, "exists")

    h=fits.open(fitsfile)
    h[0].header['BPA']=bpa # stupid Miriad
    h[0].header['BMAJ']=bmaj #deg
    h[0].header['BMIN']=bmin #deg
    # Check if the central frequency is included into the header.
    # Add the keyword if required
    try:
        freq1 = h[0].header['FREQ']
    except KeyError:
        h[0].header['FREQ'] = freq #Hz
    
    hc=deepcopy(h) # get a copy to use as template

    data_fip = h[0].data
    print("Data shape:", data_fip.shape)

    cdelt3 = hc[0].header['CDELT3']
    crval3 = hc[0].header['CRVAL3']
    print("CDELT3=",cdelt3, "sec")
    print("CRVAL3=",crval3, "sec")

    data_prev = data_fip[0,:,:]
    tstart = time.time()
    for i in range(1,data_fip.shape[0]):

        data_tmp = data_fip[i,:,:]
        image = data_tmp - data_prev
        hc[0].data=image
        hc[0].header["CRVAL3"] = crval3 + i*cdelt3

        catprefix='image-%04i' % i
        print(catprefix)
        catprefix = os.path.join(folder_cat,catprefix)
        filename=catprefix+'.fits'
        hc.writeto(filename,overwrite=True)
    
        img=bdsf.process_image(filename, thresh_isl=thresh_isl, thresh_pix=thresh_pix, rms_box=(160,50), rms_map=True, mean_map='zero', ini_method='intensity', adaptive_rms_box=True, adaptive_thresh=150, rms_box_bright=(60,15), group_by_isl=False, group_tol=10.0, flagging_opts=True, flag_maxsize_fwhm=0.5,advanced_opts=True, ncores=64, blank_limit=None)
        img.write_catalog(outfile=catprefix +'.cat.fits',catalog_type='srl',format='fits',correct_proj='True',clobber='True')
        data_prev = data_tmp
        if os.path.exists(catprefix +'.cat.fits') == False:
            os.remove(filename)

    elapsed = time.time() - tstart
    print("Elapsed time is", elapsed, "sec")
    if data_fip.shape[0] > 1:
        print("Time per image is", elapsed/(data_fip.shape[0]-1))
    
# Get a list of the catalogues in folder_cat
    catprefix = os.path.join(folder_cat,"*cat.fits")
    cat_list = glob.glob(catprefix)
    cat_list.sort()
    print(cat_list)

    detections = []
    for fc in cat_list:
        hcat=fits.open(fc)
        crval3_idx = [i for i, v in enumerate(hcat[1].header["COMMENT"]) if "CRVAL3" in v][0]
        crval3_comment = hcat[1].header["COMMENT"][crval3_idx]
        tobs = crval3_comment.split()[2]
        tobsf = float(tobs)
        sdata = hcat[1].data
        print("\n", tobsf, "sec")
        for j in range(len(hcat[1].data)):
            sdata = hcat[1].data[j]
            print(sdata[0], sdata[2], sdata[4], sdata[6], sdata[6]/sdata[7])
            detections.append(sdata)    
    
if __name__ == "__main__":

    main()

