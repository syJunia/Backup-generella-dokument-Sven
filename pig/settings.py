import configparser

MAX_SAMPLE_COUNT = 4194304

config = None

def init(cfg_filename):
    global config
    config = configparser.ConfigParser()
    config.read(cfg_filename)

