#!/bin/sh

set -e
trap "{ exit 0; }" TERM INT

OUTPUT_SUBDIR=`date +%Y-%m-%dT%H-%M-%S`

sigexport --source=/Signal /output/$OUTPUT_SUBDIR "$@"
chown -R dummy /output/
