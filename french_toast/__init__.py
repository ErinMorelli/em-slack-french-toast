"""
Copyright (c) 2021 Erin Morelli.

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

import keen
from flask import Flask
from pkg_resources import get_provider


# Common project metadata
__version__ = open('VERSION').read()
__app_name__ = 'EM Slack French Toast'
__copyright__ = f'2018-{str(date.today().year)}'

# Project URLs
base_url = os.environ.get('BASE_URL')
github_url = os.environ.get('GITHUB_URL')

# Get module info
project_info = {
    'name': __app_name__,
    'version': __version__,
    'copyright': __copyright__,
    'base_url': base_url,
    'github_url': github_url,
    'client_secret': os.environ.get('SLACK_CLIENT_SECRET'),
    'client_id': os.environ.get('SLACK_CLIENT_ID'),
    'oauth_url': os.environ.get('OAUTH_URL'),
    'auth_url': f'{base_url}/authenticate',
    'valid_url': f'{base_url}/validate',
    'toast_api_url': os.environ['TOAST_API_URL'],
    'toast_link_url': os.environ['TOAST_LINK_URL'],
    'team_scope': [
        'incoming-webhook'
    ]
}

# Set the template directory
template_dir = os.path.join(get_provider(__name__).module_path, 'templates')

# Set the French Toast alert levels
# Content taken directly from http://www.universalhub.com/french-toast
alert_levels = {
    "LOW": {
        "color": "#97FF9B",
        "img": "https://www.universalhub.com/images/2007/frenchtoastgreen.jpg",
        "title": "1 Slice / Low",
        "text": ("No storm predicted. Harvey Leonard sighs and looks dour on "
                 "the evening news. Go about your daily business but consider "
                 "buying second refrigerator for basement, diesel generator. "
                 "Good time to replenish stocks of maple syrup, cinnamon.")
    },
    "GUARDED": {
        "color": "#9799FF",
        "img": "https://www.universalhub.com/images/2007/frenchtoastblue.jpg",
        "title": "2 Slices / Guarded",
        "text": ("Light snow predicted. Subtle grin appears on Harvey "
                 "Leonard's face. Check car fuel gauge, memorize quickest "
                 "route to emergency supermarket should conditions change.")
    },
    "ELEVATED": {
        "color": "#FFFF40",
        "img": "https://www.universalhub.com/images/2007/frenchtoastyellow.jpg",
        "title": "3 Slices / Elevated",
        "text": ("Moderate, plowable snow predicted. Harvey Leonard openly "
                 "smiles during report. Empty your trunk to make room for "
                 "milk, eggs and bread. Clear space in refrigerator and head "
                 "to store for an extra gallon of milk, a spare dozen eggs "
                 "and a new loaf of bread.")
    },
    "HIGH": {
        "color": "#FF821D",
        "img": "https://www.universalhub.com/images/2007/frenchtoastorange.jpg",
        "title": "4 Slices / High",
        "text": ("Heavy snow predicted. Harvey Leonard breaks into huge grin, "
                 "can't keep his hands off the weather map. Proceed at speed "
                 "limit _before snow starts_ to nearest supermarket to pick "
                 "up two gallons of milk, a couple dozen eggs and two loaves "
                 "of bread - per person in household.")
    },
    "SEVERE": {
        "color": "#F85D58",
        "img": "https://www.universalhub.com/images/2007/frenchtoastred.jpg",
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

# Initialize flask app
app = Flask(
    'em-slack-french-toast',
    template_folder=template_dir,
    static_folder=template_dir
)

# Set up flask config
app.config.update({
    'SECRET_KEY': os.environ.get('SECURE_KEY'),
    'SQLALCHEMY_DATABASE_URI': os.environ.get('DATABASE_URL'),
    'SQLALCHEMY_TRACK_MODIFICATIONS': True
})


def report_event(name, event):
    """Asynchronously report an event."""
    event_report = Thread(
        target=keen.add_event,
        args=(name, event)
    )

    # Set up as asynchronous daemon
    event_report.daemon = True

    # Start event report
    event_report.start()
