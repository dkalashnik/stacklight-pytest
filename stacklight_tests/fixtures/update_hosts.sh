#!/usr/bin/env bash

IP="$1"
HOST="$2"
TAB=$'\t'
grep "$HOST" /etc/hosts || echo "$IP$TAB$HOST" >> /etc/hosts
grep "$HOST" /etc/hosts && sed -i "s/.*$TAB$HOST/$IP$TAB$HOST/" /etc/hosts