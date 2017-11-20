#!/bin/bash

date +"%c"
timedatectl

sudo service ntp stop
sudo ntpdate -s se.pool.ntp.org 
sudo service ntp start

SYNCTIME=$(date) 
echo $SYNCTIME
#timedatectl
#sudo hwclock

echo "Setting time on Pig 3"
ssh pi@192.168.1.102 timedatectl
ssh -t pi@192.168.1.102 sudo date --set="$SYNCTIME" 
ssh pi@192.168.1.102 timedatectl
