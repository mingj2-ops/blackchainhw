from web3 import Web3
from web3.providers.rpc import HTTPProvider
from web3.middleware import ExtraDataToPOAMiddleware
import json
import eth_account


def connect_to(chain):
    if chain == 'source':
        api_url = "https://api.avax-test.network/ext/bc/C/rpc"
    if chain == 'destination':
        api_url = "https://bnb-testnet.g.alchemy.com/v2/alch_df96p96cR5ZqzG_jn7YMG"
    if chain in ['source','destination']:
        w3 = Web3(Web3.HTTPProvider(api_url))
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    return w3


def get_contract_info(chain, contract_info):
    try:
        with open(contract_info, 'r') as f:
            contracts = json.load(f)
    except Exception as e:
        print(f"Failed to read contract info\n{e}")
        return 0
    return contracts[chain]


def get_logs_in_batches(w3, address, start_block, end_block, batch_size=5):
    all_logs = []
    for batch_start in range(start_block, end_block + 1, batch_size):
        batch_end = min(batch_start + batch_size - 1, end_block)
        try:
            logs = w3.eth.get_logs({
                'fromBlock': batch_start,
                'toBlock': batch_end,
                'address': address
            })
            all_logs.extend(logs)
        except Exception as e:
            print(f"Error getting logs {batch_start}-{batch_end}: {e}")
    return all_logs


def scan_blocks(chain, contract_info="contract_info.json"):
    if chain not in ['source','destination']:
        print(f"Invalid chain: {chain}")
        return 0

    with open('/home/codio/workspace/Bridge/sk.txt') as f:
        sk = f.read().strip()
    acct = eth_account.Account.from_key(sk)

    source_info = get_contract_info('source', contract_info)
    dest_info = get_contract_info('destination', contract_info)

    source_w3 = connect_to('source')
    dest_w3 = connect_to('destination')

    source_contract = source_w3.eth.contract(address=source_info['address'], abi=source_info['abi'])
    dest_contract = dest_w3.eth.contract(address=dest_info['address'], abi=dest_info['abi'])

    UNWRAP_ABI = json.loads('[{"type":"event","name":"Unwrap","inputs":[{"name":"underlying_token","type":"address","indexed":true},{"name":"wrapped_token","type":"address","indexed":true},{"name":"frm","type":"address","indexed":false},{"name":"to","type":"address","indexed":true},{"name":"amount","type":"uint256","indexed":false}],"anonymous":false}]')
    dest_contract2 = dest_w3.eth.contract(address=dest_info['address'], abi=UNWRAP_ABI)

    # Scan source for Deposit events -> wrap on destination
    source_end = source_w3.eth.get_block_number()
    source_start = source_end - 50
    print(f"Scanning blocks {source_start} - {source_end} on source")

    logs = get_logs_in_batches(source_w3, source_info['address'], source_start, source_end)
    deposit_events = [source_contract.events.Deposit().process_log(log) for log in logs]
    print(f"Found {len(deposit_events)} Deposit events")

    for evt in deposit_events:
        token = evt.args['token']
        recipient = evt.args['recipient']
        amount = evt.args['amount']
        print(f"Deposit: token={token} recipient={recipient} amount={amount}")
        try:
            nonce = dest_w3.eth.get_transaction_count(acct.address, 'pending')
            tx = dest_contract.functions.wrap(token, recipient, amount).build_transaction({
                'from': acct.address,
                'nonce': nonce,
                'gas': 500000,
                'gasPrice': dest_w3.eth.gas_price,
            })
            signed = dest_w3.eth.account.sign_transaction(tx, sk)
            tx_hash = dest_w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = dest_w3.eth.wait_for_transaction_receipt(tx_hash)
            print(f"wrap(): {'Success' if receipt.status == 1 else 'Failed'}")
        except Exception as e:
            print(f"Error calling wrap: {e}")

    # Scan destination for Unwrap events -> withdraw on source
    dest_end = dest_w3.eth.get_block_number()
    dest_start = dest_end - 30
    print(f"Scanning blocks {dest_start} - {dest_end} on destination")

    logs = get_logs_in_batches(dest_w3, dest_info['address'], dest_start, dest_end)
    unwrap_events = []
    for log in logs:
        try:
            evt = dest_contract2.events.Unwrap().process_log(log)
            unwrap_events.append(evt)
        except Exception:
            continue

    print(f"Found {len(unwrap_events)} Unwrap events")
    for evt in unwrap_events:
        underlying_token = evt.args['underlying_token']
        recipient = evt.args['to']
        amount = evt.args['amount']
        print(f"Unwrap: token={underlying_token} recipient={recipient} amount={amount}")
        try:
            nonce = source_w3.eth.get_transaction_count(acct.address, 'pending')
            tx = source_contract.functions.withdraw(underlying_token, recipient, amount).build_transaction({
                'from': acct.address,
                'nonce': nonce,
                'gas': 500000,
                'gasPrice': source_w3.eth.gas_price,
            })
            signed = source_w3.eth.account.sign_transaction(tx, sk)
            tx_hash = source_w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = source_w3.eth.wait_for_transaction_receipt(tx_hash)
            print(f"withdraw(): {'Success' if receipt.status == 1 else 'Failed'}")
        except Exception as e:
            print(f"Error calling withdraw: {e}")


if __name__ == "__main__":
    scan_blocks('source')
    scan_blocks('destination')
