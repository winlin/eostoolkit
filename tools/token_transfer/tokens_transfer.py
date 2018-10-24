#!/usr/bin/python
# -*- coding: utf-8 -*-
#####################################
#         Winlin@EOSBIXIN           #
#####################################

from __future__ import unicode_literals
import os
import re
import sys
import time
import signal
import requests
import traceback
import subprocess
import hashlib
import re
from calendar import timegm
from datetime import datetime
import simplejson as json

reload(sys)  # Reload does the trick!
sys.setdefaultencoding('UTF8')

# Just re-write yourself warning function body, nothing else need to be change.
def send_warning(msg, config_dict):
    ''' msg: the message need to send
        config_dict: the configures read from the bpmonitor.json
    '''
    # replace with yourself warning function
    send_dingding_msg(msg, config_dict)
    
# Send Dingtalk
def send_dingding_msg(msg, config_dict):
    headers = {
        'Content-Type': "application/json"
    }
    url = "https://oapi.dingtalk.com/robot/send"
    querystring = {"access_token":config_dict['dtalk_access_token']}
    content = {
        "msgtype": "text",
        "text": {
            "content": msg
        }
    }
    try:
        response = requests.post(url, data=json.dumps(content), headers=headers, params=querystring, timeout=3)
        print 'dingding send message:', msg #, response.text
    except Exception as e:
        print 'send_dingding_msg get exception:', e
        print traceback.print_exc()

############################################
g_stop_thread = False
g_notify_cache = {}

HTTP_TIMEOUT = 6
HTTP_AGENT = {'User-Agent':"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36"}

def notify_users(msg, config_dict, sms_flag=False, telegram_flag=True):
    global g_notify_cache
    try:
        msg_hash = hashlib.md5(msg).hexdigest()
        silent_time = config_dict['notify_interval']*6 if sms_flag else config_dict['notify_interval']
        if msg_hash in g_notify_cache and (time.time() - g_notify_cache[msg_hash] < silent_time):
            return
        g_notify_cache[msg_hash] = time.time()
        print msg
        send_warning(msg, config_dict)
    except Exception as e:
        print 'get_bpinfo get exception:', e
        print traceback.print_exc()
    finally:
        for key in g_notify_cache.keys():
            if time.time() - g_notify_cache[key] > 3600:
                del g_notify_cache[key]

def second2_str24h(cur_second, fmt="%Y-%m-%d %H:%M:%S", utc=False):
    '''Return the time in the local time tuple or UTC time according to `utc`'''
    if not utc:
        return time.strftime(fmt, time.localtime(cur_second))
    return time.strftime(fmt, time.gmtime(cur_second))

def datestr24h_2second(date_str, timezone="UTC"):
    return timegm(
        time.strptime(
            date_str + timezone,
            '%Y-%m-%dT%H:%M:%S%Z'
        )
    )

def operate_wallet(host, config_dict, unlock):
    action = 'unlock' if unlock else 'lock'
    cmdline = "sudo docker-compose exec -T %s %s -u http://localhost:%d --wallet-url http://localhost:%d wallet %s" % (
        config_dict['dockername'], config_dict['cliname'], config_dict['nodeos_port'], config_dict['wallet_port'], action
    )
    pipe = subprocess.Popen(cmdline, shell=True, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
    out, err = pipe.communicate(input=config_dict['wallet_pwd']+"\n")
    print action, ' wallet:', pipe.returncode, out
    return pipe.returncode == 0

def transfer_token(host, token_info, config_dict):
    # get token balance
    cmdline = "sudo docker-compose exec -T %s %s -u http://localhost:%d --wallet-url http://localhost:%d get currency balance %s %s" % (
        config_dict['dockername'], config_dict['cliname'], config_dict['nodeos_port'], config_dict['wallet_port'], token_info["contract"], token_info['from']
    )
    pipe = subprocess.Popen(cmdline, shell=True, stdout=subprocess.PIPE)
    out, err = pipe.communicate()
    balance = out.strip()
    print 'return code:%d get %s balance %s' % (pipe.returncode, token_info["contract"], balance)
    if pipe.returncode != 0:
        print 'Failed to get balance for:', token_info["contract"]
        return False
    if float(balance.split()[0]) < 0.0001:
        msg = "注意: %s 没有收到糖果 %s " % (second2_str24h(time.time())[:10], token_info['tokenname'])
        notify_users(msg, config_dict)
        return True 
    # transfer token
    cmdline = ''' sudo docker-compose exec -T %s %s -u http://localhost:%d --wallet-url http://localhost:%d push action %s transfer '["%s","%s","%s",""]' -p %s ''' % (
        config_dict['dockername'], config_dict['cliname'], config_dict['nodeos_port'], config_dict['wallet_port'], 
        token_info["contract"], token_info['from'], token_info['to'], balance, token_info['from']
    )
    pipe = subprocess.Popen(cmdline, shell=True, stdout=subprocess.PIPE)
    out, err = pipe.communicate()
    print 'return code:%d %s\n%s' % (pipe.returncode, token_info["contract"], out)
    if pipe.returncode != 0:
        print 'Failed to transfer balance for:', token_info["contract"], cmdline
        msg = "错误: %s 转账失败" % (token_info['tokenname'])
        return False
    msg = "%s 转账成功 %s %s " % (second2_str24h(time.time())[:10], balance, token_info['to'])
    notify_users(msg, config_dict)
    return True    

def check_rotating(host, config_dict):
    global g_stop_thread

    msg = '>>>> 开始自动转糖果: %s' % (second2_str24h(time.time()))
    notify_users(msg, config_dict)

    #unlock wallet
    operate_wallet(host, config_dict, unlock=True)
    #foreach token
    for token in config_dict['trans_info']:
        transfer_token(host, token, config_dict)
    #lock wallet
    operate_wallet(host, config_dict, unlock=False)
    msg = '<<<< 完成自动转糖果: %s' % (second2_str24h(time.time()))
    notify_users(msg, config_dict)


def signal_default_handler(sig, frame):
    global g_stop_thread
    g_stop_thread = True
    print("#### Caught signal:%d and do NOTHING ####", sig)

def main(config_dict):
    global g_stop_thread
    check_rotating(config_dict['http_urls'][0], config_dict)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print 'Usage: %s config.json' % (sys.argv[0], )
        sys.exit(1)
    config_dict = {}
    with open(sys.argv[1], "r") as fp:
        config_dict = json.loads(fp.read())
    if not config_dict:
        print 'ERROR: config.json can NOT be empty : %s' % (sys.argv[1], )
        sys.exit(1)

    signal.signal(signal.SIGINT, signal_default_handler)
    signal.signal(signal.SIGQUIT, signal_default_handler)
    signal.signal(signal.SIGABRT, signal_default_handler)
    signal.signal(signal.SIGTERM, signal_default_handler)

    main(config_dict)