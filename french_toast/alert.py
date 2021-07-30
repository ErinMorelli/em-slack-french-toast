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
import re
import json
import logging
import threading
from datetime import datetime
import xml.etree.ElementTree as ElementTree

import pika
import requests

from .storage import Teams, Status, db
from . import alert_levels, project_info, report_event


logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(name)-15s %(message)s',
    level=logging.INFO
)


class FrenchToastAlerter:
    """Class to check French Toast status and send Slack messages."""

    amqp_queue_name = os.environ.get('CLOUDAMQP_QUEUE_NAME')
    ampq_url = os.environ.get('CLOUDAMQP_URL')

    def __init__(self):
        """Set up French Toast status data."""
        self.logger = logging.getLogger(self.__class__.__name__)

        self.current_status = self._get_current_status()
        self.status = self.current_status.status
        self.timestamp = self.current_status.updated
        self.level = self._get_level_from_status(self.status)

        # Asynchronous API request session
        self.session = requests.Session()

    def check_status(self):
        """Check for a new status value on universal hub."""
        self._refresh_current()

        # Get new values
        new_status = self._get_status()
        new_level = self._get_level_from_status(new_status)
        self.logger.info('Status: current=%s, new=%s', self.status, new_status)

        # Report any bad data
        if new_status is None or new_level is None:
            self.logger.error('Bad status change')
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
            self.logger.warning('New status: %s', self.status)

        return status_changed

    def send_alert(self, team):
        """Send a single alert message to a given URL."""
        self.logger.info('Alerting team: %s', team)
        resp = self.session.post(
            team.url,
            data=self._get_message_content(),
            headers={'Content-Type': 'application/json'}
        )
        self._check_response(team, resp)

    def send_alerts(self, force=False):
        """Send Slack messages to all subscribed Teams."""
        teams = Teams.query.filter(Teams.inactive == False).all()  # noqa: E712
        self.logger.info('Team count: %s', len(teams))

        # Loop over all teams
        for team in teams:
            if force or team.last_alerted != self.timestamp:
                self.send_alert(team)

    def alert(self):
        """Check for new status and send alerts."""
        def wrapper(*_):
            status_has_changed = self.check_status()
            self.logger.info('Status changed: %s', status_has_changed)

            # Only send alerts if we saw the status change
            if status_has_changed:
                self.logger.info('Sending alerts')
                self.send_alerts()
        return wrapper

    def run(self):
        """Start the AMQP consumer."""
        def wrapper():
            self.logger.info('Waiting for messages...')
            self._channel.start_consuming()
        return wrapper

    def run_daemon(self):
        """Start the AMQP daemon."""
        self.logger.info('Starting the queue daemon.')
        self._daemon.start()

    @property
    def _daemon(self):
        """Start the AMQP consumer daemon."""
        return threading.Thread(name=self.amqp_queue_name,
                                target=self.run(),
                                daemon=True)

    @property
    def _channel(self):
        """Create AMQP channel object."""
        connection = pika.BlockingConnection(pika.URLParameters(self.ampq_url))
        channel = connection.channel()
        channel.queue_declare(queue=self.amqp_queue_name)
        channel.basic_consume(queue=self.amqp_queue_name,
                              auto_ack=True,
                              on_message_callback=self.alert())
        return channel

    def _refresh_current(self):
        """Refresh the current status data."""
        self.current_status = self._get_current_status()
        self.status = self.current_status.status
        self.timestamp = self.current_status.updated
        self.level = self._get_level_from_status(self.status)

    def _get_status(self):
        """Parse raw XML data to retrieve status."""
        status = None

        try:
            # Attempt to get API data
            response = requests.get(project_info['toast_api_url'])
            response.raise_for_status()
        except requests.exceptions.RequestException as err:
            # Report any errors
            report_event(str(err), {})
            return None

        # Parse raw XML data
        xml = ElementTree.fromstring(response.text)

        # Only return the 'status' element
        for elem in xml:
            if elem.tag == 'status':
                status = elem.text
                break

        # Check that a valid status was found
        if status is None or not isinstance(status, str):
            self.logger.error('Invalid xml status: %s', status)
            report_event('invalid_xml_status', {'status': status})
            return status

        # Return in uppercase
        return status.upper()

    def _get_level_from_status(self, status):
        """Get alert level data from status."""
        for level, level_data in alert_levels.items():
            if re.search(level, status, re.I):
                return level_data

        self.logger.error('Unknown status: %s', status)
        report_event('unknown_status', {'status': status})
        return None

    @staticmethod
    def _get_current_status():
        """Get the current status from the database."""
        return Status.query.get(1)

    def _store_new_status(self, status):
        """Save new status value to the database."""
        new = self._get_current_status()
        now = datetime.now()

        # Set status and time updated
        new.status = status
        new.updated = now

        # Save changes
        db.session.commit()

        # Update the class variables
        self._refresh_current()

    def _get_message_content(self):
        """Generate JSON for the Slack API message content."""
        return json.dumps({
            "attachments": [
                {
                    "color": self.level['color'],
                    "author_name": "French Toast Alert System",
                    "author_link": project_info['toast_link_url'],
                    "title": self.level['title'],
                    "text": self.level['text'],
                    "thumb_url": self.level['img'],
                    "ts": self.timestamp.timestamp()
                }
            ]
        })

    def _check_response(self, team, resp):
        """Process the results of sending a message to Slack."""
        self.logger.info('Updating team: %s', team)

        # Check for team not found
        if resp.status_code == 404:
            # Report event
            self.logger.error('Team marked inactive')
            report_event('team_marked_inactive', {
                'status_code': resp.status_code,
                'reason': resp.reason,
                'text': resp.text,
                'team': team.team_id
            })

            # Mark team as inactive
            team.inactive = True

        elif resp.status_code != 200:
            # Report bad request and exit
            self.logger.error('Bad slack request')
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
        db.session.commit()
