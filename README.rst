telegram-scraper-bot
====================

Overview
--------

Scraper bot for Telegram.

Requirements
------------

-  `Python >=3.7 <https://www.python.org/>`__

Installation
------------

.. code:: bash

    git clone https://github.com/dead-beef/telegram-scraper-bot
    cd telegram-scraper-bot
    python3 -m venv
    python3 -m venv --system-site-packages env
    source env/bin/activate
    pip install -e .[ig,dev]

Usage
-----

::

    usage: python -m bot [-h] [-l {critical,error,warning,info,debug}] [-w] [-s] FILE

    positional arguments:
      FILE                  config file

    optional arguments:
      -h, --help            show this help message and exit
      -l {critical,error,warning,info,debug}, --log-level {critical,error,warning,info,debug}
                            log level (default: info)
      -w, --watch
      -s, --single-run      (default)

Config
------

::
    {
      "token": "<token>",
      "proxy": "<scheme>://<host>:<port>",
      "public_admin_commands_enabled": <if true, enable admin commands in public chats/channels>,
      "last_update_id": -1,
      "update_timeout": <long polling timeout in seconds>,
      "link_update_interval": <seconds>,
      "connections_limit": <max bot api connections>,
      "loader": {
        "user_agent": "<user agent>",
        "min_delay": <min delay in seconds before loading a link>,
        "max_delay": <max delay in seconds before loading a link>,
        "max_connections": <max loader connections>,
        "max_connections_per_host": <max loader connections per host>,
        "max_workers": <max sync request threads>,
        "cookies": {
          "<url>": {
            "<key>": "<value>"
            , ...
          }
          , ...
        }
      },
      "admins": [
        <user id>
        , ...
      ],
      "chats": []
    }

Commands
--------

::
    commands:
      /start, /help - bot help
      /chatinfo - show chat info

    admin commands:
      /watch <url> - add link to current chat
      /unwatch <url> - remove link from current chat
      /unwatch - remove all links from current chat
      /admin [user_id or reply] - add bot admin
      /admin [user_id or reply] false - remove bot admin

    admin commands in private chat:
      /watch <chat_id> <url> - add link to chat by id
      /unwatch <chat_id> <url> - remove link from chat by id
      /unwatch <chat_id> - remove all links from chat by id

Testing
-------

.. code:: bash

    ./test

Licenses
--------

-  `telegram-scraper-bot <LICENSE>`__
