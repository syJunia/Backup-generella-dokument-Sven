#!/bin/bash

get_mimetype(){
    # warning: assumes that the passed file exists
    file --mime-type "$1" | sed 's/.*: //' 
}

from="m"
to="g"
subject="Some fancy title"
boundary="ZZ_/afg6432dfgkl.94531q"
body="This is the body of our email"
declare -a attachments
attachments=( "foo.pdf" "bar.jpg" "archive.zip" )

# Build headers
{
    printf '%s\n' "From: $from
    To: $to
    Subject: $subject
    Mime-Version: 1.0
    Content-Type: multipart/mixed; boundary=\"$boundary\"

    --${boundary}
    Content-Type: text/plain; charset=\"US-ASCII\"
    Content-Transfer-Encoding: 7bit
    Content-Disposition: inline

    $body
    "
     
    # now loop over the attachments, guess the type
    # and produce the corresponding part, encoded base64
    for file in "${attachments[@]}"; do

          [ ! -f "$file" ] && echo "Warning: attachment $file not found, skipping" >&2 && continue

            mimetype=$(get_mimetype "$file") 
             
              printf '%s\n' "--${boundary}
              Content-Type: $mimetype
              Content-Transfer-Encoding: base64
              Content-Disposition: attachment; filename=\"$file\"
              "
               
                base64 "$file"
                  echo
              done
               
              # print last boundary with closing --
              printf '%s\n' "--${boundary}--"
               
          } 



cd /home/pigplus/pig/Pig-Hardware-Test
cat mailhead.txt > mail.txt

line=$(tac status.txt | grep -n . | grep Time)
l2=$"$(echo "$line" | cut -d':' -f1)"
l3=$(echo $l2 | cut -d ' ' -f 1)
l4=$(($l3+1))
tail -n $l4 status.txt >> mail.txt

curl -n  --ssl-reqd --mail-from 'pig_plus@yahoo.com' \
    --mail-rcpt 'sven@tryding.se'\
    --upload-file mail.txt \
    --url 'smtps://smtp.mail.yahoo.com:465' \
    --user 'pig_plus@yahoo.com:PigPlus00!'

