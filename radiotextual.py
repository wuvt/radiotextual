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


class RDSUpdater(Telnet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.banner = self.read_until(b'\n\r', timeout=self.timeout)
        self.naughty_word_re = re.compile(
            r'shit|piss|fuck|cunt|cocksucker|tits|twat|asshole',
            re.IGNORECASE)

    def set_track(self, track, is_retry=False):
        for k, v in track.items():
            if type(v) == str:
                track[k] = self.naughty_word_re.sub('****', v)

        try:
            self.write(
                'RT={artist} - {title} [DJ: {dj}]\n'.format(**track).encode(
                    'ascii', 'replace'))
            logger.warning(self.read_until(
                b'\n\r', timeout=self.timeout).decode('ascii').strip())
        except (OSError, EOFError):
            self.open(self.host, self.port, self.timeout)
            if not is_retry:
                self.set_track(track, is_retry=True)


if __name__ == '__main__':
    config = Config()
    config.load_from_object(defaults)

    config_path = os.environ.get('APP_CONFIG_PATH', 'config.json')
    if os.path.exists(config_path):
        config.load_from_json(config_path)

    logger = logging.getLogger(__name__)

    with RDSUpdater(host=config['TELNET_SERVER'], port=config['TELNET_PORT'],
                    timeout=config['TELNET_TIMEOUT']) as rds:
        try:
            r = requests.get(config['TRACK_URL'],
                             headers={"Accept": "application/json"})
            r.raise_for_status()
            rds.set_track(r.json())
        except Exception as e:
            logger.warning("Failed to set initial radiotext: {}".format(e))

        messages = sseclient.SSEClient(config['LIVE_URL'])
        for msg in messages:
            try:
                data = json.loads(msg.data)
                if data['event'] == 'track_change':
                    track = data['tracklog']['track']
                    track['dj'] = data['tracklog']['dj']
                    logger.warning("Track change: {track}".format(track=track))
                    rds.set_track(track)
                elif data['event'] == 'track_edit':
                    track = data['tracklog']['track']
                    track['dj'] = data['tracklog']['dj']
                    logger.warning("Track edit: {track}".format(track=track))
                    rds.set_track(track)
            except ValueError as e:
                logger.warning("Failed to process message: {}".format(e))
