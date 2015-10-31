#!/usr/bin/env python2
"""
RoostLogger_Report.py - Plot relative bat activity with respect to
    time and date given recordings made with a Titley Scientific
    Anabat RoostLogger.

This script requires Python 2, NumPy, and MatPlotLib; all of which
should be installed sufficiently if ArcGIS 10.X is installed on a
Windows 7 machine (though ArcGIS is *not* a requirement at all).
Assuming Python is installed and associated with .PY files, simply
double-clicking on this script should launch it graphically.


AUTHOR
======

David A. Riggs <david_a_riggs@nps.gov>
Physical Science Technician, Lava Beds National Monument


HISTORY
=======

2015-XX-XX:  Initial public release.


LICENSE
=======

As a work of the United States Government, this project is in the
public domain within the United States.

Additionally, we waive copyright and related rights in the work
worldwide through the CC0 1.0 Universal public domain dedication.
"""

import sys, os, os.path
from datetime import datetime, date
from glob import glob
import struct
import mmap
import contextlib

import numpy as np

import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator


# Display colormap, see:  http://matplotlib.org/examples/color/colormaps_reference.html
COLORMAP = 'cubehelix'  # afmhot, gist_heat, hot, copper, cool, bone, gray

# Tweak this value higher for longer (timewise) deployments
ASPECT_RATIO = 6.0

# Specify the size of a time "pixel" in minutes
BINSIZE_MINS = 10

BINS_PER_HOUR = 60 / BINSIZE_MINS

CACHE_FILE_TIMES = '.activity_report.timestamps.txt'
CACHE_FILE_DATES = '.activity_report.dates.txt'


def anabat_date(fname):
    """Extract timestamp as datetime from Anabat format file"""
    # See: http://users.lmi.net/corben/fileform.htm#ANABAT_SEQUENCE_FILE_TYPE_132
    with open(fname, 'rb') as f:
        with contextlib.closing(mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)) as bytes:
            vals = struct.unpack_from('HBBBBB', bytes, 0x120)
            return datetime(*vals)
    

def main(dirname, logscale=True):
    """
    Plot relative RoostLogger activity with respect to time and date.
    """
    dates = []
    timestamps = []

    ## Read all the Anabat files beneath our starting directory
    if not os.path.isfile(os.path.join(dirname, CACHE_FILE_TIMES)):
        for subdir in os.listdir(dirname):
            dirpath = os.path.join(dirname, subdir)
            if not os.path.isdir(dirpath) or not subdir.startswith('20'):
                continue
            night = datetime.strptime(subdir, '%Y%m%d').date()
            dates.append(night)

            dircount= 0
            for filepath in glob(os.path.join(dirpath, '*.*#')):
                dircount += 1
                timestamp = anabat_date(filepath)
                timestamps.append(timestamp)
            print '%s  %4d  %s' % (subdir, dircount, '#' * int(round(dircount/100.0)))

        ## Write cache files
        with open(os.path.join(dirname, CACHE_FILE_TIMES), 'w') as cachefile:
            cachefile.writelines(timestamp.strftime('%Y-%m-%dT%H:%M:%S\n') for timestamp in timestamps)
        with open(os.path.join(dirname, CACHE_FILE_DATES), 'w') as cachefile:
            cachefile.writelines(date_.strftime('%Y-%m-%d\n') for date_ in dates)

    else:
        # Lets read from cached version rather than filesystem
        # TODO: we should only use cache file if no Anabat files have more recent modification timestamps
        with open(os.path.join(dirname, CACHE_FILE_TIMES), 'r') as cachefile:
            timestamps = [datetime.strptime(line, '%Y-%m-%dT%H:%M:%S\n') for line in cachefile]
        with open(os.path.join(dirname, CACHE_FILE_DATES), 'r') as cachefile:
            dates = [datetime.strptime(line, '%Y-%m-%d\n').date() for line in cachefile]

    ## Create a 2D time histogram
    histogram = np.zeros((24*BINS_PER_HOUR, len(dates)))
    for timestamp in timestamps:
        y = timestamp.hour * BINS_PER_HOUR + (timestamp.minute // BINSIZE_MINS)
        try:
            x = dates.index(timestamp.date())
        except ValueError as e:
            # FIXME: either build values from anabat file timestamps themselves, or hash by NIGHT (preferably do both)
            print >> sys.stderr, e
            continue
        histogram[y,x] += 1

    if logscale:
        histogram = np.log1p(histogram)

    ## Plot it
    fig, ax = plt.subplots()
    ax.imshow(histogram, cmap=plt.get_cmap(COLORMAP), interpolation='none', aspect=1.0/BINS_PER_HOUR*ASPECT_RATIO)
    ax.set_title('RoostLogger: ' + os.path.basename(os.path.normpath(dirname)).replace('_', ' '))

    ax.spines['left'].set_position(('outward', 10))
    ax.yaxis.set_minor_locator(MultipleLocator(BINS_PER_HOUR))
    ax.set_yticks([h*BINS_PER_HOUR for h in [0, 6, 12, 18, 23]])
    ax.set_yticklabels(['00:00', '06:00', '12:00', '18:00', '23:00'])
    ax.set_ylabel('Time')

    ax.spines['bottom'].set_position(('outward', 10))
    ax.set_xlim(0, len(dates)-1)
    ax.set_xticklabels([dates[int(i)] for i in ax.get_xticks().tolist() if i < len(dates)])
    ax.xaxis.set_minor_locator(MultipleLocator(1))
    fig.autofmt_xdate()
    ax.set_xlabel('Date')

    plt.show()    
        

if __name__ == '__main__':
    if os.name == 'nt' and 'PROMPT' not in os.environ:
        # Windows GUI
        from Tkinter import Tk
        from tkFileDialog import askdirectory
        Tk().withdraw()  # prevent root window from appearing
        dirname = askdirectory(title='Choose a folder full of RoostLogger nightly folders', mustexist=True, initialdir='~')
        if not dirname:
            sys.exit(2)
    else:
        # commandline
        if len(sys.argv) < 2:
            print >> sys.stderr, 'usage: %s DIR' % os.path.basename(sys.argv[0])
            sys.exit(2)
        dirname = sys.argv[1]

    main(dirname)
