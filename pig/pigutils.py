import signal
from binascii import hexlify
import pexpect
import time
import random
import string
import logging
import logging.handlers
import socket


# RETURN_NO_CONNECTION = 'No connection\n'

# TODO refactor tag communication code

# TODO shouldn't these be configurable?
MAX_RECONNECT_ATTEMPTS = 2

# NOTE commenting this out since it is too easy to cause issue here
# if parameters change. Always specify these value from the server
# RANGE = 10
# RATE = 50


def get_ctrl(mac, level=logging.DEBUG, log_fname=''):
    """
    Set up the relevant data structure for communicating with a tag.
    Returns the MAC address of the tag, a logger, and an entry
    for a pexpect object if there is an ongoing connection.
    """
    mac = normalize_mac_address(mac)
    logger = logging.getLogger('PigPlus {0}'.format(mac))
    if not logger.handlers:
        logger.setLevel(level)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(message)s')
        if log_fname:
            fh = logging.handlers.RotatingFileHandler(log_fname, 'a', 3000, 100)
            fh.setLevel(level)
            fh.setFormatter(formatter)
            logger.addHandler(fh)
        ch = logging.StreamHandler()
        ch.setLevel(level)
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    return {'mac': mac, 'logger': logger, 'g': None}


def connect(ctrl_data, delay=2, timeout=15):
    """
    Connect to the specified tag with random delay.
    Returns whether the connection is successful.
    If successful, the control informations will be saved in
    ctrl_data, otherwise the values of ctrl_data is undefined.
    """
    mac = ctrl_data['mac']
    logger = ctrl_data['logger']
    time.sleep(delay * random.random())
    g = pexpect.spawn('gatttool -b ' + mac + ' -t random -I')
    g.timeout = timeout
    g.expect('\[LE\]>')
    time.sleep(delay * random.random())
    g.sendline('connect')
    logger.debug("Connecting")
    try:
        g.expect(['\[CON\].*>', 'Connection successful'])
        logger.debug('Connected')
        ctrl_data['g'] = g
        return True
    except pexpect.TIMEOUT:
        logger.debug('Failed to connect to the device')
        g.terminate()
        return False


def initialize(ctrl_data):
    g = ctrl_data['g']
    g.timeout = 5
    # Enable notifications from the uart service
    g.sendline('char-write-req 0x000C 0100')
    g.expect('written successfully')


def process_start(ctrl, **kwargs):
    """
    Returns:
        SUCCESS: status, always True if no exception raised
        Timestamp: the timestamp on the observer after confirmation
            that record started. Use this together with flash pos
            to calculate timestamp after all data has been collected.
            Technically one can obtain the same timestamp from log file,
            but this makes things easier.
    """
    d_range = int(kwargs['sample_range'])
    d_rate = int(kwargs['sample_rate'])
    send_dev_command(ctrl, 'Range={0}'.format(d_range))
    time.sleep(1)
    send_dev_command(ctrl, 'Rate={0}'.format(d_rate))
    time.sleep(1)
    send_dev_command(ctrl, 'Record')
    ctrl['logger'].debug('Record started')
    return {'SUCCESS': True, 'Timestamp': time.time()}


def process_stop(ctrl, **kwargs):
    """
    Returns:
        SUCCESS: status, always True if no exception raised
    """
    send_dev_command(ctrl, 'Stop')
    ctrl['logger'].debug('Record stopped')
    return {'SUCCESS': True, 'Timestamp': time.time()}


# def process_read_state(ctrl, **kwargs):
#     g = ctrl['g']
#     send_dev_command(ctrl, "State?")
#     g.expect('value: ([^\r\n]+)')
#     str_val = str(g.match.group(1).decode('ascii')).strip().split(' ')
#     str_val = [u[1] for u in str_val]
#     if len(str_val) < 8:
#         str_val = ['0'] * (8 - len(str_val)) + str_val
#     # release after poll
#     # TODO this is not needed for commands like start / stop?
#     # TODO should it be placed in the communicate_with_tag function or here?
#     g.sendline("disconnect")
#     return ''.join(str_val)


def process_read_battery(ctrl, **kwargs):
    """
    Returns:
        SUCCESS: status, always True if no exception raised
        Timestamp: timestamp after finishing
        mV: mvolt of battery measurement
        Percent: percentage of remaining battery
    """
    g = ctrl['g']
    send_dev_command(ctrl, "Batt?")
    g.expect('value: ([^\r\n]+)')
    str_val = str(g.match.group(1).decode('ascii')).strip().split(' ')
    str_val = [u[1] for u in str_val]
    if len(str_val) < 8:
        str_val = ['0'] * (8 - len(str_val)) + str_val
    percent = int(''.join(str_val[:3]))
    mvolt = int(''.join(str_val[4:]))
    return {'SUCCESS': True, 'Timestamp': time.time(), \
            'mV': mvolt, 'Percent': percent}


