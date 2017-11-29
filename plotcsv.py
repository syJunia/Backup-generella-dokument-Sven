#!/usr/bin/python3.6
import matplotlib.pyplot as plt
import plotly.plotly as py
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

    # These are the "Tableau 20" colors as RGB.
    tableau20 = [(31, 119, 180), (174, 199, 232), (255, 127, 14), (255, 187, 120),
                 (44, 160, 44), (152, 223, 138), (214, 39, 40), (255, 152, 150),
                 (148, 103, 189), (197, 176, 213), (140, 86, 75), (196, 156, 148),
                 (227, 119, 194), (247, 182, 210), (127, 127, 127), (199, 199, 199),
                 (188, 189, 34), (219, 219, 141), (23, 190, 207), (158, 218, 229)]

    # Scale the RGB values to the [0, 1] range, which is the format matplotlib accepts.
    for i in range(len(tableau20)):
        r, g, b = tableau20[i]
        tableau20[i] = (r / 255., g / 255., b / 255.)

    # You typically want your plot to be ~1.33x wider than tall.     
    # Common sizes: (10, 7.5) and (12, 9)
    plt.figure(figsize=(12, 9))

    # Remove the plot frame lines. They are unnecessary chartjunk.
    ax = plt.subplot(111)
    ax.spines["top"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)

    # Ensure that the axis ticks only show up on the bottom and left of the plot.
    # Ticks on the right and top of the plot are generally unnecessary chartjunk.
    ax.get_xaxis().tick_bottom()
    ax.get_yaxis().tick_left()

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
    plt.plot(datenums, df.c,c=tableau20[0], ls='dotted')
    mpl_fig_obj= plt.figure()
    py.plot_mpl(mpl_fig_obj)
    #plt.show()
