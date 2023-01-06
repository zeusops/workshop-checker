#!/usr/bin/env python3

# This utility will check a given mod ID against a local state file to
# determine whether it needs updating. The state file does _not_ contain the
# actual state as is on disk, but whether the mod was marked as 'updated'
# during the last Workshop crawl/DB update.

import argparse
import json
import logging
import sys

from workshop_checker.config import FILENAME, WORKSHOP_PATH
from workshop_checker.update_db import check_mod_update, get_local_state

FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(format=FORMAT, level=logging.INFO)
logger = logging.getLogger("check_update")


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        description="Check the update status of a mod using the local cache",
    )
    parser.add_argument(
        "-w",
        dest="workshop_path",
        default=WORKSHOP_PATH,
        help="Root directory of the steam workshop",
    )
    parser.add_argument(
        "-f",
        dest="workshop_file",
        default=FILENAME,
        help="Filename of the workshop ACF file",
    )
    parser.add_argument(
        "-s",
        dest="state_path",
        help="FQFN of the state file to use.",
        default="versions_local_state.json",
    )
    parser.add_argument(
        "-e",
        dest="only_existing",
        default=False,
        action="store_true",
        help="Only update existing mods, do not download new ones.",
    )
    parser.add_argument("mod_id", help="Mod ID to check")
    args = parser.parse_args(argv)
    return args


def cli(argv: list[str] | None = None):
    if not argv:
        argv = sys.argv[1:]
    args = parse_arguments(argv)

    # 1. Read the state file
    try:
        with open(args.state_path) as f:
            workshop_state = json.load(f).get("mods_info", {})
    except FileNotFoundError as e:
        raise FileNotFoundError(
            f'Could not find the state file "{args.state_path}". '
            "Make sure that it exists and is readable"
        ) from e

    local_mods = get_local_state(args.workshop_path)
    mod_id = args.mod_id
    try:
        workshop_time = workshop_state[mod_id]["timestamp"]
    except KeyError:
        logger.error(f'Could not find mod "{mod_id}" in the state file.')
        return 0

    # 2. Check if the mod needs an update
    if check_mod_update(
        mod_id, workshop_time, local_mods, not args.only_existing
    ):
        logger.info("NEEDS UPDATE")
        return 1
    else:
        logger.info("UNCHANGED")
        return 0


def main(mod_id: str, *args):
    """Run the main function.

    This functions as the entrypoint when importing the module.
    """
    return cli([mod_id, *args])


if __name__ == "__main__":
    sys.exit(cli())
