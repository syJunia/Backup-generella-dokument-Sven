#!/usr/bin/env python
# -*- coding: utf-8 -*-
# routing_scheduler.py
#
# Python software that will route traffic between observer - tag ,
# it will ask the available observers to request data from the available tags
#
# Author: Sven Tryding
# Date: September 2017 - October 2017
#
# Server based routing script
# Read startup parameter from config_file
# Read tag log files
# Match tags to be collected with visible tags reported by observers
# Send Collect data request to observers selected in the tag_routing_queue
# Parameter is starting point for tag data to be requested and Tag id to collect from.
# (Based on timestamp in logs and available tags)
# Receive data from tags via observers
# Update tag logs by appending the received concatenated data from the tags
# Upload taglog to AWS pigplus Kinesis stream (via Iris Kinesis)
# Re-iterate the reporting process when a new schedule event occurs
import argparse
import configparser
import datetime
import glob
import logging
import logging.handlers
import os
import shutil
import time
import nmap
import pandas as pd
import requests
import schedule
import json
import datastorage as ds
import rssiutils as ru

start_pos_dict = {'tag': 0}

#  Introduce debug logging
def start_logger(level=logging.INFO, log_fname='server/serverdebug.log'):
    logger = logging.getLogger('PigPlus_server')
    logger.setLevel(level)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(message)s')
    fh = logging.handlers.RotatingFileHandler(log_fname, 'a', 3000000, 100)
    fh.setLevel(level)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    return logger


log = start_logger()


# This function will scan the LAN find devices with the part of
# the hostname as "PIG"  and add them to the file
# update_available_observers, add this feature
# when nmap on our network is operational, Perhaps hourly?
# It will find the ip and hostname to use as observers
def update_available_observers():
    log.info("Updating observers")
    nm = nmap.PortScanner()
    nm.scan(hosts='192.168.1.0/24', arguments='-sn')
    # ip_list = nm.all_hosts()
    # When we get nm[host].hostname() to return a proper value use this
    # with open('available_observers.cfg', 'w') as f:
    #    for host in nm.all_hosts():
    #        # Comment out until we get a correct hostname
    #        #if 'PIG' in nm[host].hostname():
    #        f.write(host + "," + nm[host].hostname() + "\n")
    log.info("available_observers.cfg updated")


def collect_tag_data(observer_addr, tag):
    # At the end of the data next startpos is appended after a '&
    start_pos, samples = ds.get_data_collection_range(tag)

    if samples is None:
        # Not enough data , don't collect data 
        return

    samples = str(samples)
    start_pos = str(start_pos)

    log.info("Ok samples done = " + samples)
    log.info("Ok start pos  = " + start_pos)
    s_range = "8"
    r_str = ("http://" + observer_addr + ":8081/CollectData/" + tag +
             "/" + start_pos + "/" + samples + "/" + s_range)
    try:
        r = requests.get(r_str, timeout=480)
        resp = {\
            'sess_id': ds.get_open_session(tag), \
            'start_pos': start_pos, \
            'count': samples, \
        }
        r_dict = json.loads(r.text)
        r_dict.update(resp)
        log.info('adding to datastorage')
        ds.data_event_handler('data', tag, observer_addr, r_dict)
        log.info('after adding to datastorage')

    except requests.exceptions.RequestException as e:
        log.info(e)
        # Potentially shall we count exceptions from
        # an observer if we have 5 consecutive 'GET'
        # exceptions we shall remove the observer from
        # available_observers list and
        # report an issue to the AWS - UI. "Observer - broken?"
        log.info('Failed collect data exception ' + str(e))


def start_recording(observer_addr, tag, r_range, r_rate):

    r_str = ("http://" + observer_addr + ":8081/StartRecord/"
             + tag + '/' + r_range + '/' + r_rate)
    log.info(r_str)
    st_ts =time.time()
    try:
        r = requests.get(r_str, timeout=45)
        r_dict = r.json()
        log.info(r_dict)
        ds.data_event_handler('start', tag, observer_addr, r_dict)
        return r_dict
    except requests.exceptions.RequestException as e:
        log.info('Failed start recording exception ' +  str(e))
        return {'SUCCESS' : False, 'Exception' : e}


def stop_recording(observer_addr, tag):
    r_str = ("http://" + observer_addr + ":8081/StopRecord/"
             + tag)
    log.info(r_str)
    try:
        r = requests.get(r_str, timeout=45)
        r_dict = r.json()
        ds.data_event_handler('stop', tag, observer_addr, r_dict)
        return r_dict
    except requests.exceptions.RequestException as e:
        log.info('Failed stop recording exception ' + str(e))
        return {'SUCCESS' : False,  'Exception' : e}


def read_tag_position(observer_addr, tag):
    r_str = ("http://" + observer_addr + ":8081/ReadTagPosition/"
             + tag)
    log.info(r_str)
    try:
        r = requests.get(r_str, timeout=45)
        r_dict = r.json()
        ds.data_event_handler('pos', tag, observer_addr, r_dict)
    except requests.exceptions.RequestException as e:
        log.info('Failed to read tag pos exception ' + str(e))


def read_tag_pos_job():
    log.info('Read tag ts ')
    df = pd.read_csv(r'server/tag_routing_queue.txt', names=['tag', 'obs'])
    for index, row in df.iterrows():
        observer_addr = row['obs']
        tag = row['tag']
        log.info(observer_addr)
        read_tag_position(observer_addr, tag)


