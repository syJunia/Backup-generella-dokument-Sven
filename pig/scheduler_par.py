import argparse
import signal
import datetime
import random
import time
import logging
import logging.handlers
import multiprocessing as mp
from multiprocessing import Value
import json
import requests
import pandas as pd
import datastorage as ds
import rssiutils as ru
import equiputils as eu
import settings

# interval at which main is triggered
TRIGGER_INTERVAL_SEC = 16
# interval at which the trigger process itself is waked
TRIGGER_WAKE_SEC = 2


# TODO logging doesn't support multiprocess, so go through
# everything to make sure we are not having those

# Introduce debug logging
def get_logger(level=logging.INFO, log_fname='logs/serverdebug.log'):
    logger = logging.getLogger('PigPlus_server')
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


def start_record(tag_mac, sample_range, sample_rate, addr):
    r_str = '{0}/StartRecord/{1}/{2}/{3}'.format(\
            addr, tag_mac, sample_range, sample_rate)
    # print(r_str)
    try:
        r = requests.get(r_str, timeout=120)
        return json.loads(r.text)
    except requests.exceptions.Timeout:
        return {'SUCCESS': False}
    except requests.exceptions.ConnectionError:
        return {'SUCCESS': False}


def stop_record(tag_mac, addr):
    r_str = '{0}/StopRecord/{1}'.format(addr, tag_mac)
    try:
        r = requests.get(r_str, timeout=120)
        return json.loads(r.text)
    except requests.exceptions.Timeout:
        return {'SUCCESS': False}
    except requests.exceptions.ConnectionError:
        return {'SUCCESS': False}


def get_pos(tag_mac, addr):
    r_str = '{0}/ReadTagPosition/{1}'.format(addr, tag_mac)
    try:
        r = requests.get(r_str, timeout=120)
        return json.loads(r.text)
    except requests.exceptions.Timeout:
        return {'SUCCESS': False}
    except requests.exceptions.ConnectionError:
        return {'SUCCESS': False}


def get_data(tag_mac, start_pos, count, sample_range, addr):
    r_str = '{0}/CollectData/{1}/{2}/{3}/{4}'.format(\
            addr, tag_mac, start_pos, count, sample_range)
    try:
        r = requests.get(r_str, timeout=480)
        return json.loads(r.text)
    except requests.exceptions.Timeout:
        return {'SUCCESS': False}
    except requests.exceptions.ConnectionError:
        return {'SUCCESS': False}


def trigger_runner(main_q, sig_val):
    """
    Arguments
        main_q  the runner triggers main by periodically
                putting a special "trigger" task on the main
                queue
        sig_val a value shared between main and trigger, set
                o 0 to stop the process
    """
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    count_down = TRIGGER_INTERVAL_SEC
    while sig_val.value:
        count_down -= TRIGGER_WAKE_SEC
        if count_down <= 0:
            main_q.put(('T',{}))
            count_down = TRIGGER_INTERVAL_SEC
        time.sleep(TRIGGER_WAKE_SEC)


def tag_state_collector(interval, sig_val):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    count_down = 0
    while sig_val.value:
        count_down -= TRIGGER_WAKE_SEC
        if count_down <= 0:
            try:
                ru.update_all_observers_rssi_observations()
            except:
                return
            count_down = interval
        time.sleep(TRIGGER_WAKE_SEC)


def task_runner(worker_q, main_q, hostname, addr):
    import os
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    killed = False
    def sigkill_handler(signum, frame):
        nonlocal killed
        killed = True

    signal.signal(signal.SIGTERM, sigkill_handler)

    for task_type, params in iter(worker_q.get, ('End', {})):
        if killed:
            break
        tag = params['tag']
        if task_type=='pos':
            resp = get_pos(tag, addr)
        elif task_type=='data':
            start_pos = params['start_pos']
            count = params['count']
            sample_range = params['range']
            sess_id = params['sess_id']
            resp = get_data(tag, start_pos, count, sample_range, addr)
            resp['sess_id'] = sess_id
            resp['start_pos'] = start_pos
            resp['count'] = count
        elif task_type=='start':
            sample_range = params['range']
            sample_rate = params['rate']
            resp = start_record(tag, sample_range, sample_rate, addr)
        elif task_type=='stop':
            tag = params['tag']
            resp = stop_record(tag, addr)
        else:
            continue
        resp['tag'] = tag
        resp['obs'] = hostname
        main_q.put((task_type, resp))


def start_tag_state_proc(sig_val):
    tagstate_proc = mp.Process(target=tag_state_collector, \
            args=(int(settings.config['RSSI']['FetchInterval'])*60, sig_val))
    tagstate_proc.start()
    return tagstate_proc


