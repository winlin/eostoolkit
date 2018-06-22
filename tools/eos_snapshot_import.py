#!/usr/bin/python
# -*- coding: utf-8 -*-
#
from __future__ import unicode_literals
import os
import sys
import time
import json
import yaml
import requests
import argparse
import subprocess 
import traceback
import simplejson as json
import multiprocessing
from bs4 import BeautifulSoup
from decimal import Decimal, getcontext

requests.adapters.DEFAULT_RETRIES = 3

############################################
#             EOS-BIOS FUNCS               #
############################################

def dl_ipfs_file(file_uri):
    print 'downloading:', file['name']
    tmpfile = os.path.join("/tmp/", str(time.time())+'_'+file['name'])
    wget_cmd = "wget -O %s https://ipfs.io%s > /dev/null 2>&1" % (tmpfile, file_uri)
    ret = subprocess.call(wget_cmd, shell=True)
    if ret != 0:
        print 'ERROR: Failed to get file:',wget_cmd
        return None
    return tempfile

############################################
#        Onchain Validation FUNCS          #
############################################
def token_str2float(token):
    num = Decimal(token.split(" ")[0])
    return num if num > 0 else 0

def weight_str2float(weight):
    num = Decimal(weight)
    return num/Decimal(10000.0) if num > 0 else 0

############################################
#        Validate Onchain Balance          #
############################################
def create_account(param):
    node_host, account_name, pub_key, snapshot_balance = param
    signal_onchain_amount = Decimal(-1)
    try:
        # call get account
        ret = requests.post("http://%s/v1/chain/get_account" % node_host, data=json.dumps({'account_name':account_name}), timeout=2)
        if ret.status_code/100 != 2:
            print 'ERROR: failed to call get_account for:', account_name, ret.text
            return signal_onchain_amount
        account_info = json.loads(ret.text)

        # Validate the privileged
        if not check_account_privileged(account_info):
            print 'ERROR: account %s privileged check failed:', account_info
            return signal_onchain_amount

        # Validate the public key onchain whether same with the snapshot
        owner_pubkey = account_info['permissions'][0]['required_auth']['keys'][0]['key']
        if pub_key != owner_pubkey:
            print 'ERROR: account %s snapshot pubkey(%s)!=onchain pubkey(%s)' % (account_name, pub_key, owner_pubkey)
            return signal_onchain_amount

         # call get account balance
        balance = get_onchain_balance(account_name, node_host)
        if balance < 0:
            print 'ERROR: failed to call get_table_rows accounts for:', account_name, ret.text
            return signal_onchain_amount

        net_weight, cpu_weight = weight_str2float(account_info['net_weight']), weight_str2float(account_info['cpu_weight'])
        net_delegated, cpu_delegated = Decimal(0), Decimal(0)
        if account_info['delegated_bandwidth']:
            net_delegated, cpu_delegated = token_str2float(account_info['delegated_bandwidth']['net_weight']), token_str2float(account_info['delegated_bandwidth']['cpu_weight'])

        # Validate the balance onchain whether same with the snapshot amount
        onchain_balance = balance + net_delegated + cpu_delegated
        if abs(snapshot_balance - onchain_balance) > Decimal(0.0001):
            print 'ERROR: account %s snapshot_balance(%s) != onchain_balance(%s)' % (account_name, snapshot_balance, onchain_balance)
            return signal_onchain_amount
        #print '%-12s balance:%s net_delegated:%s cpu_delegated:%s onchain_balance:%s snapshot_balance:%s' % (account_name, balance, 
        #            net_delegated, cpu_delegated, onchain_balance, snapshot_balance)
        
        signal_onchain_amount = balance + net_weight + cpu_weight
        return signal_onchain_amount
    except Exception as e:
        print 'create_account get exception:', e
        print traceback.print_exc()
        return signal_onchain_amount

