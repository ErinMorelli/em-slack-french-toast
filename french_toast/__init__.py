#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Copyright (c) 2019 Erin Morelli.

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
from datetime import date
from threading import Thread
from pkg_resources import get_provider
from flask import Flask
import keen


# =============================================================================
#  App Constants
# =============================================================================

# Set module name
__module__ = "french_toast.{0}".format(__file__)


# Get module info
def set_project_info():
    """Set project information from setup tools installation."""
    base_url = 'https://slack-french-toast.herokuapp.com'

    # Get app info from the dist
    app_name = 'french_toast'
    provider = get_provider(app_name)

    return {
        'name': app_name,
        'name_full': 'EM Slack French Toast',
        'author_url': 'http://www.erinmorelli.com',
        'github_url': 'https://github.com/ErinMorelli/em-slack-french-toast',
        'version': '2.0',
        'version_int': 2.0,
        'package_path': provider.module_path,
        'copyright': str(date.today().year),
        'client_secret': os.environ['SLACK_CLIENT_SECRET'],
        'client_id': os.environ['SLACK_CLIENT_ID'],
        'queue_name': os.environ['SQS_QUEUE_NAME'],
        'queue_region': os.environ['AWS_DEFAULT_REGION'],
        'access_key': os.environ['AWS_ACCESS_KEY_ID'],
        'secret_key': os.environ['AWS_SECRET_ACCESS_KEY'],
        'base_url': base_url,
        'oauth_url': 'https://slack.com/oauth/authorize',
        'auth_url': '{0}/authenticate'.format(base_url),
        'valid_url': '{0}/validate'.format(base_url),
        'toast_api_url': 'https://www.universalhub.com/toast.xml',
        'team_scope': [
            'incoming-webhook'
        ]
    }


# Project info
PROJECT_INFO = set_project_info()

# Set the template directory
TEMPLATE_DIR = os.path.join(PROJECT_INFO['package_path'], 'templates')

# Set the French Toast alert levels
# Content taken directly from http://www.universalhub.com/french-toast
ALERT_LEVELS = {
    "LOW": {
        "color": "#97FF9B",
        "img": "http://www.universalhub.com/images/2007/frenchtoastgreen.jpg",
        "title": "1 Slice / Low",
        "text": ("No storm predicted. Harvey Leonard sighs and looks dour on "
                 "the evening news. Go about your daily business but consider "
                 "buying second refrigerator for basement, diesel generator. "
                 "Good time to replenish stocks of maple syrup, cinnamon.")
    },
    "GUARDED": {
        "color": "#9799FF",
        "img": "http://www.universalhub.com/images/2007/frenchtoastblue.jpg",
        "title": "2 Slices / Guarded",
        "text": ("Light snow predicted. Subtle grin appears on Harvey "
                 "Leonard's face. Check car fuel gauge, memorize quickest "
                 "route to emergency supermarket should conditions change.")
    },
    "ELEVATED": {
        "color": "#FFFF40",
        "img": "http://www.universalhub.com/images/2007/frenchtoastyellow.jpg",
        "title": "3 Slices / Elevated",
        "text": ("Moderate, plowable snow predicted. Harvey Leonard openly "
                 "smiles during report. Empty your trunk to make room for "
                 "milk, eggs and bread. Clear space in refrigerator and head "
                 "to store for an extra gallon of milk, a spare dozen eggs "
                 "and a new loaf of bread.")
    },
    "HIGH": {
        "color": "#FF821D",
        "img": "http://www.universalhub.com/images/2007/frenchtoastorange.jpg",
        "title": "4 Slices / High",
        "text": ("Heavy snow predicted. Harvey Leonard breaks into huge grin, "
                 "can't keep his hands off the weather map. Proceed at speed "
                 "limit _before snow starts_ to nearest supermarket to pick "
                 "up two gallons of milk, a couple dozen eggs and two loaves "
                 "of bread - per person in household.")
    },
    "SEVERE": {
        "color": "#F85D58",
        "img": "http://www.universalhub.com/images/2007/frenchtoastred.jpg",
        "title": "5 Slices / Severe",
        "text": ("Nor'easter predicted. This is it, people, THE BIG ONE. "
                 "Harvey Leonard makes repeated references to the Blizzard "
                 "of '78. RUSH to emergency supermarket NOW for multiple "
                 "gallons of milk, cartons of eggs and loaves of bread. "
                 "IGNORE cries of little old lady you've just trampled in "
                 "mad rush to get last gallon of milk. Place pets in basement "
                 "for use as emergency food supply if needed.")
    }
}


def report_event(name, event):
    """Asynchronously report an event."""
    # Set up thread
    event_report = Thread(
        target=keen.add_event,
        args=(name, event)
    )

    # Set up as asynchronous daemon
    event_report.daemon = True

    # Start event report
    event_report.start()


# =============================================================================
# Flask App Configuration
# =============================================================================

# Initialize flask app
APP = Flask(
    'em-slack-french-toast',
    template_folder=TEMPLATE_DIR,
    static_folder=TEMPLATE_DIR
)

# Set up flask config
APP.config.update({
    'SECRET_KEY': os.environ['SECURE_KEY'],
    'SQLALCHEMY_DATABASE_URI': os.environ['DATABASE_URL'],
    'SQLALCHEMY_TRACK_MODIFICATIONS': True
})
