import requests
import os
import shutil
import json
from PIL import Image

base_url = 'https://api.thingiverse.com'


def get_filename_from_url(url):
    return url.split('/')[-1].split('?')[0]


def get_cleaned_folder_name(name):
    return name.strip().replace('_', ' ').replace(':', '-').replace('/', '-')


def retrying_download(url, ttl=20):
    if ttl == 0:
        return

    try:
        return requests.get(url, timeout=10)
    except Exception as ex:
        return retrying_download(url, ttl=ttl - 1)


def download_thing(thing_id, folder, token):
    if not os.path.exists(folder):
        os.mkdir(folder)

    files_dir = os.path.join(folder, 'files')
    if not os.path.exists(files_dir):
        os.mkdir(files_dir)

    response = retrying_download(f'{base_url}/things/{thing_id}/files/?access_token={token}')
    if not (response and response.status_code == 200):
        print(f'Unable to download {thing_id}: unable to find download url')
        return

    for thing_file_obj in response.json():
        thing_file_path = os.path.join(files_dir, thing_file_obj['name'])
        if os.path.exists(thing_file_path) and os.path.getsize(thing_file_path) > 1000:
            continue

        file_id = thing_file_obj['id']
        response = retrying_download(thing_file_obj['download_url'] + f'?access_token={token}')

        if not (response and response.status_code == 200):
            print(f'Unable to download {file_id} from {thing_id}: {response}')
            continue

        with open(thing_file_path, 'wb') as thing_file:
            thing_file.write(response.content)


def download_images(thing_id, folder, token):
    if not os.path.exists(folder):
        os.mkdir(folder)

    response = retrying_download(f'{base_url}/things/{thing_id}/images/?access_token={token}')
    if not (response and response.status_code == 200):
        print(f'Unable to find {thing_id} images')
        return

    for image in response.json():
        download_image(image, folder)


def download_image(image_obj, folder):
    if not image_obj:
        return

    matched_size = [i for i in image_obj['sizes'] if i['type'] == 'display' and i['size'] == 'large'][0]

    name = image_obj['name']
    image_path = os.path.join(folder, name)

    if os.path.exists(image_path):
        return

    response = retrying_download(matched_size['url'])
    if not (response and response.status_code == 200):
        return

    with open(image_path, 'wb') as image_file:
        image_file.write(response.content)

    # fix image extension
    new_path = '{}.{}'.format('.'.join(image_path.split('.')[:-1]), Image.open(image_path).format.lower())
    if new_path != image_path:
        shutil.move(image_path, new_path)


def sync_collection(collection_id, name, token):
    folder = os.path.join('scraped', name)
    if not os.path.exists(folder):
        os.mkdir(folder)

    page = 1
    global_index = 1

    while True:
        data = retrying_download(
            f'{base_url}/collections/{collection_id}/things/?access_token={token}&page={page}').json()
        items_num = len(data)

        print(f'found {items_num} items on page {page}')

        if items_num == 0:
            print('Done!')
            break

        for thing in data:
            thing_name = thing['name'].strip()
            thing_id = thing['id']
            print(f'downloading {global_index}. {thing_name} ({thing_id})')

            thing_folder = os.path.join(folder, get_cleaned_folder_name(thing['name']))
            if os.path.exists(thing_folder):
                global_index += 1
                continue

            response = retrying_download(f'{base_url}/things/{thing_id}/?access_token={token}')
            if not (response and response.status_code == 200):
                print(f'Unable to fetch info for {thing_id}: {response}')
                continue

            thing_data = response.json()

            if not os.path.exists(thing_folder):
                os.mkdir(thing_folder)

            # write description
            with open(os.path.join(thing_folder, 'description.txt'), 'w') as description_file:
                description_file.write(thing_data['description'])

            # write id
            with open(os.path.join(thing_folder, f'{thing_id}.id'), 'w') as id_file:
                id_file.write(str(thing_id))

            # write url
            with open(os.path.join(thing_folder, f'{thing_id}.url'), 'w') as url_file:
                url_file.write("[InternetShortcut]\nURL={}\n".format(thing_data['public_url']))

            # write ancestors
            with open(os.path.join(thing_folder, f'{thing_id}.ancestors'), 'w') as ancestors_file:
                ancestors_json = retrying_download(
                    f'{base_url}/things/{thing_id}/ancestors/?access_token={token}&page={page}').json()
                ancestors_file.write(json.dumps(ancestors_json, indent=2))

            download_image(thing_data['default_image'], thing_folder)
            download_images(thing['id'], os.path.join(thing_folder, 'images'), token)
            download_thing(thing['id'], thing_folder, token)

            global_index += 1

        page += 1
