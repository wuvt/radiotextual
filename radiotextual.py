#!/usr/bin/python3

import defaults
import json
import logging
import os.path
import re
import requests
import sseclient
from telnetlib import Telnet


class Config(dict):
    def load_from_object(self, obj):
        for key in dir(obj):
            if key.isupper():
                self[key] = getattr(obj, key)

    def load_from_json(self, path):
        with open(path) as f:
            self.update(json.load(f))


def update_rds(track):
    naughty_word_re = re.compile(
        r'shit|piss|fuck|cunt|cocksucker|tits|twat|asshole',
        re.IGNORECASE)
    for k, v in track.items():
        if type(v) == str:
            track[k] = naughty_word_re.sub('****', v)

    with Telnet(host=config['TELNET_SERVER'], port=config['TELNET_PORT'],
                timeout=config['TELNET_TIMEOUT']) as tn:
        tn.read_until(b'\n\r', timeout=config['TELNET_TIMEOUT'])
        tn.write('RT={artist} - {title} [DJ: {dj}]\n'.format(**track).encode(
            'ascii', 'replace'))
        logger.warning(tn.read_until(
            b'\n\r', timeout=config['TELNET_TIMEOUT']).decode('ascii'))


if __name__ == '__main__':
    config = Config()
    config.load_from_object(defaults)

    config_path = os.environ.get('APP_CONFIG_PATH', 'config.json')
    if os.path.exists(config_path):
        config.load_from_json(config_path)

    logger = logging.getLogger(__name__)

    r = requests.get(config['TRACK_URL'],
                     headers={"Accept": "application/json"})
    if r.status_code == 200:
        try:
            update_rds(r.json())
        except Exception as e:
            logger.warning("Failed to set initial radio text: {}".format(e))

    messages = sseclient.SSEClient(config['LIVE_URL'])
    for msg in messages:
        try:
            data = json.loads(msg.data)
            if data['event'] == 'track_change':
                track = data['tracklog']['track']
                track['dj'] = data['tracklog']['dj']
                update_rds(track)
            elif data['event'] == 'track_edit':
                track = data['tracklog']['track']
                track['dj'] = data['tracklog']['dj']
                update_rds(track)
        except Exception as e:
            logger.warning("Failed to process message: {}".format(e))
