from web3 import Web3
from web3.providers.rpc import HTTPProvider
from web3.middleware import ExtraDataToPOAMiddleware
from datetime import datetime
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


def scan_blocks(chain, contract_info="contract_info.json"):
    if chain not in ['source','destination']:
        print(f"Invalid chain: {chain}")
        return 0

    with open('/home/codio/workspace/Bridge/sk.txt') as f:
        sk = f.read().strip()
    acct = eth_account.Account.from_key(sk)

    info = get_contract_info(chain, contract_info)
    other = 'destination' if chain == 'source' else 'source'
    other_info = get_contract_info(other, contract_info)

    w3 = connect_to(chain)
    other_w3 = connect_to(other)

    contract = w3.eth.contract(address=info['address'], abi=info['abi'])
    other_contract = other_w3.eth.contract(address=other_info['address'], abi=other_info['abi'])

    end_block = w3.eth.get_block_number()
    start_block = end_block - 5

    print(f"Scanning blocks {start_block} - {end_block} on {chain}")

    if chain == 'source':
        # Scan in batches of 5 blocks up to 30 blocks back
        all_events = []
        for batch_end in range(end_block, end_block - 31, -5):
            batch_start = batch_end - 5
            try:
                logs = w3.eth.get_logs({
                    'fromBlock': batch_start,
                    'toBlock': batch_end,
                    'address': info['address']
                })
                events = [contract.events.Deposit().process_log(log) for log in logs]
                all_events.extend(events)
            except Exception as e:
                print(f"Error getting logs for batch {batch_start}-{batch_end}: {e}")

        print(f"Found {len(all_events)} Deposit events")
        for evt in all_events:
            token = evt.args['token']
            recipient = evt.args['recipient']
            amount = evt.args['amount']
            print(f"Deposit: token={token} recipient={recipient} amount={amount}")
            try:
                tx = other_contract.functions.wrap(token, recipient, amount).build_transaction({
                    'from': acct.address,
                    'nonce': other_w3.eth.get_transaction_count(acct.address),
                    'gas': 500000,
                    'gasPrice': other_w3.eth.gas_price,
                })
                signed = other_w3.eth.account.sign_transaction(tx, sk)
                tx_hash = other_w3.eth.send_raw_transaction(signed.raw_transaction)
                receipt = other_w3.eth.wait_for_transaction_receipt(tx_hash)
                print(f"wrap(): {'Success' if receipt.status == 1 else 'Failed'}")
            except Exception as e:
                print(f"Error calling wrap: {e}")

    elif chain == 'destination':
        # Scan in batches of 5 blocks up to 30 blocks back
        all_events = []
        for batch_end in range(end_block, end_block - 31, -5):
            batch_start = batch_end - 5
            try:
                logs = w3.eth.get_logs({
                    'fromBlock': batch_start,
                    'toBlock': batch_end,
                    'address': info['address']
                })
                events = [contract.events.Unwrap().process_log(log) for log in logs]
                all_events.extend(events)
            except Exception as e:
                print(f"Error getting logs for batch {batch_start}-{batch_end}: {e}")

        print(f"Found {len(all_events)} Unwrap events")
        for evt in all_events:
            underlying_token = evt.args['underlying_token']
            recipient = evt.args['to']
            amount = evt.args['amount']
            print(f"Unwrap: token={underlying_token} recipient={recipient} amount={amount}")
            try:
                tx = other_contract.functions.withdraw(underlying_token, recipient, amount).build_transaction({
                    'from': acct.address,
                    'nonce': other_w3.eth.get_transaction_count(acct.address),
                    'gas': 500000,
                    'gasPrice': other_w3.eth.gas_price,
                })
                signed = other_w3.eth.account.sign_transaction(tx, sk)
                tx_hash = other_w3.eth.send_raw_transaction(signed.raw_transaction)
                receipt = other_w3.eth.wait_for_transaction_receipt(tx_hash)
                print(f"withdraw(): {'Success' if receipt.status == 1 else 'Failed'}")
            except Exception as e:
                print(f"Error calling withdraw: {e}")


if __name__ == "__main__":
    scan_blocks('source')
    scan_blocks('destination')
