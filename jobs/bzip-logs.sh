#!/bin/bash
cd ~/bot/logs
bzip2 --compress archiv-* mp-help-bot-* pb-bot-* vm-erl*
rm archiv-*.log mp-help-bot-*.log pb-bot-*.log vm-erl*.log
