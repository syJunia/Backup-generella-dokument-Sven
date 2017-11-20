#!/bin/bash
cd /home/pigplus/pig/Pig-Hardware-Test
tag_file='server/available_tags.cfg'
# read in all tag names
echo "Reading tags ..."
tag_cnt=0 
while read -r line
do
    if [[ $line == *"tag"* ]]; then
        continue
    fi    
    tag_names+=("$line")
    echo "Tag read from file - ${tag_names[tag_cnt]}"
    ((tag_cnt += 1))
done < "$tag_file"
echo "Looking in rssi ..."

echo "==================================" > status.txt
echo "Time is now:  $(date +'%d-%b-%Y %T')" >> status.txt
send_mail=false
echo "-----------------------------------------------------------" >> status.txt
for i in "${tag_names[@]}"
do
    b_str="$(tac 'logs/rssi.recent' | grep $i | tail -n 1)"
    b_tid="$(echo "$b_str" | cut -d',' -f1)"
    b_status="$(echo "$b_str" | cut -d',' -f4)"
    b_batt="$(echo "$b_str" | cut -d',' -f5)"
    t_str="$(cat 'logs/tagts.latest' | grep $i )"
    d_p1="$(echo "$t_str" | cut -d',' -f2)"
    d_p2="$(echo "$t_str" | cut -d',' -f4)"
    diff="$(((d_p1-d_p2)/50))"
    echo "diff : $diff"
    echo "Value : ("$d_p1" - "$d_p2") > 0"
    if [[ $diff < 0 ]]; then
        echo "wrap"
        diff="$(((d_p1+4194304-d_p2)/50))" 
    fi
    d_date="$(echo "$t_str" | cut -d',' -f5)"
    last_collect_t=$(date +'%d-%b-%Y %T' -d @$d_date)
    echo "Tag $i" >> status.txt
    if [[ $b_status != "1" ]]; then
        echo "WARNING: Not recording!" >> status.txt
        # Send Mail !
        echo "We should send mail - Not recording ..."
        send_mail=true
    fi    
    echo "Battery = $b_batt" >> status.txt
    echo "Last collected data at $last_collect_t" >> status.txt
    echo "Difference recorded vs collected = $diff" >> status.txt
    echo "-----------------------------------------------------------" >> status.txt
done
echo "-----------------------------------------------------------" >> status.txt
python3 server/summary.py --config server/server.cfg >> status.txt
df -h / >> status.txt

if [ "$send_mail" = true ]; then
    ./post_warning_summary.sh
fi
echo "status.txt updated"
