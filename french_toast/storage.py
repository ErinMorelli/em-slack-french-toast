#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Copyright (c) 2018 Erin Morelli

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
from flask.ext.sqlalchemy import SQLAlchemy


# Create database
DB = SQLAlchemy(APP)


class Teams(DB.Model):
    """Table for storing Slack Webhook URLs."""

    __tablename__ = 'french_toast_teams'

    id = DB.Column(DB.String(16), primary_key=True)
    webhook_url = DB.Column(DB.String(255))
    added = DB.Column(DB.DateTime)

    def __init__(self, team_id):
        """Initialize new Team in db."""
        self.id = team_id
        self.added = datetime.now()

    def __repr__(self):
        """Friendly representation of Team for debugging."""
        return '<Team {0}>'.format(self.id)


try:
    # Attempt to initialize database
    DB.create_all()

except:  # pylint: disable=bare-except
    # Other wise, refresh the session
    DB.session.rollback()
