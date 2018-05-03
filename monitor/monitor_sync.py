#!/usr/bin/env python
# coding: utf-8
# 
import io
import os
import sys
import time
import json
import signal
import datetime
import argparse
import libconf
import threading
import pyjsonrpc
import inspect
import requests
import subprocess

DEFAULT_FREQ = 10

TELEGRAM_TOKEN = ""
TELEGRAM_CHATID = 0

MONITOR_NODES = [
    #("hostname", "1.1.1.1", 8888) 
]

def log(message):
    caller_info = inspect.stack()[1]
    print("[%s %s %d] %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), caller_info[3], caller_info[2], message))


def telegram_alarm(message):
    try:
        url = "https://api.telegram.org/bot%s/sendMessage" % (TELEGRAM_TOKEN,)
        param = {"chat_id":TELEGRAM_CHATID, "text":message, }
        result = requests.post(url, param, timeout=5.0)
        log("telegram_alarm send result:%s" % result.text)
    except Exception as e:
        log("Get exception:%s" % str(e))


NODE_STATUS = {}
def check_node(node):
    global NODE_STATUS
    if node[1] not in NODE_STATUS:
        NODE_STATUS[node[1]] = {'head_block_num':0, 'last_irreversible_block_num':0}
    try:
        url = "http://%s:%d/v1/chain/get_info" % (node[1], node[2] )
        result = requests.get(url, timeout=3.0)
        if result.status_code/100 !=2 :
            log('Failed to call %s result:%s ' % (url, result.text))
            return
        result_info = json.loads(result.text)

        message = ""
        if result_info["head_block_num"] <= NODE_STATUS[node[1]]['head_block_num'] and NODE_STATUS[node[1]]['head_block_num'] > 0:
            message = "head_block_num increase ERROR %d;" % (result_info["head_block_num"])
        if result_info["last_irreversible_block_num"] <= NODE_STATUS[node[1]]['last_irreversible_block_num'] and NODE_STATUS[node[1]]['last_irreversible_block_num'] > 0:
            message += "\nlast_irreversible_block_num increase ERROR %d;" % (result_info["last_irreversible_block_num"])

        NODE_STATUS[node[1]]['head_block_num'], NODE_STATUS[node[1]]['last_irreversible_block_num'] = result_info["head_block_num"], result_info["last_irreversible_block_num"]
        log("Get %s %s head_block_num=%d last_irreversible_block_num=%d" %(node[0], node[1], result_info["head_block_num"], result_info["last_irreversible_block_num"]))
        if message:
            message += "\n%s %s" % (node[0], node[1])
            telegram_alarm(message)
    except Exception as e:
        log("Get exception:%s %s" % (str(e), node[0]))


def usage():
    global DEFAULT_FREQ, TELEGRAM_TOKEN, TELEGRAM_CHATID
    parser = argparse.ArgumentParser(description='BP nodeosd monitor tool.')
    parser.add_argument('-i', '--interval', default=DEFAULT_FREQ, help='check interval(s) default:%d seconds' % DEFAULT_FREQ)
    parser.add_argument('-t', '--token', required=True, help='telegram bot token')
    parser.add_argument('-d', '--chatid', required=True, help='message recieve telegram chat id')
    args = parser.parse_args()
    DEFAULT_FREQ, TELEGRAM_CHATID = int(args.interval), int(args.chatid)
    TELEGRAM_TOKEN = args.token
    if DEFAULT_FREQ <10 or not TELEGRAM_TOKEN:
        log('Paramaters illegal: port>1024 interval>=10')
        sys.exit(1)
    if len(MONITOR_NODES)<1:
        log("Please modify the code and add monitored node info")
        sys.exit(1)


def main():
    global DEFAULT_FREQ
    head_block_num, last_irreversible_block_num = -1, -1
    while True:
        log("Going to start check node ...")
        for node in MONITOR_NODES:
            check_node(node)
        sys.stdout.flush()
        time.sleep(DEFAULT_FREQ)


if __name__ == '__main__':
    usage()
    main()
