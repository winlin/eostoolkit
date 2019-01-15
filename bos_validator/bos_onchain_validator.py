#!/usr/bin/python
# -*- coding: utf-8 -*-
#####################################
#         Winlin@EOSBIXIN           #
#####################################

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
def get_eosbios_producer_account(seed_network_http_address):
        return True, set()
        ret = requests.get(seed_network_http_address, timeout=6)
        if ret.status_code/100 != 2:
            print 'ERROR: failed to get producer account from:', seed_network_http_address
            return False, None
        producer_names = set()
        soup = BeautifulSoup(ret.text, 'html.parser')
        plist = soup.find_all('p')
        for line in plist:
            if 'Account:' not in str(line):
                continue
            pname = line.strong.text
            if len(pname) != 12:
                print 'ERROR: get illegal producer name len<12:', pname
                return False, None
            producer_names.add(pname)
        return True, producer_names

def dl_files(conf_dict, disco_conf):
    for file in disco_conf['target_contents']:
        if file['name'] not in ('boot_sequence.yaml', 'snapshot.csv'):
            continue
        print 'downloading:', file['name']
        tmpfile = os.path.join("/tmp/", str(time.time())+'_'+file['name'])
        wget_cmd = "wget -O %s https://ipfs.io%s > /dev/null 2>&1" % (tmpfile, file['ref'])
        ret = subprocess.call(wget_cmd, shell=True)
        if ret != 0:
            print 'ERROR: Failed to get file:',wget_cmd
            sys.exit(1)
        conf_dict['dlfiles'][file['name']] = tmpfile

def wget_snapshot_file(conf_dict):
    print 'downloading:', conf_dict['snapshot_url']
    tmpfile = os.path.join("/tmp/", str(time.time())+'_'+'snapshot.csv')
    wget_cmd = "wget -O %s %s > /dev/null 2>&1" % (tmpfile, conf_dict['snapshot_url'])
    ret = subprocess.call(wget_cmd, shell=True)
    if ret != 0:
        print 'ERROR: Failed to get file:',wget_cmd
        sys.exit(1)
    conf_dict['dlfiles']['snapshot.csv'] = tmpfile

def get_eosbios_account(conf_dict):
    conf_dict['sys_accounts'] = set(['eosio','eosio.msig','eosio.token','eosio.burned','eosio.names',
                                        'eosio.saving','eosio.bpay','eosio.vpay','eosio.disco',
                                        'eosio.ramfee','eosio.ram','eosio.unregd','eosio.stake','genesisblock'])
    conf_dict['producer_names'] = set()
    wget_snapshot_file(conf_dict)

    if 'eos-bios' not in conf_dict or not conf_dict['eos-bios']['enable']:
        return
    if not os.path.isfile(conf_dict['eos-bios']['my_discovery_file']):
        print 'ERROR: eos-bios my_discovery_file file not exist:',conf_dict['eos-bios']['my_discovery_file']
        sys.exit(1)
    disco_conf = None
    with open(conf_dict['eos-bios']['my_discovery_file'], 'r') as fp:
        disco_conf = yaml.load(fp)
    if not disco_conf:
        print 'ERROR: Failed to load the my_discovery_file file'
        sys.exit(1) 
    conf_dict['producer_names'].add(disco_conf['seed_network_account_name'])
    dl_files(conf_dict, disco_conf)

    # Get the create account in the BOOT SEQUENCE FILE
    eosbios_conf = None
    with open(conf_dict['dlfiles']['boot_sequence.yaml'], 'r') as fp:
        eosbios_conf = yaml.load(fp)
    if not eosbios_conf:
        print 'ERROR: Failed to load the boot_sequence file'
        sys.exit(1)
    
    for opt in eosbios_conf['boot_sequence']:
        if opt['op'] != 'system.newaccount': 
            continue
        if opt['data']['new_account'] and opt['data']['new_account'] not in ('b1',):
            conf_dict['sys_accounts'].add(opt['data']['new_account'])
    print 'Get ', len(conf_dict['sys_accounts']), ' system accounts from boot sequence file:', conf_dict['sys_accounts']

    # Get the producer account from blockchain
    if conf_dict['eos-bios']['single_boot']:
        print 'This is eos-bios single boot so will not query the producer accounts'
        return
    ret, conf_dict['producer_names'] = get_eosbios_producer_account(conf_dict['eos-bios']['seed_network_http_address'])
    if not ret:
        print 'Failed to get producer names'
        sys.exit(1)
    print 'Get ', len(conf_dict['producer_names']), ' producer account from chain:', conf_dict['producer_names']


############################################
#        Onchain Validation FUNCS          #
############################################
def token_str2float(token):
    num = Decimal(token.split(" ")[0])
    return num if num > 0 else 0

def weight_str2float(weight):
    num = Decimal(weight)
    return num/Decimal(10000.0) if num > 0 else 0

