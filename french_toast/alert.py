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
import logging
import threading
from datetime import datetime
import xml.etree.ElementTree as ElementTree

import requests
from sqs_listener import SqsListener

from french_toast.storage import Teams, Status, DB
from french_toast import ALERT_LEVELS, PROJECT_INFO, report_event

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(name)-15s %(message)s',
    level=logging.INFO
)


class FrenchToastAlerter:
    """Class to check French Toast status and send Slack messages."""

    queue_name = PROJECT_INFO['queue_name']
    queue_args = {
        'force_delete': True,
        'interval': 60,  # 1 mins
        'visibility_timeout': 300,  # 5 mins
    }

    def __init__(self):
        """Set up French Toast status data."""
        self.logger = logging.getLogger('FrenchToastAlerter')

        self.current_status = self._get_current_status()
        self.status = self.current_status.status
        self.timestamp = self.current_status.updated
        self.level = self._get_level_from_status(self.status)
        self._xml = None

        # Asynchronous API request session
        self.session = requests.Session()
        self.session.hooks['response'] = self._response_hook

    def check_status(self):
        """Check for a new status value on universal hub."""
        self._refresh_current()

        # Get new values
        new_status = self._get_status()
        new_level = self._get_level_from_status(new_status)
        self.logger.info(
            'status check: current=%s, new=%s', self.status, new_status)

        # Report any bad data
        if new_status is None or new_level is None:
            self.logger.error('bad status change')
            report_event('bad_status_change', {
                'status': new_status,
                'level': new_level
            })
            return False

        # Check for status change
        status_changed = (new_status != self.status)

        # Store the new status
        if status_changed:
            self._store_new_status(new_status)
            self.logger.warning('new status: %s', self.status)

        return status_changed

    def send_alert(self, team):
        """Send a single alert message to a given URL."""
        self.session.post(
            team.url,
            data=self._get_message_content(),
            headers={'Content-Type': 'application/json'}
        )

    def send_alerts(self, force=False):
        """Send Slack messages to all subscribed Teams."""
        # pylint: disable=singleton-comparison
        # Get a list of team URLs based on last_alerted timestamp
        teams = Teams.query.filter(Teams.inactive == False).all()  # noqa: E712
        self.logger.info('team count: %s', len(teams))

        # Generate message
        msg_data = self._get_message_content()

        # Loop over all teams
        for team in teams:
            if force or team.last_alerted != self.timestamp:
                self.logger.info('alerting team: %s', team)
                self.session.post(
                    team.url,
                    data=msg_data,
                    headers={'Content-Type': 'application/json'}
                )

    def alert(self):
        """Check for new status and send alerts."""
        status_has_changed = self.check_status()
        self.logger.info('status_has_changed: %s', status_has_changed)

        # Only send alerts if we saw the status change
        if status_has_changed:
            self.logger.info('sending alerts')
            self.send_alerts()

    def run(self):
        """Start the SQS listener."""
        self.logger.info('starting the alerting job.')
        self._listener.listen()

    def run_daemon(self):
        """Start the SQS daemon."""
        self.logger.info('starting the alerting daemon.')
        self._daemon.start()

    @property
    def _daemon(self):
        """Start the SQS listener daemon."""
        daemon = threading.Thread(
            name="french_toast_status",
            target=self._listener.listen
        )
        daemon.setDaemon(True)
        return daemon

    @property
    def _listener(self):
        """Create SQS listener object."""
        class FrenchToastListener(SqsListener):
            """Custom SqsListener object configuration."""

            class_ = self
            logger = logging.getLogger('sqs_listener')

            def __init__(self, queue, **kwargs):
                self.logger.info('initializing listener')
                super().__init__(queue, **kwargs)

            def handle_message(self, body, _1, _2):
                self.logger.info('handle_message: %s', body)
                self.class_.alert()

        return FrenchToastListener(self.queue_name, **self.queue_args)

    def _refresh_current(self):
        """Refresh the current status data."""
        self.current_status = self._get_current_status()
        self.status = self.current_status.status
        self.timestamp = self.current_status.updated
        self.level = self._get_level_from_status(self.status)

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
            self.logger.error('invalid xml status: %s', status)
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

    def _get_level_from_status(self, status):
        """Get alert level data from status."""
        if status not in ALERT_LEVELS.keys():
            self.logger.error('unknown status: %s', status)
            report_event('unknown_status', {
                'status': status
            })
            return None

        return ALERT_LEVELS[status]

    @staticmethod
    def _get_current_status():
        """Get the current status from the database."""
        return Status.query.get(1)

    def _store_new_status(self, status):
        """Save new status value to the database."""
        new = Status.query.get(1)
        now = datetime.now()

        # Set status and time updated
        new.status = status
        new.updated = now

        # Save changes
        DB.session.commit()

        # Update the class variables
        self._refresh_current()

    def _get_message_content(self):
        """Generate JSON for the Slack API message content."""
        return json.dumps({
            "attachments": [
                {
                    "color": self.level['color'],
                    "author_name": "French Toast Alert System",
                    "author_link": "http://www.universalhub.com/french-toast",
                    "title": self.level['title'],
                    "text": self.level['text'],
                    "thumb_url": self.level['img'],
                    "ts": self.timestamp.timestamp()
                }
            ]
        })

    def _response_hook(self, resp, *args, **kwargs):  # pylint: disable=W0613
        """Process the results of sending a message to Slack."""
        # Bail if we're missing a team URL
        if not resp.url:
            self.logger.error('missing team url')
            report_event('missing_team_url', {
                'status_code': resp.status_code,
                'reason': resp.reason,
                'text': resp.text
            })
            return

        # Locate team based on the request URL
        team = Teams.query.filter(Teams.url == resp.url).first()
        self.logger.info('updating team: %s', team)

        # Bail if team not found
        if team is None:
            self.logger.error('team not found')
            report_event('team_not_found', {
                'url': resp.url
            })
            return

        # Check for team not found
        if resp.status_code == 404:
            # Report event
            self.logger.error('team marked inactive')
            report_event('team_marked_inactive', {
                'status_code': resp.status_code,
                'reason': resp.reason,
                'text': resp.text,
                'url': resp.url,
                'team': team.team_id
            })

            # Mark team as inactive
            team.inactive = True

        elif resp.status_code != 200:
            # Report bad request and exit
            self.logger.error('bad slack request')
            report_event('bad_slack_request', {
                'status_code': resp.status_code,
                'reason': resp.reason,
                'text': resp.text,
                'url': resp.url
            })
            return

        # Otherwise, update last alerted timestamp
        team.last_alerted = self.timestamp

        # Save changes to database
        DB.session.commit()
