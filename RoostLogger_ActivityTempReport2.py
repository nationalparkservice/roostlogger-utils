#!/usr/bin/env python2

import sys, os, os.path
from datetime import datetime, date
from glob import glob
import struct
import mmap
import contextlib
from collections import defaultdict

import numpy as np

import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator


def anabat_date(fname):
    """Extract timestamp as datetime from Anabat format file"""
    # See: http://users.lmi.net/corben/fileform.htm#ANABAT_SEQUENCE_FILE_TYPE_132
    with open(fname, 'rb') as f:
        with contextlib.closing(mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)) as bytes:
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
    if not values:
        return None
    return sum(values) / float(len(values))


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


def main(dirname):
    dates = []
    timestamps = []
    counts = []
    
    ## Read all the Anabat files beneath our starting directory
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
        counts.append(dircount)
        print '%s  %4d  %s' % (subdir, dircount, '#' * int(round(dircount/100.0)))

    ## Read the HumiTemp.txt file
    fname = os.path.join(dirname, 'HumiTemp.txt')
    dates2, temps_min, temps_max, temps_avg = zip(*read_humitemp_summary(fname))
    print len(dates), dates
    print len(dates2), dates2

    ## Plot   
    fig, (ax1, ax2) = plt.subplots(nrows=2, ncols=1, sharex=True)
    fig.autofmt_xdate()

    # Activity bar plot
    ax1.bar(dates, counts, 0.85, log=False)
    ax1.spines['bottom'].set_position(('outward', 10))
    ax1.set_xlim(dates[0], dates[-1])
    ax1.xaxis.set_minor_locator(MultipleLocator(1))
    ax1.set_xlabel('Date')

    # Temperature line plot
    ax2.fill_between(dates2, temps_min, temps_max, facecolor='#D0D0D0')
    ax2.plot(dates2, temps_avg, color='green')
    ax2.plot(dates2, temps_min, color='blue', lw=1.5)
    ax2.plot(dates2, temps_max, color='red', lw=1.5)
    ax2.set_ylabel('Temp $^\circ$C')
    ax2.xaxis.set_minor_locator(MultipleLocator(1))
    ax2.set_xlabel('Date')
    
    plt.tight_layout()
    plt.show()

    

if __name__ == '__main__':
    if os.name == 'nt' and 'PROMPT' not in os.environ and len(sys.argv) < 2:
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
