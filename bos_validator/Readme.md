# bos_onchain_validator.py 
#### Used to validate the balances by the snapshot files on BOS blockchain.

(BOS Snapshot)[https://github.com/boscore/bos-airdrop-snapshots]

### Theories:
As the BOS Mainnet need about 1.5 hours to inject the snapshot, and the ABP will be one from BOS Core Team,  
so we just need to validate the snapshot file and the keys.

The validation balance legality is the simple rules:
- compare the snapshot account's balance with the same account's onchain balance
- compare the snapshot account's keys with the same account's onchain keys
- the aridrop amount must equal with the all account balances
- aridrop.bos balance should be 0 after airdrop


### Feature:
- Account privilege check
- Snapshot balance validation

#### Requirements
This tool use Python 2.7 and with several packages, install with: pip install --upgrade xxx
```
simplejson
requests
argparse
```

### Usage:
```
usage: bos_onchain_validator.py [-h] --config CONFIG

BOS onchain validator tool.

optional arguments:
  -h, --help       show this help message and exit
  --config CONFIG  validator.json config file path
```

### validator.json
```
For example:
{
  "nodeosd_host":"127.0.0.1:87",
  "token_name":"BOS",
  "snapshot.csv":"/data/bos/bos-airdrop-snapshots/accounts_info_bos_snapshot.airdrop.normal.csv",
  "snapshot.json":"/data/bos/bos-airdrop-snapshots/accounts_info_bos_snapshot.airdrop.msig.json"
}
```

### Validate
```
python bos_onchain_validator.py --config validator.json
```