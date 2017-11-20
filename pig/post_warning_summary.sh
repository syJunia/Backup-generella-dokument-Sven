#!/bin/bash

rtmp_url="smtps://smtp.mail.yahoo.com:465"
rtmp_from='pig_plus@yahoo.com' 
rtmp_to="sven@tryding.se"
rtmp_credentials='pig_plus@yahoo.com:PigPlus00!'

file_upload="data.txt"
st=$(<status.txt)

mail_from="PigPlus <$rtmp_from>"
mail_to="Team PigPlus"
mail_subject="Warningmail PigPlus!"
mail_reply_to="PigPlus <$rtmp_from>"
mail_cc=""

# add an image to data.txt : 
# $1 : type (ex : image/png)
# $2 : image content id filename (match the cid:filename.png in html document)
# $3 : image content base64 encoded
# $4 : filename for the attached file if content id filename empty
function add_file {
    echo "--MULTIPART-MIXED-BOUNDARY
Content-Type: $1
 name="$2"
Content-Transfer-Encoding: base64" >> "$file_upload"

    echo "Content-Disposition: attachment;
 filename=$2" >> "$file_upload"
    printf "\n" >> "$file_upload"

    echo "$3 
 
" >> "$file_upload"
}

# add an image to data.txt : 
# $1 : type (ex : image/png)
# $2 : image content id filename (match the cid:filename.png in html document)
# $3 : image content base64 encoded
function add_file_inline {
    echo "--MULTIPART-MIXED-BOUNDARY

Content-Type: $1
Content-Transfer-Encoding: base64" >> "$file_upload"

    echo "Content-Disposition:inline
Content-Id: <$2>" >> "$file_upload"
    echo "$3
    
">> "$file_upload"
}

echo "From: $mail_from
To: $mail_to
Subject: $mail_subject
Reply-To: $mail_reply_to
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary=\"MULTIPART-MIXED-BOUNDARY\"

--MULTIPART-MIXED-BOUNDARY
Content-Type: text/plain; charset=utf-8; format=flowed
Content-Transfer-Encoding: 7bit

$st
" > "$file_upload"

END=5
for ((i=0;i<=END;i++)); do
    echo $i
    driftfile="drift_$i.png"
    img_file="$(cat $driftfile | base64)"
    add_file "image/png;" "$driftfile" "$img_file"
    msfile="missed_sample_$i.png"
    img_file="$(cat $msfile | base64)"
    add_file "image/png;" "$msfile" "$img_file"
done

# add the status file
status_file="$(cat status.txt | base64)"
add_file "text/plain;" '"status.txt"' "$status_file"

# end of uploaded file
echo "--MULTIPART-MIXED-BOUNDARY--" >> "$file_upload"

# send email
echo "sending ...."
curl -s "$rtmp_url" \
     --mail-from "$rtmp_from" \
     --mail-rcpt "$rtmp_to" \
     --ssl -u "$rtmp_credentials" \
     -T "$file_upload" -k --anyauth
res=$?
if test "$res" != "0"; then
   echo "sending failed with: $res"
else
    echo "OK"
fi

rtmp_to="sven.tryding@sony.com"
echo "sending next ...."
curl -s "$rtmp_url" \
     --mail-from "$rtmp_from" \
     --mail-rcpt "$rtmp_to" \
     --ssl -u "$rtmp_credentials" \
     -T "$file_upload" -k --anyauth
res=$?
if test "$res" != "0"; then
   echo "sending failed with: $res"
else
    echo "OK"
fi

rtmp_to="sangxia.huang@sony.com"
echo "sending next ...."
curl -s "$rtmp_url" \
     --mail-from "$rtmp_from" \
     --mail-rcpt "$rtmp_to" \
     --ssl -u "$rtmp_credentials" \
     -T "$file_upload" -k --anyauth
res=$?
if test "$res" != "0"; then
   echo "sending failed with: $res"
else
    echo "OK"
fi

rtmp_to="fredrik.j.fornander@sony.com"
echo "sending next ...."
curl -s "$rtmp_url" \
     --mail-from "$rtmp_from" \
     --mail-rcpt "$rtmp_to" \
     --ssl -u "$rtmp_credentials" \
     -T "$file_upload" -k --anyauth
res=$?
if test "$res" != "0"; then
   echo "sending failed with: $res"
else
    echo "OK"
fi

rtmp_to="sara.berg@sony.com"
echo "sending next ...."
curl -s "$rtmp_url" \
     --mail-from "$rtmp_from" \
     --mail-rcpt "$rtmp_to" \
     --ssl -u "$rtmp_credentials" \
     -T "$file_upload" -k --anyauth
res=$?
if test "$res" != "0"; then
   echo "sending failed with: $res"
else
    echo "OK"
fi


