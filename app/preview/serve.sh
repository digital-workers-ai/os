#!/usr/bin/env bash

set -euo pipefail

source /preview/env.sh

exec > >(cat) 2>&1
exec supervisord -c /etc/supervisord.conf
