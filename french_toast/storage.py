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
from datetime import datetime

from cryptography.fernet import Fernet
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError

from . import app

# Create database
db = SQLAlchemy(app)


class Teams(db.Model):
    """Table for storing Slack Webhook URLs."""
    __tablename__ = 'french_toast_teams'
    __cipher = Fernet(os.environ.get('TOKEN_KEY', '').encode('utf8'))

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.String(16))
    channel_id = db.Column(db.String(16))
    url = db.Column(db.String(255), unique=True)
    encrypted_url = db.Column(db.BLOB)
    added = db.Column(db.DateTime, default=datetime.now)
    last_alerted = db.Column(db.DateTime)
    inactive = db.Column(db.Boolean, default=False)

    def __init__(self, team_id, channel_id, url):
        """Initialize new Team in db."""
        self.team_id = team_id
        self.channel_id = channel_id
        self.set_url(url)

    def set_url(self, url):
        """Encrypt and set url value ."""
        if not isinstance(url, bytes):
            url = url.encode('utf-8')
        self.encrypted_url = self.__cipher.encrypt(url)

    def get_token(self):
        """Retrieve decrypted URL."""
        return self.__cipher.decrypt(self.url).decode('utf-8')

    def __repr__(self):
        """Friendly representation of Team for debugging."""
        active = ' [INACTIVE]' if self.inactive else ''
        return f'<Team id={self.id} last_alerted={self.last_alerted}{active}>'


class Status(db.Model):
    """Table for storing current French Toast status."""
    __tablename__ = 'french_toast_status'

    id = db.Column(db.Integer, primary_key=True, default=1)
    status = db.Column(db.String(16))
    updated = db.Column(db.DateTime)

    db.CheckConstraint('id == 1', name='has_id')

    def __init__(self, status, updated):
        """Initialize new status in db."""
        self.status = status
        self.updated = updated

    def __repr__(self):
        """Friendly representation of Status for debugging."""
        return f'<Status "{self.status}" at {self.updated}>'


try:
    # Attempt to initialize database
    db.create_all()
except SQLAlchemyError:
    # Other wise, refresh the session
    db.session.rollback()
