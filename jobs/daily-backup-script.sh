#!/bin/sh
cd public_html/sqldumps/
today=`(date +%F)`
mysqldump p_dewpmp_production -h sql-s2-rr.toolserver.org > p_dewpmp_production_$today.sql
bzip2 --compress p_dewpmp_production_$today.sql
