#!/usr/bin/env python3

# This utility will check a given mod ID against a local state file to determine whether it needs updating.
# The state file does _not_ contain the actual state as is on disk, but whether the mod was marked as 'updated'
# during the last Workshop crawl/DB update.

import argparse
import json
import sys

parser = argparse.ArgumentParser()
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
        jsonState = json.load(f)
except FileNotFoundError as e:
    raise FileNotFoundError(f'Could not find state file "{args.state_path}", '
                            'does it exist and is readable?') from e

# 2. Check if the ID is contained in the state, i.e. was marked as updated
if modId in jsonState['state']:
    print('NEEDS UPDATE')
    sys.exit(1)
else:
    print('UNCHANGED')
    sys.exit(0)
