# -*- coding: utf-8 -*-

# acc_stream.py
#
# Simple example of showing streamed accelerometer values
#
# Author: Peter Lerup
# Date: January 2017
#

import random
import time
import sys
import pexpect
import time
from struct import unpack
from datetime import datetime
from binascii import hexlify, unhexlify, a2b_qp
import argparse
import pigutils
from pigutils import normalize_mac_address
from pigutils import s10
from pigutils import register_sigterm

parser = argparse.ArgumentParser(description='Accelerometer stream listener')
parser.add_argument('-b', '--device', dest='mac', required=True,
                    help='Device mac address')
parser.add_argument('-r', '--range', dest='range', default='16',
                    help='Resoultion range in G (2-16)')
parser.add_argument('-s', '--rate', dest='rate', default='50',
                    help='Sample rate in Hz (10-100)')
parser.add_argument('-l', '--log', dest='log', default='',
                    help='Write data to this file')
parser.add_argument('-dl', '--debuglog', dest='debuglog', default='',
                    help='Write debug information to this file')
args = parser.parse_args()
if int(args.range) < 2 or int(args.range) > 16:
    sys.exit("Invalid range: " + args.range)
if int(args.rate) < 10 or int(args.rate) > 100:
    sys.exit("Invalid rate: " + args.rate)

args.mac = normalize_mac_address(args.mac)

time_suffix = '.' + str(int(time.time()))
log = open(args.log + (time_suffix if not args.log.startswith('/dev') else ''), 'w') \
        if len(args.log) else sys.stdout
debug_fname = (args.debuglog + (time_suffix if not args.debuglog.startswith('/dev') else '')) \
        if len(args.debuglog) else ''

ctrl = pigutils.get_ctrl(args.mac, log_fname=debug_fname)
logger = ctrl['logger']

logger.debug("Started sampling of {0} at: {1}".format(args.mac, str(datetime.now())))
logger.debug("Sample rate: {0} Hz. Resolution: {1} G".format(args.rate, args.range))

register_sigterm(args.mac)
random.seed()

prev_process_time = 0.

err_buffer_size = 200
err_buffer = [0.]*err_buffer_size
err_buffer_ptr = 0
err_buffer_count = 0
err_buffer_sum = 0.

try:
    while True:
        pigutils.connect(ctrl, delay=5)
        g = ctrl['g']
        if g is None:
            continue

        time_inc = 1.0/int(args.rate)
        logger.debug("Running")

        try:
            pigutils.initialize_stream(ctrl, args.range, args.rate)
            m_range = int(args.range)

            # Catch and decode the streaming values
            rec_ind = 0
            t = 0
            packet_count = 0
            while True:
                g.expect('value: ([^\r\n]+)')
                str_val = str(g.match.group(1).decode('ascii')).replace(' ', '')
                start = time.time() - time_inc*len(str_val)/8.0
                #print(len(str_val))
                if t < start-2.:
                    logger.debug("Set timestamp from {0:.3f} to {1:.3f}, packet # {2}, prev proc time {3:.3f}".format(t, start, packet_count, prev_process_time))
                    t = start
                curr_time = time.time()
                #if t > curr_time+.5:
                #    logger.debug(\
                #            "Time from the future {0:.3f} vs. {1:.3f}, diff {2:.3f}, packet # {3}".format(\
                #            t, curr_time, t-curr_time, packet_count))
                prev_process_time = curr_time
                skipped = False
                for pos in range(0, len(str_val), 8):
                    try:
                        # Unpack little endian
                        int_val = unpack('<i', unhexlify(str_val[pos:pos+8]))[0]
                        x = s10(int_val, 0, m_range)
                        y = s10(int_val, 10, m_range)
                        z = s10(int_val, 20, m_range)
                        send_ind = (int_val >> 30) & 0x03
                        while send_ind != rec_ind:
                            # Missing value(s)
                            logger.debug("Missing, receiving ts {0:.3f}, current ts {1:.3f}, send_ind {2} rec_ind {3}, packet # so far {4}".format(\
                                    t, time.time(), send_ind, rec_ind, packet_count))
                            rec_ind = (rec_ind+1) % 4
                            t += time_inc
                            skipped = True
                        rec_ind = (send_ind+1) % 4
                        # Show time and accelerometer values in CSV
                        if pos+8 == len(str_val):
                            log.write("%.3f,%.5f,%.5f,%.5f,1\n" % (t, x, y, z))
                        else:
                            log.write("%.3f,%.5f,%.5f,%.5f,0\n" % (t, x, y, z))
                        t += time_inc
                    except struct.error:
                        logger.exception("Exception when unpack, current ts {0:.3f}, pos {1}, str {2}".format(time.time(), pos, str_val), exc_info=True)
                        continue
                    except TypeError:
                        logger.exception("Exception when unhexlify, current ts {0:.3f}, pos {1}, str {2}".format(time.time(), pos, str_val), exc_info=True)
                        continue
                packet_count += 1
                err_buffer_sum += (t-curr_time) - err_buffer[err_buffer_ptr]
                err_buffer[err_buffer_ptr] = t-curr_time
                err_buffer_ptr = (err_buffer_ptr+1) % err_buffer_size
                if err_buffer_count < err_buffer_size:
                    err_buffer_count += 1
                if packet_count % 100 == 99:
                    logger.debug("Time error {0:.3f}".format(err_buffer_sum/err_buffer_count))
                #if skipped:
                #    console_mess(args.mac, "")

        except (pexpect.TIMEOUT):
            logger.debug("Device timeout")
            g.terminate()
            ctrl['g'] = None
            continue

except KeyboardInterrupt:
    if len(args.log):
        log.close()
    g.close()
    logger.debug("Exit")
    sys.exit(1)
