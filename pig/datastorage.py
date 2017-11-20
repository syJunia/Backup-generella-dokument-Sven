"""
Manages activity data collection

Many operations are not atomic, so risk of inconsistency exist in many
places. But assuming that the tag doesn't restart, it is unlikely to be 
a problem.

Every time we give a Record command, we start a new "Session" on the tag.
The data files are organized based on Sessions.

Usage
1. Upon start up, run initialize_logfiles(). If clean is True, then
    a new set of logs is created, otherwise old records are kept.
2. After Start and Stop, call data_event_handler() to update
3. When there is an update of Pos, call data_event_handler() to update
4. When a data collection is scheduled
    a. Call get_open_session() to get the current open session id
    b. Call get_data_collection_range() to get the start_pos and count
    c. After data is collected, add `sess_id`, `start_pos` and `count`
        to the resp dictionary, and then call data_event_handler() to 
        update

START_STOP_LOG (append only):
    sess_id, is_start, tag_mac, hostname, ts, ts_send
    NOTE that the absense of stop does not mean the tag is
    still running. it only means that no explicit stop command
    has been sent
TAG_POS_LOG_HIST (append only, use this for timestamp calibration):
    tag_mac, hostname, host_ts, host_ts_send, server_ts, pos, sess_id
TAG_POS_LOG_LATEST (used for deciding data collection)
    tag_mac, pos, server_ts_pos, next, server_ts_next
COLLECTION_EVENT_LOG (append only, only successful events):
    server_ts, tag_mac, hostname, start_pos, count, sess_id, seq_id
    data files will be saved as <sess_id>_<seqid>.csv

"""

import settings
import logging
from os import path
import numpy as np
import pandas as pd
import time

# TODO only check Pos for tags that are running
# TODO clean up status after collection stopped

DTYPE_START_STOP_LOG = {\
        'sess_id': np.int, \
        'is_start': np.int, \
        }
DTYPE_TAG_POS_LOG_HIST = {\
        'pos': np.int, \
        }
DTYPE_TAG_POS_LOG_LATEST = {\
        'pos': np.int, \
        'next': np.int, \
        }
DTYPE_COLLECTION_EVENT_LOG = {\
        'start_pos': np.int, \
        'count': np.int, \
        'sess_id': np.int, \
        'seq_id': np.int, \
        }


def get_logger():
    return logging.getLogger('PigPlus_server')


def initialize_logfiles(clean=False):
    if (not path.isfile(settings.config['Data']['StartStopLog'])) or (clean):
        with open(settings.config['Data']['StartStopLog'], 'w') as f:
            _ = f.write('sess_id,is_start,tag_mac,hostname,ts,ts_send\n')
    if (not path.isfile(settings.config['TagTimestamp']['HistoryFilename'])) or (clean):
        with open(settings.config['TagTimestamp']['HistoryFilename'], 'w') as f:
            _ = f.write('tag_mac,hostname,host_ts,host_ts_send,server_ts,pos,sess_id\n')
    if (not path.isfile(settings.config['TagTimestamp']['LatestFilename'])) or (clean):
        with open(settings.config['TagTimestamp']['LatestFilename'], 'w') as f:
            _ = f.write('tag_mac,pos,server_ts_pos,next,server_ts_next\n')
    if (not path.isfile(settings.config['Data']['EventLog'])) or (clean):
        with open(settings.config['Data']['EventLog'], 'w') as f:
            _ = f.write('server_ts,tag_mac,hostname,start_pos,count,sess_id,seq_id\n')


def get_start_stop_log_df():
    return pd.read_csv(settings.config['Data']['StartStopLog'], dtype=DTYPE_START_STOP_LOG)


def get_open_session(tag_mac):
    """
    Return the current open session for the tag. 
    Return None if there is no open session for the tag.
    """
    df = get_start_stop_log_df()
    df = df.loc[df['tag_mac'] == tag_mac]
    if df.shape[0] == 0:
        return None
    idmax = df.index.max()
    if df.loc[idmax, 'is_start'] == 0:
        return None
    else:
        return df.loc[idmax, 'sess_id']


