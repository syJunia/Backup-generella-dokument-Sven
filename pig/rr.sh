#!/bin/bash
while IFS='' read -r line || [[ -n "$line" ]]; do
    echo "Text read from file: $line"
    echo " contains charaters  ${#line}"
    echo " ts1  ${line:27:10}"
    ts1=${line:27:10}
    echo "$ts1"
    ts2=echo date -d @$ts1 
    echo "$ts2"
done < "$1"
