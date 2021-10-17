#!/bin/sh
cd /data/project/spbot/logs/
today=`(date +%F)`
mkdir "$today"
mv ../archive-resolved-* ../bot-stats* ../daily-log-* ../pers-bek* ../mp-helper* "$today"
bzip2 --compress "$today"/*
rm "$today"/*.err "$today"/*.out
