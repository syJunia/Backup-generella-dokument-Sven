#!/usr/bin/python3.6
import matplotlib.pyplot as plt
import matplotlib.dates as md
import numpy as np
import datetime as dt
import time
import pandas as pd
import math
import sys

if len(sys.argv)<=3:
    print('Must specify file and start epoch', file=sys.stderr)
else:
    filename= sys.argv[1]
    headers=['pos', 'x', 'y', 'z']
    df=pd.read_csv(filename, names=headers)
    df['c'] = df.apply(lambda row: math.sqrt(row.x**2 + row.y**2 + row.z**2), axis=1)

    duration, _ =df.shape
    n=duration
    epoch_start_time=int(sys.argv[2])
    freq=int(sys.argv[3])
    t_inc=duration/freq
    print("duration minutes=", t_inc/60)
    ts=time.mktime(time.localtime(epoch_start_time))
    timestamps=np.linspace(ts,ts+t_inc,n)
    dates=[dt.datetime.fromtimestamp(ts) for ts in timestamps]
    datenums=md.date2num(dates)
    plt.ylabel('Accelerometer vector')
    plt.xlabel('Time')
    plt.title('Plot of '+ filename)
    plt.subplots_adjust(bottom=0.2)
    plt.xticks( rotation=25 )
    ax=plt.gca()
    xfmt = md.DateFormatter('%d/%m %H:%M')
    ax.xaxis.set_major_formatter(xfmt)
    plt.plot(datenums,df.c,c='g',ls='dotted')
    plt.show()
