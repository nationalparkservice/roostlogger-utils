#!/usr/bin/env python2

import sys
import os, os.path
from datetime import datetime
from glob import glob
import struct
import mmap
import contextlib
from collections import defaultdict

import numpy as np

import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator


Byte = struct.Struct('< B')


def anabat_date(fname):
    """Extract timestamp as datetime from Anabat format file"""
    # See: http://users.lmi.net/corben/fileform.htm#ANABAT_SEQUENCE_FILE_TYPE_132
    with open(fname, 'rb') as f:
        with contextlib.closing(mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)) as bytes:
            vals = struct.unpack_from('HBBBBB', bytes, 0x120)
            return datetime(*vals)


def anabat_duration(fname):
    """Extract the duration in seconds from an Anabat file"""
    with open(fname, 'rb') as f, contextlib.closing(mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)) as m:
        size = len(m)

        # parse header
        data_info_pointer, file_type = struct.unpack_from('< H x B', m)
        data_pointer, res1, divratio, vres = struct.unpack_from('< H H B B', m, data_info_pointer)
        #print 'file_type: %d\tdata_info_pointer: 0x%3x\tdata_pointer: 0x%3x' % (file_type, data_info_pointer, data_pointer)

        # parse actual sequence data
        i = data_pointer   # byte index as we scan through the file (data starts at 0x150 for v132, 0x120 for older files)
        intervals_us = np.empty(2**14, np.dtype('u4'))
        int_i = 0

        while i < size:
            byte = Byte.unpack_from(m, i)[0]

            if byte <= 0x7F:
                # Single byte is a 7-bit signed two's complement offset from previous interval
                offset = byte if byte < 2**6 else byte - 2**7  # clever two's complement unroll
                if int_i > 0:
                    intervals_us[int_i] = intervals_us[int_i-1] + offset
                    int_i += 1
                else:
                    print >> sys.stderr, 'Sequence file starts with a one-byte interval diff! Skipping byte %x' % byte
                    #intervals.append(offset)  # ?!

            elif 0x80 <= byte <= 0x9F:
                # time interval is contained in 13 bits, upper 5 from the remainder of this byte, lower 8 bits from the next byte
                accumulator = (byte & 0b00011111) << 8
                i += 1
                accumulator |= Byte.unpack_from(m, i)[0]
                intervals_us[int_i] = accumulator
                int_i += 1

            elif 0xA0 <= byte <= 0xBF:
                # interval is contained in 21 bits, upper 5 from the remainder of this byte, next 8 from the next byte and the lower 8 from the byte after that
                accumulator = (byte & 0b00011111) << 16
                i += 1
                accumulator |= Byte.unpack_from(m, i)[0] << 8
                i += 1
                accumulator |= Byte.unpack_from(m, i)[0]
                intervals_us[int_i] = accumulator
                int_i += 1

            elif 0xC0 <= byte <= 0xDF:
                # interval is contained in 29 bits, the upper 5 from the remainder of this byte, the next 8 from the following byte etc.
                accumulator = (byte & 0b00011111) << 24
                i += 1
                accumulator |= Byte.unpack_from(m, i)[0] << 16
                i += 1
                accumulator |= Byte.unpack_from(m, i)[0] << 8
                i += 1
                accumulator |= Byte.unpack_from(m, i)[0]
                intervals_us[int_i] = accumulator
                int_i += 1

            elif 0xE0 <= byte <= 0xFF:
                # status byte which applies to the next n dots
                status = byte & 0b00011111
                i += 1
                dotcount = Byte.unpack_from(m, i)[0]
                print >> sys.stderr, 'UNSUPPORTED: Status %X for %d dots' % (status, dotcount)
                # TODO: not yet supported

            else:
                raise Exception('Unknown byte %X at offset 0x%X' % (byte, i))

            i += 1

    intervals_us = intervals_us[:int_i]
    duration_s = np.sum(intervals_us) * 1e-6
    print >> sys.stderr, '%s (%.1f sec)' % (fname, duration_s)
    return duration_s


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


def cache_exists():
    return os.path.exists(os.path.join(dirname, '.activity_temp_report.dates.txt'))

