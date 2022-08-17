#!/usr/bin/env python
# coding: utf-8

import os
import time
from astropy.io import fits
from astropy.time import Time
from PIL import Image, ImageDraw, ImageFont

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import sys
from optparse import OptionParser


# fontPath = '/usr/share/fonts/dejavu/DejaVuSansMono.ttf' # CSD3
fontPath = "/usr/share/matplotlib/mpl-data/fonts/ttf/DejaVuSansMono.ttf"  # Fedora35

sans48 = ImageFont.truetype(fontPath, 48)

def main():

    parser = OptionParser(usage="%prog [options] fitsname")
    parser.add_option(
        "--vmin", dest="vmin", default=None, help="Minimum value for output"
    )
    parser.add_option(
        "--vmax", dest="vmax", default=None, help="Maximum value for output"
    )

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
        print("Please specify a FITS file")
        sys.exit()
    else:
        fitsfile = args[0].rstrip("/")

    fitsfile_base = os.path.basename(fitsfile)

    hdul = fits.open(fitsfile)
    hdul.info()
    nframes = hdul[0].header["NAXIS3"]
    ny = hdul[0].header["NAXIS2"]
    data = hdul[0].data
    data.shape
    for i in range(nframes):
        map_date = hdul[0].header["CRVAL3"] + i * hdul[0].header["CDELT3"]
        t_mjd = Time(map_date, format="jd", scale="utc").mjd
        tt = str(t_mjd)
        pp = "pic_" + str(i).zfill(4) + ".png"
        print(pp)
        tstart = time.time()
        plt.imshow(data[i], vmin=vmin, vmax=vmax)
        plt.colorbar()
        plt.savefig(pp, dpi=200)
        plt.clf()
        # plt.show()
        telapsed = time.time() - tstart
        print("Elapsed time1 = ", telapsed, "sec")
        tstart = time.time()
        img = Image.open(pp)
        xx = data.shape[1]
        yy = data.shape[2]
        draw = ImageDraw.Draw(img)
        factor = 2048 / ny
        draw.text(
            (0.18 * xx * factor, 0.0137 * yy * factor),
            "Frame : " + str(i).zfill(len(str(nframes))) + " / " + str(nframes),
            fill=("black"),
            font=sans48,
        )
        draw.text(
            (0.137 * xx * factor, 0.434 * yy * factor),
            "Time  : " + tt,
            fill=("black"),
            font=sans48,
        )
        img.save(pp)
        telapsed = time.time() - tstart
        print("Elapsed time2 = ", telapsed, "sec")

    frame = "2048x2048"
    fps = 10
    opmovie = fitsfile_base.split("-t")[0] + ".mp4"
    os.system(
        "ffmpeg -y -r "
        + str(fps)
        + " -f image2 -s "
        + frame
        + " -i pic_%04d.png -vcodec libx264 -crf 25 -pix_fmt yuv420p "
        + opmovie
    )


if __name__ == "__main__":

    main()
