from __future__ import print_function
from os import path
import argparse
import glob
import datetime
from dateutil import tz

def transmit(fnames):
    # TODO implement!
    print('\n'.join(fnames))

def convert_log_ts_to_utc(s):
    """
    inputs are like 2017-09-28_07-31-25
    """
    year, month, day, hour, minute, second = [
            int(s[st:ed]) for st,ed in \
                    [(0,4),(5,7),(8,10),(11,13),(14,16),(17,19)]]
    dt = datetime.datetime(year, month, day, hour, minute, second, \
            tzinfo = tz.gettz('UTC'))
    return int(dt.timestamp())

parser = argparse.ArgumentParser(\
        description='Collects RSSI logs after a certain time period')
parser.add_argument('--log_base_filename', dest='basefile', \
        type=str, required=True, \
        help='The base filename of the logs')
parser.add_argument('--timestamp', dest='timestamp', \
        type=int, required=True, \
        help='UTC seconds, only transmit logs started no later than \
        the given timestamp')
parser.add_argument('--zip', dest='use_zip', \
        action='store_true', \
        help='Compress the files before transmission')
args = parser.parse_args()

fnames = [ \
        (f, convert_log_ts_to_utc(f[len(args.basefile)+1:]))
        for f in glob.glob(args.basefile + '.*')]
fnames = [u for u in fnames if u[1] >= args.timestamp]
if len(fnames)==0:
    # TODO make sure the server handles this
    print('0 file to be transmitted')
    exit(0)
fnames = sorted(fnames, key=lambda u: u[1])
# TODO make sure the server handles this
print(('Max transmitted ts:', fnames[-1][1]))
if not args.use_zip:
    transmit([u[0] for u in fnames])
else:
    import tempfile
    import gzip
    import shutil
    with tempfile.TemporaryDirectory() as tmpdirname:
        print(('Temp dir name', tmpdirname))
        transmit_list = []
        for fname_in, _ in fnames:
            fname_out = path.join(tmpdirname, fname_in+'.gz')
            with open(fname_in, 'rb') as f_in, \
                    gzip.open(fname_out, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
            transmit_list.append(fname_out)
        transmit(transmit_list)

