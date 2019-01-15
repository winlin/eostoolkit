# bos_onchain_validator.py 
#### is used to validate the balances by the snapshot files on BOS blockchain.

### Theories:
The validation balance legality is the simple formula:
```
    BOS_SUPPLY_AMMOUNT = account_balance + account_net_weight + account_cpu_weight
```
- compare the snapshot account's balance with the same account's onchain balance
- compare the snapshot account's public key with the same account's active key
- extra account was created the formula will false
- check the extra system account by call /v1/history/get_controlled_accounts

### Feature:
- Contracts validation
- Account privilege check
- Snapshot balance validation

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
usage: bos_onchain_validator.py [-h] --action ACTION --config CONFIG

BOS onchain validator tool.

optional arguments:
  -h, --help       show this help message and exit
  --action ACTION  all|contract_validate|chain_validate
  --config CONFIG  validator.json config file path
```

### validator.json - for EOS-BIOS
```
nodeosd_host: ip:host for the target network noedeosd ip and http port, for example 127.0.0.1:8888
snapshot_lines: 0 means check all the accounts; >0 means the number of the accounts to check
snapshot_url: the HTTP url to download, if eos-bios.enable==true, the snapshot file in ipfs will be used
code_hash_compare.nodeosd_host: the node which running the BOS mainnet version with system contracts and accounts
code_hash_compare.accounts: the codehash of account will be compared between nodeosd_host and code_hash_compare.nodeosd_host by /chain/get_code API

For example:
{
  "nodeosd_host":"127.0.0.1:81",
  "snapshot_lines":0,
  "token_name":"EOS",
  "snapshot_url":"https://raw.githubusercontent.com/eosauthority/genesis/master/snapshot-files/final/2/snapshot.csv",
  "eos-bios":{
    "enable":true,
    "single_boot":false,
    "my_discovery_file":"/data/eos/eosbios/stage20/my_discovery_file.yaml",
    "seed_network_http_address":"NO_USE"
  },
  "code_hash_compare":{
    "nodeosd_host":"127.0.0.1:80",
    "accounts":["bos","bos.msig","bos.token","bos.ram","bos.ramfee","bos.stake","bos.names","bos.saving","bos.bpay","bos.vpay"]
  }
}

```

### validator.json - for Ghostbuster / Manual Startup
```
nodeosd_host: ip:host for the target network noedeosd ip and http port, for example 127.0.0.1:8888
snapshot_lines: 0 means check all the accounts; >0 means the number of the accounts to check
snapshot_url: the HTTP url to download, if eos-bios.enable==true, the snapshot file in ipfs will be used
eos-bios.enable: false means the target network NOT boosted by eos-bios
eos-bios.single_boot: whether the target neteork is running by eos-bios boot --single
eos-bios.seed_network_http_address: the seed network of eos-bios to get the registered producer accounts
code_hash_compare.nodeosd_host: the node which running the BOS mainnet version with system contracts and accounts
code_hash_compare.accounts: the codehash of account will be compared between nodeosd_host and code_hash_compare.nodeosd_host by /chain/get_code API

For example:
{
  "nodeosd_host":"127.0.0.1:81",
  "snapshot_lines":0,
  "token_name":"EOS",
  "snapshot_url":"https://raw.githubusercontent.com/eosauthority/genesis/master/snapshot-files/final/2/snapshot.csv",
  "eos-bios":{
    "enable":false,
    "single_boot":false,
    "my_discovery_file":"/data/eos/eosbios/stage20/my_discovery_file.yaml",
    "seed_network_http_address":"NO_USE"
  },
  "code_hash_compare":{
    "nodeosd_host":"127.0.0.1:80",
    "accounts":["BOS","BOS.msig","BOS.token","BOS.ram","BOS.ramfee","BOS.stake","BOS.names","BOS.saving","BOS.bpay","BOS.vpay"]
  }
}
```

### Validate all
```
python bos_onchain_validator.py --action all --config validator.json
```

### Validate the contract
```
python bos_onchain_validator.py --action chain_validate --config validator.json
```

### Validate the balances
```
python bos_onchain_validator.py --action contract_validate --config validator.json
```

### TODO:
 - find another way to decrease HTTP request times. 
    - keepalive to nodeosd has been tried, nodeosd will close the conntection

### Others
 - The validation of snapshot.cvs
    - this can be done by query the ETH fullnode, and it need to build the fullnode by yourself which maybe too complex. I prefer to use the version which get the most consensus from the community.
    - thank [ZhaoYu](https://github.com/JohnnyZhao) to realize the ETH onchain check code


