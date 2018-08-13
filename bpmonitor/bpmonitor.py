#!/usr/bin/python
# -*- coding: utf-8 -*-
#####################################
#         Winlin@EOSBIXIN           #
#####################################

from __future__ import unicode_literals
import os
import sys
import uuid
import time
import signal
import requests
import argparse
import traceback
import collections
import hashlib
from threading import Thread
import simplejson as json
from decimal import Decimal

# Just re-write yourself warning function body, nothing else need to be change.
def send_warning(msg, config_dict, sms_flag):
    ''' msg: the message need to send 
        config_dict: the configures read from the bpmonitor.json
    '''
    # replace with yourself warning function 
    # if sms_flag:
    #    send_mobile_msg(msg, config_dict)
    send_dingding_msg(msg, config_dict)
    send_telegram_msg(msg, config_dict)
    
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
        print 'dingding send message:', msg, response.text
    except Exception as e:
        print 'get_current_bp get exception:', e
        print traceback.print_exc()

# Send Telegram Bot
def send_telegram_msg(msg, config_dict):
    try:
        url = "https://api.telegram.org/bot%s/sendMessage" % (config_dict["telegram"]["token"])
        param = {"chat_id":config_dict["telegram"]["chat_id"], "text":msg, }
        result = requests.post(url, param, timeout=5.0)
        print "telegram_alarm send message:", msg, result.text
    except Exception as e:
        print 'get_current_bp get exception:', e
        print traceback.print_exc()

# Send SMS
def send_mobile_msg(msg, config_dict):
    send_phones = []
    for key in config_dict['notify_phones']:
        if key == '*':
            send_phones.extend(config_dict['notify_phones'][key])
            continue
        if key.lower() in msg:
            send_phones.extend(config_dict['notify_phones'][key])
            continue
    send_phones = set(send_phones)
    print 'Send to :', send_phones
    sign = ' [EOSBIXIN]'
    querystring = {"action": "send",
                   "userid": config_dict['yqq_userid'],
                   "account": config_dict['yqq_account'],
                   "password": config_dict['yqq_password'],
                   "mobile": ",".join(send_phones),
                   "content": msg + sign,
                   "sendTime": "", "extno": ""}
    headers = {
        'Cache-Control': "no-cache",
    }
    try:
        res = requests.request("GET", config_dict['yqq_smsurl'], headers=headers, params=querystring)
        rj = json.loads(res.content)
        print rj['returnstatus']
    except Exception as e:
        print 'get_current_bp get exception:', e
        print traceback.print_exc()

############################################
g_stop_thread = False
g_notify_cache = {}

HTTP_TIMEOUT = 6
HTTP_AGENT = {'User-Agent':"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36"}

def notify_users(msg, config_dict, sms_flag=False):
    global g_notify_cache
    try:
        msg_hash = hashlib.md5(msg).hexdigest()
        if msg_hash in g_notify_cache and (time.time() - g_notify_cache[msg_hash] < config_dict['notify_interval']):
            return
        g_notify_cache[msg_hash] = time.time()
        print msg
        send_warning(msg, config_dict, sms_flag)
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

def datestr24h_2second(date_str):
    return int(time.mktime(time.strptime(date_str, "%Y-%m-%dT%H:%M:%S")))

def get_current_bp(host):
    try:
        get_info = "%s/v1/chain/get_info" % (host)
        ret = requests.get(get_info, timeout=HTTP_TIMEOUT, 
                    headers={'User-Agent':"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36"})
        if ret.status_code/100 != 2:
            print 'ERROR: failed to call:', get_info, ret.text
            return None, 'get_current_bp failed:' + host
        result = json.loads(ret.text)
        return result, None
    except Exception as e:
        print 'get_current_bp get exception:', e
        print traceback.print_exc()
    return None, 'get_current_bp get exception:' + host

def get_bp_order(host):
    try:
        top_limit = 30
        data = '{ "json": true, "lower_bound": "", "limit": %d}' % top_limit
        list_prods = "%s/v1/chain/get_producers" % (host)
        ret = requests.post(list_prods, data=data, timeout=HTTP_TIMEOUT, 
                    headers={'User-Agent':"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36"})
        if ret.status_code/100 != 2:
            print 'ERROR: failed to call:', list_prods, ret.text
            return None, 'get_producers failed:' + host
        result = json.loads(ret.text)
        bps_rank = []
        for index, item in enumerate(result['rows']):
            if index>20:
                break
            bps_rank.append(item["owner"])
            if time.time() - int(item['last_claim_time'])/1000000 > 3600*24.2:
                #daily claim delay
                msg = "%s claimreward delay for more than 12min" % (item["owner"])
                notify_users(msg, config_dict, sms_flag=True)
        return sorted(bps_rank), None
    except Exception as e:
        #pass
        print 'get_bp_order get exception:', e
        print traceback.print_exc()
    return None, 'get_bp_order get exception:' + host 

