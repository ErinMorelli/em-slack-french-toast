#!/usr/bin/env python
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
import pika


def main():
    """Send a message to the status check queue."""
    amqp_queue_name = os.environ.get('CLOUDAMQP_QUEUE_NAME')
    amqp_url = os.environ.get('CLOUDAMQP_URL')

    # Set up connection
    connection = pika.BlockingConnection(pika.URLParameters(amqp_url))
    channel = connection.channel()
    channel.queue_declare(queue=amqp_queue_name)

    # Send message
    channel.basic_publish(exchange='',
                          routing_key=amqp_queue_name,
                          body=b'Status check')

    # Close connection
    connection.close()


if __name__ == '__main__':
    main()
