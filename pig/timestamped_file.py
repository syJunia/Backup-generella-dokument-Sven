import io
import time
import glob

class TimestampedFile(io.TextIOBase):

    # For appending only
    # TODO test with logging

    def __init__(self, base_filename, interval=900):
        """
        Arguments
          base_filename - filename are of the format base_filename.start_timestamp
          interval - max interval of each file
        """
        self.interval = interval
        self.base_filename = base_filename
        file_timestamps = sorted([int(f[len(base_filename)+1:]) \
                for f in glob.glob(base_filename + '*')])
        curr_time = int(time.time())
        self.f = None
        if len(file_timestamps):
            ddl = file_timestamps[-1] + interval
            if ddl > curr_time:
                self.f = open('{0}.{1}'.format(base_filename, ddl-interval), 'a')
                self.ddl = ddl
        if self.f is None:
            self.f = open('{0}.{1}'.format(base_filename, curr_time), 'a')
            self.ddl = curr_time + interval

    def write(self, s):
        curr_time = int(time.time())
        print(self.ddl, curr_time, s)
        if self.ddl <= curr_time:
            self.f.close()
            self.f = open('{0}.{1}'.format(self.base_filename, curr_time), 'a')
            self.ddl = curr_time + self.interval
        return self.f.write(s)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # TODO assume that we are not handling any exception for now
        self.f.close()
        return None

