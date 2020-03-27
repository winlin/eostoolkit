#!/usr/bin/python
# -*- coding: utf-8 -*-
#####################################
#         Winlin@EOSBIXIN           #
#####################################

from __future__ import unicode_literals
import os
import re
import sys
import uuid
import time
import signal
import requests
import argparse
import traceback
import collections
import hashlib
import re
from calendar import timegm
from datetime import datetime
from threading import Thread
import simplejson as json
from decimal import Decimal
from Queue import Empty
from operator import itemgetter
import threading
from multiprocessing import Queue
from multiprocessing.pool import ThreadPool


reload(sys)  # Reload does the trick!
sys.setdefaultencoding('UTF8')

HTTP_TIMEOUT = 2.5
HTTP_AGENT = {'User-Agent':"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36"}

# Just re-write yourself warning function body, nothing else need to be change.
def send_warning(msg, config_dict, sms_flag=False, telegram_flag=True):
    ''' msg: the message need to send
        config_dict: the configures read from the bpmonitor.json
    '''
    # replace with yourself warning function
    send_dingding_msg(msg, config_dict)
    send_pagerduty_msg(msg, config_dict)

    if sms_flag:
       send_mobile_msg(msg, config_dict)
    if telegram_flag:
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
        response = requests.post(url, data=json.dumps(content), headers=headers, params=querystring, timeout=HTTP_TIMEOUT)
        print 'dingding send message:', msg #, response.text
    except Exception as e:
        print 'send_dingding_msg get exception:', e
        print traceback.print_exc()

# Send Telegram Bot
def send_telegram_msg(msg, config_dict):
    try:
        url = "https://api.telegram.org/bot%s/sendMessage" % (config_dict["telegram"]["token"])
        param = {"chat_id":config_dict["telegram"]["chat_id"], "text":msg, }
        result = requests.post(url, param, timeout=HTTP_TIMEOUT)
        print "telegram_alarm send message:", msg, result.text
    except Exception as e:
        print 'send_telegram_msg get exception:', e
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
    if not send_phones:
        return
    param = {
        'apikey':config_dict['sms']['apikey'],
        'text':config_dict['sms']['tmpl'] + msg,
        'mobile':','.join(send_phones)
    }
    print 'Send to: ', send_phones, msg
    headers = {"Accept":"application/json;charset=utf-8;","Content-Type":"application/x-www-form-urlencoded;charset=utf-8;"}
    try:
        res = requests.post(config_dict['sms']['batch_send_url'], data=param, headers=headers, timeout=HTTP_TIMEOUT)
        print res.text
    except Exception as e:
        print 'send_mobile_msg get exception:', e
        print traceback.print_exc()

# Send PagerDuty
def send_pagerduty_msg(msg, config_dict):
    if 'notify_pagerduties' not in config_dict:
        return
    send_pagerduties = []
    for key in config_dict['notify_pagerduties']:
        if key == '*':
            send_pagerduties.extend(config_dict['notify_pagerduties'][key])
            continue
        if key.lower() in msg:
            send_pagerduties.extend(config_dict['notify_pagerduties'][key])
            continue
    send_pagerduties = set(send_pagerduties)
    if not send_pagerduties:
        return

    matchObj = re.match(r'(\w{12}).*missed (\d+) blocks.*', msg, re.I)
    if not matchObj:
        return

    bp = matchObj.group(1)
    missed = matchObj.group(2)
    severity = 'critical' if missed == '12' else 'warning'

    param = {
        'payload': {
            'summary': msg,
            'severity': severity,
            'source': bp,
            'group': 'bpmonitor'
        },
        'event_action': 'trigger',
        'client': 'bpmonitor',
    }
    headers = {
        'Content-Type': 'stringapplication/json'
    }

    for integration_key in send_pagerduties:
        param['routing_key'] = integration_key
        print 'Send to pageduty: ', msg

        try:
            res = requests.post('https://events.pagerduty.com/v2/enqueue', json=param, headers=headers, timeout=HTTP_TIMEOUT)
            print res.text
        except Exception as e:
            print 'send_pagerduty_msg get exception:', e
            print traceback.print_exc()

