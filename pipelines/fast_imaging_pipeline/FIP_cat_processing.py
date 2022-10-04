#!/usr/bin/env python
# coding: utf-8

import numpy as np
import  scipy.signal.signaltools

from astropy.io import fits
from copy import deepcopy
import time
import os
import glob
import sys
from optparse import OptionParser

from sklearn.cluster import MeanShift

#folder_cat = "PyBDSF_test/BDSF_result"
#cat_ascii = "transients_cat.dat"

def main():

    parser = OptionParser(usage="%prog [options] catalogue_folder")
    parser.add_option(
        "--cat_ascii", 
        dest="cat_ascii", 
        default="transients_cat.dat", 
        help="A file with a list of detected transients (default = transients_cat.dat)"
    )
    
    (options, args) = parser.parse_args()
    cat_ascii = options.cat_ascii
 
    if len(args) != 1:
        print("Please specify the folder with the catalogue fits-files")
        sys.exit()
    else:
        folder_cat = args[0].rstrip("/")
   


    # Get a list of the catalogues in folder_cat
    catprefix = os.path.join(folder_cat,"*cat.fits")
    cat_list = glob.glob(catprefix)
    cat_list.sort()
    print(cat_list)


    detections = []
    dettimes = []
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
            dettimes.append(tobsf)

    detections1 = np.asarray(detections)

    sample = detections1[:, (2,4)].astype(float)
    clustering = MeanShift(bandwidth=0.01).fit(sample)
    clabels = clustering.labels_
    clabels_unique = np.unique(clabels)
    idx_sorted = np.argsort(clabels)

    f_output = open(cat_ascii, 'w')
    print()    
    print("Output catalogue of the transients:")
    title_string = "Ns RA_deg     RA_err   Dec_deg    Dec_err Flux    Flux_err T_sec T_err Nobs\n"
    print(title_string)
    f_output.write(title_string)
    # Just find the parameters of the sources
    Source_number = 0
    for label in clabels_unique:
        idxl = np.where(clabels == label)
        #print(label, idxl)    
        stimes = np.asarray(dettimes)[idxl]
        if len(stimes) > 2:
            Source_number = Source_number + 1
            sflux = detections1[idxl,6].astype(float)[0]
            sRA  = detections1[idxl,2].astype(float)[0]
            sDec = detections1[idxl,4].astype(float)[0]
            stimes_diff = np.diff(stimes)
            Period_T_mean = np.mean(stimes_diff)
            Period_T_std  = np.std(stimes_diff)
            Flux_mean     = np.mean(sflux)
            Flux_std      = np.std(sflux)
            RA_mean       = np.mean(sRA)
            RA_std        = np.std(sRA)
            Dec_mean      = np.mean(sDec)
            Dec_std       = np.std(sDec)
            source_string = "{} {:.6f} {:.6f} {:.6f} {:.6f} {:.5f} {:.5f} {:.3f} {:.3f} {}".format(Source_number, RA_mean, RA_std, Dec_mean, Dec_std, Flux_mean, Flux_std, Period_T_mean, Period_T_std, len(stimes))
            print(source_string)
            f_output.write(source_string + "\n")
    f_output.close()

if __name__ == "__main__":

    main()


