# some utility functions that processes recent rssi readings

import numpy as np
import pandas as pd
import time

def tags_seen(recent_fname):
    df = pd.read_csv(recent_fname, \
        header=None, names=['ts','host','tag_mac','rssi'])
    return set(df['tag_mac'])

def tags_obs_stats(recent_fname, window=None):
    """
    returns a dict mapping tag mac address to another
    dict, mapping host to observation count and rssi

    can specify a different interval window (in minutes)
    than what is configured for RSSI recent
    """
    df = pd.read_csv(recent_fname, \
        header=None, names=['ts','host','tag_mac','rssi'])
    if window is not None:
        thr = time.time()-window*60
        df = df.loc[df['ts']>=thr]
    df.drop(['ts'], axis=1, inplace=True)
    df['count'] = 1
    df = pd.pivot_table(df, index=['tag_mac','host'], \
            values=['rssi','count'], aggfunc=np.sum)
    df['rssi'] = df['rssi'] / df['count']
    df = df.to_dict()
    ret = {}
    for tag,host in df['count']:
        if tag not in ret:
            ret[tag] = {}
        ret[tag][host] = (df['count'][(tag,host)], df['rssi'][(tag,host)])
    return ret

def get_best_obs(stats, tag, minobs):
    """
    return the observer that have seen the tag at least minobs times
    and that has the best average rssi 
    """
    if tag not in stats:
        return None
    l = [(obs,u[1]) for obs,u in stats[tag].items() if u[0]>=minobs]
    if len(l)==0:
        return None
    return max(l, key=lambda x: x[1])