def collect_tag_data_job():
    log.info('Collect tag data')
    df = pd.read_csv(r'server/tag_routing_queue.txt', names=['tag', 'obs'])
    for index, row in df.iterrows():
        observer_addr = row['obs']
        tag = row['tag']
        log.info(observer_addr)
        log.info('Req data')
        collect_tag_data(observer_addr, tag)


def start_tag_recordings():
    import numpy
    from multiprocessing import Pool

    # First stop potential ongoing recording, then initiates a new recording
    df_available_tags = pd.read_csv(r'server/available_tags.cfg')
    for index, row in df_available_tags.iterrows():
        tag = row['tag']
        log.info("tag = " +  tag)
        # Use previous rssi.recent, is probably better than anything else
        df_recent = pd.read_csv(r'server/rssi.recent',
                                names=['ts', 'host', 'tag', 'status', 'rssi'])  # Temp to use old rssi.recent
        df_tag = df_recent[df_recent['tag'].isin([tag])]
        if not df_tag.empty:
            maxpos = df_tag['rssi'].idxmax()
            if numpy.isnan(maxpos):
                maxpos = 0
            use_observer = df_tag.at[maxpos, 'host']
            use_observer.capitalize()
        else:
            log.info('Tag not seen :' + tag)
            use_observer = 'PIG1'  # TODO Decide what to do if not seen
        df_o = pd.read_csv(r'server/available_observers.cfg')

        if use_observer in df_o.index:
            obs_ind = df_o[df_o['Host'].isin([use_observer])].index
            obs_ip = df_o.loc[obs_ind]['IP']
            obs_ip_s = obs_ip.iloc[0]
        else:
            # Fallback to availible observer
            obs_ip_s = df_o.loc[0]['IP']

        log.info(obs_ip_s)
        log.info(tag)
        # TODO Read range and rate from config file
        start_recording(obs_ip_s, tag, "8", "50")
    log.info("All available tags now started ...")

def tag_record_watchdog():
    #
    #   Check status in rssi log.
    #   Note that we must ensure that the Rssi log has been updated since we started
    #   If tag is not recording - restart it.
    #   a battery glitch might have re-started the tag
    df = pd.read_csv(r'server/available_tags.cfg')
    for index, row in df.iterrows():
        tag = row['tag']
        state = ru.read_tag_state(tag)
        log.info('State =' + json.dumps(state))  # +' of ' + tag)
        
        if state['State'] > 0:
            # Fine we are recording
            pass
        else:
            # Stopped recording ?!
            # Battery lost ?
            #log.info('State' + state + ' of tag' + tag + ' restarting ')
            log.info('What ?!, Battery connection?')
            config = configparser.ConfigParser()
            config.read('server/server.cfg')
            df_recent = pd.read_csv(config['RSSI']['RecentFilename'], names=['ts', 'host', 'tag', 'status', 'battery', 'rssi'])
            df_tag = df_recent[df_recent['tag'].isin([tag])]
            if not df_tag.empty:
                maxpos = df_tag['rssi'].idxmax()
                use_observer = df_tag.at[maxpos, 'host']
                use_observer.capitalize()
            else:
                log.info('Tag not seen : ' + tag)
                use_observer = 'PIG2'
            df_o = pd.read_csv(r'server/available_observers.cfg')
            obs_ind = df_o[df_o['Host'].isin([use_observer])].index
            obs_ip = df_o.loc[obs_ind]['IP']
            obs_ip_s = obs_ip.iloc[0]
            start_recording(obs_ip_s, tag, "8", "50")

def check_watchdog_and_update_rssi():
    # First ensure that we have updated rssi status from observers
    ru.update_all_observers_rssi_observations()
    # check if any tag stoped recording,  Restart if it has soped
    tag_record_watchdog()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='server/server.cfg',
                        help='File with config parameters')
    parser.add_argument('--logger', default='server/serverdebug.log',
                        help='Debug logfile')
    args = parser.parse_args()
    config = configparser.ConfigParser()
    config.read(args.config)


    # initialize datastorage
    ds.initialize_logfiles(clean=True)
    # Ensure that we get the later rssi values
    ru.update_all_observers_rssi_observations()
    # Create the routing queue
    ru.create_tag_routing_queue()  # Will update the match_queue.que files
    log.info('Start tags to record data')
    # Trig all tags to start record data
    start_tag_recordings()
    log.info('Tag recording started')

    # Here we start the schedulers
    log.info("We start the timers, lets wait for scheduled events")
    collect_data_timer = int(config['Data']['CollectionInterval']) * 60  
    tag_pos_timer = int(config['TagTimestamp']['Interval']) * 60  #To seconds
    rssi_ts_timer = int(config['RSSI']['FetchInterval']) * 60  # shall be 60 To seconds
    schedule.every(collect_data_timer).seconds.do(collect_tag_data_job)
    schedule.every(tag_pos_timer).seconds.do(read_tag_pos_job)
    schedule.every(rssi_ts_timer).seconds.do(check_watchdog_and_update_rssi)

    # Listen only for keyboard interrupt to stop the script
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        log.info('Interrupted!')
        pass


if __name__ == "__main__":
    main()
