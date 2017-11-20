#!/usr/bin/env python
#
# Python software that will be executed on an observer.
# It will get data from a tag when asked to to so from the server.
#
# Author: Sven Tryding
# Date: September 2017
#
#  This script is a server listening to “Commands“ from the main server based routing script
#  Discriminate on command the read parameters (tag id and starting time  e.g.)
#  Communicate with the tag to perform the command e.g. Collect data or Read battery
#  Receive response from the tag
#  Return the received log data to server
#  Designed as a Command receiving HTTP server in python. Test from command line with these requests e.g.
# Usage::
#    ./rpi-commandreceiver-server.py [<port>]
# Send a GET request::
#    curl http://localhost:8081, use the proper ip of the rpi this script is executed on
# Send a HEAD request::
#    curl -I http://localhost:8081
# Send a POST request::
#    curl -d "foo=bar&bin=baz" http://localhost:8081


from http.server import BaseHTTPRequestHandler, HTTPServer
import tempfile
import shutil
import glob
import time
import argparse
import pigutils
import socket
import signal
import os
import datetime
import json


def convert_log_ts_to_utc(s):
    """
    inputs are like 2017-09-28_07-31-25. returns
    number of seconds 
    """
    ts = time.mktime(datetime.datetime.strptime(
        s, "%Y-%m-%d_%H-%M-%S").timetuple())
    return int(ts)


def handler(signum, frame):
    print('Signal handler called with signal', signum)
    raise IOError("Couldn't open device!")


def send_rssi_log(from_time_stamp):

    # find the RSSI logger, send a signal to trigger a roll-over
    import subprocess
    try:
        log_pid = int(subprocess.check_output(\
                ['pgrep', 'log_rssi.py']).decode().strip())
    except subprocess.CalledProcessError:
        print('RSSI log not running')
        return None
    os.kill(log_pid, signal.SIGUSR1)
    time.sleep(.5)

    basefile = socket.gethostname() + '.log'
    timestamp = int(from_time_stamp)
    print('Log_fnames')
    print(timestamp)

    fnames = [
        (f, convert_log_ts_to_utc(f[len(basefile) + 1:]))
        for f in glob.glob(basefile + '.*')]
    fnames = [u for u in fnames if u[1] > timestamp]
    if len(fnames) == 0:
        # make sure the server handles this
        print('0 file to be transmitted')
        return None
    print('fnames created')
    fnames = sorted(fnames, key=lambda u: u[1])
    # make sure the server handles this
    print('Max transmitted ts:', fnames[-1][1])
    with tempfile.TemporaryDirectory() as tmpdirname:
        from shutil import make_archive
        print('Temp dir name', tmpdirname)
        out_list = []
        for fname_in, _ in fnames:
            fname_out = os.path.join(tmpdirname, fname_in)
            with open(fname_in, 'rb') as f_in, \
                    open(fname_out, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
            out_list.append(fname_out)
        with open('meta', 'w') as f:
            _ = f.write('\n'.join(out_list) + '\n')
            _ = f.write('{0}\n'.format(fnames[-1][1]+1))

        archive_name = os.path.expanduser(os.path.join('~', 'rssi_arch'))
        make_archive(archive_name, 'zip', tmpdirname)
        print(archive_name)
    return archive_name


class Server(BaseHTTPRequestHandler):
    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

    def do_GET(self):
        self._set_headers()
        if "/CollectData" in self.path:
            # TODO if the data gets large enough, it probably
            # make sense to send files. on the other hand
            # collecting large batches of data is quite risky,
            # so maybe we should avoid doing that anyways.

            # /CollectData/TagMac/StartPosition/SampleCount/SampleRange
            parameters = self.path.split('/')
            tag_mac = parameters[2]
            start_pos = parameters[3]
            num_samples = parameters[4]
            sample_range = parameters[5]
            collected_data = pigutils.collect_data(tag_mac, \
                    start_pos, num_samples, sample_range)
            self.wfile.write(json.dumps(collected_data).encode('utf-8'))
        elif "/ReadBattery" in self.path:
            # /ReadBattery/TagMac
            parameters = self.path.split('/')
            tag_mac = parameters[2]
            print('Battery tag mac = {0}'.format(tag_mac))
            battery_data = pigutils.read_battery(tag_mac)
            self.wfile.write(json.dumps(battery_data).encode('utf-8'))
        elif "/ReadTagPosition" in self.path:
            # /ReadTagTimeCounter/TagMac
            parameters = self.path.split('/')
            tag_mac = parameters[2]
            position = pigutils.read_position(tag_mac)
            self.wfile.write(json.dumps(position).encode('utf-8'))
        elif "/StartRecord" in self.path:
            # /StartRecord/TagMac/Range/Rate
            parameters = self.path.split('/')
            tag_mac = parameters[2]
            r_range = parameters[3]
            r_rate = parameters[4]
            ret = pigutils.start_recording(tag_mac, r_range, r_rate)
            self.wfile.write(json.dumps(ret).encode('utf-8'))
        elif "/StopRecord" in self.path:
            # /StopRecord/TagMac
            parameters = self.path.split('/')
            tag_mac = parameters[2]
            #ret = pigutils.stop_recording(tag_mac)
            ret = {'Success': True}
            self.wfile.write(json.dumps(ret).encode('utf-8'))
        elif "/ReadRssiLog" in self.path:
            # /ReadRssiLog/FromTime
            parameters = self.path.split('/')
            from_time = parameters[2]
            print("ReadRssi from time", from_time)
            self.send_header('Content-type', 'application/zip')
            rssi_arch_zip = send_rssi_log(from_time) + '.zip'
            self.send_header('Content-Disposition', \
                    'attachment; filename=%s' % rssi_arch_zip)
            self.end_headers()

            # TODO
            # the following is a (shorter) alternative. does this work?
            # with open(rssi_arch_zip, 'rb') as f:
            #     shutil.copyfileobj(f, self.wfile)

            f = open(rssi_arch_zip, 'rb')
            while True:
                file_data = f.read(32768)  # use an appropriate chunk size
                if file_data is None or len(file_data) == 0:
                    break
                self.wfile.write(file_data)
            f.close()
        else:
            # Unknown Command
            self.wfile.write("This command is not yet defined, \
                    update the code if required".encode())

    def do_HEAD(self):
        self._set_headers()

    def do_POST(self):
        # Don't do anything with posted data
        # When it is time to introduce "'LightLED' TagMac" it
        # can fit here in a POST, (or a separate command in the GET
        # but one argument to place it here could be to visualize
        # it is changing state in a tag rather than just reading back data
        # 
        # Sangxia 2017-10-17: start and stop also changes states of tags?
        self._set_headers()
        self.wfile.write("POST!".encode())


def run(server_class=HTTPServer, handler_class=Server, port=8081):
    host_name = ""
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print('Starting httpd...')
    print(time.asctime(), "Server Starts - %s:%s" % (host_name, port))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Command Receiver Server')
    parser.add_argument('--port', dest='port',
                        type=str, default='8081',
                        help='port number to listen to \
                            default is 8081 should be used')
    args = parser.parse_args()
    run(port=int(args.port))