def process_read_pos(ctrl, **kwargs):
    """
    Returns:
        SUCCESS: status, always True if no exception raised
        Timestamp: timestamp after finishing
        Pos: current position in flash
    """
    g = ctrl['g']
    send_dev_command(ctrl, "Pos?")
    g.expect('value: ([^\r\n]+)')
    str_val = str(g.match.group(1).decode('ascii')).strip().split(' ')
    str_val = [u[1] for u in str_val]
    # TODO this should not be necessary if pos is just an int, right?
    # if len(str_val) < 8:
    #     str_val = ['0'] * (8 - len(str_val)) + str_val
    # release after poll
    g.sendline("disconnect")
    return {'SUCCESS': True, 'Timestamp': time.time(), \
            'Pos': int(str_val)}

def process_collect_data(ctrl, **kwargs):
    start_pos = int(kwargs['start_pos'])
    num_samples = int(kwargs['num_samples'])
    m_range = int(kwargs['sample_range'])
    if num_samples % 5:
        # NOTE just to make things easier
        raise ValueError('Number of samples collected must be multiples of 5')
    g = ctrl['g']
    cmd_str = 'Play={0:d},{1:d}'.format(start_pos, num_samples)
    send_dev_command(ctrl, cmd_str)
    ret_val = ''
    t = start_pos
    # Max 20 bytes e.g. 5 samples per line of a response
    loop_range = num_samples // 5
    for i in range(0, loop_range):
        g.expect('value: ([^\r\n]+)')
        str_val = str(g.match.group(1).decode('ascii')).strip().split(' ')
        if len(str_val) != 40:
            # some sanity check on len(str_val)
            # otherwise issues will be catched further up as an exception. 
            # is probably still fine but may not be ideal
            ctrl['logger'].error('Unexpected length of str_val in {0}'.format(str_val))
            return {'SUCCESS': False}
        for pos in range(0, len(str_val), 8):
            # Unpack little endian
            b_arr = bytearray.fromhex(''.join((str_val[pos:pos + 8])))
            int_val = int.from_bytes(b_arr, byteorder='little')
            x = s10(int_val, 0, m_range)
            y = s10(int_val, 10, m_range)
            z = s10(int_val, 20, m_range)
            # Show time and accelerometer values in CSV
            add_val = '{0},{1:.3f},{2:.3f},{3:.3f}\n'.format(t,x,y,z)
            ret_val += add_val
            # TODO am I understanding this correctly? /Sangxia
            t += 1
    # release after poll
    g.sendline("disconnect")
    # TODO Next should wrap around?
    return {'SUCCESS': True, 'Timestamp': time.time(), \
            'Data': ret_val, 'Next': start_pos+num_samples}


def communicate_with_tag(tag_mac, message_type, **kwargs):
    tag_mac = normalize_mac_address(tag_mac)
    debug_fname = 'observer/'+ socket.gethostname() + '.debug'
    # if not isfile(debug_fname):
    #     with open(debug_fname, 'w') as f:
    #         _ = f.write('')

    ctrl = get_ctrl(tag_mac, log_fname=debug_fname)
    logger = ctrl['logger']
    retry_attempts = 0
    ret_val = {}
    while retry_attempts < MAX_RECONNECT_ATTEMPTS:
        retry_attempts += 1
        try:
            if connect(ctrl, delay=3):
                g = ctrl['g']
                initialize(ctrl)
                if message_type == 'start':
                    ret_val = process_start(ctrl, **kwargs)
                elif message_type == 'stop':
                    ret_val = process_stop(ctrl, **kwargs)
                # elif message_type == 'state':
                #     ret_val = process_read_state(ctrl, **kwargs)
                elif message_type == 'pos':
                    ret_val = process_read_pos(ctrl, **kwargs)
                elif message_type == 'batt':
                    ret_val = process_read_battery(ctrl, **kwargs)
                elif message_type == 'data':
                    ret_val = process_collect_data(ctrl, **kwargs)
            if 'SUCCESS' in ret_val and ret_val['SUCCESS']:
                break
        except pexpect.TIMEOUT:
            logger.debug('Timeout')
        except OSError as err:
            logger.error("OS error: {0}".format(err))
        except ValueError:
            logger.error("Could not convert data to an integer.")
        except Exception as e:
            logger.exception("Unexpected error {0}".format(e))
        if ctrl['g'] is not None:
            ctrl['g'].close()
    if ctrl['g'] is not None:
        ctrl['g'].close()
    if 'SUCCESS' not in ret_val:
        ret_val['SUCCESS'] = False
    return ret_val


def start_recording(tag_mac, s_range, s_rate):
    return communicate_with_tag(tag_mac, 'start', \
            sample_range=s_range, sample_rate=s_rate)


def stop_recording(tag_mac):
    return communicate_with_tag(tag_mac, 'stop')


def read_position(tag_mac):
    return communicate_with_tag(tag_mac, 'pos')


# def read_state(tag_mac):
#     return communicate_with_tag(tag_mac, 'state')


