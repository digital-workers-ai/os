#!/usr/bin/env bash

set -euo pipefail

source /preview/env.sh

exec > >(cat) 2>&1
cd /app

supervisord -c /etc/supervisord.conf &
supervisor=$!

status() {
  python -c '
import sys, urllib.error, urllib.request
request = urllib.request.Request("http://localhost:8000/api/" + sys.argv[2], method=sys.argv[1])
try:
    print(urllib.request.urlopen(request).status)
except urllib.error.HTTPError as error:
    print(error.code)
except OSError:
    print(0)
' "$1" "$2"
}

wait_for_backend() {
  for _ in $(seq 60); do
    if [ "$(status GET health)" = 200 ]; then
      return 0
    fi
    sleep 5
  done
  echo "the backend did not answer within 5 minutes" >&2
  return 1
}

post_api() {
  for _ in $(seq 5); do
    code=$(status POST "$1")
    echo "POST /api/$1 -> $code"
    case "$code" in
      2*) return 0 ;;
      409) sleep 3 ;;
      *) return 1 ;;
    esac
  done
  return 1
}

wait_for_backend
post_api sync
post_api rebuild
post_api rebuild
python -m tools.seed_demo

kill "$supervisor"
wait "$supervisor" || true
