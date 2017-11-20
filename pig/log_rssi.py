from __future__ import print_function
# Author: Sangxia Huang

import argparse
import logging.handlers
import time
import os
import subprocess
import signal


def kill_hci_process(sig: object, frame: object):
    if (kill_hci_process.current is not None) and (kill_hci_process.current.poll() is None):
        os.kill(kill_hci_process.current.pid, signal.SIGINT)
    if sig == signal.SIGTERM:
        exit(0)
    time.sleep(0.5)


kill_hci_process.current = None


def get_rollover_func(r, err_log):
    def rollover_func(sig, frame):
        err_log.warning('Rollover triggered')
        r()
    return rollover_func


parser = argparse.ArgumentParser(description='Logs AccStream RSSI')
parser.add_argument('--hci_timeout', dest='hci_restart',
        type=float, default=3.,
        help='Number of seconds after which hciadv is killed and restarted')
parser.add_argument('--rollover_period', dest='rollover',
        type=float, default=600.,
        help='Number of seconds for logging rollover')
parser.add_argument('--use_stdout', dest='use_stdout', action='store_true')
parser.add_argument('--use_fileout', dest='outfile',
        type=str, default='',
        help='If a filename is specified, then log RSSI to a \
        timed rotating handler with the filename as base filename')
parser.add_argument('--hostname', dest='host',
        type=str, default='',
        help='Host name to be used when logging, mandatory if using \
        outfile, ignored if not')
args = parser.parse_args()


if len(args.outfile)>0 and len(args.host)==0:
    print('Must specify host name when logging to file')
    exit(1)
if len(args.outfile)==0 and not args.use_stdout:
    print('No output destination specified')
    exit(1)
formatter = logging.Formatter('%(created)f,%(message)s')
logger = logging.getLogger('events')
logger.setLevel(logging.INFO)
err_logger = logging.getLogger('errors')
err_logger.setLevel(logging.WARNING)
if args.use_stdout:
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    ch.setLevel(logging.INFO)
    logger.addHandler(ch)
    err_logger.addHandler(ch)
if args.outfile:
    rh = logging.handlers.TimedRotatingFileHandler(
            args.outfile, when='S', interval=args.rollover, utc=True)
    rh.setFormatter(formatter)
    rh.setLevel(logging.INFO)
    logger.addHandler(rh)
    er = logging.FileHandler(args.outfile+'_errors')
    er.setLevel(logging.WARNING)
    er.setFormatter(formatter)
    err_logger.addHandler(er)

err_logger.warning('PID: {0}'.format(os.getpid()))
signal.signal(signal.SIGTERM, kill_hci_process)
if args.outfile:
    signal.signal(signal.SIGUSR1, get_rollover_func(rh.doRollover, err_logger))

try:
    while True:
        p = subprocess.Popen(['hciadv','-r', '1'], stdout = subprocess.PIPE, stderr = subprocess.PIPE)
        kill_hci_process.current = p
        for r in p.stdout:
            try:
                s = r.decode('ascii').strip()
            except UnicodeDecodeError:
                err_logger.warning('Undecodable: {0}'.format(r))
                continue
            if not s:
                continue
            s = s.split(';')
            if s[1].startswith('Pig'):
                logger.info('{0},{1},{2},{3}'.format(args.host,s[0],s[2],s[3]))
        for r in p.stderr:
            try:
                s = r.decode('ascii').strip()
            except UnicodeDecodeError:
                err_logger.warning('Undecodable: {0}'.format(r))
                continue
            if s.startswith('Enable scan failed: Input/output error'):
                err_logger.critical('hciadv scan failed')
                exit(1)
        p.stdout.close()
        p.stderr.close()
except KeyboardInterrupt:
    kill_hci_process(None,None)
except Exception as ex:
    err_logger.exception(ex)
    kill_hci_process(None,None)
