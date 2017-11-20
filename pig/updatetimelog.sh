#!/bin/bash

echo "nuc time" >> timesynclog.txt
date -u "+%s%N"  >> timesynclog.txt
echo "pig1 time" >> timesynclog.txt
ssh -i .ssh/id_rsa pi@192.168.1.106 date -u "+%s%N" >> timesynclog.txt
echo "nuc time" >> timesynclog.txt
date -u "+%s%N"  >> timesynclog.txt
echo "pig2 time" >> timesynclog.txt
ssh -i .ssh/id_rsa pi@192.168.1.103 date -u "+%s%N" >> timesynclog.txt
echo "nuc time" >> timesynclog.txt
date -u "+%s%N"  >> timesynclog.txt
echo "pig3 time" >> timesynclog.txt
ssh -i .ssh/id_rsa pi@192.168.1.112 date -u "+%s%N" >> timesynclog.txt
echo "nuc time" >> timesynclog.txt
date -u "+%s%N"  >> timesynclog.txt
echo "pig4 time" >> timesynclog.txt
ssh -i .ssh/id_rsa pi@192.168.1.100 date -u "+%s%N" >> timesynclog.txt
echo "nuc time" >> timesynclog.txt
date -u "+%s%N"  >> timesynclog.txt
echo "pig5 time" >> timesynclog.txt
ssh -i .ssh/id_rsa pi@192.168.1.111 date -u "+%s%N" >> timesynclog.txt
