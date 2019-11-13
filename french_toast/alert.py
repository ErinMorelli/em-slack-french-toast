#!/usr/bin/env python
# pylint: disable=no-self-use
# -*- coding: UTF-8 -*-
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

import json
import requests
import logging
from sqlalchemy import cast
from datetime import datetime
import xml.etree.ElementTree as ElementTree
from requests_futures.sessions import FuturesSession

from french_toast.storage import Teams, Status, DB
from french_toast import ALERT_LEVELS, PROJECT_INFO, report_event

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(name)-15s %(message)s',
    level=logging.DEBUG
)


class FrenchToastAlerter(object):
    """Class to check French Toast status and send Slack messages."""

    def __init__(self):
        """Set up French Toast status data."""
        self.logger = logging.getLogger('FrenchToastAlerter')
        self.status = self._get_status()
        self.logger.warning('status: %s', self.status)
        self.timestamp = self._get_status_timestamp()
        self.logger.warning('timestamp: %s', self.timestamp)
        self.previous_status = self._get_previous_status()
        self.logger.warning('previous_status: %s', self.previous_status)
        self.level = self._get_level_from_status()
        self.logger.warning('level: %s', self.level)
        self.status_changed = self._has_status_changed()
        self.logger.warning('status_changed: %s', self.status_changed)

        # Store the new status
        if self.status_changed:
            self._store_new_status()

        # Slack API request message data
        self.msg_data = json.dumps(self._generate_message_content())
        self.logger.warning('msg_data: %s', self.msg_data)

        # Asynchronous API request session
        self.session = FuturesSession()

    @staticmethod
    def _get_raw_xml():
        """Get raw status data from French Toast XML API."""
        try:
            # Attempt to get API data
            response = requests.get(PROJECT_INFO['toast_api_url'])
            response.raise_for_status()

        except requests.exceptions.RequestException as err:
            # Report any errors
            report_event(str(err), {})
            return False

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
            report_event('invalid_xml_status', {
                'status': status
            })
            return status

        # Return in uppercase
        return status.upper()

    def _get_status(self):
        """Get status from XML data."""
        raw_xml = self._get_raw_xml()

        # Check for invalid data
        if not raw_xml:
            return None

        # Parse raw XML data
        self._xml = ElementTree.fromstring(raw_xml)

        return self._get_status_from_xml()

    def _get_level_from_status(self):
        """Get alert level data from status."""
        if self.status not in ALERT_LEVELS.keys():
            report_event('unknown_status', {
                'status': self.status
            })
            return None

        return ALERT_LEVELS[self.status]

    @staticmethod
    def _get_previous_status():
        """Get the previous status from the database."""
        previous = Status.query.get(1)

        return previous.status

    @staticmethod
    def _get_status_timestamp():
        """Get the timestamp of the current status."""
        current = Status.query.get(1)

        return current.updated

    def _has_status_changed(self):
        """Compare the current status to the previously seen status."""
        if (
                self.status is None or
                self.previous_status is None or
                self.level is None
        ):
            report_event('bad_status_change', {
                'status': self.status,
                'previous_status': self.previous_status,
                'level': self.level
            })
            return False

        # If have statuses, compare them
        return self.status != self.previous_status

    def _store_new_status(self):
        """Save new status value to the database."""
        new = Status.query.get(1)
        now = datetime.now()

        # Set status and time updated
        new.status = self.status
        new.updated = now

        # Save changes
        DB.session.commit()

        # Return timestamp
        return now

    def _generate_message_content(self):
        """Generate hash of Slack API message content."""
        timestamp = self._get_status_timestamp()

        # Return JSON-ready hash of message data
        return {
            "attachments": [
                {
                    "color": self.level['color'],
                    "author_name": "French Toast Alert System",
                    "author_link": "http://www.universalhub.com/french-toast",
                    "title": self.level['title'],
                    "text": self.level['text'],
                    "thumb_url": self.level['img'],
                    "ts": timestamp.timestamp()
                }
            ]
        }

    def _send_result(self, session, response):  # pylint: disable=W0613
        """Process the results of sending a message to Slack."""
        # Bail if we're missing a team URL
        if not response.url:
            report_event('missing_team_url', {
                'status_code': response.status_code,
                'reason': response.reason,
                'text': response.text
            })
            return

        # Locate team based on the request URL
        team = Teams.query.filter_by(url=response.url).first()

        # Bail if team not found
        if team is None:
            report_event('team_not_found', {
                'url': response.url
            })
            return

        # Check for team not found
        if response.status_code == 404:
            # Report event
            report_event('team_marked_inactive', {
                'status_code': response.status_code,
                'reason': response.reason,
                'text': response.text,
                'url': response.url,
                'team': team.team_id
            })

            # Mark team as inactive
            team.inactive = True

        elif response.status_code != 200:
            # Report bad request and exit
            report_event('bad_slack_request', {
                'status_code': response.status_code,
                'reason': response.reason,
                'text': response.text,
                'url': response.url
            })
            return

        # Otherwise, update last alerted timestamp
        team.last_alerted = self.timestamp

        # Save changes to database
        DB.session.commit()

    def send_alert(self, team, force=False):
        """Send a single alert message to a given URL."""
        # Only send messages to the team if it hasn't been sent
        if (
                force or
                (team.last_alerted != self.timestamp and not team.inactive)
        ):
            self.session.post(
                team.url,
                data=self.msg_data,
                headers={'Content-Type': 'application/json'},
                hooks={'response': self._send_result}
            )

    def send_alerts(self, force=False):
        """Send Slack messages to all subscribed Teams."""
        # Get a list of team URLs based on last_alerted timestamp
        if force:
            teams = Teams.query.all()
        else:
            teams = Teams.query.filter(
                cast(Teams.last_alerted, DB.DateTime) != self.timestamp
            ).filter_by(
                inactive=False
            ).all()

        # Temporary logging item for debugging
        report_event('sending_alerts', {
            'count': len(teams)
        })

        # Loop over all teams
        for team in teams:
            self.session.post(
                team.url,
                data=self.msg_data,
                headers={'Content-Type': 'application/json'},
                hooks={'response': self._send_result}
            )


def check_status():
    """Run the French Toast alerter."""
    logger = logging.getLogger('FrenchToastAlerter')
    logger.warning('CHECK_STATUS: %s', datetime.now())
    FrenchToastAlerter().send_alerts()
