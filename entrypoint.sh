#!/bin/sh

DB_PORT="${MYSQL_PORT}"

/wait-for-it.sh db:$DB_PORT --timeout=30 --strict -- python server.py