#!/usr/bin/env python
# -*- coding: utf-8 -*-

# battery.py
#
# Simple example of showing battery value
#
# Author: Sangxia Huang
# Date: September 2017
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
from pigutils import s10, send_dev_command

parser = argparse.ArgumentParser(description='Accelerometer stream listener')
parser.add_argument('-b', '--device', dest='mac', required=True,
                    help='Device mac address')
args = parser.parse_args()
args.mac = normalize_mac_address(args.mac)

ctrl = pigutils.get_ctrl(args.mac)

while True:
    pigutils.connect(ctrl, delay=1)
    g = ctrl['g']
    if g is None:
        continue
    print('connected')
    pigutils.initialize(ctrl)
    pigutils.send_dev_command(ctrl, "Batt?")
    g.expect('value: ([^\r\n]+)')
    str_val = str(g.match.group(1).decode('ascii')).strip().split(' ')
    str_val = [u[1] for u in str_val]
    print(str_val)
    if len(str_val) < 8:
        str_val = ['0']*(8-len(str_val)) + str_val
    percent = int(''.join(str_val[:3]))
    mvolt = int(''.join(str_val[4:]))
    print(percent, mvolt)
    break

