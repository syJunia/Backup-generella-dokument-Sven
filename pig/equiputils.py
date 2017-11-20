import settings
import datetime
import glob
import os
import time
from os import path
import pandas as pd
import numpy as np
import logging


def get_observer_name(hostip):
    df = pd.read_csv(settings.config['General']['ObserverList'])
    ip_map = df.set_index('IP').to_dict()['Host']
    if hostip in ip_map:
        return ip_map[hostip]
    else:
        return None


def get_observer_ip(hostname):
    df = pd.read_csv(settings.config['General']['ObserverList'])
    ip_map = df.set_index('Host').to_dict()['IP']
    if hostname in ip_map:
        return ip_map[hostname]
    else:
        return None


def get_available_tags():
    df = pd.read_csv(settings.config['General']['TagList'])
    return set(df['tag'])


def get_stop_tags():
    df = pd.read_csv(settings.config['General']['TagStopList'])
    return set(df['tag'])


def get_available_observer_names():
    df = pd.read_csv(settings.config['General']['ObserverList'])
    return set(df['Host'])


def get_available_observer_ips():
    df = pd.read_csv(settings.config['General']['ObserverList'])
    return set(df['IP'])


def get_blacklist_observer_names():
    df = pd.read_csv(settings.config['General']['ObserverBlackList'])
    return set(df['Host'])


def get_blacklist_observer_ips():
    df = pd.read_csv(settings.config['General']['ObserverBlackList'])
    return set(df['IP'])



