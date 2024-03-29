#!/usr/bin/env python
# -*- coding: UTF-8 -*-
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

from flask import redirect, render_template, request

import french_toast.auth as auth
from french_toast import app, project_info


@app.route('/')
def home():
    """Render app homepage template."""
    return render_template('index.html', project=project_info)


@app.route('/authenticate')
def authenticate():
    """Redirect to generated Slack authentication url."""
    return redirect(auth.get_redirect())


@app.route('/validate')
def validate():
    """Validate the returned values from authentication."""
    return redirect(auth.validate_return(request.args.to_dict()))
