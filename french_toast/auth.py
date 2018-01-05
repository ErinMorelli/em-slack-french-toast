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

from datetime import timedelta
from urllib.parse import urlencode
from flask import abort
from slacker import OAuth, Error
from french_toast import PROJECT_INFO, report_event
from french_toast.storage import Teams, DB
from french_toast.alert import FrenchToastAlerter
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

# Create serializer
GENERATOR = URLSafeTimedSerializer(PROJECT_INFO['client_secret'])


def get_redirect():
    """Generate Slack authentication URL."""
    # Generate state token
    state_token = GENERATOR.dumps(PROJECT_INFO['client_id'])

    # URL encode params
    params = urlencode({
        'client_id': PROJECT_INFO['client_id'],
        'redirect_uri': PROJECT_INFO['valid_url'],
        'scope': ' '.join(PROJECT_INFO['team_scope']),
        'state': state_token
    })

    # Set full location
    location = "{0}?{1}".format(PROJECT_INFO['oauth_url'], params)

    # Return URL for redirect
    return location


def validate_state(state):
    """Validate state token returned by authentication."""
    try:
        # Attempt to decode state
        state_token = GENERATOR.loads(
            state,
            max_age=timedelta(minutes=60).total_seconds()
        )

    except SignatureExpired:
        # Token has expired
        report_event('token_expired', {
            'state': state
        })
        abort(400)

    except BadSignature:
        # Token is not authorized
        report_event('token_not_authorized', {
            'state': state
        })
        abort(401)

    if state_token != PROJECT_INFO['client_id']:
        # Token is not authorized
        report_event('token_not_valid', {
            'state': state,
            'state_token': state_token
        })
        abort(401)


def get_token(code):
    """Request a token from the Slack API."""
    # Set OAuth access object
    oauth = OAuth()

    try:
        # Attempt to make request
        result = oauth.access(
            client_id=PROJECT_INFO['client_id'],
            client_secret=PROJECT_INFO['client_secret'],
            redirect_uri=PROJECT_INFO['valid_url'],
            code=code
        )

    except Error as err:
        report_event('oauth_error', {
            'code': code,
            'error': str(err)
        })
        abort(400)

    if not result.successful:
        report_event('oauth_unsuccessful', {
            'code': code,
            'result': result.__dict__
        })
        abort(400)

    # Setup return info
    info = {
        'team_id': result.body['team_id'],
        'channel_id': result.body['incoming_webhook']['channel_id'],
        'url': result.body['incoming_webhook']['url']
    }

    # Return info
    return info


def store_data(info):
    """Store validated data in the database."""
    # Check if user exists
    team = Teams.query.filter_by(
        team_id=info['team_id'],
        channel_id=info['channel_id']
    ).first()

    if team is None:
        # Create new team
        new_team = Teams(
            team_id=info['team_id'],
            channel_id=info['channel_id'],
            url=info['url']
        )

        # Store new user
        report_event('team_added', info)
        DB.session.add(new_team)

        # Update DB
        DB.session.commit()

        # Return new team object
        return new_team

    # Update team info
    team.url = info['url']
    report_event('team_updated', info)

    # Update DB
    DB.session.commit()

    # Return team object
    return team


def send_initial_alert(team):
    """Send an initial alert to the team."""
    alerter = FrenchToastAlerter()
    alerter.send_alert(team, True)


def validate_return(args):
    """Run data validation functions."""
    # Make sure we have args
    if not args['state'] or not args['code']:
        report_event('missing_args', args)
        abort(400)

    # Validate state
    validate_state(args['state'])

    # Get access token and info
    token_info = get_token(args['code'])

    # Set up storage methods
    team = store_data(token_info)

    # Send initial alert
    send_initial_alert(team)

    # Set success url
    redirect_url = '{0}?success=1'.format(PROJECT_INFO['base_url'])

    # Return successful
    return redirect_url
