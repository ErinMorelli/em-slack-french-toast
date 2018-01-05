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

import os
from setuptools import setup


def gen_data_files(*dirs):
    """Generate list of files for package data installation."""
    results = []

    for src_dir in dirs:
        src_dir = os.path.join('french_toast', src_dir)
        for root, dirs, files in os.walk(src_dir):
            top = root.split(os.sep)
            top.pop(0)
            root = (os.sep).join(top)
            for item in files:
                results.append(os.path.join(root, item))
    return results


# Set up french_toast package
setup(
    name='em-slack-french-toast',
    version='1.2',
    author='Erin Morelli',
    author_email='erin@erinmorelli.com',
    url='http://slack-french-toast.herokuapp.com',
    license='MIT',
    platforms='Linux, OSX',
    # description='Roll some dice on Slack.',
    long_description=open('README.md').read(),

    packages=[
        'french_toast',
        'french_toast.templates'
    ],

    package_data={
        'french_toast': gen_data_files('templates')
    },

    install_requires=[
        'Flask',
        'Flask-SQLAlchemy',
        'Flask-APScheduler',
        'newrelic',
        'keen',
        'pkginfo',
        'psycopg2',
        'requests',
        'requests_futures',
        'slacker'
    ]
)
