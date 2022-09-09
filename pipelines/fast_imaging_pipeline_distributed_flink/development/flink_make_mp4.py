#!/usr/bin/env python
# coding: utf-8

import glob
import os
import random
import string
import time
from astropy.io import fits
from astropy.time import Time
from PIL import Image, ImageDraw, ImageFont

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pathlib
import sys
from optparse import OptionParser

from natsort import natsorted

# fontPath = '/usr/share/fonts/dejavu/DejaVuSansMono.ttf' # CSD3
fontPath = '/usr/share/matplotlib/mpl-data/fonts/ttf/DejaVuSansMono.ttf'  # Fedora35

sans48 = ImageFont.truetype(fontPath, 48)


# fitsfile = "1636091170_sdp_l0_128ch_t100sec_MTP0013_scan8_2048p.fits"

def main():
    parser = OptionParser(usage='%prog [options] fits_folder_name')
    parser.add_option('--vmin', dest='vmin', default=None, help='Minimum value for output')
    parser.add_option('--vmax', dest='vmax', default=None, help='Maximum value for output')

    (options, args) = parser.parse_args()
    try:
        vmin = float(options.vmin)
    except:
        vmin = None

    try:
        vmax = float(options.vmax)
    except:
        vmax = None

    if len(args) != 1:
        print('Please specify a folder with fits files')
        sys.exit()
    else:
        fitsfile_loc = args[0].rstrip('/')

    fitsfile_base = os.path.basename(fitsfile_loc)

    from os import listdir
    from os.path import isfile, join

    fitsfiles = [f for f in listdir(fitsfile_loc) if isfile(join(fitsfile_loc, f))]
    fitsfiles = natsorted(fitsfiles)
    print("fits files found: ", fitsfiles)
    for fitsfile in fitsfiles:
        fits_with_path = str(str(fitsfile_loc) + "/" + str(fitsfile))
        hdul = fits.open(fits_with_path)
        hdul.info()
        ny = hdul[0].header['NAXIS2']
        data = hdul[0].data
        data.shape
        i = int(os.path.basename(fitsfile).split('_')[0]) # fits filename specific
        map_date = hdul[0].header['CRVAL3'] + i * hdul[0].header['CDELT3']
        t_mjd = Time(map_date, format='jd', scale='utc').mjd
        tt = str(t_mjd)
        pp = './pics/pic_' + str(i).zfill(4) + '.png'
        print(pp)
        tstart = time.time()
        plt.imshow(data, vmin=vmin, vmax=vmax);
        plt.colorbar()
        plt.savefig(pp, dpi=200)
        plt.clf()
        # plt.show()
        telapsed = time.time() - tstart
        print("Elapsed time1 = ", telapsed, "sec")
        tstart = time.time()
        img = Image.open(pp)
        xx = data.shape[0]
        yy = data.shape[1]
        draw = ImageDraw.Draw(img)
        factor = 2048 / ny
        draw.text((0.18 * xx * factor, 0.0137 * yy * factor),
                  'Frame : ' + str(i).zfill(len(str(len(fitsfiles)))) + ' / ' + str(len(fitsfiles)), fill=('black'), font=sans48)
        draw.text((0.137 * xx * factor, 0.434 * yy * factor), 'Time  : ' + tt, fill=('black'), font=sans48)
        img.save(pp)
        telapsed = time.time() - tstart
        print("Elapsed time2 = ", telapsed, "sec")

    frame = '2048x2048'
    fps = 10
    opmovie = fitsfile_base.split('-t')[0] + '.mp4'
    os.system('ffmpeg -y -r ' + str(
        fps) + ' -f image2 -s ' + frame + ' -i ./pics/pic_%04d.png -vcodec libx264 -crf 25 -pix_fmt yuv420p ' + opmovie)


if __name__ == '__main__':
    main()