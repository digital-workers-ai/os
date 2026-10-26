#!/usr/bin/env bash

set -euo pipefail

source /preview/env.sh

exec supervisord -c /etc/supervisord.conf
