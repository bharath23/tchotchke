#!/bin/sh

# Create the following crontab entry
# * * * * * /usr/bin/env > $HOME/bin/cron-env
# Once the cron-env file is created you can remove the entry
/usr/bin/env -i $(cat $HOME/bin/cron-env) "$@"
