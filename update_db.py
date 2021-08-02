#!/usr/bin/env python3

# This utility will fetch update times for a given set of mod IDs and store
# them in a JSON DB

# Returns 0 for no updates, 1 for updates and > 1 for errors.

import argparse
import json
import smtplib
import ssl
import sys
import textwrap
import traceback
from email.message import EmailMessage
from typing import Any, Dict, List
from urllib import parse, request


def fetch_workshop_pages(itemIds: List[str]) -> Dict[str, int]:
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
        raise ValueError(f"The API returned {result_count} results, but we "
                         f"expected {len(itemIds)}!")
    result = json_data['response']['result']
    if result != 1:
        raise ValueError(f"The API returned result \"{result}\", but we "
                         "expected \"1\"!")

    # Okay, so we got all the info, we want to return a dict mapping id to last
    # update timestamp
    update_times = {}
    for result in json_data['response']['publishedfiledetails']:
        published_file_id = result['publishedfileid']
        if published_file_id not in itemIds:
            raise ValueError(f"The API returned a result for an item with "
                             f"ID \"{published_file_id}\", but we were not "
                             "expecting that!")
        update_times[published_file_id] = result['time_updated']
    return update_times


def update_and_check_db(db_path: str, update_times: Dict[str, int]):
    try:
        with open(db_path) as f:
            json_db = json.load(f)
    except FileNotFoundError:
        print(f"Warning: The specified JSON DB file \"{db_path}\" does not "
              "exist, will create an empty, fresh one!")
        json_db = {"mods": {}}

    results = []
    had_updates = False
    json_mods = json_db['mods']

    for itemId, current_timestamp in update_times.items():
        last_timestamp = -1
        item_id_str = str(itemId)
        if item_id_str in json_mods:
            last_timestamp = json_mods[item_id_str]
        else:
            print(f"Mod {itemId} was not present in DB, adding and assuming "
                  "updated state.")

        if last_timestamp != current_timestamp:
            print(f"Detected update for mod {itemId}.")
            results.append(itemId)
            json_mods[item_id_str] = current_timestamp
            had_updates = True

    if had_updates:
        json_db = {'mods': json_mods}
        with open(db_path, 'w') as f:
            json.dump(json_db, f, indent=2)

    return results


def send_mail(message_text: str, recipients: list):
    hostname = 'smtp.zeusops.com'
    port = 587  # For starttls
    from secret import password, sender_mail

    # Create a secure SSL context
    context = ssl.create_default_context()

    # Try to log in to server and send email
    try:
        server = smtplib.SMTP(hostname, port)
        server.ehlo()  # Can be omitted
        server.starttls(context=context)  # Secure the connection
        server.ehlo()  # Can be omitted
        server.login(sender_mail, password)
        for recipient in recipients:
            msg = EmailMessage()
            msg.set_content(message_text)

            msg['Subject'] = 'ZeusOps Mod Update Notification'
            msg['From'] = sender_mail
            msg['To'] = recipient
            server.send_message(msg)
    finally:
        server.quit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', dest='db_path',
                        help="Filename of the JSON DB file to use. Will be "
                             "created if does not exist.",
                        default="versions_workshop.json")
    parser.add_argument('-s', dest='state_path',
                        help="Filename of the state file to use. Will be "
                             "created if does not exist.",
                        default="versions_local_state.json")
    parser.add_argument('-m', dest='send_mail', default=False,
                        action='store_true',
                        help="Send mail to admins about mod updates")
    parser.add_argument('mod_ids', nargs='+', help="Mod IDs to check")
    args = parser.parse_args()

    modIds = args.mod_ids
    print(f"Welcome, we will try fetching update info for {len(modIds)} "
          "mods...")

    # For debugging: a static list of IDs
    # modIds = {"820924072", "1181881736"}

    try:
        # 1. Get the update timestamps for each item
        update_times = fetch_workshop_pages(modIds)

        # 2. Check our DB to see if any have updated
        updatedModIds = update_and_check_db(args.db_path, update_times)
        updatedModCount = len(updatedModIds)
        print('Found updates for {} mods.'.format(updatedModCount))

        # 3. Write the IDs of updated mods to the state file.
        jsonState = dict({'state': list(updatedModIds)})
        with open(args.state_path, 'w') as f:
            json.dump(jsonState, f, indent=2)
        for updatedModId in updatedModIds:
            print('Updated: {}'.format(updatedModId))
    except ValueError as e:
        traceback.print_exc()
        print("An internal error occurred")
        sys.exit(3)
    except Exception as e:
        traceback.print_exc()
        print('An unexpected internal error occurred, update failed.')
        sys.exit(4)

    # 4. Send a mail to peeps
    if updatedModCount > 0:
        if args.send_mail:
            messageText = textwrap.dedent("""\
                Yo, at least {0} mod{1} updated!

                ID{1}: {2}

                Cheers,
                    UpdateBot.
                """.format(updatedModCount,
                        's' if updatedModCount != 1 else '',
                        ', '.join(updatedModIds)))
            from secret import mail_recipient
            send_mail(messageText, mail_recipient)

    print('Bye!')
    sys.exit(0 if updatedModCount == 0 else 1)


if __name__ == '__main__':
    main()
