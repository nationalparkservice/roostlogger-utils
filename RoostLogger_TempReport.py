#!/usr/bin/env python2
"""
RoostLogger_TempReport.py - Plot roost temperature with respect to
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
from collections import defaultdict

import numpy as np

import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator


# Display colormap, see:  http://matplotlib.org/examples/color/colormaps_reference.html
COLORMAP = 'afmhot'  # afmhot, gist_heat, hot, copper, cool, bone, gray

# Tweak this value higher for longer (timewise) deployments
ASPECT_RATIO = 2.5


def anabat_date(fname):
    """Extract timestamp as datetime from Anabat format file"""
    # See: http://users.lmi.net/corben/fileform.htm#ANABAT_SEQUENCE_FILE_TYPE_132
    with open(fname, 'rb') as f:
        bytes = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        vals = struct.unpack_from('HBBBBB', bytes, 0x120)
        return datetime(*vals)
    

def read_humitemp(fname):
    """Produce sequence of (timestamp, temperature) from `HumiTemp.txt` file"""
    with open(fname, 'r') as f:
        headers = f.readline().split('\t')
        for line in f:
            timestamp, temp, humidity = line.split('\t')
            timestamp = datetime.strptime(timestamp, '%Y/%m/%d %H:%M:%S')
            temp = float(temp)
            yield timestamp, temp


def mean(values):
    """Calculate the mean (average) value of a list"""
    if not values:
        return None
    return sum(values) / float(len(values))


def c2f(temp_c):
    """Convert temperature in Degrees Celsius to Degrees Fahrenheit"""
    return temp_c * 1.8 + 32

def read_humitemp_summary(fname):
    """Produce sequence of (date, min, max, avg) from `HumiTemp.txt` file"""
    # TODO: should these cover a "night" instead?
    dates = defaultdict(list)  # date -> [float]
    for timestamp, temp in read_humitemp(fname):
        dates[timestamp.date()].append(temp)
    summary = {}
    for date, values in dates.items():
        summary[date] = min(values), max(values), mean(values)
    for date in sorted(summary.keys()):
        min_, max_, avg = summary[date]
        yield date, min_, max_, avg

def main(fname):
    """
    Plot temperature from a RoostLogger with respect to time and date.
    """
    dates, timestamps, temps = [], [], []

    ## Read in all the Temperature data at once
    data = [row for row in read_humitemp(fname)]
    timestamps, temps = zip(*data)
    dates = sorted(set([timestamp.date() for timestamp in timestamps]))

    ## Create a 2D time histogram
    histogram = np.zeros((24*12, len(dates)))
    for timestamp, temp in data:
        y = timestamp.hour * 12 + (timestamp.minute // 5)  # nearest 5-minute bin
        try:
            x = dates.index(timestamp.date())
        except ValueError, e:
            # TODO: this should be indexed by NIGHT not by date
            print >> sys.stderr, e
            continue
        histogram[y,x] = temp

    ## Plot the histogram
    fig, (ax1, ax2) = plt.subplots(nrows=2, sharex=True)
    ax1.imshow(histogram, cmap=plt.get_cmap(COLORMAP), interpolation='none', aspect=1.0/12*ASPECT_RATIO)
    ax1.set_title('RoostLogger: ' + os.path.basename(os.path.dirname(os.path.abspath(fname))).replace('_', ' '))

    ax1.spines['left'].set_position(('outward', 10))
    ax1.yaxis.set_minor_locator(MultipleLocator(1*12))
    ax1.set_yticks([h*12 for h in [0, 6, 12, 18, 23]])
    ax1.set_yticklabels(['00:00', '06:00', '12:00', '18:00', '23:00'])
    ax1.set_ylabel('Time')

    ax1.spines['bottom'].set_position(('outward', 10))
    ax1.set_xlim(0, len(dates)-1)
    ax1.set_xticklabels([dates[int(i)] for i in ax1.get_xticks().tolist() if i < len(dates)])
    ax1.xaxis.set_minor_locator(MultipleLocator(1))
    ax1.tick_params(labelright=True)
    fig.autofmt_xdate()
    #ax1.set_xlabel('Date')

    ## Plot the daily summary
    ax3 = ax2.twinx()  # Fahrenheit scale

    def update_ax3(ax2):
        y1, y2 = ax2.get_ylim()
        ax3.set_ylim(c2f(y1), c2f(y2))
        ax3.figure.canvas.draw()

    ax2.callbacks.connect('ylim_changed', update_ax3)

    ax2.yaxis.grid(True)

    dates, mins, maxs, avgs = zip(*read_humitemp_summary(fname))
    ax2.fill_between(range(len(dates)), mins, maxs, facecolor='#D0D0D0')
    ax2.plot(avgs, color='green')
    ax2.plot(mins, color='blue', lw=1.5)
    ax2.plot(maxs, color='red', lw=1.5)
    ax2.set_ylabel('Temp $^\circ$C')
    ax2.set_xlabel('Date')
    ax3.set_ylabel('Temp $^\circ$F')

    plt.show()
    

if __name__ == '__main__':
    if os.name == 'nt' and 'PROMPT' not in os.environ:
        # Windows GUI
        from Tkinter import Tk
        from tkFileDialog import askopenfilename
        Tk().withdraw()  # prevent root window from appearing
        fname = askopenfilename(title='Choose a `HumiTemp.txt` file', defaultextension='.txt', filetypes=[('RoostLogger HumiTemp.txt', '.txt')])
        if not fname:
            sys.exit(2)
    else:
        # commandline
        if len(sys.argv) < 2:
            print >> sys.stderr, 'usage: %s HumiTemp.txt' % os.path.basename(sys.argv[0])
            sys.exit(2)
        fname = sys.argv[1]

    main(fname)