def get_all_open_sessions():
    """
    Return a dictionary of tag->sess_id
    """
    df = get_start_stop_log_df()
    tags = set(df['tag_mac'])
    ret = {}
    for tag in tags:
        sess = get_open_session(tag)
        if sess is not None:
            ret[tag] = sess
    return ret


def open_session(tag_mac, hostname, ts, ts_s):
    df = get_start_stop_log_df()
    new_id = df.shape[0]
    df.loc[new_id] = [new_id,1,tag_mac,hostname,ts,ts_s]
    df.to_csv(settings.config['Data']['StartStopLog'], index=False)
    # reset position cache since everything is restarted
    df = pd.read_csv(settings.config['TagTimestamp']['LatestFilename'], dtype=DTYPE_TAG_POS_LOG_LATEST)
    df = df.loc[df['tag_mac'] != tag_mac]
    df.loc[df.shape[0]] = [tag_mac, 0, 0, 0, 0]
    df.to_csv(settings.config['TagTimestamp']['LatestFilename'], index=False)


def close_session(tag_mac, hostname, ts):
    df = get_start_stop_log_df()
    df.loc[df.shape[0]] = [-1,0,tag_mac,hostname,ts,None]
    df.to_csv(settings.config['Data']['StartStopLog'], index=False)


def update_pos(tag_mac, hostname, resp):
    sess_id = get_open_session(tag_mac)
    if sess_id is None:
        get_logger().error('Cannot update pos: no session open for tag {0}'.format(tag_mac))
        return False
    with open(settings.config['TagTimestamp']['HistoryFilename'], 'a') as f:
        _ = f.write('{0},{1},{2:.3f},{3:.3f},{4:.3f},{5},{6}\n'.format(\
                tag_mac, hostname, \
                resp['Timestamp'], resp['Timestamp_send'], \
                time.time(), resp['Pos'], sess_id))
    df = pd.read_csv(settings.config['TagTimestamp']['LatestFilename'], dtype=DTYPE_TAG_POS_LOG_LATEST)
    if tag_mac in set(df['tag_mac']):
        df.loc[df['tag_mac']==tag_mac, 'pos'] = resp['Pos']
        df.loc[df['tag_mac']==tag_mac, 'server_ts_pos'] = time.time()
    else:
        # NOTE in theory we will not get here
        df.loc[df.shape[0]] = [tag_mac, resp['Pos'], time.time(), 0, 0]
    df.to_csv(settings.config['TagTimestamp']['LatestFilename'], index=False)


def update_next_pos(tag_mac, hostname, next_pos):
    df = pd.read_csv(settings.config['TagTimestamp']['LatestFilename'], dtype=DTYPE_TAG_POS_LOG_LATEST)
    df.loc[df['tag_mac']==tag_mac, 'next'] = next_pos
    df.loc[df['tag_mac']==tag_mac, 'server_ts_next'] = time.time()
    df.to_csv(settings.config['TagTimestamp']['LatestFilename'], index=False)


def get_pos_poll_set(interval):
    """
    return the set of tag_mac whose Pos has not been updated for
    `interval` seconds
    """
    th = time.time()-interval
    df = pd.read_csv(settings.config['TagTimestamp']['LatestFilename'], dtype=DTYPE_TAG_POS_LOG_LATEST)
    df = df[df['server_ts_pos'] < th]
    return set(df['tag_mac'])


