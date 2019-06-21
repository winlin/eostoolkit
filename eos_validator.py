
# Check the TOKEN amount
def check_balance(node_host="http://localhost:8888", snapshot_csv="./snapshot.csv", eos_total=1000000000):
    with open(snapshot_csv, 'r') as fp:
        account_onchain_total = 0
        for onepersion in fp.readline()
            account_name, account_amount, pub_key = json.loads(onepersion)['name'], json.loads(onepersion)['amount'],json.loads(onepersion)['pub'] 
            if account_amount<1.0:
                continue
            account_balance = exec('cleos -u ' + node_host + ' get currency balance eosio.token ' + account_name)
            account_net_delegated = exec('cleos -u ' + node_host + ' get account ' + account_name)['delegated_bandwidth']['net_weight']
            account_cpu_delegated = exec('cleos -u ' + node_host + ' get account ' + account_name)['delegated_bandwidth']['cpu_weight']
            account_onchain_amount = account_balance+account_net_delegated+account_net_delegated
            if abs(account_amount - account_onchain_amount) > 0.0001:
                # Validate Failed because the amount in onchainblock NOT same with the snapshot
                raise Exception("account balance failed: ", account_name)

            account_onchain_pubkey = exec('cleos -u ' + node_host + ' get account ' + account_name)['permissions']['owner']
            if pub_key!=account_onchain_pubkey:
                # Validate Failed because the public key in onchainblock NOT same with the snapshot
                raise Exception("account public key failed: ", account_name)

            eosio_onchain_balance += account_onchain_amount

        eosio_onchain_balance = exec('cleos -u ' + node_host + ' get currency balance eosio.token eosio')
        if abs(eos_total - (eosio_onchain_balance + eosio_onchain_balance)) > 0.0001:
            # Validate Failed because the eos_total NOT match all legal amount
            raise Exception("There are illegal SYS transfer to unknow accounts")


# Check the CONTRACT
def check_contract(node_host="http://localhost:8888")
    contract_hash_map = {
        'eosio.msig':{'cmd':'cleos get code eosio.msig' 'abi':'YOUR_ABI_HASH_VAL', 'wasm':'YOUR_WASM_HASH_VAL'}
        'eosio.token':{'cmd':'cleos get code eosio.token', 'abi':'YOUR_ABI_HASH_VAL', 'wasm':'YOUR_WASM_HASH_VAL'}
        'eosio.disco':{'cmd':'cleos get code eosio.disco', 'abi':'YOUR_ABI_HASH_VAL', 'wasm':'YOUR_WASM_HASH_VAL'}
        'eosio.unregd':{'cmd':'cleos get code eosio.unregd', 'abi':'YOUR_ABI_HASH_VAL', 'wasm':'YOUR_WASM_HASH_VAL'}
        'eosio':{'cmd':'cleos get code eosio', 'abi':'YOUR_ABI_HASH_VAL', 'wasm':'YOUR_WASM_HASH_VAL'}
        #... maybe more other contract
    }
    for contract in contract_hash_map:
        abi_json, wasm_content = get_code(contract_hash_map[contract]['cmd'])
        wasm_hash = sha256(wasm_content)
        if wasm_hash != contract_hash_map[contract]['wasm']:
            # Validate Failed because the WASM file NOT match
            raise Exception("WASM file NOT match")
        if sha256(sort_json(abi_json)) != contract_hash_map[contract]['abi']:
            # Validate Failed because the ABI file NOT match
            raise Exception("ABI file NOT match")


