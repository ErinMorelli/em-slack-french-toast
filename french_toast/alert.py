#!/usr/bin/env python
# -*- coding: UTF-8 -*-
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

import json
import time
from datetime import datetime
import xml.etree.ElementTree as ET
import requests
from french_toast.storage import Teams, Status, DB
from french_toast import ALERT_LEVELS, PROJECT_INFO
from requests_futures.sessions import FuturesSession


class FrenchToastAlerter(object):
    """Class to check French Toast status and send Slack messages."""

    def __init__(self):
        """Set up French Toast status data."""
        self.status = self._get_status()
        self.previous_status = self._get_previous_status()
        self.status_changed = self._has_status_changed()
        self.level = self._get_level_from_status()

        # Slack API request message data
        self.msg_data = json.dumps(self._generate_message_content())

        # Asynchronous API request session
        self.session = FuturesSession()

    def _get_raw_xml(self):
        """Get raw status data from French Toast XML API."""
        response = requests.get(PROJECT_INFO['toast_api_url'])
        response.raise_for_status()

        # Only return the text data
        return response.text

    def _get_status_from_xml(self):
        """Parse raw XML data to retrieve status."""
        status = None

        # Only return the 'status' element
        for elem in self._xml:
            if elem.tag == 'status':
                status = elem.text
                break

        # Check that a valid status was found
        if status is None or not isinstance(status, str):
            raise ValueError('A valid status was not found!')

        # Return in uppercase
        return status.upper()

    def _get_status(self):
        """Get status from XML data."""
        self._xml = ET.fromstring(self._get_raw_xml())

        return self._get_status_from_xml()

    def _get_level_from_status(self):
        """Get alert level data from status."""
        if self.status not in ALERT_LEVELS.keys():
            raise ValueError('Status "{s}" not found!'.format(s=self.status))

        return ALERT_LEVELS[self.status]

    def _get_previous_status(self):
        """Get the previous status from the database."""
        previous = Status.query.get(1)

        return previous.status

    def _has_status_changed(self):
        """Compare the current status to the previously seen status."""
        return self.status != self.previous_status

    def _store_new_status(self):
        """Save new status value to the database."""
        new = Status.query.get(1)

        # Set status and time updated
        new.status = self.status
        new.updated = datetime.now()

        # Save changes
        DB.session.commit()

    def _generate_message_content(self):
        """Generate hash of Slack API message content."""
        return {
            "attachments": [
                {
                    "color": '#{color}'.format(color=self.level['color']),
                    "author_name": "French Toast Alert System",
                    "author_link": "http://www.universalhub.com/french-toast",
                    "title": self.status,
                    "text": self.level['desc'],
                    "thumb_url": self.level['img'],
                    "ts": int(time.time())
                }
            ]
        }

    def _get_send_urls(self):
        """Get array of Slack URLs to make API requests to from database."""
        teams = DB.session.query(Teams.url).all()

        # Convert list of tuples into a list of strings
        urls = [url[0] for url in teams]

        return urls

    def _send_result(self, session, response):
        """Make POST request to a given Slack webhook URL."""
        print(response)

    def send_alerts(self):
        """Send Slack messages to all subscribed Teams."""
        urls = self._get_send_urls()

        # Loop over all URLs
        for url in urls:
            self.session.post(
                url,
                data=self.msg_data,
                headers={'Content-Type': 'application/json'},
                background_callback=self._send_result
            )

    def execute(self):
        """Run the alerting functions."""
        # Don't do anything if the status hasn't changed
        if not self.status_changed:
            return

        # Save the new status so this doesn't get run again
        self._store_new_status()

        # Send alerts to webhook URLs
        self._send_alerts()


def check_status():
    """Run the French Toast alerter."""
    FrenchToastAlerter().execute()