def schedule_task(worker_qs, dead_observers, \
        current_tag_comm, current_obs_tasks, \
        tag, task):
    # TODO right now if a scheduling failed there is no mechanism for retry
    blacklist = [obs for obs,l in current_obs_tasks.items() if len(l)>=3]
    blacklist = set(blacklist).union(set(dead_observers))
    h = ru.get_observer_to_use(tag, blacklist=blacklist)
    if h is None:
        get_logger().error('Cannot schedule {0} for tag {1}'.format(task[0], tag))
        return False
    worker_qs[h].put(task)
    hname = eu.get_observer_name(h)
    current_tag_comm[tag] = task[0]
    if hname not in current_obs_tasks:
        current_obs_tasks[hname] = []
    current_obs_tasks[hname].append(task)
    get_logger().info('Scheduled {0} for tag {1} on {2}'.format(task[0], tag, h))
    return True


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='server/server.cfg',
                        help='File with config parameters')
    parser.add_argument('--logger', default='logs/serverdebug.log',
                        help='Debug logfile')
    parser.add_argument('--noclean', action='store_true')
    args = parser.parse_args()

    if not args.noclean:
        c = ''
        while c not in ['y','n']:
            c = input('ALL PREVIOUS LOGS WILL BE ERASED, continue? [y/n] ')
            c = str.lower(c)
        if c == 'n':
            return

    _ = get_logger(level=logging.INFO, log_fname=args.logger)
    settings.init(args.config)

    ds.initialize_logfiles(clean=not args.noclean)
    ru.initialize_logfiles(clean=not args.noclean)

    HostAddresses = eu.get_available_observer_ips()
    get_logger().info(str(HostAddresses))


    # ip -> queue
    worker_qs = dict([(host,mp.Queue()) for host in HostAddresses])
    main_q = mp.Queue()
    interrupted = False
    sig_val = Value('i', 1)

    def sigint_handler(signum, frame):
        nonlocal interrupted
        interrupted = True
        get_logger().info('Interrupt received!')

    tagstate_proc = start_tag_state_proc(sig_val)

    # dictionary, tag->'data'/'pos'
    current_tag_comm = {}
    # dictionary, hostname -> list of tasks
    current_obs_tasks = {}
    # start processes
    proc_timer = mp.Process(target=trigger_runner, \
            args=(main_q, sig_val))
    proc_timer.start()
    workers = {eu.get_observer_name(addr):mp.Process(target=task_runner, \
            args=(worker_q, main_q, eu.get_observer_name(addr), addr)) \
            for addr,worker_q in worker_qs.items()}
    for hostname, p in workers.items():
        p.start()

    tm = int(settings.config['General']['Timer'])
    if tm > 0:
        STOP_TIME = time.time()+60*tm
    else:
        STOP_TIME = 1e11
    get_logger().info('stop time {0:.2f}, timer {1}'.format(STOP_TIME, tm))

    prepare_to_stop = False
    stop_record_sent = False

    # set the sigint handler for the main process
    signal.signal(signal.SIGINT, sigint_handler)

    get_logger().info('Tag state process: {0}'.format(tagstate_proc.pid))
    get_logger().info('Timer process: {0}'.format(proc_timer.pid))
    get_logger().info('Workers')
    for hostname, p in workers.items():
        get_logger().info('{0}: process {1}'.format(hostname, p.pid))

    # main loop
    # data structure to be maintained: 
    #   worker_qs: IP -> Queue
    #   workers: hostname -> process
    #   current_tag_comm: tag -> task name
    #   current_obs_tasks: hostname -> list of tasks
    for t,params in iter(main_q.get, (None,None)):
        try:
            dead_observers = [hname for hname,p in workers.items() if not p.is_alive()]
            if t=='T':
                settings.init(args.config)

                if not prepare_to_stop:
                    # only schedule new tasks if there is no stop signal

                    # make sure the tag status collector is running
                    if not tagstate_proc.is_alive():
                        tagstate_proc = start_tag_state_proc(sig_val)

                    # start tags that are not currently running
                    available_tags = eu.get_available_tags()
                    stop_tags = eu.get_stop_tags()
                    open_sessions = ds.get_all_open_sessions()
                    for tag in available_tags:
                        if tag in current_tag_comm:
                            # tag busy, no communication possible, skip for this round
                            continue
                        if (tag not in open_sessions) and (tag not in stop_tags):
                            schedule_task(worker_qs, dead_observers, current_tag_comm, current_obs_tasks, tag, \
                                ('start', {\
                                'tag': tag, \
                                'range': int(settings.config['Data']['SampleRange']), \
                                'rate': int(settings.config['Data']['SampleRate'])}))
                        elif (tag in open_sessions) and (tag in stop_tags):
                            schedule_task(worker_qs, dead_observers, current_tag_comm, current_obs_tasks, tag, \
                                    ('stop', {'tag': tag}))

                    # schedule data collection
                    for tag,sess_id in random.sample(open_sessions.items(), len(open_sessions)):
                        if tag not in current_tag_comm:
                            start_pos, count = ds.get_data_collection_range(\
                                    tag, max_samples=int(settings.config['Data']['MaxSamplesPerPoll']), \
                                    min_samples=int(settings.config['Data']['MinSamplesPerPoll']))
                            if start_pos is not None:
                                schedule_task(worker_qs, dead_observers, current_tag_comm, current_obs_tasks, tag, \
                                        ('data', {\
                                        'sess_id': sess_id, \
                                        'range': int(settings.config['Data']['SampleRange']), \
                                        'tag': tag, \
                                        'start_pos': start_pos, \
                                        'count': count}))
                                        
                    # schedule pos
                    pos_tags = ds.get_pos_poll_set(int(settings.config['TagTimestamp']['Interval'])*60)
                    for tag in random.sample(pos_tags, len(pos_tags)):
                        if tag not in current_tag_comm:
                            schedule_task(worker_qs, dead_observers, current_tag_comm, current_obs_tasks, tag, \
                                    ('pos', {'tag': tag}))

            elif t=='start':
                tag = params['tag']
                del current_tag_comm[tag]
                observer = params['obs']
                _ = current_obs_tasks[observer].pop(0)
                ds.data_event_handler('start', tag, observer, params)
                get_logger().info('Start job finished: {0}'.format(params))
            elif t=='stop':
                tag = params['tag']
                del current_tag_comm[tag]
                observer = params['obs']
                _ = current_obs_tasks[observer].pop(0)
                ds.data_event_handler('stop', tag, observer, params)
                get_logger().info('Stop job finished: {0}'.format(params))
                # if (not params['SUCCESS']):
                #     schedule_task(worker_qs, dead_observers, current_tag_comm, current_obs_tasks, tag, ('stop', {'tag': tag}))
            elif t=='pos':
                tag = params['tag']
                del current_tag_comm[tag]
                observer = params['obs']
                _ = current_obs_tasks[observer].pop(0)
                ds.data_event_handler('pos', tag, observer, params)
                get_logger().info('Pos job finished: {0}'.format(params))
            elif t=='data':
                tag = params['tag']
                del current_tag_comm[tag]
                observer = params['obs']
                _ = current_obs_tasks[observer].pop(0)
                ds.data_event_handler('data', tag, observer, params)
                if (not prepare_to_stop) and (not interrupted):
                    schedule_task(worker_qs, dead_observers, current_tag_comm, current_obs_tasks, tag, \
                            ('pos', {'tag': tag}))
                if 'Data' in params:
                    del params['Data']
                get_logger().info('Data job finished from tag {0}, result {1}'.format(tag, params))

            if interrupted or time.time()>STOP_TIME:
                # NOTE not using break here just so that tasks
                # that are already running can finish
                prepare_to_stop = True
                if not stop_record_sent:
                    if len(current_tag_comm) == 0:
                        sig_val.value = 0
                        get_logger().info('preparing to stop')
                        for tag in ds.get_all_open_sessions():
                            schedule_task(worker_qs, dead_observers, current_tag_comm, current_obs_tasks, tag, ('stop', {'tag': tag}))
                        stop_record_sent = True

                if all(q.empty() for q in worker_qs.values()) and main_q.empty() and (len(current_tag_comm)==0):
                    break

            # reschedule tasks for killed observers
            for obs in dead_observers:
                if len(current_obs_tasks[obs]):
                    for task in current_obs_tasks[obs]:
                        get_logger().info('Rescheduling from observer {0} task {1}'.format(obs, task))
                        schedule_task(worker_qs, dead_observers, current_tag_comm, current_obs_tasks, task[1]['tag'], task)
                    current_obs_tasks[obs] = []

            # restart observer processes
            obs_blacklist = eu.get_blacklist_observer_names()
            for obsname in dead_observers:
                if obsname in obs_blacklist:
                    continue
                get_logger().info('Restarting {0}'.format(obsname))
                addr = eu.get_observer_ip(obsname)
                worker_q = mp.Queue()
                worker_qs[addr] = worker_q
                workers[obsname] = mp.Process(target=task_runner, \
                        args=(worker_q, main_q, obsname, addr))
                workers[obsname].start()
                get_logger().info('{0}: process {1}'.format(obsname, workers[obsname].pid))

            get_logger().info('Current communications: {0}'.format(current_tag_comm))
            get_logger().info('Current task list: {0}'.format(current_obs_tasks))
        except:
            get_logger().exception('Unknown exception')
            continue


    # terminating
    get_logger().info('Signal workers to stop')
    for q in worker_qs.values():
        q.put(('End',{}))
    get_logger().info('Waiting for workers to stop')
    for p in workers.values():
        p.join()
    get_logger().info('Waiting for timer to stop')
    proc_timer.join()
    get_logger().info('Waiting for tag state collector to stop')
    tagstate_proc.join()


if __name__ == "__main__":
    main()

