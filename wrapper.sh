#!/bin/bash

DIR="$(cd "$(dirname $0)" && pwd)"
name=$(basename $0)
script_name=${name%.sh}.py
cd $DIR
$DIR/venv/bin/python $script_name $@
