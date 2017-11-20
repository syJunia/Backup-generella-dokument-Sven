# Merge new RSSI observations stats into existing logs
# 
# Author: Sangxia Huang

import pandas as pd
import configparser
import argparse
import time

parser = argparse.ArgumentParser()
parser.add_argument('new_rssi_logs', \
        nargs='+', \
        help='New observations')
parser.add_argument('--config', default='server/server.cfg')
args = parser.parse_args()

config = configparser.ConfigParser()
config.read(args.config)

with open(config['RSSI']['HistoryFilename'], 'a') as f_hist, \
        open(config['RSSI']['RecentFilename'], 'a') as f_recent:
    for fname_in in args.new_rssi_logs:
        with open(fname_in) as f_in:
            s = f_in.read()
            _ = f_hist.write(s)
            _ = f_recent.write(s)

thr = time.time() - float(config['RSSI']['RecentWindow'])*60
df = pd.read_csv(config['RSSI']['RecentFilename'], \
        header=None, names=['ts','host','tag_mac','rssi'])
df = df.loc[df['ts'] >= thr]
df.to_csv(config['RSSI']['RecentFilename'], header=False, index=False)

