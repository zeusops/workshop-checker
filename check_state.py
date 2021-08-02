# This utility will check a given mod ID against a local state file to determine whether it needs updating.
# The state file does _not_ contain the actual state as is on disk, but whether the mod was marked as 'updated'
# during the last Workshop crawl/DB update.

import argparse
import json
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("state_path",
                    help="state_path FQFN of the state file to use.",
                    default="versions_local_state.json")
parser.add_argument('mod_id', help="mod_id Mod ID to check")
args = parser.parse_args()

modId = args.mod_id

# For debugging: a static list of IDs
# modId = '820924072'

# 1. Read the state file
stateFile = Path(args.state_path)
if not stateFile.is_file():
    raise ValueError('Could not find state file "{}", does it exist and is readable?'.format(args.state_path))
jsonState = json.load(stateFile.open('r', encoding='utf-8'))

# 2. Check if the ID is contained in the state, i.e. was marked as updated
if modId in jsonState['state']:
    print('UPDATED')
    sys.exit(1)
else:
    print('UNCHANGED')
    sys.exit(0)