############################################
g_stop_thread = False
g_notify_cache = {}
g_bp_queue = Queue()
g_notify_queue = Queue()

def enqueue_msg(msg, config_dict=None, sms_flag=False, telegram_flag=False):
    global g_notify_queue
    g_notify_queue.put({
        "msg": msg,
        "sms_flag": sms_flag,
        "telegram_flag": telegram_flag
    })

def notify_users(msg, config_dict, sms_flag=False, telegram_flag=True):
    global g_notify_cache
    try:
        msg_hash = hashlib.md5(msg).hexdigest()
        silent_time = config_dict['notify_interval']*6 if sms_flag else config_dict['notify_interval']
        if msg_hash in g_notify_cache and (time.time() - g_notify_cache[msg_hash] < silent_time):
            return
        g_notify_cache[msg_hash] = time.time()
        print msg
        send_warning(msg, config_dict, sms_flag, telegram_flag)
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

def get_current_bp(host):
    try:
        get_info = "%s/v1/chain/get_info" % (host)
        ret = requests.get(get_info, timeout=HTTP_TIMEOUT,
                    headers=HTTP_AGENT)
        if ret.status_code/100 != 2:
            print 'ERROR: failed to call:', get_info, ret.text
            return None, 'get_current_bp failed:' + host
        return json.loads(ret.text), None
    except Exception as e:
        print 'get_current_bp get exception:', e
        print traceback.print_exc()
    return None, 'get_current_bp get exception:' + host

def get_bp_schedule(host):
    try:
        data = '{}'
        prods_schd = "%s/v1/chain/get_producer_schedule" % (host)
        ret = requests.post(prods_schd, data=data, timeout=HTTP_TIMEOUT,
                    headers=HTTP_AGENT)
        if ret.status_code/100 != 2:
            print 'ERROR: failed to call:', prods_schd, ret.text
            return None, None, 'get_producer_schedule failed:' + host
        result = json.loads(ret.text)
        bp_schedule = [ item['producer_name'] for item in result['active']['producers'] ]
        print 'Schedule Version:', result['active']['version'], ' ', bp_schedule
        return result['active']['version'], bp_schedule, None
    except Exception as e:
        print 'get_producer_schedule get exception:', e
        print traceback.print_exc()
    return None, None, 'get_producer_schedule get exception:' + host

g_claim_cache = {}
def get_bp_rank(host):
    global g_claim_cache
    try:
        top_limit = 40
        data = '{ "json": true, "lower_bound": "", "limit": %d}' % top_limit
        list_prods = "%s/v1/chain/get_producers" % (host)
        ret = requests.post(list_prods, data=data, timeout=HTTP_TIMEOUT,
                    headers=HTTP_AGENT)
        if ret.status_code/100 != 2:
            print 'ERROR: failed to call:', list_prods, ret.text
            return None, 'get_producers failed:' + host
        result = json.loads(ret.text)
        bps_rank = []
        for index, item in enumerate(result['rows']):
            if index>30:
                break
            bps_rank.append(item["owner"])
            unclaim_hours = 0
            if ':' in item['last_claim_time']:
                unclaim_hours = (time.time() - datestr24h_2second(item['last_claim_time'][:-4]))/3600.0
            else:
                unclaim_hours = (time.time() - int(item['last_claim_time'])/1000000)/3600.0
            if unclaim_hours < 26 or (item['owner'] in g_claim_cache and time.time() - g_claim_cache[item['owner']] < 3600*3):
                continue
            g_claim_cache[item['owner']] = time.time()
            #daily claim delay
            msg = "%s claimreward delayed for more than %.1f hours" % (item["owner"], unclaim_hours)
            enqueue_msg(msg, config_dict, sms_flag=True, telegram_flag=True)
        return bps_rank, None
    except Exception as e:
        print 'get_bp_rank get exception:', e
        print traceback.print_exc()
    return None, 'get_bp_rank get exception:' + host

