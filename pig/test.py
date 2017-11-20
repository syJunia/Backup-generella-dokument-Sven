#!/usr/bin/env python
# -*- coding: utf-8 -*-

# test.py
#
# Test example showing how to do periodic poll of a Pigplus tag
#
# Author: Peter Lerup
# Date: October 2017
#

import sys
import pexpect
import time
from struct import unpack
from datetime import datetime
from binascii import unhexlify
from binascii import hexlify, a2b_qp
import argparse

# Encode 10 bit signed value at the given position and scale according to range
def s10(value, pos, m_range):
    value = (value & (0x3FF << pos)) >> pos
    if value & 0x200:
        value -= 0x400
    return value/float(0x200)*m_range

#--------------------------------------------------------------------

# Send uart service command to the device
def send_dev_command(g, command):
    try:
        _ = eval("1 if True else 2")
        print(command)
        msg = hexlify(bytes(command, 'ascii'))
        g.sendline('char-write-req 0x000e ' + msg.decode('ascii'))
    except SyntaxError:
        g.sendline('char-write-req 0x000e ' + command.encode('hex'))
    g.expect('written successfully')
    g.expect('value: ([^\r\n]+)')
    resp = str(g.match.group(1).decode('ascii')).strip().split(' ')
    if "ERR:" in resp:
        console_mess(resp)

#--------------------------------------------------------------------

def console_mess(mess):
    sys.stderr.write("* " + mess + "\n")

#--------------------------------------------------------------------

def connect(g):
    g.timeout = 15
    while True:
        g.sendline('connect')
        try:
            g.expect(['\[CON\].*>', 'Connection successful'])
            g.timeout = 5
            # Enable notifications from the uart service
            g.sendline('char-write-req 0x000C 0100')
            g.expect('written successfully')
            return
        except (pexpect.TIMEOUT):
            console_mess('Failed to connect to the device');
            print(g.before)
            time.sleep(5)


#--------------------------------------------------------------------

parser = argparse.ArgumentParser(description='Accelerometer stream listener')
parser.add_argument('-b', '--device', dest='mac', required=True,
                    help='Device mac address')
parser.add_argument('-r', '--range', dest='range', default='8',
                    help='Resoultion range in G (2-16)')
parser.add_argument('-s', '--rate', dest='rate', default='10',
                    help='Accelerometer sample rate in Hz (10-100)')
parser.add_argument('-p', '--poll', dest='poll', default='60',
                    help='Poll rate i seconds')
parser.add_argument('-l', '--log', dest='log', default='',
                    help='Write data to this file')
args = parser.parse_args()
if int(args.range) < 2 or int(args.range) > 16:
    sys.exit("Invalid range: " + args.range)
if int(args.rate) < 10 or int(args.rate) > 100:
    sys.exit("Invalid sample rate: " + args.rate)
if int(args.poll) < 10 or int(args.poll) > 1000:
    sys.exit("Invalid poll rate: " + args.poll)

console_mess("Started sampling of %s at: %s" % (args.mac, str(datetime.now())))
console_mess("Sample rate: %s Hz. Resolution: %s G" % (args.rate, args.range))
console_mess("Poll rate: %s s" % (args.poll))
log = open(args.log, "w") if len(args.log) else sys.stdout

args.rate = int(args.rate)
args.poll = int(args.poll)
time_inc = 1.0/args.rate
m_range = int(args.range)

g = pexpect.spawn('gatttool -b ' + args.mac + ' -t random -I')
g.expect('\[LE\]>')

console_mess('Setting up the device...')
connect(g)
# Stop possible ongoing recordings
send_dev_command(g, "Stop")
send_dev_command(g, "Range=%s" % args.range)
send_dev_command(g, "Rate=%d" % args.rate)
console_mess("Start recording")
send_dev_command(g, "Record")
t = time.time()
g.sendline("disconnect")

first = True
sample_pos = 0;
try:
    while True:
        console_mess('Waiting...');
        time.sleep(float(args.poll))
        try:
            console_mess('Polling')
            connect(g);
            # Sample the accumulated values
            sample_cnt = int((time.time() - t)*args.rate)
            cmd_str = ("Play=%d,%d" % (sample_pos, sample_cnt))
            print(cmd_str)
            send_dev_command(g, cmd_str)
            # Max 20 bytes e.g. 5 samples per line of a response
            loop_range = int((sample_cnt+4)/5)
            for i in range(0, loop_range):
                g.expect('value: ([^\r\n]+)')
                #str_val = g.match.group(1).replace(' ', '')
                str_val = str(g.match.group(1).decode('ascii')).strip().split(' ')
                for pos in range(0, len(str_val), 8):
                    # Unpack little endian
                    b_arr = bytearray.fromhex(''.join((str_val[pos:pos+8])))
                    int_val = int.from_bytes(b_arr, byteorder='little')
                    x = s10(int_val, 0, m_range)
                    y = s10(int_val, 10, m_range)
                    z = s10(int_val, 20, m_range)
                    # Show time and accelerometer values in CSV
                    log.write("%.2f,%.2f,%.2f,%.2f\n" % (t, x, y, z))
                    t += time_inc
            g.sendline("disconnect")
            sample_pos += sample_cnt

        except (pexpect.TIMEOUT):
            console_mess("Device timeout")
            continue

except KeyboardInterrupt:
    if len(args.log):
        log.close()
    g.close()
    console_mess("\nExit")
    sys.exit(1)
