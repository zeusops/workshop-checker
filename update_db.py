# This utility will fetch update times for a given set of mod IDs and store them in a JSON DB
# Returns 0 for no updates, 1 for updates and > 1 for errors.
import argparse
import json
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path
from urllib import request, parse


def fetch_workshop_pages(itemIds):
    url = 'https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/?format=json'
    raw_data = {
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
    decoded_response = response.read().decode('utf-8')
    # The response should be JSON, so lets parse it
    json_data = json.loads(decoded_response)
    # print(json.dumps(json_data, sort_keys=True, indent=4))
    if json_data['response']['resultcount'] != len(itemIds):
        raise ValueError('The API returned {0} results, but we expected {1}!'.format(json_data['response']['resultcount'], len(itemIds)))
    if json_data['response']['result'] != 1:
        raise ValueError('The API returned result "{}", but we expected "1!'.format(json_data['response']['result']))

    # Okay, so we got all the info, we want to return a dict mapping id to last update timestamp
    id_to_update_time_map = {}
    for result in json_data['response']['publishedfiledetails']:
        published_file_id = result['publishedfileid']
        if published_file_id not in itemIds:
            raise ValueError('The API returned a result for an item with ID "{}", but we were not expecting that!'
                             .format(published_file_id))
        id_to_update_time_map[published_file_id] = result['time_updated']
    return id_to_update_time_map


def update_db_and_return_updated(json_db_file, id_to_last_updated_timestamp_map):
    file = Path(json_db_file)
    json_db = json.loads('{ "mods": {} }')
    try:
        with open(json_db_file) as f:
            json_db = json.load(f)
    except FileNotFoundError:
        print('Warning: The specified JSON DB file "{}" does not exist, will create an empty, fresh one!'
              .format(json_db_file))

    result_set = set()
    had_update = False
    json_mod_list = dict(json_db['mods'])

    for itemId in id_to_last_updated_timestamp_map:
        current_timestamp = id_to_last_updated_timestamp_map[itemId]
        last_timestamp = -1
        item_id_str = str(itemId)
        if item_id_str in json_mod_list:
            last_timestamp = json_mod_list[item_id_str]
        else:
            print('Mod {} was not present in DB, adding and assuming updated state.'.format(itemId))

        if last_timestamp != current_timestamp:
            print('Detected update for mod {}.'.format(itemId))
            result_set.add(itemId)
            json_mod_list[item_id_str] = current_timestamp
            had_update = True

    if had_update:
        json_db = dict({'mods': json_mod_list})
        json.dump(json_db, file.open('w', encoding='utf-8'))

    return result_set


def send_mail(message_text, recipients):
    hostname = 'smtp.zeusops.com'
    port = 587  # For starttls
    from secret import sender_mail
    from secret import password

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
    except Exception as e:
        # Print any error messages to stdout
        print(e)
    finally:
        server.quit()


parser = argparse.ArgumentParser()
parser.add_argument('-d',
                    dest='db_path',
                    help="FQFN of the JSON DB file to use. Will be created if it does not exist.",
                    default="versions_workshop.json")
parser.add_argument('-s',
                    dest='state_path',
                    help="FQFN of the state file to use. Will be created if it does not exist.",
                    default="versions_local_state.json")
parser.add_argument('mod_ids', nargs='+', help="Mod IDs to check")
args = parser.parse_args()

modIds = args.mod_ids
print(f"Welcome, we will try fetching update info for {len(modIds)} mods...")


# For debugging: a static list of IDs
# modIds = {820924072, 1181881736}

# For signaling that updating has failed
hadUpdateError = True

try:
    # 1. Get the update timestamps for each item
    idToLastUpdatedTimestampMap = fetch_workshop_pages(modIds)

    # 2. Check our DB to see if any have updated
    updatedModIds = update_db_and_return_updated(args.db_path, idToLastUpdatedTimestampMap)
    updatedModCount = len(updatedModIds)
    print('Found updates for {} mods.'.format(updatedModCount))

    # 3. Write the IDs of updated mods to the state file.
    jsonState = dict({'state': list(updatedModIds)})
    stateFile = Path(args.state_path)
    json.dump(jsonState, stateFile.open('w', encoding='utf-8'))
    for updatedModId in updatedModIds:
        print('Updated: {}'.format(updatedModId))
    hadUpdateError = False
except ValueError as err:
    print('An internal error occurred: {}'.format(err))
    sys.exit(3)
except:
    print('An unexpected internal error occurred, update failed.')
    sys.exit(4)

# 4. Send a mail to peeps
if updatedModCount > 0:
    from secret import mail_recipient
    messageText = """\
Yo, at least {0} mod{1} updated!

ID{1}: {2}

Cheers,
    UpdateBot.
    """.format(updatedModCount, 's' if updatedModCount != 1 else '', ', '.join(updatedModIds))
    # send_mail(messageText, mail_recipient)
    print(messageText)

print('Bye!')
sys.exit(0 if updatedModCount == 0 else 1)
