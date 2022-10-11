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
import logging

import AegeanTools
from AegeanTools.source_finder import SourceFinder
from AegeanTools import __citation__, __date__, __version__


def main():

    parser = OptionParser(usage="%prog [options] fitsname")
    parser.add_option(
        "--folder_cat", 
        dest="folder_cat", 
        default="Aegean_result", 
        help="A folder to keep the catalogs (default = ./Aegean_result)"
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
        "--make_diff_maps",
        dest="make_diff_maps",
        default=True,
        help="Perform source detection of the difference frames (default = True)",
    )

    (options, args) = parser.parse_args()
    folder_cat = options.folder_cat
    bmaj = float(options.bmaj)
    bmin = float(options.bmin)
    bpa = float(options.bpa)
    freq = float(options.freq)
    make_diff_maps = options.make_diff_maps

    if len(args) != 1:
        print("Please specify the FITS file for point source detection")
        sys.exit()
    else:
        fitsfile = args[0].rstrip("/")

    if make_diff_maps==True :
        print("Starting point source detection in the frame differences in ", os.path.basename(fitsfile))
    else:
        print("Starting point source detection in ", os.path.basename(fitsfile))

    try:
        os.mkdir(folder_cat)
    except FileExistsError:
        print(folder_cat, "exists")
        
    # Logging configuration
    # configure logging
    logging.basicConfig(format="%(module)s:%(levelname)s %(message)s")
    log = logging.getLogger("Aegean")
    logging_level = logging.INFO
    log.setLevel(logging_level)
    log.info("This is Aegean {0}-({1})".format(__version__, __date__))
    log.info("Run Aegean source finder in a script")    

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

    if make_diff_maps == True: 
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
            outcat = catprefix +'.cat.dat'
            outfile=open(outcat, 'w')
            sf = SourceFinder(log=log)
            found = sf.find_sources_in_image(filename, outfile=outfile)
                                        
            if len(found) == 0:
                log.info("No sources found in image")
                os.remove(outcat)
                os.remove(filename)

            data_prev = data_tmp

        elapsed = time.time() - tstart
    else:
        tstart = time.time()
        for i in range(data_fip.shape[0]):
            image = data_fip[i,:,:]
            hc[0].data=image
            hc[0].header["CRVAL3"] = crval3 + i*cdelt3
            catprefix='image-%04i' % i
            print(catprefix)
            catprefix = os.path.join(folder_cat,catprefix)
            filename=catprefix+'.fits'
            hc.writeto(filename,overwrite=True)
            outcat = catprefix +'.cat.dat'
            outfile=open(outcat, 'w')
            sf = SourceFinder(log=log)
            found = sf.find_sources_in_image(filename, outfile=outfile)
                                        
            if len(found) == 0:
                log.info("No sources found in image")
                os.remove(outcat)
                os.remove(filename)

        elapsed = time.time() - tstart

    print("Elapsed time is", elapsed, "sec")
    if data_fip.shape[0] > 0:
        print("Time per image is", elapsed/data_fip.shape[0])
    
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

