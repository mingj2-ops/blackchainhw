#!/bin/python
import hashlib
import os
import random


def mine_block(k, prev_hash, transactions):
    """
        k - Number of trailing zeros in the binary representation (integer)
        prev_hash - the hash of the previous block (bytes)
        rand_lines - a set of "transactions," i.e., data to be included in this block (list of strings)

        Complete this function to find a nonce such that 
        sha256( prev_hash + rand_lines + nonce )
        has k trailing zeros in its *binary* representation
    """
    if not isinstance(k, int) or k < 0:
        print("mine_block expects positive integer")
        return b'\x00'

    # TODO your code to find a nonce here
    nonce = 0
    while True:
        nonce_bytes = nonce.to_bytes((nonce.bit_length() + 7) // 8 or 1, 'big')

        m = hashlib.sha256()
        m.update(prev_hash)
        for t in transactions:
            m.update(t.encode('utf-8'))
        m.update(nonce_bytes)

        hash_bytes = m.digest()

        # Check k trailing zero bits
        hash_int = int.from_bytes(hash_bytes, 'big')
        if hash_int % (2 ** k) == 0:
            break

        nonce += 1

    assert isinstance(nonce_bytes, bytes), 'nonce should be of type bytes'
    return nonce_bytes


def get_random_lines(filename, quantity):
    """
    This is a helper function to get the quantity of lines ("transactions")
    as a list from the filename given. 
    Do not modify this function
    """
    lines = []
    with open(filename, 'r') as f:
        for line in f:
            lines.append(line.strip())

    random_lines = []
    for x in range(quantity):
        random_lines.append(lines[random.randint(0, quantity - 1)])
    return random_lines


if __name__ == '__main__':
    filename = "bitcoin_text.txt"
    num_lines = 10

    diff = 20

    transactions = get_random_lines(filename, num_lines)
    prev_hash = os.urandom(32)
    nonce = mine_block(diff, prev_hash, transactions)
    print(f"Found nonce: {nonce}")
    print(f"Nonce (hex): {nonce.hex()}")