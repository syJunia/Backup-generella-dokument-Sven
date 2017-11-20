#!/usr/bin/env python
# -*- coding: utf-8 -*-
# rssiutils.py
#
# Python software that will update rssi records on the server 
# it will ask the observers to report rssi levels for all availible tags
#
# Author: Sven Tryding
# Date: October 2017
#
# Server based scripts
#


"""

available_observers.cfg
    IP,Host

config['RSSI']['RecentFilename']
config['RSSI']['HistoryFilename']
    ts,host,tag,status,battery,rssi

server/rssi_ts_file.csv
    Host,Next_ts
"""

import settings
import equiputils as eu
import datetime
import glob
import os
import shutil
import time
from os import path
import pandas as pd
import numpy as np
import requests
import random
import logging


DTYPE_RSSI_RECENT = {\
        'status': np.int, \
        'battery': np.int, \
        'rssi': np.int, \
        }


def initialize_logfiles(clean=False):
    if (not path.isfile(settings.config['RSSI']['HistoryFilename'])) or (clean):
        with open(settings.config['RSSI']['HistoryFilename'], 'w') as f:
            _ = f.write('ts,host,tag,status,battery,rssi\n')
    if (not path.isfile(settings.config['RSSI']['RecentFilename'])) or (clean):
        with open(settings.config['RSSI']['RecentFilename'], 'w') as f:
            _ = f.write('ts,host,tag,status,battery,rssi\n')
    if (not path.isfile(settings.config['RSSI']['NextTSFilename'])) or (clean):
        with open(settings.config['RSSI']['NextTSFilename'], 'w') as f:
            _ = f.write('Host,Next_ts\n')


def get_logger(level=logging.INFO, log_fname='logs/serverdebug_tagstate.log'):
    logger = logging.getLogger('PigPlus_server_tagstatus')
    if not logger.handlers:
        logger.setLevel(level)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(message)s')
        fh = logging.handlers.RotatingFileHandler(log_fname, 'a', 300000000, 1000)
        fh.setLevel(level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    return logger


def get_next_ts_all():
    df = pd.read_csv(settings.config['RSSI']['NextTSFilename'])
    return df.set_index('Host').to_dict()['Next_ts']


def update_next_rssi(obsname, new_ts):
    df = pd.read_csv(settings.config['RSSI']['NextTSFilename'])
    if obsname in set(df['Host']):
        df.loc[df['Host']==obsname, 'Next_ts'] = new_ts
    else:
        df.loc[df.shape[0]] = [obsname, new_ts]
    df.to_csv(settings.config['RSSI']['NextTSFilename'], index=False)


def read_tag_state(tag):
    df = pd.read_csv(settings.config['RSSI']['RecentFilename'], dtype=DTYPE_RSSI_RECENT)
    if tag not in set(df['tag']):
        return {'SUCCESS': False}
    df = df.loc[df['tag'] == tag]
    batt = df['battery'].mean()
    rssi = df['rssi'].mean()
    status = df.iloc[-1]['status']
    return {'SUCCESS': True, 'battery': batt, 'rssi': rssi, 'status': status}


def read_rssi(from_time, observer_addr):
    """
    Read rssi logs from observers and extract them
    """
    import io
    import zipfile
    from contextlib import closing

    r_str = observer_addr + "/ReadRssiLog/" + from_time
    try:
        r = requests.get(r_str, timeout=120)
        closing(r)
        # Test that we got a valid response
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            z.extractall('server/')
        return True
    except requests.exceptions.RequestException:
        get_logger().exception('Exception in reading from server')
        return False
    except:
        get_logger().exception('Unknown exception')
        return False


def merge_received_log_for_routing(hostname):
    """
    Merge the logs received from read_rssi()
    """
    outfilename = 'server/' + hostname + '.rssi'
    received_logfilename = 'server/' + hostname + '.log.*'
    with open(outfilename, 'wb') as outfile:
        received_files = glob.glob(received_logfilename)
        for filename in received_files:
            with open(filename, 'rb') as readfile:
                shutil.copyfileobj(readfile, outfile)
        # Now we can remove the log files, they are merged 
        for f in glob.glob(received_logfilename):
            os.remove(f)
    get_logger().info('Outfile is ' +  outfilename)
    return outfilename


def update_all_observers_rssi_observations():
    # pool = Pool(processes=4)
    recent_window = int(settings.config['RSSI']['RecentWindow'])
    # Read back next_ts_to_use
    observer_set = eu.get_available_observer_names()
    next_ts_to_use_rssi = get_next_ts_all()

    # Loop through available observers

    for obsname in observer_set:
        obsip = eu.get_observer_ip(obsname)
        next_ts = next_ts_to_use_rssi[obsname] \
                if obsname in next_ts_to_use_rssi \
                else int(time.time())-180*recent_window

        next_ts_str = str(next_ts)
        get_logger().info('poll observer {0} for rssi with ts {1}, curr time {2:.3f}'.format(obsname, next_ts_str, time.time()))

        if not read_rssi(next_ts_str, obsip):
            get_logger().info('tag state collection from observer {0} failed'.format(obsname))
            continue

        fname_in = merge_received_log_for_routing(obsname)
        with open('server/meta') as f:
            last_line = f.readlines()[-1]
        get_logger().info('last ts from rssi = ' + last_line)

        update_next_rssi(obsname, int(last_line.strip()))
        next_ts_to_use_rssi[obsname] = int(last_line.strip())

        get_logger().info('Merge rssi from ' + fname_in)
        with open(settings.config['RSSI']['HistoryFilename'], 'a') as f_hist, \
                open(settings.config['RSSI']['RecentFilename'], 'a') as f_recent:
            with open(fname_in) as f_in:
                s = f_in.read()
                _ = f_hist.write(s)
                _ = f_recent.write(s)

    # update recent
    thr = time.time() - float(settings.config['RSSI']['RecentWindow'])*60
    df = pd.read_csv(settings.config['RSSI']['RecentFilename'], dtype=DTYPE_RSSI_RECENT)
    df = df.loc[df['ts'] >= thr]
    df.to_csv(settings.config['RSSI']['RecentFilename'], index=False)


def get_observer_to_use(tag, blacklist=[]):
    obsset = eu.get_available_observer_names()
    obsset = obsset.difference(eu.get_blacklist_observer_names())
    obsset = obsset.difference(set(blacklist))
    df = pd.read_csv(settings.config['RSSI']['RecentFilename'], dtype=DTYPE_RSSI_RECENT)
    df_tag = df.loc[df['tag'] == tag]
    df_tag = df.loc[df['host'].isin(obsset)]
    if df_tag.shape[0] == 0:
        return None
    # calculate the best rssi
    df_tag.loc[:, 'count'] = 1
    df_tag = pd.pivot_table(df_tag, \
            index='host', values=['rssi','count'], \
            aggfunc=sum)
    df_tag['rssi'] = df_tag['rssi'] / df_tag['count']
    minobs = int(settings.config['Data']['MinObsCount'])
    df_tag = df_tag[df_tag['count'] >= minobs]
    best_rssi = df_tag['rssi'].max()
    # generate candidate set
    rssi_thr = best_rssi * float(settings.config['Data']['RSSIRatio'])
    candidate_observers = set(df_tag[df_tag['rssi']>=rssi_thr].index)
    obs = random.sample(candidate_observers,1)[0]
    return eu.get_observer_ip(obs)