def get_block_producer(params):
    try:
        host, num = params
        url = host + "/v1/chain/get_block"
        payload = "{\"block_num_or_id\":%d}" % num
        response = requests.post(url, data=payload, timeout=HTTP_TIMEOUT,
                        headers=HTTP_AGENT.update({'Range': 'bytes=0-500'}),
                        stream=True)
        bpline = str(response.raw.read(500))
        match_regxs = {
            'producer' : '(?<=\"producer\":\")[^\",]*',
            'timestamp' : '(?<=\"timestamp\":\")[^\",]*',
            'schedule_version' : '(?<=\"schedule_version\":)[^,]*'
        }
        result = {}
        for key in match_regxs:
            ret = re.search(match_regxs[key], bpline)
            if not ret:
                print 'ERROR: Failed to get in block:', key
                return num, None, key + ' failed:' + host
            result[key] = ret.group(0).strip()
        return num, result, None
    except Exception as e:
        pass
        #print 'get_block_producer get exception:', e
        #print traceback.print_exc()
    return num, None, 'get_block_producer get exception:' + host

def check_nextbp_legal(bp_schedule, pre_bp, cur_bp):
    try:
        legal_bp = bp_schedule[bp_schedule.index(pre_bp)+1]
        if legal_bp != cur_bp:
            return False, legal_bp
    except Exception as e:
        pass
    # The first 21 bps order may change, so here just assume legal
    return True, None

def check_bprank_change(pre_rank, cur_rank):
    print pre_rank, '\n', cur_rank
    outrank_bps = set(pre_rank) - set(cur_rank)
    rank_changed = False
    for bp in outrank_bps:
        rank_changed = True
        msg = "%s out rank of %d" % (bp, len(cur_rank))
        enqueue_msg(msg, config_dict, sms_flag=True, telegram_flag=True)

    for index,bp in enumerate(cur_rank):
        if bp not in pre_rank:
            rank_changed = True
            msg = "%s rank changed into %d" % (bp, index+1)
            enqueue_msg(msg, config_dict, sms_flag=True, telegram_flag=True)
            continue
        if cur_rank.index(bp) != pre_rank.index(bp):
            rank_changed = True
            msg = "%s rank changed from %d to %d" % (bp, pre_rank.index(bp)+1, index+1)
            enqueue_msg(msg, config_dict, sms_flag=True, telegram_flag=True)
    return rank_changed

def get_libblock_process(host):
    print('current_bp_process started !')
    global g_stop_thread, g_bp_queue
    prev_lib_num, pool, sleep_time  = -1, ThreadPool(8), 0.5

    while not g_stop_thread:
        try:
            bp_info, err = get_current_bp(host)
            if err:
                enqueue_msg(err)
                continue
            cur_lib_num = bp_info['last_irreversible_block_num']
            if prev_lib_num == cur_lib_num:
                continue

            if prev_lib_num < 0:
                num, info, err = get_block_producer((host, cur_lib_num))
                if err:
                    enqueue_msg(err)
                    print 'WARNING: need to retry from LIB:', prev_lib_num
                    continue
                print 'Get one block %d :%s' % (num, info)
                prev_lib_num = cur_lib_num
                g_bp_queue.put({"num": cur_lib_num, "info": info})
                continue
            if cur_lib_num <= prev_lib_num:
                continue
            # prev_lib_num < cur_lib_num
            print('unprocessed block size: ', cur_lib_num - prev_lib_num)
            result = pool.map(get_block_producer, [ (host, num) for num in range(prev_lib_num + 1, cur_lib_num + 1) ])
            # if failed one block get need to retry
            stop_flag = False
            for item in result:
                if item[2] or item[1] is None:
                    print 'WARNING: need to retry from LIB:', prev_lib_num
                    stop_flag = True
                    break
            if stop_flag:
                continue

            for item in sorted(result, key=itemgetter(0)):
                print 'Get block %d :%s' % (item[0], item[1])
                g_bp_queue.put({"num": item[0], "info": item[1]})

            prev_lib_num = cur_lib_num
            sleep_time = 0.2
        except Exception as e:
            print 'get_libblock_process get exception:', e
            print traceback.print_exc()
        finally:
            time.sleep(sleep_time)
            sleep_time = 0.5

