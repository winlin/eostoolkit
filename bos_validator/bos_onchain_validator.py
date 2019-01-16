#!/usr/bin/python
# -*- coding: utf-8 -*-
#####################################
#         Winlin@EOSBIXIN           #
#####################################

from __future__ import unicode_literals
import os
import sys
import time
#import json
#import yaml
import requests
import argparse
import subprocess
import traceback
import simplejson as json
import multiprocessing
from decimal import Decimal, getcontext

requests.adapters.DEFAULT_RETRIES = 3

############################################
#        Onchain Validation FUNCS          #
############################################
def token_str2float(token):
    num = Decimal(token.split(" ")[0])
    return num if num > 0 else 0

def weight_str2float(weight):
    num = Decimal(weight)
    return num/Decimal(10000.0) if num > 0 else 0

def get_onchain_balance(account_name, node_host):
        body = {'scope':account_name, 'code':'eosio.token', 'table':'accounts', 'json':True}
        ret = requests.post("http://%s/v1/chain/get_table_rows" % node_host, data=json.dumps(body), timeout=4)
        if ret.status_code/100 != 2:
            print 'ERROR: failed to call get_table_rows accounts for:', account_name, ret.text
            return -1
        balance_info = json.loads(ret.text)
        balance = Decimal(0.0)
        if balance_info['rows']:
            # {"rows":[{"balance":"804148103.4130 SYS"}],"more":false}
            balance = token_str2float(balance_info['rows'][0]['balance'])
        return balance

def  check_permissions_keys(local_keys,promote_keys):
    times=0
    for promote_key_types in promote_keys:
        have=False
        if promote_key_types["perm_name"] not in ("owner","active"):
            continue ;
        times+=1
        for local_key_types in local_keys:
            
            if promote_key_types["perm_name"]==local_key_types["perm_name"]:
                have=True
                # if promote_key_types["threshold"]!=local_key_types["threshold"]:
                #     return False
                length=len(promote_key_types["required_auth"]["keys"])
                for promote_key in promote_key_types["required_auth"]["keys"]:
                    for local_key in local_key_types["required_auth"]["keys"]:
                        if promote_key["key"]==local_key["key"]:
                            length-=1
                            break
                if length>0:
                    print "ERROR:check %s failed detail onchain info:\n%s \nsnapshot info:\n%s" % (promote_key_types["perm_name"],
                        json.dumps(promote_keys), json.dumps(local_keys))
                    #return False
        if not have:
            print("ERROR:check perm_name failed detail %s" %(json.dumps(promote_keys)))
            return False;
    return times==2


def check_balance_signal_account(param):
    node_host, account_name, permissions, snapshot_balance = param
    signal_onchain_amount = Decimal(-1)
    try:
        # call get account
        ret = requests.post("http://%s/v1/chain/get_account" % node_host, data=json.dumps({'account_name':account_name}), timeout=4)
        if ret.status_code/100 != 2:
            print 'ERROR: failed to call get_account for:', account_name, ret.text
            return signal_onchain_amount
        account_info = json.loads(ret.text)

        # Validate the public key onchain whether same with the snapshot
        #owner_pubkey = account_info['permissions'][0]['required_auth']['keys'][0]['key']
        if not check_permissions_keys(permissions, account_info["permissions"]):
            print 'ERROR: account %s snapshot active key or owner key not equal ' % (account_name)
            return signal_onchain_amount

        balance = token_str2float(account_info['core_liquid_balance'])
        if balance > Decimal(10.0001):
            print 'ERROR: %-12s balance:%s > 10.0001' % (account_name, balance)
            return signal_onchain_amount

        net_weight, cpu_weight = token_str2float(account_info['total_resources']['net_weight']), token_str2float(account_info['total_resources']['cpu_weight'])
        if abs(net_weight - cpu_weight) > Decimal(0.0001):
            print 'ERROR: %-12s net_weight %s != cpu_weight %s' % (account_name, net_weight, cpu_weight)
            return signal_onchain_amount

        # Validate the balance onchain whether same with the snapshot amount
        onchain_balance = balance + net_weight + cpu_weight
        if balance > 0.5000 and abs(snapshot_balance - onchain_balance) > Decimal(0.2001):
            print '%-12s balance:%s net_weight:%s cpu_weight:%s onchain_balance:%s snapshot_balance:%s' % (account_name, balance,
                     net_weight, cpu_weight, onchain_balance, snapshot_balance)
            print 'ERROR: account %s snapshot_balance(%s) != onchain_balance(%s)' % (account_name, snapshot_balance, onchain_balance)
            return signal_onchain_amount

        signal_onchain_amount = balance + net_weight + cpu_weight + Decimal(0.3) # RAM
        return signal_onchain_amount
    except Exception as e:
        print 'check_balance_signal_account get exception:', e
        print traceback.print_exc()
        return signal_onchain_amount


