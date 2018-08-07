import os
import sys
import json
import time
import signal
import traceback
import requests
from multiprocessing import Pool

HTTP_HOST = 'http://127.0.0.1:80'

def usage():
    if len(sys.argv) < 4:
        print "%s start_block_num end_block_num bpaccount" % (sys.argv[0])
        print "EX: %s 9784673 9794036 eosbixinboot" % (sys.argv[0])
        sys.exit(1)

def datestr24h_2second(date_str):
    return int(time.mktime(time.strptime(date_str, "%Y-%m-%dT%H:%M:%S")))

def get_block_producer(num):
    url = HTTP_HOST + "/v1/chain/get_block"
    payload = "{\"block_num_or_id\":%d}" % num
    response = requests.request("POST", url, data=payload)
    bpline = response.text[:64] + '}'
    block_info = json.loads(bpline)
    return block_info['producer']+'='+block_info['timestamp']

def main(start_num, end_num, target_bpaccount, pool, pool_size):
    start_t, start_ts, end_t, block_num, producer_startnum, producer_endnum = None, None, None, 0, 0, 0
    for i in range(int(start_num), int(end_num), pool_size):
        results = pool.map(get_block_producer, range(i, i+pool_size), pool_size)
        for index,item in enumerate(results):
            items = item.split('=')
            producder, timestamp,cur_num = items[0], items[1], i+index
            if producder == target_bpaccount:
                if start_t is None:
                    producer_startnum = cur_num
                    start_t, start_ts = datestr24h_2second(timestamp[:-4]), timestamp
                block_num += 1
                end_t, end_ts = datestr24h_2second(timestamp[:-4]), timestamp
                producer_endnum = cur_num

            if start_t and cur_num - producer_startnum > 20:
                print "%s %s [%d - %d] count:%d" % (start_ts, end_ts, producer_startnum, producer_endnum, block_num)
                start_t, block_num = None, 0

if __name__ == '__main__':
    usage()
    try:
        pool_size = 8
        pool = Pool(processes=pool_size)
        def signal_default_handler(sig, frame):
            pool.close()
            pool.join()
            sys.exit(1)
            
        signal.signal(signal.SIGINT, signal_default_handler)
        signal.signal(signal.SIGQUIT, signal_default_handler)
        signal.signal(signal.SIGABRT, signal_default_handler)
        signal.signal(signal.SIGTERM, signal_default_handler)

        main(sys.argv[1], sys.argv[2], sys.argv[3], pool, pool_size)
    except Exception as e:
        print traceback.print_exc()
    finally:
        pool.close()
        pool.join()

