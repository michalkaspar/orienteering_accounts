#!/bin/sh
# wait-for-postgres.sh

set -e

SCRIPTPATH="$( cd "$(dirname "$0")" ; pwd -P )"

cmd="$@"

until python "$SCRIPTPATH/test_postgresql.py"; do
  >&2 echo "Postgres is unavailable - sleeping"
  sleep 1
done

>&2 echo "Postgres is up - executing command"
exec $cmd
