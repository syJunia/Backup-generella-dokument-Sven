#!/usr/bin/env python
# -*- coding: utf-8 -*-

# acc_stream.py
#
# Simple example of showing streamed accelerometer values
#
# Author: Peter Lerup
# Date: January 2017
#

import os
import sys
import signal
import pexpect
import time
from struct import unpack
from datetime import datetime
from binascii import hexlify, unhexlify, a2b_qp
import argparse
import numpy as np
import pigutils
from pigutils import normalize_mac_address, lower_mac_address
from pigutils import s10, console_mess, send_dev_command
from pigutils import register_sigterm

parser = argparse.ArgumentParser(description='Accelerometer stream listener')
parser.add_argument('-b', '--device', dest='mac', required=True,
                    help='Device mac address')
parser.add_argument('-r', '--range', dest='range', default='8',
                    help='Resoultion range in G (2-16)')
parser.add_argument('-s', '--rate', dest='rate', default='10',
                    help='Sample rate in Hz (10-100)')
parser.add_argument('-w', '--window', dest='window', default='100',
                    help='Write data to this file')
parser.add_argument('-l', '--log', dest='log', default='',
                    help='Write data to this file')
args = parser.parse_args()
if int(args.range) < 2 or int(args.range) > 16:
    sys.exit("Invalid range: " + args.range)
if int(args.rate) < 10 or int(args.rate) > 100:
    sys.exit("Invalid rate: " + args.rate)

args.mac = normalize_mac_address(args.mac)
lower_mac = lower_mac_address(args.mac)

console_mess(args.mac, "Started sampling of %s at: %s" % (args.mac, str(datetime.now())))
console_mess(args.mac, "Sample rate: %s Hz. Resolution: %s G" % (args.rate, args.range))
log = open(args.log, "w") if len(args.log) else sys.stdout

register_sigterm(args.mac)

calib_file = 'calib_{0}_result.txt'.format(lower_mac)
if os.path.isfile(calib_file):
    with open(calib_file) as f:
        data = [[float(x) for x in r.strip().split()] for r in f]
        num_rounds = len(data)
        calib = [np.mean([data[i][j] for i in range(num_rounds)]) \
                for j in range(6)]
else:
    calib = [1., 0., 1., 0., 1., 0.]
print(calib)

try:
    past_g = np.array([0.]*int(args.window))
    past_g_calib = np.array([0.]*int(args.window))
    g_count = 0.
    g_sum = 0.
    g_calib_sum = 0.
    g_pointer = 0

    while True:
        g = pigutils.connect(args.mac, delay=2)
        if g is None:
            continue

        time_inc = 1.0/int(args.rate)
        console_mess(args.mac, "Running")

        try:
            pigutils.initialize_stream(g, args.range, args.rate)
            m_range = int(args.range)

            # Catch and decode the streaming values
            rec_ind = 0
            t = 0
            while True:
                g.expect('value: ([^\r\n]+)')
                str_val = str(g.match.group(1).decode('ascii')).replace(' ', '')
                start = time.time() - time_inc*len(str_val)/8.0
                if t < start:
                    t = start
                for pos in range(0, len(str_val), 8):
                    # Unpack little endian
                    int_val = unpack('<i', unhexlify(str_val[pos:pos+8]))[0]
                    x = s10(int_val, 0, m_range)
                    y = s10(int_val, 10, m_range)
                    z = s10(int_val, 20, m_range)
                    send_ind = (int_val >> 30) & 0x03
                    while send_ind != rec_ind:
                        # Missing value(s)
                        rec_ind = (rec_ind+1) % 4
                        t += time_inc
                    rec_ind = (send_ind+1) % 4
                    # Show time and accelerometer values in CSV
                    log.write("%.3f,%.3f,%.3f,%.3f\n" % (t, x, y, z))
                    current_g = np.sqrt(x**2 + y**2 + z**2)
                    g_sum += (current_g - past_g[g_pointer])
                    past_g[g_pointer] = current_g

                    x = x*calib[0] + calib[1]
                    y = y*calib[2] + calib[3]
                    z = z*calib[4] + calib[5]
                    current_g_calib = np.sqrt(x**2 + y**2 + z**2)
                    g_calib_sum += (current_g_calib - past_g_calib[g_pointer])
                    past_g_calib[g_pointer] = current_g_calib

                    g_count = min(g_count + 1, int(args.window))
                    g_pointer = (g_pointer + 1) % int(args.window)
                    if (g_count == int(args.window)) and (np.std(past_g) < 0.01):
                        print('g {0:.3f} g_calib {1:.3f}, err g {2:.3f} g_calib {3:.3f}'.format(\
                                g_sum / g_count, g_calib_sum / g_count, \
                                np.abs(1-g_sum/g_count), np.abs(1-g_calib_sum/g_count)))

                    t += time_inc

        except (pexpect.TIMEOUT):
            console_mess(args.mac, "Device timeout")
            continue

except KeyboardInterrupt:
    if len(args.log):
        log.close()
    g.close()
    console_mess(args.mac, "\nExit")
    sys.exit(1)
