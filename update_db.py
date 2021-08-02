# This utility will fetch update times for a given set of mod IDs and store them in a JSON DB
import argparse
import json
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
    if file.is_file():
        # Load the old JSON
        json_db = json.load(file.open('r', encoding='utf-8'))
    else:
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


parser = argparse.ArgumentParser()
parser.add_argument("db_path",
                    help="db_path FQFN of the JSON DB file to use. Will be created if it does not exist.",
                    default="versions_workshop.json")
parser.add_argument("state_path",
                    help="state_path FQFN of the state file to use. Will be created if it does not exist.",
                    default="versions_local_state.json")
parser.add_argument('mod_ids', nargs='*', help="mod_ids Mod IDs to check")
args = parser.parse_args()

modIds = args.mod_ids
modIdCount = len(modIds)
if modIdCount <= 0:
    raise ValueError('You need to specify at least one ID!')
print('Welcome, we will try fetching update info for {} mods...'.format(modIdCount))


# For debugging: a static list of IDs
# modIds = {820924072, 1181881736}

# 1. Get the update timestamps for each item
idToLastUpdatedTimestampMap = fetch_workshop_pages(modIds)

# 2. Check our DB to see if any have updated
updatedModIds = update_db_and_return_updated(args.db_path, idToLastUpdatedTimestampMap)
print('Found updates for {} mods.'.format(len(updatedModIds)))

# 3. Write the IDs of updated mods to the state file.
jsonState = dict({'state': list(updatedModIds)})
stateFile = Path(args.state_path)
json.dump(jsonState, stateFile.open('w', encoding='utf-8'))
for updatedModId in updatedModIds:
    print('Updated: {}'.format(updatedModId))
print('Bye!')
