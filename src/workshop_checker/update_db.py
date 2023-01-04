#!/usr/bin/env python3

# This utility will fetch update times for a given set of mod IDs and store
# them in a JSON DB

# Returns 0 for no updates, 1 for updates and > 1 for errors.

import argparse
import json
import logging
import os
from pathlib import Path
import smtplib
import ssl
import sys
import traceback
from email.message import EmailMessage
from typing import Any, Dict, List, Union
from urllib import parse, request

from steamfiles import acf

from workshop_checker.config import WORKSHOP_PATH, FILENAME


# Log debug, info -> stdout, warn, error -> stderr
FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
fmt = logging.Formatter(FORMAT)

logger = logging.getLogger('update_db')
logger.setLevel(logging.INFO)

h1 = logging.StreamHandler(sys.stdout)
h1.setLevel(logging.DEBUG)
h1.addFilter(lambda record: record.levelno <= logging.INFO)
h1.setFormatter(fmt)
logger.addHandler(h1)

h2 = logging.StreamHandler()
h2.setLevel(logging.WARNING)
h2.setFormatter(fmt)
logger.addHandler(h2)


def fetch_workshop_pages(itemIds: List[str]) -> Dict[str, Dict[str, Any]]:
    url = ('https://api.steampowered.com/ISteamRemoteStorage/'
           'GetPublishedFileDetails/v1/?format=json')
    raw_data: Dict[str, Any] = {
        'itemcount': len(itemIds)
    }
    currentItemCount = 0
    for itemId in itemIds:
        raw_data['publishedfileids[{}]'.format(currentItemCount)] = itemId
        currentItemCount += 1

    data = parse.urlencode(raw_data).encode()
    # POST is used if data != None
    req = request.Request(url, data=data, method="POST")
    response = request.urlopen(req)
    decoded_response: str = response.read().decode()
    # The response should be JSON, so lets parse it
    json_data = json.loads(decoded_response)
    # print(json.dumps(json_data, sort_keys=True, indent=4))
    result_count = json_data['response']['resultcount']
    if result_count != len(itemIds):
        # See https://partner.steamgames.com/doc/api/steam_api#EResult for
        # explanations of result codes
        raise ValueError(f"The API returned {result_count} results, but we "
                         f"expected {len(itemIds)}!")
    result = json_data['response']['result']
    if result != 1:
        raise ValueError(f"The API returned result \"{result}\", but we "
                         "expected \"1\"!")

    # Okay, so we got all the info, we want to return a dict mapping id to last
    # update timestamp
    mod_info = {}
    for result in json_data['response']['publishedfiledetails']:
        mod_id = result['publishedfileid']
        if result['result'] != 1:
            logger.warning(
                f"The API returned result "
                f"\"{result['result']}\" for the item "
                f"{mod_id}, but we expected \"1\"!")
            continue
        if mod_id not in itemIds:
            raise ValueError(f"The API returned a result for an item with "
                             f"ID \"{mod_id}\", but we were not "
                             "expecting that!")
        mod_info[mod_id] = {
            'name': result['title'],
            'timestamp': result['time_updated']
        }
    return mod_info


def get_local_state(ws_path: Union[Path, str]) -> Dict[str, int]:
    workshop = Path(os.path.expanduser(ws_path))
    workshop_path = (workshop / 'steamapps/workshop' / FILENAME)

    try:
        with open(workshop_path) as f:
            data = acf.load(f)['AppWorkshop']['WorkshopItemsInstalled']
    except FileNotFoundError:
        data = {}
    local_mods = {}

    for mod in data:
        local_mods[mod] = int(data[mod]['timeupdated'])
    return local_mods


def check_mod_update(mod_id: str, workshop_timestamp: int,
                     local_mods: Dict[str, int], download_new=True) -> bool:
    try:
        local_timestamp = local_mods[mod_id]
    except KeyError:
        if download_new:
            logger.info(
                f"Mod {mod_id} was not found locally, assuming that "
                "it needs an update.")
            return True
        else:
            logger.info(f"Mod {mod_id} was not found locally, skipping")
            return False
    else:
        logger.log(5, f"ID: {mod_id}, local: {local_timestamp}, "
                      f"workshop: {workshop_timestamp}")
        if local_timestamp < workshop_timestamp:
            logger.debug(f"ID: {mod_id}, local: {local_timestamp}, "
                         f"workshop: {workshop_timestamp}")
            return True
    return False


def check_updates(ws_path: str, mods_info: Dict[str, Dict[str, Any]],
                  download_new=True) -> List[str]:
    results = []
    local_mods = get_local_state(ws_path)

    for item_id, mod_info in mods_info.items():
        if check_mod_update(item_id, mod_info['timestamp'], local_mods,
                            download_new):
            results.append(item_id)
    return results


