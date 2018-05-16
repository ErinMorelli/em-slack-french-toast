#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# pylint: disable=invalid-name
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

from datetime import datetime
from french_toast import APP
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError

# Create database
DB = SQLAlchemy(APP)


class Teams(DB.Model):  # pylint: disable=too-few-public-methods
    """Table for storing Slack Webhook URLs."""

    __tablename__ = 'french_toast_teams'

    id = DB.Column(DB.Integer, primary_key=True)
    team_id = DB.Column(DB.String(16))
    channel_id = DB.Column(DB.String(16))
    url = DB.Column(DB.String(255), unique=True)
    added = DB.Column(DB.DateTime, default=datetime.now)
    last_alerted = DB.Column(DB.DateTime)
    inactive = DB.Column(DB.Boolean, default=False)

    def __init__(self, team_id, channel_id, url):
        """Initialize new Team in db."""
        self.team_id = team_id
        self.channel_id = channel_id
        self.url = url

    def __repr__(self):
        """Friendly representation of Team for debugging."""
        return '<Team id={id} team={team} channel={channel}>'.format(
            id=self.id,
            team=self.team_id,
            channel=self.channel_id
        )


class Status(DB.Model):  # pylint: disable=too-few-public-methods
    """Table for storing current French Toast status."""

    __tablename__ = 'french_toast_status'

    id = DB.Column(DB.Integer, primary_key=True, default=1)
    status = DB.Column(DB.String(16))
    updated = DB.Column(DB.DateTime, default=datetime.now)

    DB.CheckConstraint('id == 1', name='has_id')

    def __init__(self, status):
        """Initialize new status in db."""
        self.status = status

    def __repr__(self):
        """Friendly representation of Status for debugging."""
        return '<Status "{status}" at {updated}>'.format(
            status=self.status,
            updated=str(self.updated)
        )


try:
    # Attempt to initialize database
    DB.create_all()

except SQLAlchemyError:
    # Other wise, refresh the session
    DB.session.rollback()
