#!/usr/bin/env python3

# This utility will check a given mod ID against a local state file to
# determine whether it needs updating. The state file does _not_ contain the
# actual state as is on disk, but whether the mod was marked as 'updated'
# during the last Workshop crawl/DB update.

import argparse
import json
import sys

from config import FILENAME, WORKSHOP_PATH
from update_db import check_mod_update, get_local_state

parser = argparse.ArgumentParser()
parser.add_argument('-w', dest='workshop_path', default=WORKSHOP_PATH,
                    help="Root directory of the steam workshop")
parser.add_argument('-f', dest='workshop_file', default=FILENAME,
                    help="Filename of the workshop ACF file")
parser.add_argument('-s',
                    dest='state_path',
                    help="FQFN of the state file to use.",
                    default="versions_local_state.json")
parser.add_argument('mod_id', help="Mod ID to check")
args = parser.parse_args()

modId = args.mod_id

# For debugging: a static list of IDs
# modId = '820924072'

# 1. Read the state file
try:
    with open(args.state_path) as f:
        workshop_state = json.load(f)
except FileNotFoundError as e:
    raise FileNotFoundError(f"Could not find the state file "
                            f"\"{args.state_path}\". Make sure that it "
                            "exists and is readable") from e

local_mods = get_local_state(args.workshop_path)
mod_id = args.mod_id
workshop_time = workshop_state[mod_id]['timestamp']

# 2. Check if the mod needs an update
if check_mod_update(mod_id, workshop_time, local_mods):
    print('NEEDS UPDATE')
    sys.exit(1)
else:
    print('UNCHANGED')
    sys.exit(0)