def notify_process(config_dict):
    """notify user errors"""
    print("notify_process started !")
    global g_stop_thread, g_notify_queue

    while not g_stop_thread:
        try:
            msg = g_notify_queue.get(False)
            notify_users(msg["msg"], config_dict, msg["sms_flag"], msg["telegram_flag"])
        except Empty as e:
            time.sleep(.5)

def check_rotating_process(host, config_dict):
    print('check_rotating_process started !')
    global g_stop_thread, g_bp_queue

    pre_bp, cur_bp, prebp_rank, bp_rank, bp_schedule, pre_sch_ver, cur_sch_ver = None, None, None, None, None, 0, 0
    curbp_bcount, cur_lib_num, start_lib_num = 0, 0, 0
    ignore_timestamp = time.time() - 180

    while not g_stop_thread:
        try:
            item = g_bp_queue.get(False)
        except Empty as e:
            time.sleep(.1)
            continue
        cur_lib_num, block_bpinfo = item["num"], item["info"]
        if not block_bpinfo:
            print('get block %d failed !' % cur_lib_num)
            continue
        if start_lib_num < 1:
            start_lib_num = cur_lib_num

        try:
            cur_bp, cur_sch_ver = block_bpinfo['producer'], block_bpinfo['schedule_version']
            if not pre_bp:
                pre_bp = cur_bp
            if not pre_sch_ver:
                pre_sch_ver = cur_sch_ver
            if bp_rank is None :
                bp_rank, err = get_bp_rank(host)
                if err:
                    enqueue_msg(err)
                    continue
                prebp_rank = bp_rank
            if not bp_schedule:
                schedule_ver, bp_schedule, err = get_bp_schedule(host)
                if err:
                    enqueue_msg(err)
                    continue

            if pre_bp != cur_bp:
                bp_rank, err = get_bp_rank(host)
                if err:
                    enqueue_msg(err)
                    continue

                rank_changed = check_bprank_change(prebp_rank, bp_rank)
                prebp_rank = bp_rank
                if pre_sch_ver != cur_sch_ver or rank_changed:
                    print('21th bp rank changed:pre_sch_ver:%s cur_sch_ver:%s rank_changed:%s' % (pre_sch_ver, cur_sch_ver, rank_changed))
                    ignore_timestamp = time.time() + 600
                    schedule_ver, bp_schedule, err = get_bp_schedule(host)
                    if err:
                        enqueue_msg(err)
                        continue

                pre_sch_ver = cur_sch_ver

            if pre_bp == cur_bp:
                curbp_bcount += 1
                continue

            legal, legal_bp = check_nextbp_legal(bp_schedule, pre_bp, cur_bp)
            cur_block_timestamp = datestr24h_2second(block_bpinfo['timestamp'][:-4])
            if not legal and ignore_timestamp < cur_block_timestamp:
                msg = "%s MIGHT miss 12 blocks after %d" % (legal_bp, cur_lib_num - 1)
                enqueue_msg(msg, sms_flag=True, telegram_flag=True)

            if ignore_timestamp < cur_block_timestamp and curbp_bcount < 12 and cur_lib_num - start_lib_num > 11:
                msg = "%s [%d - %d] missed %d blocks. Next is %s " % (
                    pre_bp, cur_lib_num - curbp_bcount, cur_lib_num - 1, 12 - curbp_bcount, cur_bp)
                enqueue_msg(msg, sms_flag=(True if curbp_bcount < 11 else False), telegram_flag=True)
            curbp_bcount = 1
            pre_bp = cur_bp
        except Exception as e:
            print('check_rotating get exception:', e)
            print(traceback.print_exc())

def signal_default_handler(sig, frame):
    global g_stop_thread
    g_stop_thread = True
    print("#### Caught signal:%d and do NOTHING ####", sig)

def main(config_dict):
    global g_stop_thread
    
    host = config_dict['http_urls'][0]

    threads = [
        threading.Thread(target=get_libblock_process, args=(host,)),
        threading.Thread(target=check_rotating_process, args=(host, config_dict)),
        threading.Thread(target=notify_process, args=(config_dict,)),
    ]
    for th in threads:
        th.start()

    while not g_stop_thread:
        time.sleep(.5)

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