def check_account_privileged(account_info):
    #Validate the privileged, ONLY (eosio、eosio.msig) can be privileged FOR NOW
    is_sys_acct = account_info['account_name'] in ('eosio', 'eosio.msig')
    if (account_info['privileged'] and not is_sys_acct) or (not account_info['privileged'] and is_sys_acct):
        print 'privileged check failed :', account_info['account_name'], ' privileged:', account_info['privileged']
        return False
    #Check the ram_quota
    if account_info['ram_quota'] > 8157:
        print 'ram_quota <= 8157 check failed:', account_info['ram_quota']
        return False
    return True

def get_onchain_balance(account_name, node_host):
        body = {'scope':account_name, 'code':'eosio.token', 'table':'accounts', 'json':True}
        ret = requests.post("http://%s/v1/chain/get_table_rows" % node_host, data=json.dumps(body), timeout=2)
        if ret.status_code/100 != 2:
            print 'ERROR: failed to call get_table_rows accounts for:', account_name, ret.text
            return -1
        balance_info = json.loads(ret.text)
        balance = Decimal(0.0)
        if balance_info['rows']:
            # {"rows":[{"balance":"804148103.4130 SYS"}],"more":false}
            balance = token_str2float(balance_info['rows'][0]['balance'])
        return balance

def check_balance_signal_account(param):
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

        if balance > Decimal(10.0001):
            print 'ERROR: %-12s balance:%s > 10.0001' % (account_name, balance)
            return signal_onchain_amount

        net_weight, cpu_weight = token_str2float(account_info['total_resources']['net_weight']), token_str2float(account_info['total_resources']['cpu_weight'])
        if abs(net_weight - cpu_weight) > Decimal(0.0001):
            print 'ERROR: %-12s net_weight %s != cpu_weight %s' % (account_name, net_weight, cpu_weight)
            return signal_onchain_amount

        net_delegated, cpu_delegated = Decimal(0), Decimal(0)
        if account_info['delegated_bandwidth']:
            net_delegated, cpu_delegated = token_str2float(account_info['delegated_bandwidth']['net_weight']), token_str2float(account_info['delegated_bandwidth']['cpu_weight'])

        # Validate the balance onchain whether same with the snapshot amount
        onchain_balance = balance + net_weight + cpu_weight

        if abs(snapshot_balance - onchain_balance) > Decimal(0.0001):
            print '%-12s balance:%s net_delegated:%s cpu_delegated:%s net_weight:%s cpu_weight:%s onchain_balance:%s snapshot_balance:%s' % (account_name, balance, 
                    net_delegated, cpu_delegated, net_weight, cpu_weight, onchain_balance, snapshot_balance)
            print 'ERROR: account %s snapshot_balance(%s) != onchain_balance(%s)' % (account_name, snapshot_balance, onchain_balance)
            return signal_onchain_amount
        
        signal_onchain_amount = balance + net_weight + cpu_weight
        return signal_onchain_amount
    except Exception as e:
        print 'check_balance_signal_account get exception:', e
        print traceback.print_exc()
        return signal_onchain_amount

def get_sys_producer_balance_account(node_host, account_name, account_type):
    onchain_amount = Decimal(0)
    try:
        # call get account
        ret = requests.post("http://%s/v1/chain/get_account" % node_host, data=json.dumps({'account_name':account_name}), timeout=2)
        if ret.status_code/100 != 2:
            print 'WARNING: failed to call get_account for:', account_name
            return onchain_amount
        account_info = json.loads(ret.text)

        # Validate the privileged
        if not check_account_privileged(account_info):
            print 'ERROR: account %s privileged check failed:', account_info
            return signal_onchain_amount
        
        net_weight, cpu_weight = weight_str2float(account_info['net_weight']), weight_str2float(account_info['cpu_weight'])

        net_delegated, cpu_delegated = Decimal(0), Decimal(0)
        if account_info['delegated_bandwidth']:
            net_delegated, cpu_delegated = token_str2float(account_info['delegated_bandwidth']['net_weight']), token_str2float(account_info['delegated_bandwidth']['cpu_weight'])

        # call get account balance
        balance = get_onchain_balance(account_name, node_host)
        if balance < 0:
            print 'ERROR: failed to call get_table_rows accounts for:', account_name, ret.text
            return onchain_amount

        print '%-12s balance:%s net_delegated:%s cpu_delegated:%s net_weight:%s cpu_weight:%s onchain_amount:%s' % (account_name, balance, 
                    net_delegated, cpu_delegated, net_weight, cpu_weight, (balance+net_delegated+cpu_delegated))

        onchain_amount = balance + net_weight + cpu_weight
        return onchain_amount
    except Exception as e:
        print 'get_sys_producer_balance_account get exception:', e
        print traceback.print_exc()
        return onchain_amount

def get_sys_producer_balances(conf_dict):
    # Check whether there is other system account
    conf_dict['eosio_descendant_account'] = set(conf_dict['sys_accounts'])
    if not get_sys_account_servants(conf_dict):
        print 'ERROR: failed to get the system accounts servants'
        return False
    other_account = conf_dict['eosio_descendant_account'] - conf_dict['sys_accounts']
    if len(other_account)>0:
        print 'ERROR: there are other system accounts:', ", ".join(other_account)
        return False

    conf_dict['sys_producer_amount'] = {}
    for key in ('sys_accounts','producer_names'):
        for acct in conf_dict[key]:
            if key == 'sys_accounts' and acct == 'eosio.stake':
                # eosio.stake contains the net_weight/cup_weight of accounts so here just skip
                continue
            conf_dict['sys_producer_amount'][acct] = get_sys_producer_balance_account(conf_dict['nodeosd_host'], acct, key)
    return True

