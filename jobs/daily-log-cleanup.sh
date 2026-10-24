#!/bin/sh
# Daily at 23:59 UTC: move the bot logs of the day to logs/YYYY-MM-DD/ and
# gzip the logs of earlier days (their jobs have finished writing by then).
set -u

LOGDIR="${LOGDIR:-$HOME/logs}"
cd "$LOGDIR" || exit 1

today=$(date -u +%F)
echo "== $today =="
mkdir -p "$today" || exit 1

# Own logs (daily-log-cleanup.*) stay in place: this run is still writing them.
moved=0
for f in archive-resolved-* bot-stats* pers-bek* mp-helper* bot-login*; do
    [ -f "$f" ] || continue
    # never overwrite a file of the same name from an earlier run today
    if [ -e "$today/$f" ]; then
        echo "skipped $f: $today/$f exists" >&2
        continue
    fi
    mv "$f" "$today/" && moved=$((moved + 1))
done
echo "moved $moved files to $today/"

# gzip non-empty logs in all older day directories; this also catches up after
# a failed or missed run. Files changed within the last hour are skipped.
find . -mindepth 2 -maxdepth 2 -path './20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]/*' \
    ! -path "./$today/*" -type f -size +0 ! -name '*.gz' -mmin +60 \
    -exec gzip -9 {} + || exit 1
echo "done"