def write_cache(dates, timestamps, counts, durations):
    with open(os.path.join(dirname, '.activity_temp_report.dates.txt'), 'w') as cachefile:
        cachefile.writelines(date_.strftime('%Y-%m-%d\n') for date_ in dates)
    with open(os.path.join(dirname, '.activity_temp_report.timestamps.txt'), 'w') as cachefile:
        cachefile.writelines(timestamp.strftime('%Y-%m-%dT%H:%M:%S\n') for timestamp in timestamps)
    with open(os.path.join(dirname, '.activity_temp_report.counts'), 'w') as cachefile:
        cachefile.writelines(('%d\n' % count) for count in counts)
    with open(os.path.join(dirname, '.activity_temp_report.durations'), 'w') as cachefile:
        cachefile.writelines(('%f\n' % dur) for dur in durations)

def read_cache():
    dates, timestamps, counts, durations = None, None, None, None
    with open(os.path.join(dirname, '.activity_temp_report.dates.txt'), 'r') as cachefile:
        dates = [datetime.strptime(date_, '%Y-%m-%d\n').date() for date_ in cachefile]
    with open(os.path.join(dirname, '.activity_temp_report.timestamps.txt'), 'r') as cachefile:
        timestamps = [datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S\n') for timestamp in cachefile]
    with open(os.path.join(dirname, '.activity_temp_report.counts'), 'r') as cachefile:
        counts = [int(count) for count in cachefile]
    with open(os.path.join(dirname, '.activity_temp_report.durations'), 'r') as cachefile:
        durations = [float(dur) for dur in cachefile]
    return dates, timestamps, counts, durations


def main(dirname, logscale=False):
    dates = []
    timestamps = []
    counts = []
    durations = []

    if not cache_exists():
        ## Read all the Anabat files beneath our starting directory
        for subdir in os.listdir(dirname):
            dirpath = os.path.join(dirname, subdir)
            if not os.path.isdir(dirpath) or not subdir.startswith('20'):
                continue
            night = datetime.strptime(subdir, '%Y%m%d').date()
            dates.append(night)

            dircount = 0
            total_duration = 0.0
            for filepath in glob(os.path.join(dirpath, '*.*#')):
                dircount += 1
                timestamp = anabat_date(filepath)
                timestamps.append(timestamp)
                total_duration += anabat_duration(filepath)
            counts.append(dircount)
            durations.append(total_duration)
            print '%s  %4d  %4.1fs  %s' % (subdir, dircount, total_duration, '#' * int(round(dircount/100.0)))

        write_cache(dates, timestamps, counts, durations)
    else:
        dates, timestamps, counts, durations = read_cache()

    durations = [dur/60.0 for dur in durations]  # convert to minutes

    ## Read the HumiTemp.txt file
    fname = os.path.join(dirname, 'HumiTemp.txt')
    dates2, temps_min, temps_max, temps_avg = zip(*read_humitemp_summary(fname))

    ## Plot
    #fig, (ax1, ax2) = plt.subplots(nrows=2, ncols=1, sharex=True, gridspec_kw={'height_ratios': [3,1]})
    fig = plt.figure()
    fig.autofmt_xdate()
    ax1 = plt.subplot2grid((3,1), (0,0), rowspan=2)
    ax2 = plt.subplot2grid((3,1), (2,0), rowspan=1, sharex=ax1)

    # Activity bar plot
    ax1.bar(dates, durations, 0.85, log=logscale)
    ax1.spines['bottom'].set_position(('outward', 10))
    ax1.set_xlim(dates[0], dates[-1])
    ax1.xaxis.set_minor_locator(MultipleLocator(1))
    ax1.tick_params(labelright=True)
    ax1.yaxis.grid(True)
    ax1.set_ylabel('Activity Duration (minutes)')
    ax1.set_xlabel('Date')

    # Temperature line plot
    ax3 = ax2.twinx()  # Fahrenheit scale

    def update_ax3(ax2):
        y1, y2 = ax2.get_ylim()
        ax3.set_ylim(c2f(y1), c2f(y2))
        ax3.figure.canvas.draw()

    ax2.callbacks.connect('ylim_changed', update_ax3)

    ax2.yaxis.grid(True)

    ax2.fill_between(dates2, temps_min, temps_max, facecolor='#D0D0D0')
    ax2.plot(dates2, temps_avg, color='green')
    ax2.plot(dates2, temps_min, color='blue', lw=1.5)
    ax2.plot(dates2, temps_max, color='red', lw=1.5)
    ax2.set_ylabel('Temp ($^\circ$C)')
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
