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


def update_auth(account, auth_rule):
    cmd_line_active = "sudo docker exec 62f1ea95193d cleos -u http://127.0.0.1:8008 --wallet-url http://127.0.0.1:8888 push action eosio updateauth '%s' -p %s@owner" % (json.dumps(auth_rule), account)
    print cmd_line_active
    ret = subprocess.call(cmd_line_active, shell=True)
    return ret == 0

def twins(param):
    account1, auth_rule1,account2, auth_rule2,line=param
    print 'Updateauth %d %s' % (line, account1)
    v1= update_auth(account1, auth_rule1)
    v2=update_auth(account2, auth_rule2)
    return v1 and v2

def multi_run(process_pool,cpu_count,path):
    try:
        line_nu=0
        account=[]
        rule=[]
        batch_lines, cur_len ,batch_size= [None] * batch_size, 0,  cpu_count*100
        with open(path, 'r') as fp:
            for line in fp.readlines():
                account_info = json.loads(line)
                account.append(account_info['data']['account'])
                rule.append(account_info['data'])
                if line_nu%2==1:
                    batch_lines[cur_len] = (account[0],rule[0],account[1],rule[1],line_nu)
                    account=[]
                    rule=[] 
                line_nu += 1
                if cur_len<batch_size:
                    continue
                
                result= process_pool.map( twins,batch_lines)
                if result:
                    print 'Failed to create %s line_nu:%d' % (account[0], line_nu)
                        #sys.exit(1)
                batch_lines, cur_len = [None] * batch_size, 0   

        if cur_len>0:
                result= process_pool.map( twins,batch_lines)
                if result:
                    print 'Failed to create %s line_nu:%d' % (account[0], line_nu)     
    except Exception as e:
        print 'EXCEPTION: there are exception:', e
        print traceback.print_exc()


def main():
    # Start the validation
    cpu_count = multiprocessing.cpu_count()
    process_pool = multiprocessing.Pool(processes=cpu_count)
    try:
        multi_run(process_pool,sys.argv[1])

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