def check_balance(snapshot_csv, conf_dict, process_pool, cpu_count):
    node_host = conf_dict['nodeosd_host']
    batch_size = cpu_count*100
    try:
        with open(snapshot_csv, 'r') as fp:
            batch_lines, cur_len, line_nu = [None] * batch_size, 0, 0
            for line in fp.readlines():
                _, account_name, pub_key, snapshot_balance = line.replace('"','').split(',')
                batch_lines[cur_len] = (node_host, account_name, pub_key, Decimal(snapshot_balance))
                cur_len += 1
                line_nu += 1
                if conf_dict['snapshot_lines']>0 and line_nu>=conf_dict['snapshot_lines']:
                    print 'Stop validate because snapshot_lines was set to:', conf_dict['snapshot_lines']
                    break
                if cur_len<batch_size:
                    continue
                results = process_pool.map(create_account, batch_lines, cpu_count)
                for signal_onchain_amount in results:
                    if signal_onchain_amount < 0:
                        return False, line_nu
                    account_onchain_balance_total += signal_onchain_amount
                print 'check progress, account number:', line_nu, ' common accounts balance:', account_onchain_balance_total
                batch_lines, cur_len = [None] * batch_size, 0

            if cur_len>0:
                results = process_pool.map(create_account, batch_lines[:cur_len], cpu_count)
                for signal_onchain_amount in results:
                    if signal_onchain_amount < 0:
                        return False, line_nu
                    account_onchain_balance_total += signal_onchain_amount
            sys_producer_balance = sum(conf_dict['sys_producer_amount'].values())
            print 'Onchain: system&producer accounts balance:',sys_producer_balance, 'common accounts balance:', account_onchain_balance_total, ' account number:', line_nu
            onchain_account_balance = sys_producer_balance + account_onchain_balance_total

            anonymous_amount = token_str2float(conf_dict['eos_stats']['supply']) - onchain_account_balance
            if abs(anonymous_amount) > Decimal(0.0001):
                print 'ERROR: There are some illegal transfer token action eos_issued(%s) != onchain_total(%s) anonymous amount:%s' % (token_str2float(conf_dict['eos_stats']['supply']), onchain_account_balance, anonymous_amount)
                return False, line_nu
            return True, line_nu
    except Exception as e:
        print 'EXCEPTION: there are exception:', e
        print traceback.print_exc()
        return False, 0


############################################
#        Validate Onchain Contract         #
############################################
def check_contracts(conf_dict):
    try:
        for account_name in conf_dict["code_hash_compare"]["accounts"]:
            cur_ret = requests.post("http://%s/v1/chain/get_code" % conf_dict['nodeosd_host'], data=json.dumps({'account_name':account_name}), timeout=5)
            if cur_ret.status_code/100 != 2:
                print 'ERROR: failed to call get_code for:', account_name, conf_dict['nodeosd_host'], ret.text
                raise Exception("")
            cur_code_info = json.loads(cur_ret.text)
            compare_ret = requests.post("http://%s/v1/chain/get_code" % conf_dict['code_hash_compare']['nodeosd_host'], data=json.dumps({'account_name':account_name}), timeout=5)
            if compare_ret.status_code/100 != 2:
                print 'ERROR: failed to call get_code for:', account_name, conf_dict['code_hash_compare']['nodeosd_host'], compare_ret.text
                raise Exception("")
            compare_code_info = json.loads(compare_ret.text)
            if cur_code_info['code_hash'] != compare_code_info['code_hash']:
                print 'ERROR: code hash compare failed:', account_name, cur_code_info['code_hash'], compare_code_info['code_hash']
                raise Exception("")
            print account_name, cur_code_info['code_hash'], compare_code_info['code_hash']
        print 'SUCCESS: !!! The Contracts Check SUCCESS !!!'
        return True
    except Exception as e:
        print 'ERROR: !!! The Contracts Check FAILED !!!'
        return False

####################################################################


def main():
    parser = argparse.ArgumentParser(description='EOSIO onchain validator tool.')
    parser.add_argument('--snapshot', type=str, required=True, help='/ipfs/QmeAL8aTvrBVKQbKEzeYwp9oKEPuajQSaaubLxHBuAZXCo')
    parser.add_argument('--host', type=str, required=True, help='nodeos HTTP host 127.0.0.1:8888')
    args = parser.parse_args()
    ipfs_snapshot, host = args.snapshot, args.host
    snapshot_file = dl_ipfs_file(ipfs_snapshot)
    if not snapshot_file:
        sys.exit(1)

    # Start the validation
    cpu_count = multiprocessing.cpu_count()
    process_pool = multiprocessing.Pool(processes=cpu_count)
    try:
        time_start = time.time()
        result, line_number = check_balance(snapshot_file, conf_dict, process_pool, cpu_count)
        if not result:
            print 'ERROR: !!! The Balances Onchain Check FAILED !!!'
        else:
            print 'SUCCESS: !!! The Balances Onchain Check SUCCESS !!!'
        time_usage = time.time()-time_start
        print 'TIME USAGE:%ss, %s accounts/s ' % (time_usage, line_number/time_usage)
        return result
    except Exception as e:
        print action, ' get exception:', e
        print traceback.print_exc()
    finally:
        process_pool.close()
        process_pool.join()
        for file in conf_dict['dlfiles']:
            os.remove(conf_dict['dlfiles'][file])

if __name__ == '__main__':
    sys.exit( 0 if main() else 1)
