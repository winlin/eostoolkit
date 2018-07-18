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

try:
    reload(sys)
    sys.setdefaultencoding('utf8')
except NameError:
    pass
except Exception as err:
    raise err

# Just re-write yourself warning function body, nothing else need to be change.
def send_warning(msg, config_dict):
    ''' msg: the message need to send 
        config_dict: the configures read from the bpmonitor.json
    '''
    # replace with yourself warning function 
    send_alisms(msg, config_dict)
    send_dingding_msg(msg)
    
# Send Dingtalk
def send_dingding_msg(msg, config_dict):
    headers = {
        'Content-Type': "application/json"
    }
    url = "https://oapi.dingtalk.com/robot/send"
    querystring = {"access_token":config_dict['dtalk_access_token'}
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

# Send SMS
def send_alisms(msg, config_dict):
    try:
        from aliyunsdkdysmsapi.request.v20170525 import SendSmsRequest
        from aliyunsdkcore.client import AcsClient
        from aliyunsdkcore.profile import region_provider

        REGION = "cn-hangzhou"
        PRODUCT_NAME = "Dysmsapi"
        DOMAIN = "dysmsapi.aliyuncs.com"
        acs_client = AcsClient(config_dict['accessid'], config_dict['accessidkey'], REGION)
        region_provider.add_endpoint(PRODUCT_NAME, REGION, DOMAIN)
        smsRequest = SendSmsRequest.SendSmsRequest()
        smsRequest.set_TemplateCode(config_dict['template_code'])
        template_param = '{"timestamp":"%s","account":"%s","offlinetime":"","message":"%s"}' % (
            second2_str24h(time.time(), fmt="%H:%M:%S"), config_dict['bpaccount'], msg[:20]
        )
        smsRequest.set_TemplateParam(template_param)
        smsRequest.set_OutId(uuid.uuid1())
        smsRequest.set_SignName(config_dict['signname'])
        smsRequest.set_PhoneNumbers(",".join(config_dict['phones']))
        print acs_client.do_action_with_exception(smsRequest)
    except Exception as e:
        print 'get_current_bp get exception:', e
        print traceback.print_exc()

############################################
g_stop_thread = False
g_notify_cache = {}
g_http_timeout = 1.5
def notify_users(msg, config_dict):
    global g_notify_cache
    try:
        msg_hash = hashlib.md5(msg).hexdigest()
        if msg_hash in g_notify_cache and (time.time() - g_notify_cache[msg_hash] < config_dict['notify_interval']):
            return
        g_notify_cache[msg_hash] = time.time()
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

def get_current_bp(host):
    try:
        get_info = "%s/v1/chain/get_info" % (host)
        ret = requests.get(get_info, timeout=g_http_timeout, 
                    headers={'User-Agent':"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36"})
        if ret.status_code/100 != 2:
            print 'ERROR: failed to call:', get_info, ret.text
            return None, 'get_current_bp failed:' + host
        result = json.loads(ret.text)
        return result['head_block_producer'], None
    except Exception as e:
        print 'get_current_bp get exception:', e
        print traceback.print_exc()
    return None, 'get_current_bp get exception:' + host

def get_bpinfo(host, account):
    try:
        top_limit = 50
        data = '{ "json": true, "lower_bound": "", "limit": %d}' % top_limit
        list_prods = "%s/v1/chain/get_producers" % (host)
        ret = requests.post(list_prods, data=data, timeout=g_http_timeout, 
                    headers={'User-Agent':"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36"})
        if ret.status_code/100 != 2:
            print 'ERROR: failed to call:', list_prods, ret.text
            return None, 'get_producers failed:' + host
        result = json.loads(ret.text)
        account_info = {'vote_rate':0.0, 'account':account,}
        for index,item in enumerate(result['rows']):
            if item['owner'] != account:
                continue
            account_info['vote_rate'] = float(Decimal(item['total_votes']) / Decimal(result['total_producer_vote_weight']))
            account_info['rank'] = index + 1
            return account_info, None
        return None, 'You have out of top %d' % (top_limit)
    except Exception as e:
        print 'get_bpinfo get exception:', e
        print traceback.print_exc()
    return None, 'get_bpinfo get exception:' + host

def check_rotating(host, status_dict, config_dict):
    global g_stop_thread
    if host not in status_dict:
        status_dict[host] = {'vote_rates_24h': collections.deque(maxlen=24), 'rank_last_2':collections.deque(maxlen=2), 'last_cblock_time':time.time()}
    while not g_stop_thread:
        try:
            # check the bp rank
            bpinfo, err = get_bpinfo(host, config_dict['bpaccount'])
            if err:
                notify_users(err, config_dict)
                continue
            if int(time.time()) % 3600 == 0:  # store the vote rate per hour
                status_dict[host]['vote_rates_24h'].append(bpinfo['vote_rate'])
            status_dict[host]['rank_last_2'].append(bpinfo['rank'])
            if len(status_dict[host]['rank_last_2'])>1 and status_dict[host]['rank_last_2'][0] != status_dict[host]['rank_last_2'][1]:
                msg = "Rank changd: from %d to %d" % (status_dict[host]['rank_last_2'][1], status_dict[host]['rank_last_2'][0])
                notify_users(msg, config_dict)

            # update monitor account last create block timestamp
            if bpinfo['rank'] < 22 and int(time.time()) % 3 == 0:   # get create block account per 3 secs
                curbp, err = get_current_bp(host)
                print second2_str24h(time.time()), curbp, host
                if err:
                    notify_users(err, config_dict)
                if curbp == config_dict['bpaccount']:
                    status_dict[host]['last_cblock_time'] = time.time()
        except Exception as e:
            print 'check_rotating get exception:', e
            print traceback.print_exc()
        finally:
            time.sleep(0.5)

def calc_day_reward(vote_rate, rank):
    reward_eos = 0
    if rank < 22:
        reward_eos += 1000000000*0.01*0.25/365/21
    reward_eos += 1000000000*0.01*0.75/365 * vote_rate
    return reward_eos

def signal_default_handler(sig, frame):
    global g_stop_thread
    g_stop_thread = True
    print("#### Caught signal:%d and do NOTHING ####", sig)

def main(config_dict):
    global g_stop_thread
    status_dict = {}
    threadlist = []

    for host in config_dict['http_urls']:
        th = Thread(target=check_rotating, args=(host, status_dict, config_dict))
        threadlist.append(th)
        th.start()

    reward_flags, latest_cblock_time = collections.deque(maxlen=5), time.time()
    while not g_stop_thread:
        time.sleep(1)
        need_check_cblock = False
        for host in status_dict:
            rate_len = len(status_dict[host]['vote_rates_24h'])
            if rate_len == 0:
                continue
            latest_cblock_time = max(latest_cblock_time, status_dict[host]['last_cblock_time'])
            need_check_cblock = status_dict[host]['rank_last_2'][0] < 22 
            reward_flag = int(time.time()) / (3600*24)     # store one day's average reward
            if int(time.time()) % (3600*24) == 0:
                if reward_flag in reward_flags:
                    continue
                reward_flags.append(reward_flag)
                with open(config_dict['reward_output'], "a") as fp:
                    day_str = second2_str24h(int(time.time()))
                    day_avg_rate = sum(status_dict[host]['vote_rates_24h']) * 1.0 / len(status_dict[host]['vote_rates_24h'])
                    day_reward = calc_day_reward(day_avg_rate, status_dict[host]['rank_last_2'][0])
                    fp.write("%s,%f,%f\n" % (day_str, day_avg_rate, day_reward))

        if need_check_cblock and time.time() - latest_cblock_time > 130:  # rotate period is 120 secs
            msg = "Long time NO create blocks, lasttime: %s " % second2_str24h(latest_cblock_time)
            print second2_str24h(time.time()), msg
            notify_users(msg, config_dict)
    
    for th in threadlist:
        th.join()

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