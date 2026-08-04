from web3 import Web3
from web3.providers.rpc import HTTPProvider
from web3.middleware import ExtraDataToPOAMiddleware
from pathlib import Path
import json
from datetime import datetime
import pandas as pd


def scan_blocks(chain, start_block, end_block, contract_address, eventfile='deposit_logs.csv'):
    if chain == 'avax':
        api_url = f"https://api.avax-test.network/ext/bc/C/rpc"
    if chain == 'bsc':
        api_url = f"https://data-seed-prebsc-1-s1.binance.org:8545/"
    if chain in ['avax','bsc']:
        w3 = Web3(Web3.HTTPProvider(api_url))
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    else:
        w3 = Web3(Web3.HTTPProvider(api_url))

    DEPOSIT_ABI = json.loads('[ { "anonymous": false, "inputs": [ { "indexed": true, "internalType": "address", "name": "token", "type": "address" }, { "indexed": true, "internalType": "address", "name": "recipient", "type": "address" }, { "indexed": false, "internalType": "uint256", "name": "amount", "type": "uint256" } ], "name": "Deposit", "type": "event" }]')
    contract = w3.eth.contract(address=contract_address, abi=DEPOSIT_ABI)

    if start_block == "latest":
        start_block = w3.eth.get_block_number()
    if end_block == "latest":
        end_block = w3.eth.get_block_number()

    if end_block < start_block:
        print(f"Error end_block < start_block!")
        return

    if start_block == end_block:
        print(f"Scanning block {start_block} on {chain}")
    else:
        print(f"Scanning blocks {start_block} - {end_block} on {chain}")

    # Use get_logs instead of create_filter (works on all nodes)
    logs = w3.eth.get_logs({
        'fromBlock': start_block,
        'toBlock': end_block,
        'address': contract_address
    })

    events = [contract.events.Deposit().process_log(log) for log in logs]

    for evt in events:
        block = w3.eth.get_block(evt['blockNumber'])
        timestamp = datetime.utcfromtimestamp(block['timestamp']).strftime('%m/%d/%Y %H:%M:%S')
        row = {
            'chain': chain,
            'token': evt.args['token'],
            'recipient': evt.args['recipient'],
            'amount': evt.args['amount'],
            'transactionHash': evt.transactionHash.hex(),
            'address': evt.address,
            'date': timestamp
        }
        if Path(eventfile).exists():
            pd.DataFrame([row]).to_csv(eventfile, mode='a', header=False, index=False)
        else:
            pd.DataFrame([row]).to_csv(eventfile, index=False)

    print(f"Found {len(events)} events")
