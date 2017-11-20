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
import logging
import logging.handlers
import time
import nmap
import pandas as pd
import requests
import schedule
import json
import datastorage as ds
import rssiutils as ru
import settings

start_pos_dict = {'tag': 0}

#  Introduce debug logging
def start_logger(level=logging.INFO, log_fname='server/serverdebug.log'):
    logger = logging.getLogger('PigPlus_rssi_reader')
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


def update_rssi():
    # First ensure that we have updated rssi status from observers
    ru.update_all_observers_rssi_observations()
    # check if any tag stoped recording,  Restart if it has soped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='server/server.cfg',
                        help='File with config parameters')
    parser.add_argument('--logger', default='server/serverdebug.log',
                        help='Debug logfile')
    args = parser.parse_args()

    settings.init(args.config)


    # Here we start the schedulers, 2017-10-26, Only RSSI
    log.info("We start the timers, Read Rssi logs regulary")
    rssi_ts_timer = int(settings.config['RSSI']['FetchInterval']) * 6  # shall be 60 To seconds
    schedule.every(rssi_ts_timer).seconds.do(update_rssi)

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
