import json

from scraper import sync_collection


def get_config():
    with open('config.json', 'r') as config_file:
        config = json.load(config_file)
    return config


def main():
    config = get_config()
    for collection in config['collections']:
        sync_collection(collection['id'], collection['name'], config['token'])

main()
