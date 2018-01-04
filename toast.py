#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime
from french_toast.app import APP
from french_toast import EmSlackFrenchToast
from apscheduler.schedulers.blocking import BlockingScheduler


def check_alert_status():
    print(str(datetime.now()))
    EmSlackFrenchToast().execute()


def main():
    scheduler = BlockingScheduler()
    scheduler.add_job(check_alert_status, 'interval', minutes=1)
    scheduler.start()


if __name__ == '__main__':
    # main()

    # Start Flask app
    APP.run(host='0.0.0.0', port=int(environ.get("PORT", 5000)))
