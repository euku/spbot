#!/bin/sh
cd ~/logs/
today=`(date +%F)`
mkdir "$today"
mv archive-resolved-* bot-stats* pers-bek* mp-helper* bot-login* "$today"

bzip2 --compress "$today"/*
rm "$today"/*.err "$today"/*.out
