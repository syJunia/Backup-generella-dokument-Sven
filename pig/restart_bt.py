# Simple script to restart bluetooth if
# 
# NOTE this is a separate script instead of included in
# log_rssi because we need to make sure that this does not
# interrupt other data collection activities.

import time
import pexpect

g = pexpect.spawn('bluetoothctl')
time.sleep(.5)
g.sendline('power off')
time.sleep(1.)
g.sendline('power on')
time.sleep(1.)
g.sendline('exit')