def get_block_producer(host, num):
    try:
        url = host + "/v1/chain/get_block"
        payload = "{\"block_num_or_id\":%d}" % num
        response = requests.post(url, data=payload, timeout=HTTP_TIMEOUT,
                        headers={'User-Agent':"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36"})
        bpline = response.text[:64] + '}'
        print 'Get block %d :%s' % (num, bpline)
        return json.loads(bpline), None
    except Exception as e:
        pass
        #print 'get_block_producer get exception:', e
        #print traceback.print_exc()
    return None, 'get_block_producer get exception:' + host 

def check_nextbp_legal(bp_order, pre_bp, cur_bp):
    try:
        if bp_order[bp_order.index(pre_bp)+1] != cur_bp:
            return False, bp_order[bp_order.index(pre_bp)+1]
    except Exception as e:
        pass
    # The first 21 bps order may change, so here just assume legal
    return True, None

def check_bprank_change(pre_rank, cur_rank, config_dict):
    outrank_bps = set(pre_rank) - set(cur_rank)
    for bp in outrank_bps:
        msg = "%s out rank of %d" % (bp, len(cur_rank))
        notify_users(msg, config_dict, sms_flag=True)

    for bp in cur_rank:
        if cur_rank.index(bp) != pre_rank.index(bp):
            msg = "%s rank changed from %d to %d" % (bp, pre_rank.index(bp), cur_rank.index(bp))
            notify_users(msg, config_dict, sms_flag=True)

def check_rotating(host, status_dict, config_dict):
    global g_stop_thread
    if host not in status_dict:
        status_dict[host] = {'vote_rates_24h': collections.deque(maxlen=24), 'rank_last_2':collections.deque(maxlen=2), 'last_cblock_time':time.time()}
    
    pre_bp, cur_bp, bp_order = None, None, None
    curbp_bcount, lib_num, cur_lib_num, start_lib_num = 0, 0, 0, 0
    rotate_time, pre_bprank = time.time(), None
    while not g_stop_thread:
        try:
            curbp_info, err = get_current_bp(host)
            if err:
                notify_users(err, config_dict, sms_flag=False)
                rotate_time = time.time()
                continue
            lib_num = curbp_info['last_irreversible_block_num']
            if cur_lib_num < 1:
                cur_lib_num, start_lib_num = lib_num, lib_num
            if cur_lib_num > lib_num:
                # wait for LIB increase
                rotate_time = time.time()
                continue

            block_bpinfo, err = get_block_producer(host, cur_lib_num)
            if err:
                notify_users(err, config_dict, sms_flag=False)
                rotate_time = time.time()
                continue
            cur_bp = block_bpinfo['producer']
            if not pre_bp:
                pre_bp = cur_bp
            if pre_bp != cur_bp:
                bp_order, err = get_bp_order(host)
                if err:
                    notify_users(err, config_dict, sms_flag=False)
                    rotate_time = time.time() + 1.0
                    continue
                if not pre_bprank:
                    pre_bprank = bp_order
                check_bprank_change(pre_bprank, bp_order, config_dict)
                pre_bprank = bp_order

            cur_lib_num += 1
            if pre_bp == cur_bp:
                curbp_bcount += 1
                continue
        
            legal, legal_bp = check_nextbp_legal(bp_order, pre_bp, cur_bp) 
            if not legal:
                msg = "%s MIGHT missed 12 blocks after %d" % (legal_bp, cur_lib_num-1)
                notify_users(msg, config_dict, sms_flag=True)

            if curbp_bcount<10 and cur_lib_num-start_lib_num>11:
                msg = "%s [%d - %d] missed %d blocks " % (pre_bp, cur_lib_num-1-curbp_bcount, cur_lib_num-2, 12-curbp_bcount)
                notify_users(msg, config_dict, sms_flag=True)
            curbp_bcount = 1
            pre_bp = cur_bp
        except Exception as e:
            print 'check_rotating get exception:', e
            print traceback.print_exc()
        finally:
            sleep_time = 2.0 + rotate_time - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)

def signal_default_handler(sig, frame):
    global g_stop_thread
    g_stop_thread = True
    print("#### Caught signal:%d and do NOTHING ####", sig)

def main(config_dict):
    global g_stop_thread
    status_dict = {}
    check_rotating(config_dict['http_urls'][0], status_dict, config_dict)

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