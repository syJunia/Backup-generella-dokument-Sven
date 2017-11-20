import argparse
import numpy as np
import time
import settings
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

MAX_SAMPLE_COUNT = 4194304


def process_pos_seq(pos):
    ret = []
    base = 0
    prev = -1
    for p in pos:
        tp = int(p)
        if tp <= prev:
            base += MAX_SAMPLE_COUNT
        ret.append(tp+base)
        prev = tp
    return ret

def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='server/server.cfg',
                        help='File with config parameters')
    args = parser.parse_args()
    settings.init(args.config)

    data_fmt = settings.config['Data']['DataFileFormat']

    print('Reading logs')
    df_startstop = pd.read_csv(settings.config['Data']['StartStopLog'])
    df_ts = pd.read_csv(settings.config['TagTimestamp']['HistoryFilename'])
    df_ts_latest = pd.read_csv(settings.config['TagTimestamp']['LatestFilename'])
    df_data_index = pd.read_csv(settings.config['Data']['EventLog'])
    tags = set(df_startstop['tag_mac'])
    time_fmt = '%Y-%m-%d %H:%M:%S (Stockholm)'
    for tag in tags:
        print('Processing {0}'.format(tag))
        df_tag = df_startstop.loc[df_startstop['tag_mac']==tag]
        tag_state = 0
        start_ts = 0
        current_sess = -1
        for idx, row in df_tag.iterrows():
            if row['is_start'] == 1:
                if tag_state != 0:
                    print('WARNING: start command on a running tag at {0:.2f}, prev session {1}'.format(row['ts'], current_sess))
                current_sess = row['sess_id']
                tag_state = 1
                start_ts = row['ts']
                # analyze pos
                df_tag_ts = df_ts.loc[(df_ts['tag_mac']==tag) & (df_ts['sess_id']==current_sess)]
                print('Found {0} successful Pos for session {1}'.format(\
                        df_tag_ts.shape[0], current_sess\
                        ))
                real_pos = process_pos_seq(df_tag_ts['pos'])

                plt.figure(figsize=(12,12))
                X = (df_tag_ts['host_ts']+df_tag_ts['host_ts_send']-row['ts']-row['ts_send'])/2
                Y = np.array(real_pos)/50.
                plt.scatter(X, Y-X, s=1)
                plt.xlabel('Seconds since start')
                plt.ylabel('Drift (s)')
                plt.title('Drift for tag {0} session {1}'.format(tag, current_sess))
                plt.savefig('drift_{0}.png'.format(current_sess))
                plt.close()

                df_tag_data = df_data_index.loc[(df_data_index['tag_mac']==tag) & (df_data_index['sess_id']==current_sess)]
                print('Found {0} successful data segments for session {1}'.format(\
                        df_tag_data.shape[0], current_sess\
                        ))
                real_start_pos = process_pos_seq(df_tag_data['start_pos'])
                counts = list(df_tag_data['count'])
                print('Collected {0}, recorded {1}, diff {2}'.format(real_start_pos[-1]+counts[-1], real_pos[-1], \
                        real_start_pos[-1]+counts[-1]-real_pos[-1]))
                print('Sequence continuity check:')

                missed_sample_rate = []
                sample_count = []
                for seqid,st,c,nxt in zip(list(df_tag_data['seq_id'].iloc[:-1]), real_start_pos[:-1], counts[:-1], real_start_pos[1:]):
                    if st+c != nxt:
                        print('Discontinuity at seq {0}, start {1} count {2} next start {3}'.format(\
                                current_sess, st, c, nxt))
                    sample_count.append(c)
                    try:
                        df_tmp_data = pd.read_csv(settings.config['Data']['DataFileFormat'].format(current_sess, seqid))
                        missed_sample_rate.append(1.-df_tmp_data.shape[0]/c)
                    except:
                        print('Error reading session {0} seq {1}'.format(current_sess, seqid))
                        missed_sample_rate.append(None)
                plt.figure(figsize=(12,12))
                plt.scatter(real_start_pos[:-1], missed_sample_rate, s=1)
                plt.xlabel('Start pos')
                plt.ylabel('Ratio of missed samples')
                plt.title('Ratio of missed samples for tag {0} session {1}'.format(tag, current_sess))
                plt.savefig('missed_sample_{0}.png'.format(current_sess))
                plt.close()

                print('Done.')
            elif row['is_start'] == 0:
                if tag_state != 1:
                    print('WARNING: stop command on a non-running tag at {0:.2f}'.format(row['ts']))
                else:
                    print('Session {0} complete: from {1} to {2}'.format(\
                            current_sess, \
                            time.strftime(time_fmt, time.localtime(start_ts)), \
                            time.strftime(time_fmt, time.localtime(row['ts'])), \
                            ))
                tag_state = 0
        if tag_state != 0:
            print('WARNING: log ended without tag stop, started at {0}, session {1}'.format(\
                    time.strftime(time_fmt, time.localtime(start_ts)), \
                    current_sess, \
                    ))
        print()
    print('='*30)


if __name__ == "__main__":
    main()

