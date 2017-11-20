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
import struct
from datetime import datetime
import binascii 
import argparse
import pigutils
import copy

parser = argparse.ArgumentParser(description='Accelerometer stream listener')
parser.add_argument('-b', '--device', dest='mac', required=True,
                    help='Device mac address')
parser.add_argument('-r', '--range', dest='range', default='8',
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

m_range = int(args.range)
args.mac = pigutils.normalize_mac_address(args.mac)

time_suffix = '.' + str(int(time.time()))
log = open(args.log + (time_suffix if not args.log.startswith('/dev') else ''), 'w') \
        if len(args.log) else sys.stdout
log.write("rec_time,send_cnt,x,y,z\n")
debug_fname = (args.debuglog + (time_suffix if not args.debuglog.startswith('/dev') else '')) \
        if len(args.debuglog) else ''

ctrl = pigutils.get_ctrl(args.mac, log_fname=debug_fname)
logger = ctrl['logger']

logger.debug("Started sampling of {0} at: {1}".format(args.mac, str(datetime.now())))
logger.debug("Sample rate: {0} Hz. Resolution: {1} G".format(args.rate, args.range))

pigutils.register_sigterm(args.mac)
random.seed()

terminate = False

ten_seconds = int(args.rate)*10 // 4

while True:
    if terminate:
        break
    pigutils.connect(ctrl, delay=5)
    g = ctrl['g']
    if g is None:
        continue

    time_inc = 1.0/int(args.rate)
    logger.debug("Running")

    # handle timeout and reconnect
    try:
        pigutils.initialize_stream(ctrl, args.range, args.rate)
        start_time = time.time()
        log.write("Start time {0:.3f}\n".format(start_time))

        # the first sample should have index 1
        dropped_samples = 0
        packet_data = [0, (), (), (), ()]
        packet_count = 0
        prev_packet = None
        # id of the last received sample, always matched with 2-bit indices
        last_id = 0
        while True:
            # handle keyboard interrupt and potential EOF
            try:
                g.expect('value: ([^\r\n]+)')
                str_val = str(g.match.group(1).decode('ascii')).replace(' ', '')
                if len(str_val) != 40:
                    logger.debug("Ignore packet of unusual size in {0}".format(str_val))
                    continue
                int_val = 0
                for pos in range(0, len(str_val), 8):
                    # handle potential data corruption
                    try:
                        # Unpack little endian
                        int_val = struct.unpack('<i', binascii.unhexlify(str_val[pos:pos+8]))[0]
                        if pos == 0:
                            packet_data[0] = int_val
                        else:
                            x = pigutils.s10(int_val, 0, m_range)
                            y = pigutils.s10(int_val, 10, m_range)
                            z = pigutils.s10(int_val, 20, m_range)
                            send_ind = (int_val >> 30) & 0x03
                            packet_data[pos//8] = (x,y,z,send_ind)
                    except struct.error:
                        logger.exception("Exception when unpack, current ts {0:.3f}, pos {1}, str {2}".format(time.time(), pos, str_val), exc_info=True)
                        packet_data[pos//8] = ()
                        continue
                    except (TypeError, binascii.Error):
                        logger.exception("Exception when unhexlify, current ts {0:.3f}, pos {1}, str {2}".format(time.time(), pos, str_val), exc_info=True)
                        packet_data[pos//8] = ()
                        continue

                # basic packet data verification
                if packet_data[0] & 0x03 != packet_data[1][-1]:
                    logger.debug("Incorrect sample id in {0}".format(packet_data))
                    
                if last_id > packet_data[0]:
                    logger.debug("Non-increasing sample id, last {0}, packet {1}".format(last_id, packet_data))
                    continue

                if last_id & 0x03 == packet_data[1][-1]:
                    if last_id == packet_data[0]:
                        logger.debug("Identical adjacent in {0}".format(packet_data))
                        logger.debug("and previous packet {0}".format(prev_packet))
                    else:
                        diff = packet_data[0]-last_id-1
                        dropped_samples += diff
                        if diff:
                            logger.debug("Sample drop {0} at start, {1} vs {2}".format(diff, last_id, packet_data[0]))
                        last_id = packet_data[0]
                        log.write("{0:.3f},{1},{2:.5f},{3:.5f},{4:.5f}\n".format(time.time(), last_id, \
                                packet_data[1][0], packet_data[1][1], packet_data[1][2]))
                else:
                    diff = packet_data[0]-last_id-1
                    dropped_samples += diff
                    if diff:
                        logger.debug("Sample drop {0} at start, {1} vs {2}".format(diff, last_id, packet_data[0]))
                    last_id = packet_data[0]
                    log.write("{0:.3f},{1},{2:.5f},{3:.5f},{4:.5f}\n".format(time.time(), last_id, \
                            packet_data[1][0], packet_data[1][1], packet_data[1][2]))

                for i in range(2, len(packet_data)):
                    if len(packet_data[i])==0:
                        continue
                    if last_id & 0x03 == packet_data[i][-1]:
                        logger.debug("Identical adjacent send ind in {0} pos {1}, last id {2}".format(packet_data, i, last_id))
                    else:
                        diff = ((packet_data[i][-1] - (last_id & 0x03) + 4) % 4) - 1
                        dropped_samples += diff
                        if diff:
                            logger.debug("Sample drop {0} at pos {1}, {1} vs {2}".format(diff, i, last_id, packet_data[i][-1]))
                        last_id += (packet_data[i][-1] - (last_id & 0x03) + 4) % 4
                        log.write("{0:.3f},{1},{2:.5f},{3:.5f},{4:.5f}\n".format(time.time(), last_id, \
                                packet_data[i][0], packet_data[i][1], packet_data[i][2]))

                prev_packet = copy.copy(packet_data)
                packet_count += 1
                if packet_count % ten_seconds == ten_seconds-1:
                    logger.debug("Time check {0:.3f}".format(last_id*time_inc+start_time-time.time()))
                    logger.debug("Dropped samples {0}".format(dropped_samples))
                if terminate:
                    logger.debug(packet_data)
            except (pexpect.EOF):
                if terminate:
                    print("Terminated")
                    break
                else:
                    logger.debug("EOF")
                    continue
            except KeyboardInterrupt:
                logger.debug("Terminating...")
                logger.debug("Current {0}".format(packet_data))
                terminate = True
                g.terminate()
                continue

    except (pexpect.TIMEOUT):
        logger.debug("Device timeout")
        g.terminate()
        ctrl['g'] = None
        continue

if len(args.log):
    log.close()
g.close()
logger.debug("Exit")
sys.exit(1)