def read_battery(tag_mac):
    return communicate_with_tag(tag_mac, 'batt')


def collect_data(tag_mac, start_pos, num_samples, sample_range):
    return communicate_with_tag(tag_mac, 'data', \
            start_pos=start_pos, num_samples=num_samples, sample_range=sample_range)


# def collect_data(tag_mac, start_pos, samples):
#     time_inc = 1.0 / int(RATE)  # TODO read from start ....
#     tag_mac = normalize_mac_address(tag_mac)
#     debug_fname = 'observer/' + socket.gethostname() + '.debug'
#     ctrl = get_ctrl(tag_mac, log_fname=debug_fname)
#     ret_val = ""
#     str_val = RETURN_NO_CONNECTION
#     retry_attempts = 0
#     samples_per_poll = int(samples)
#     while retry_attempts < MAX_RECONNECT_ATTEMPTS:
#         retry_attempts += 1
#         try:
#             if connect(ctrl, delay=2):
#                 g = ctrl['g']
#                 #  Use new system for start_pos
#                 initialize(ctrl)
#                 cmd_str = "Play={0:d}".format(int(start_pos))
#                 cmd_str = cmd_str + ",{0:d}".format(samples_per_poll)
#                 send_dev_command(ctrl, cmd_str)
#                 #t = time.time()
#                 t = start_pos  #  use position value as t
#                 m_range = RANGE
#                 # Max 20 bytes e.g. 5 samples per line of a response
#                 loop_range = int((samples_per_poll + 4) / 5)
#                 for i in range(0, loop_range):
#                     g.expect('value: ([^\r\n]+)')
#                     str_val = str(g.match.group(1).decode('ascii')).strip().split(' ')
#                     for pos in range(0, len(str_val), 8):
#                         # Unpack little endian
#                         b_arr = bytearray.fromhex(''.join((str_val[pos:pos + 8])))
#                         int_val = int.from_bytes(b_arr, byteorder='little')
#                         x = s10(int_val, 0, m_range)
#                         y = s10(int_val, 10, m_range)
#                         z = s10(int_val, 20, m_range)
#                         # Show time and accelerometer values in CSV
#                         add_val = '{:.2f}'.format(t)
#                         add_val += ',{:.2f}'.format(x)
#                         add_val += ',{:.2f}'.format(y)
#                         add_val += ',{:.2f}'.format(z) + "\n"
#                         t += time_inc
#                         ret_val = ret_val + add_val
#                 # release after poll
#                 g.sendline("disconnect")
#             print("Poll ready, disconnect")
#         except OSError as err:
#             print("OS error: {0}".format(err))
#         except ValueError:
#             print("Could not convert data to an integer.")
#         except:
#             print("Unexpected error:", sys.exc_info()[0])
#         break
#     # Add next start pos in reply separated by ;
#     next_start_pos_int = int(start_pos) + samples_per_poll
#     next_start_pos = str(next_start_pos_int)
#     ret_val = ret_val + "&" + next_start_pos
#     # If it is the first string use t as t = 0
#     if ret_val[0] == '0':
#         ret_val = ret_val [1:]
#         t_str = str(time.time())
#         ret_val = t_str + ret_val
#     return ret_val


# Encode 10 bit signed value at the given position and scale according to range
def s10(value, pos, m_range):
    value = (value & (0x3FF << pos)) >> pos
    if value & 0x200:
        value -= 0x400
    return float(value) / float(0x200) * float(m_range)


# Send uart service command to the device
def send_dev_command(ctrl_data, command):
    g = ctrl_data['g']
    msg = hexlify(bytes(command, 'ascii'))
    g.sendline('char-write-req 0x000e ' + msg.decode('ascii'))
    g.expect('written successfully')
    # NOTE commenting this out since this interferes with value expected
    # elsewhere
    # g.expect('value: ([^\r\n]+)')
    # resp = str(g.match.group(1).decode('ascii')).strip().split(' ')
    # if "ERR:" in resp:
    #     raise RuntimeError('Failed to send command {0}'.format(command))


# def console_mess(mess):
#     # TODO this function should be removed and use logger instead
#     # it is only used on line 323 in this file and Peter's script
#     sys.stderr.write("* " + mess + " @ " +  "\n")

def normalize_mac_address(s):
    if len(s) == 12:
        return ':'.join(s[i:i + 2].upper() for i in range(0, 12, 2))
    else:
        return s.upper()

def lower_mac_address(s):
    return (''.join(c for c in s if c in string.ascii_letters + string.digits)).lower()


def gen_sig_term_func(mac):
    def sig_term_func(sig, frame):
        print(mac, " exit\n")
        # TODO perhaps it is good to send a stop command to the tag here
        # need to think more about what is going on in the new HW flow, because
        # this, as well as register_sigterm() may not be needed
        exit(0)
    return sig_term_func

def register_sigterm(mac): 
    signal.signal(signal.SIGTERM, gen_sig_term_func(mac))

