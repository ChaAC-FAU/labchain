#!/usr/bin/env python3

import argparse
import requests

from binascii import hexlify, unhexlify

from src.blockchain import Blockchain
from src.block import Block
from src.transaction import Transaction
from src.crypto import Signing

def send_transaction(sess, url, transaction):
    resp = sess.put(url + 'new-transaction', data=transaction.to_json_compatible())
    resp.raise_for_status()

def network_info(sess, url):
    resp = sess.get(url + 'network-info')
    resp.raise_for_status()
    return resp.json()

def get_transactions(sess, url, pubkey):
    resp = sess.post(url + 'transactions', data=pubkey.as_bytes())
    resp.raise_for_status()
    return [Transaction.from_json_compatible(t) for t in resp.json()]

def main():
    parser = argparse.ArgumentParser(description="Wallet.")
    parser.add_argument("--miner-port", default=40203, type=int,
                        help="The RPC port of the miner to connect to.")
    parser.add_argument("--show-transactions", type=argparse.FileType("rb"), default=[], action="append",
                        help="Shows all transactions involving the public key stored in the specified file.")
    parser.add_argument("--show-network", action="store_true", default=False,
                        help="Prints networking information about the miner.")
    args = parser.parse_args()

    url = "http://localhost:{}/".format(args.miner_port)
    s = requests.session()

    for key in args.show_transactions:
        for trans in get_transactions(s, url, Signing(key.read())):
            print(trans.to_json_compatible())
        key.close()

    if args.show_network:
        for [k, v] in network_info(s, url):
            print("{}\t{}".format(k, v))

if __name__ == '__main__':
    main()
