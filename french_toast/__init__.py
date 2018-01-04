#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Copyright (c) 2018 Erin Morelli.

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.
"""

import os
import json
import time
import requests
from datetime import date
from flask import Flask
import xml.etree.ElementTree as ET
from pkg_resources import get_provider


# =============================================================================
#  App Constants
# =============================================================================

# Set module name
__module__ = "french_toast.{0}".format(__file__)


# Get module info
def set_project_info():
    """Set project information from setup tools installation."""
    # CUSTOMIZE THIS VALUE FOR YOUR OWN INSTALLATION
    base_url = 'https://slack-french-toast.herokuapp.com'

    # Get app info from the dist
    app_name = 'french_toast'
    provider = get_provider(app_name)

    return {
        'name': app_name,
        'name_full': 'EM Slack French Toast',
        'author_url': 'http://www.erinmorelli.com',
        'github_url': 'https://github.com/ErinMorelli/em-slack-french-toast',
        'version': '1.0',
        'version_int': 1.0,
        'package_path': provider.module_path,
        'copyright': '2018-{0}'.format(str(date.today().year)),
        'client_secret': os.environ['SLACK_CLIENT_SECRET'],
        'client_id': os.environ['SLACK_CLIENT_ID'],
        'base_url': base_url,
        'oauth_url': 'https://slack.com/oauth/authorize',
        'hook_url': 'https://hooks.slack.com/services',
        'auth_url': '{0}/authenticate'.format(base_url),
        'valid_url': '{0}/validate'.format(base_url),
        'team_scope': ['incoming-webhook']
    }

# Project info
PROJECT_INFO = set_project_info()

# Set the template directory
TEMPLATE_DIR = os.path.join(PROJECT_INFO['package_path'], 'templates')

# =============================================================================
# Flask App Configuration
# =============================================================================

# Initalize flask app
APP = Flask(
    'em-slack-french-toast',
    template_folder=TEMPLATE_DIR,
    static_folder=TEMPLATE_DIR
)

# Set up flask config
# SET THESE ENV VALUES FOR YOUR OWN INSTALLATION
APP.config.update({
    'SECRET_KEY': os.environ['SECURE_KEY'],
    'SQLALCHEMY_DATABASE_URI': os.environ['DATABASE_URL'],
    'SQLALCHEMY_TRACK_MODIFICATIONS': True
})


class EmSlackFrenchToast(object):

    # Constants
    TOAST_API_URI = 'http://www.universalhub.com/toast.xml'
    STATUS_FILE = '.status'
    LEVELS = {
        "LOW": {
            "color": "97FF9B",
            "image": "http://www.universalhub.com/images/2007/frenchtoastgreen.jpg",
            "description": "No storm predicted. Harvey Leonard sighs and looks dour on the evening news. Go about your daily business but consider buying second refrigerator for basement, diesel generator. Good time to replenish stocks of maple syrup, cinnamon."
        },
        "GUARDED": {
            "color": "9799FF",
            "image": "http://www.universalhub.com/images/2007/frenchtoastblue.jpg",
            "description": "Light snow predicted. Subtle grin appears on Harvey Leonard's face. Check car fuel gauge, memorize quickest route to emergency supermarket should conditions change."
        },
        "ELEVATED": {
            "color": "FFFF40",
            "image": "http://www.universalhub.com/images/2007/frenchtoastyellow.jpg",
            "description": "Moderate, plowable snow predicted. Harvey Leonard openly smiles during report. Empty your trunk to make room for milk, eggs and bread. Clear space in refrigerator and head to store for an extra gallon of milk, a spare dozen eggs and a new loaf of bread."
        },
        "HIGH": {
            "color": "FF821D",
            "image": "http://www.universalhub.com/images/2007/frenchtoastorange.jpg",
            "description": "Heavy snow predicted. Harvey Leonard breaks into huge grin, can't keep his hands off the weather map. Proceed at speed limit _before snow starts_ to nearest supermarket to pick up two gallons of milk, a couple dozen eggs and two loaves of bread - per person in household."
        },
        "SEVERE": {
            "color": "F85D58",
            "image": "http://www.universalhub.com/images/2007/frenchtoastred.jpg",
            "description": "Nor'easter predicted. This is it, people, THE BIG ONE. Harvey Leonard makes repeated references to the Blizzard of '78. RUSH to emergency supermarket NOW for multiple gallons of milk, cartons of eggs and loaves of bread. IGNORE cries of little old lady you've just trampled in mad rush to get last gallon of milk. Place pets in basement for use as emergency food supply if needed."
        }
    }

    def __init__(self):
        self.status = self._get_status()
        self.previous_status = self._get_previous_status()
        self.status_changed = self._has_status_changed()
        self.level = self._get_level_from_status()

    def _get_raw_xml(self):
        response = requests.get(self.__class__.TOAST_API_URI)
        response.raise_for_status()

        return response.text

    def _get_status_from_xml(self):
        status = None

        for elem in self._xml:
            if elem.tag == 'status':
                status = elem.text
                break

        if status is None or not isinstance(status, str):
            raise ValueError('A valid status was not found!')

        return status.upper()

    def _get_status(self):
        self._xml = ET.fromstring(self._get_raw_xml())

        return self._get_status_from_xml()

    def _get_level_from_status(self):
        if self.status not in self.__class__.LEVELS.keys():
            raise ValueError('Status "{s}" was not found!'.format(s=self.status))

        return self.__class__.LEVELS[self.status]

    def _get_previous_status(self):
        previous_status = ''

        if os.path.isfile(self.__class__.STATUS_FILE):
            with open(self.__class__.STATUS_FILE) as status_file:
                previous_status = status_file.read()

        return previous_status

    def _has_status_changed(self):
        return self.status != self.previous_status

    def _store_new_status(self):
        with open(self.__class__.STATUS_FILE, 'w') as status_file:
            status_file.write(self.status)

    def _generate_message_content(self):
        return {
            "attachments": [
                {
                    "color": '#{color}'.format(color=self.level['color']),
                    "author_name": "French Toast Alert System",
                    "author_link": "http://www.universalhub.com/french-toast",
                    "title": self.status,
                    "text": self.level['description'],
                    "thumb_url": self.level['image'],
                    "ts": int(time.time())
                }
            ]
        }

    def send_slack_alert(self):
        responses = []

        message_data = self._generate_message_content()

        # Iterate over webhook URLs
        for webhook_url in WEBHOOK_URLS:

            # Make POST request to Slack webhook
            response = requests.post(
                webhook_url,
                data=json.dumps(message_data),
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()

            # Return JSON response
            responses.append({
                "status_code": response.status_code,
                "reason": response.reason
            })

        return responses

    def execute(self):
        if not self.status_changed:
            print('NO CHANGE')
            return

        self._store_new_status()
        pprint(self.send_slack_alert())
