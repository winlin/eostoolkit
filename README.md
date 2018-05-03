# eostoolkit

Thie repository is a collection of EOSBIXIN toolkit for maintaining EOSIO node machine.
## Function list 

-  eosbpinit.sh can install apps/pips, pull lastest EOSIO source code and trigger eosio_build.sh with TAG name
- docker-compose.yml can be adjusted and to setup custom nodeosd's docker image for Block Producer role
- docker-compose-fullnode.yml same as docker-compose.yml instead of expose both p2p&http port for Full Node role
- bash_profile demo to define alias 
- fullnode & producer folder contain demo config.ini and genesis.json
- monitor folder contains monitor script and supervisor configure file template

## eosboinit.sh

### Usage:
```
ubuntu:~/inithost/eostoolkit$ bash eosbpinit.sh
Usage: eosbpinit.sh init|pull|source|docker
      init: just initialize the machine
      pull: just pull the latest code for EOSIO
      source: just pull the latest code for EOSIO and call eosio_build.sh
      docker: just pull the latest code for EOSIO and wait for docker build
```

### initialize machine auto install apps, lastest git, docker and docker-compose etc.
```
git clone https://github.com/winlin/eostoolkit.git
cd eostoolkit
bash eosbpinit.sh init
```

## monitor_sync.py

### You have to modify the monitor_sync.py and add MONITOR_NODES, and monitor_sync.py will call /v1/chain/get_info for every node with special interval.
### The warning message will be send by Telegram bot, if you are not familiar with Telegram, this [[ https://www.forsomedefinition.com/automation/creating-telegram-bot-notifications/ | manual ]] maybe useful.
### Then you can modify the monitor_sync.conf_tpl and add it into /etc/supervisor/conf.d/ to keep the monitor script always running.

### Usage:
```
ubuntu:~/inithost/eostoolkit/monitor$ python monitor_sync.py -h
usage: monitor_sync.py [-h] [-i INTERVAL] -t TOKEN -d CHATID

BP nodeosd monitor tool.

optional arguments:
  -h, --help            show this help message and exit
  -i INTERVAL, --interval INTERVAL
                        check interval(s) default:10 seconds
  -t TOKEN, --token TOKEN
                        telegram bot token
  -d CHATID, --chatid CHATID
                        message recieve telegram chat id
```