def get_sys_account_servants(conf_dict):
    for account_name in conf_dict['sys_accounts']:
        ret = requests.post("http://%s/v1/history/get_controlled_accounts" % conf_dict['nodeosd_host'], data=json.dumps({'controlling_account':account_name}), timeout=2)
        if ret.status_code/100 != 2:
            print 'WARNING: failed to call get_controlled_accounts for:', account_name
            return False
        accounts = json.loads(ret.text)
        if len(accounts['controlled_accounts'])>0:
            conf_dict['eosio_descendant_account'] |= set(accounts['controlled_accounts'])
    return True

def get_eos_currency_stat(conf_dict):
    ret = requests.post("http://%s/v1/chain/get_currency_stats" % conf_dict['nodeosd_host'], data=json.dumps({"json":True,"code":"eosio.token","symbol":conf_dict['token_name']}), timeout=2)
    if ret.status_code/100 != 2:
        print 'WARNING: failed to call get_currency_stats for EOS'
        return False
    eos_stats = json.loads(ret.text)
    if not eos_stats or not eos_stats['EOS']:
        print 'WARNING: get empty to call get_currency_stats for EOS'
        return False
    conf_dict['eos_stats'] = eos_stats['EOS']
    return True


############################################
#        Validate Onchain Balance          #
############################################
def check_balance(conf_dict, process_pool, cpu_count):
    get_eosbios_account(conf_dict)

    if not get_eos_currency_stat(conf_dict):
        return False, 0

    if not get_sys_producer_balances(conf_dict):
        return False, 0

    node_host, snapshot_csv = conf_dict['nodeosd_host'], conf_dict['dlfiles']['snapshot.csv']
    account_onchain_balance_total, batch_size = Decimal(0.0), cpu_count*100
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
        check_result = True
        for account_name in conf_dict["code_hash_compare"]["accounts"]:
            print 'Comparing codehash for:', account_name 
            cur_ret = requests.post("http://%s/v1/chain/get_code" % conf_dict['nodeosd_host'], data=json.dumps({'account_name':account_name}), timeout=5)
            if cur_ret.status_code/100 != 2:
                print 'ERROR: failed to call get_code for:', account_name, conf_dict['nodeosd_host'], cur_ret.text
                check_result = False
            cur_code_info = json.loads(cur_ret.text)
            compare_ret = requests.post("http://%s/v1/chain/get_code" % conf_dict['code_hash_compare']['nodeosd_host'], data=json.dumps({'account_name':account_name}), timeout=5)
            if compare_ret.status_code/100 != 2:
                print 'ERROR: failed to call get_code for:', account_name, conf_dict['code_hash_compare']['nodeosd_host'], compare_ret.text
                check_result = False
            compare_code_info = json.loads(compare_ret.text)
            if cur_code_info['code_hash'] != compare_code_info['code_hash']:
                print 'ERROR: code hash compare failed:', account_name, cur_code_info['code_hash'], compare_code_info['code_hash']
                check_result = False
            print account_name, cur_code_info['code_hash'], compare_code_info['code_hash']
        if check_result:
            print 'SUCCESS: !!! The Contracts Check SUCCESS !!!'
        else:
            print 'ERROR: !!! The Contracts Check FAILED !!!'
        return check_result
    except Exception as e:
        print 'ERROR: !!! The Contracts Check FAILED !!!'
        print traceback.print_exc()
        return False

####################################################################


def main():
    parser = argparse.ArgumentParser(description='EOSIO onchain validator tool.')
    parser.add_argument('--action', type=str, required=True, help='all|contract_validate|chain_validate')
    parser.add_argument('--config', type=str, required=True, help='validator.json config file path')
    args = parser.parse_args()
    action, conf_file = args.action, os.path.abspath(os.path.expanduser(args.config))
    # Check the parameters
    if action not in ('all', 'contract_validate', 'chain_validate'):
        print 'ERROR: action should be one of all|contract_validate|chain_validate'
        sys.exit(1)
    if not os.path.isfile(conf_file):
        print 'ERROR: validator config file not exist:',conf_file
        sys.exit(1)
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
        if action == 'all':
            check_contracts(conf_dict)

            time_start = time.time()
            result, line_number = check_balance(conf_dict, process_pool, cpu_count)
            if not result:
                print 'ERROR: !!! The Balances Onchain Check FAILED !!!'
            else:
                print 'SUCCESS: !!! The Balances Onchain Check SUCCESS !!!'
            time_usage = time.time()-time_start
            print 'TIME USAGE:%ss, %s accounts/s ' % (time_usage, line_number/time_usage)
            return result
        elif action == 'contract_validate':
            return check_contracts(conf_dict)

        elif action == 'chain_validate':
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