def send_mail(message_text: str, recipients: list,
              subject="Zeusops Pending Mod Updates"):
    hostname = 'smtp.zeusops.com'
    port = 587  # For starttls
    from workshop_checker.secret import password, sender_mail

    # Create a secure SSL context
    context = ssl.create_default_context()

    # Try to log in to server and send email
    server = None
    try:
        server = smtplib.SMTP(hostname, port)
        server.ehlo()  # Can be omitted
        server.starttls(context=context)  # Secure the connection
        server.ehlo()  # Can be omitted
        server.login(sender_mail, password)
        # for recipient in recipients:
        msg = EmailMessage()
        msg.set_content(message_text)

        msg['Subject'] = subject
        msg['From'] = sender_mail
        msg['To'] = (', '.join(recipients)
                     if len(recipients) > 1
                     else recipients[0])
        server.send_message(msg)
    finally:
        if server:
            server.quit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-w', dest='workshop_path', default=WORKSHOP_PATH,
                        help="Root directory of the steam workshop")
    parser.add_argument('-f', dest='workshop_file', default=FILENAME,
                        help="Filename of the workshop ACF file")
    parser.add_argument('-s', dest='state_path',
                        help="Filename of the state file to use. Will be "
                             "created if does not exist.",
                        default="versions_local_state.json")
    parser.add_argument('--notify', dest='notify', default=False,
                        action='store_true',
                        help="Notify admins about mod updates (by email, Discord)")
    parser.add_argument('--no-mail', dest='send_mail', default=True,
                        action='store_false',
                        help="Do not send mail to admins about mod updates")
    parser.add_argument('--no-discord', dest='notify_discord', default=True,
                        action='store_false',
                        help="Do not send Discord messages to admins about mod updates")
    parser.add_argument('-c', '--check-updates', dest='check_updates', default=False,
                        action='store_true', help="Check for mod updates")
    parser.add_argument('-e', '--only-existing', dest='only_existing', default=False,
                        action='store_true', help="Only update existing mods, "
                        "do not download new ones.")
    parser.add_argument('-v', '--verbose', default=0, action='count',
                        help=("Enable verbose output. Repeat flag to increase "
                              "verbosity"))
    parser.add_argument('mod_ids', nargs='+', help="Mod IDs to check")
    args = parser.parse_args()

    modIds = args.mod_ids
    logger.info(
        f"Welcome, we will try to fetch update info for {len(modIds)} mods")

    if args.verbose == 1:
        logger.setLevel(logging.DEBUG)
    elif args.verbose == 2:
        logger.setLevel(5)

    # For debugging: a static list of IDs
    # modIds = {"820924072", "1181881736"}

    try:
        # 1. Get the update timestamps for each item
        mods_info = fetch_workshop_pages(modIds)
    except ValueError:
        traceback.print_exc()
        logger.warning("An internal error occurred")
        sys.exit(3)

    try:
        with open(args.state_path, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}
    logger.info("Update info fetched")
    logger.debug(f"data: {data}")

    last_mailed: List[str] = data.get("last_mailed", [])
    last_discord: List[str] = data.get("last_discord", [])

    if args.check_updates:
        # 2. Check our DB to see if any have updated
        updated_mod_ids = check_updates(args.workshop_path, mods_info,
                                        not args.only_existing)
        updated_mod_count = len(updated_mod_ids)
        logger.info('Found updates for {} mods.'.format(updated_mod_count))

        # 3. Write the IDs of updated mods to the state file.
        mods_combined = []
        for mod_id in updated_mod_ids:
            mod_name = mods_info[mod_id]['name']
            combined = f"{mod_id} - {mod_name}"
            logger.info(f"Has update: {combined}")
            mods_combined.append(combined)

        # 4. Send a mail to peeps
        if updated_mod_count > 0 and args.notify:
            # Check if a mail has already been sent about the same mod IDs
            needs_mail = any(elem not in last_mailed
                             for elem in updated_mod_ids)
            needs_discord = any(elem not in last_discord
                                for elem in updated_mod_ids)
            if needs_mail or needs_discord:
                message_text = (
                    "Yo, at least {0} mod{1} need{2} an update:\n"
                    "  {3}\n"
                    .format(updated_mod_count,
                            's' if updated_mod_count != 1 else '',
                            's' if updated_mod_count == 1 else '',
                            '\n  '.join(mods_combined)))
                if args.send_mail and needs_mail:
                    from workshop_checker.secret import mail_recipient
                    send_mail(message_text, mail_recipient)
                    last_mailed = updated_mod_ids
                if args.notify_discord and needs_discord:
                    from workshop_checker.secret import webhook_url
                    from discord_webhook import DiscordWebhook

                    webhook = DiscordWebhook(url=webhook_url,
                                             content=message_text)
                    webhook.execute()
                    last_discord = updated_mod_ids


        logger.info("Bye!")
        exit_code = 0 if updated_mod_count == 0 else 4
    else:
        logger.info("Not checking for updates")
        exit_code = 0

    with open(args.state_path, 'w') as f:
        data_out = {
            "mods_info": mods_info,
            "last_mailed": last_mailed,
            "last_discord": last_discord,
        }
        json.dump(data_out, f, indent=2)

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
