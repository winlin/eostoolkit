# eos_onchain_validator.py 
#### is used to validate the balances by the snapshot.cvs and the legitimacy of the contracts on EOSIO blockchain.

### Theories:
The validation balance legality is the simple formula:
```
    EOS_SUPPLY_AMMOUNT = account_balance + account_net_weight + account_cpu_weight
```
- compare the snapshot account's balance with the same account's onchain balance
- compare the snapshot account's public key with the same account's active key
- extra account was created the formula will false
- check the extra system account by call /v1/history/get_controlled_accounts

### Feature:
- Contracts validation
- Account privilege check
- Snapshot balance validation
- Support eos-bios BIOS and easily to DIY

#### Requirements
This tool use Python 2.7 and with several packages, install with: pip install --upgrade xxx
```
pyyaml
beautifulsoup4
simplejson
requests
argparse
```

### Usage:
```
usage: eos_onchain_validator.py [-h] --action ACTION --config CONFIG

EOSIO onchain validator tool.

optional arguments:
  -h, --help       show this help message and exit
  --action ACTION  all|contract_validate|chain_validate
  --config CONFIG  validator.json config file path
```

### validator.json 
```
nodeosd_host: ip:host for the target network noedeosd ip and http port, for example 127.0.0.1:8888
snapshot_lines: 0 means check all the accounts; >0 means the number of the accounts to check
eos-bios.enable: true means the target network boosted by eos-bios
eos-bios.single_boot: whether the target neteork is running by eos-bios boot --single
eos-bios.seed_network_http_address: the seed network of eos-bios to get the registered producer accounts
code_hash_compare.nodeosd_host: the node which running the EOSIO mainnet version with system contracts and accounts
code_hash_compare.accounts: the codehash of account will be compared between nodeosd_host and code_hash_compare.nodeosd_host by /chain/get_code API

For example:
{
  "nodeosd_host":"127.0.0.1:10020",
  "eos_issued":2000000000.0000,
  "snapshot_lines":1000,
  "eos-bios":{
    "enable":true,
    "single_boot":false,
    "my_discovery_file":"/data/eos/eosbios/stage16/my_discovery_file.yaml",
    "seed_network_http_address":"http://stage15.testnets.eoscanada.com"
  },
  "code_hash_compare":{
    "nodeosd_host":"127.0.0.1:10016",
    "accounts":["eosio","eosio.msig","eosio.token","eosio.ram","eosio.ramfee","eosio.stake","eosio.names","eosio.saving","eosio.bpay","eosio.vpay"]
  }
}

```

### Validate all
```
python eos_onchain_validator.py --action all --config validator.json
```

### Validate the contract
```
python eos_onchain_validator.py --action chain_validate --config validator.json
```

### Validate the balances
```
python eos_onchain_validator.py --action contract_validate --config validator.json
```

### TODO:
 - find another way to decrease HTTP request times. 
    - keepalive to nodeosd has been tried, nodeosd will close the conntection

### Others
 - The validation of snapshot.cvs
    - this can be done by query the ETH fullnode, and it need to build the fullnode by yourself which maybe too complex. I prefer to use the version which get the most consensus from the community.
    - thank [ZhaoYu](https://github.com/JohnnyZhao) to realize the ETH onchain check code


