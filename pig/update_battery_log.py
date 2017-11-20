# Merge and update battery status
# 
# Author: Sangxia Huang

# TODO test this

import pandas as pd
import configparser
import argparse
import time

parser = argparse.ArgumentParser()
parser.add_argument('tag_address', help='MAC address of the tag')
parser.add_argument('observer', \
        help='Observer from which the information is received')
parser.add_argument('level', type=int, help='Battery level')
parser.add_argument('mv', type=int, help='Battery voltage')
parser.add_argument('--config', default='server/server.cfg')
args = parser.parse_args()

config = configparser.ConfigParser()
config.read(args.config)

with open(config['Battery']['HistoryFilename'], 'a') as f:
    _ = f.write('{0:.5f},{1},{2},{3},{4}\n'.format(\
            time.time(), args.tag_address, args.observer, \
            args.level,args.mv))

battery_dict = {}
with open(config['Battery']['LatestFilename']) as f:
    for r in f:
        s = r.strip().split(',')
        battery_dict[s[1]] = (float(s[0]), int(s[2]))
battery_dict[args.tag_address] = args.level
with open(config['Battery']['LatestFilename'], 'w') as f:
    for k,v in battery_dict.items():
        _ = f.write('{0:.5f},{1},{2}\n'.format(v[0],k,v[1]))