############################################
#        Validate Onchain Balance          #
############################################
def check_balance(conf_dict, process_pool, cpu_count):
    node_host, snapshot_csv ,snapshot_json= conf_dict['nodeosd_host'], conf_dict['snapshot.csv'],conf_dict['snapshot.json']
    account_onchain_balance_total, batch_size = Decimal(0.0), cpu_count*100

    try:
        line_nu=0
        with open(snapshot_csv, 'r') as fp:
            batch_lines, cur_len = [None] * batch_size, 0
            for line in fp.readlines():
                _, owner_key,active_key,eos_balance,bos_account,bos_balance = line.split(',')
                batch_lines[cur_len] = (node_host, bos_account,[
                    {"perm_name": "active",
            "required_auth": {
                "threshold": 2,
                "keys": [{"key": active_key}]}},
                {"perm_name": "owner",
            "required_auth": {
                "threshold": 2,
                "keys": [{"key": owner_key}]}}
                ], Decimal(token_str2float(bos_balance)))
                cur_len += 1
                line_nu += 1
                if conf_dict['snapshot_lines']>0 and line_nu>=conf_dict['snapshot_lines']:
                    print 'Stop validate because snapshot_lines was set to:', conf_dict['snapshot_lines']
                    break
                if cur_len<batch_size:
                    continue
                results = process_pool.map(check_balance_signal_account, batch_lines, cpu_count)
                for signal_onchain_amount in results:
                    if signal_onchain_amount < 0:
                        return False, line_nu
                    account_onchain_balance_total += signal_onchain_amount
                print 'check progress, account number:', line_nu, ' common accounts balance:', account_onchain_balance_total
                batch_lines, cur_len = [None] * batch_size, 0

            if cur_len>0:
                results = process_pool.map(check_balance_signal_account, batch_lines[:cur_len], cpu_count)
                for signal_onchain_amount in results:
                    if signal_onchain_amount < 0:
                        return False, line_nu
                    account_onchain_balance_total += signal_onchain_amount

        with open(snapshot_json, 'r') as fp:
            batch_lines, cur_len= [None] * batch_size, 0
            for line in fp.readlines():
                accountmsg=json.loads(line)
                batch_lines[cur_len] = (node_host, accountmsg["bos_account"], accountmsg['permissions'], token_str2float(accountmsg["bos_balance"]))
                cur_len += 1
                line_nu += 1
                if conf_dict['snapshot_lines']>0 and line_nu>=conf_dict['snapshot_lines']:
                    print 'Stop validate because snapshot_lines was set to:', conf_dict['snapshot_lines']
                    break
                if cur_len<batch_size:
                    continue
                results = process_pool.map(check_balance_signal_account, batch_lines, cpu_count)
                for signal_onchain_amount in results:
                    if signal_onchain_amount < 0:
                        return False, line_nu
                    account_onchain_balance_total += signal_onchain_amount
                print 'check progress, account number:', line_nu, ' common accounts balance:', account_onchain_balance_total
                batch_lines, cur_len = [None] * batch_size, 0

            if cur_len>0:
                results = process_pool.map(check_balance_signal_account, batch_lines[:cur_len], cpu_count)
                for signal_onchain_amount in results:
                    if signal_onchain_amount < 0:
                        return False, line_nu
                    account_onchain_balance_total += signal_onchain_amount

            print 'Onchain: common accounts balance:', account_onchain_balance_total, ' account number:', line_nu
            
            airdrop_bos = get_onchain_balance('airdrop.bos', node_host)
            print 'Get airdrop.bos balance:%s' % airdrop_bos
    
            onchain_account_balance = account_onchain_balance_total

            if abs(Decimal(conf_dict['airdrop.bos'])-onchain_account_balance-airdrop_bos) > Decimal(50.0001):  # 50 BOS to buy RAM
                print 'ERROR: airdrop failed: airdrop online amount:', onchain_account_balance
                return False, line_nu
            return True, line_nu
    except Exception as e:
        print 'EXCEPTION: there are exception:', e
        print traceback.print_exc()
        return False, 0


####################################################################


def main():
    parser = argparse.ArgumentParser(description='EOSIO onchain validator tool.')
    parser.add_argument('--config', type=str, required=True, help='validator.json config file path')
    args = parser.parse_args()
    conf_file = os.path.abspath(os.path.expanduser(args.config))
    conf_dict = None
    with open(conf_file, 'r') as fp:
        conf_dict = json.loads(fp.read())
    if not conf_dict:
        print 'ERROR: validator config can not be empty:',conf_file
        sys.exit(1)
    conf_dict['dlfiles'] = {}

    # Start the validation
    cpu_count = multiprocessing.cpu_count() 
    process_pool = multiprocessing.Pool(processes=cpu_count)
    try:
        time_start = time.time()
        result, line_number = check_balance(conf_dict, process_pool, cpu_count)
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