def get_data_collection_range(tag_mac, \
        max_samples = None, \
        min_samples = None):

    """
    Read the log of the latest tag position and the latest position
    that has been collected, return the parameters to be used for
    the next poll.

    If there are not enough samples, or if the records of the tag 
    cannot be found, return None, None
    """
    if max_samples is None:
        max_samples = int(settings.config['Data']['MaxSamplesPerPoll'])
    if min_samples is None:
        min_samples = int(settings.config['Data']['MinSamplesPerPoll'])

    df = pd.read_csv(settings.config['TagTimestamp']['LatestFilename'], dtype=DTYPE_TAG_POS_LOG_LATEST)
    if tag_mac not in set(df['tag_mac']):
        return None, None
    df = df.loc[df['tag_mac'] == tag_mac]
    idx = df.index.min()
    next_pos, max_pos = df.loc[idx, 'next'], df.loc[idx, 'pos']
    max_len = (max_pos+settings.MAX_SAMPLE_COUNT-next_pos) % settings.MAX_SAMPLE_COUNT
    if max_len < min_samples:
        return None, None
    if max_len > max_samples:
        max_len = max_samples
    return next_pos, max_len - max_len % 5


def save_data(tag_mac, hostname, resp):
    """
    Get a new sequence id and write the data into file
    """
    sess_id = resp['sess_id']
    start_pos = resp['start_pos']
    sample_count = resp['count']
    df = pd.read_csv(settings.config['Data']['EventLog'], dtype=DTYPE_COLLECTION_EVENT_LOG)
    seq_id = df.shape[0]
    df.loc[seq_id] = [time.time(), tag_mac, hostname, \
            start_pos, sample_count, sess_id, seq_id]
    with open(settings.config['Data']['DataFileFormat'].format(sess_id, seq_id), 'w') as f:
        _ = f.write('pos,x,y,z\n')
        _ = f.write(resp['Data'])
    df.to_csv(settings.config['Data']['EventLog'], index=False)


def data_event_handler(event_type, tag_mac, hostname, resp):
    """
    event types:
      start
      stop
      force_stop
      pos
      data collection
    """
    if event_type == 'start':
        if not resp['SUCCESS']:
            return False
        sess_id = get_open_session(tag_mac)
        if sess_id is not None:
            get_logger().info('Restarted session for tag {0}, old sess_id {1}'.format(tag_mac, sess_id))
            close_session(tag_mac, None, time.time())
        open_session(tag_mac, hostname, resp['Timestamp'], resp['Timestamp_send'])
        return True
    elif event_type == 'stop':
        if not resp['SUCCESS']:
            return False
        sess_id = get_open_session(tag_mac)
        if sess_id is not None:
            close_session(tag_mac, hostname, resp['Timestamp'])
            return True
        else:
            return False
    elif event_type == 'force_stop':
        # TODO not yet clear how this is to be used, probably need a file to keep track
        # of the latest status
        sess = get_open_session(tag_mac)
        if sess is not None:
            close_session(tag_mac, None, time.time())
            return True
        else:
            return False
    elif event_type == 'pos':
        if not resp['SUCCESS']:
            if 'DBG_TAG_STATE' in resp:
                if resp['DBG_TAG_STATE'] == 0:
                    get_logger().error('Pos for tag {0} via obs {1} failed - tag state off'.format(tag_mac, hostname))
                    close_session(tag_mac, None, time.time())
                elif resp['DBG_TAG_STATE'] == -1:
                    get_logger().error('Pos for tag {0} via obs {1} failed - tag not found'.format(tag_mac, hostname))
            return False
        update_pos(tag_mac, hostname, resp)
        return True
    elif event_type == 'data':
        if not resp['SUCCESS']:
            if 'DBG_TAG_STATE' in resp:
                if resp['DBG_TAG_STATE'] == 0:
                    get_logger().error('Data collection for tag {0} via obs {1} failed - tag state off'.format(tag_mac, hostname))
                    close_session(tag_mac, None, time.time())
                elif resp['DBG_TAG_STATE'] == -1:
                    get_logger().error('Data collection for tag {0} via obs {1} failed - tag not found'.format(tag_mac, hostname))
            return False
        if 'sess_id' not in resp or \
                'start_pos' not in resp or \
                'count' not in resp:
            return False
        resp['Next'] = resp['Next'] % settings.MAX_SAMPLE_COUNT
        save_data(tag_mac, hostname, resp)
        update_next_pos(tag_mac, hostname, resp['Next'])
        return True
    else:
        return False


