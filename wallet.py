#!/usr/bin/env python3

"""
The wallet allows a user to query account balance, send money, and get status information about a
miner.
"""

__all__ = []

import argparse
import requests
import sys
import json
from binascii import hexlify

from src.blockchain import Blockchain
from src.block import Block
from src.transaction import Transaction, TransactionTarget, TransactionInput
from src.crypto import Signing

def send_transaction(sess, url, transaction):
    resp = sess.put(url + 'new-transaction', data=json.dumps(transaction.to_json_compatible()),
                    headers={"Content-Type": "application/json"})
    resp.raise_for_status()

def network_info(sess, url):
    resp = sess.get(url + 'network-info')
    resp.raise_for_status()
    return resp.json()

def get_transactions(sess, url, pubkey):
    resp = sess.post(url + 'transactions', data=pubkey.as_bytes(),
                     headers={"Content-Type": "application/json"})
    resp.raise_for_status()
    return [Transaction.from_json_compatible(t) for t in resp.json()]

def show_balance(sess, url, pubkeys):
    resp = sess.post(url + "show-balance", data=json.dumps([pk.to_json_compatible() for pk in pubkeys]),
                     headers={"Content-Type": "application/json"})
    resp.raise_for_status()
    return zip(pubkeys, resp.json())

def build_transaction(sess, url, source_keys, targets, change_key):
    resp = sess.post(url + "build-transaction", data=json.dumps({
            "sender-pubkeys": [k.to_json_compatible() for k in source_keys],
            "amount": sum(t.amount for t in targets),
        }), headers={"Content-Type": "application/json"})
    resp.raise_for_status()
    resp = resp.json()
    remaining = resp['remaining_amount']
    if remaining < 0:
        print("You do not have sufficient funds for this transaction. ({} missing)".format(-remaining), file=sys.stderr)
        sys.exit(2)
    elif remaining > 0:
        targets = targets + [TransactionTarget(change_key, remaining)]

    inputs = [TransactionInput.from_json_compatible(i) for i in resp['inputs']]
    trans = Transaction(inputs, targets)
    trans.sign([source_keys[idx] for idx in resp['key_indices']])
    send_transaction(sess, url, trans)

def parse_targets():
    start = True
    def parse(val):
        nonlocal start
        if start:
            val = Signing.from_file(val)
        else:
            val = int(val)
        start = not start
        return val
    return parse

def private_signing(path):
    val = Signing.from_file(path)
    if not val.has_private:
        raise ValueError("The specified key is not a private key.")
    return val

def main():
    parser = argparse.ArgumentParser(description="Wallet.")
    parser.add_argument("--miner-port", default=40203, type=int,
                        help="The RPC port of the miner to connect to.")
    subparsers = parser.add_subparsers(dest="command")
    balance = subparsers.add_parser("show-balance",
                                    help="Shows the current balance of the public key "
                                         "stored in the specified file.")
    balance.add_argument("key", nargs="+", type=Signing.from_file)
    trans = subparsers.add_parser("show-transactions",
                                  help="Shows all transactions involving the public key "
                                       "stored in the specified file.")
    trans.add_argument("key", nargs="+", type=Signing.from_file)
    subparsers.add_parser("show-network",
                          help="Prints networking information about the miner.")
    transfer = subparsers.add_parser("transfer", help="Transfer money.")
    transfer.add_argument("--private-key", type=private_signing,
                          default=[], action="append", required=True,
                          help="The private key(s) whose coins should be used for the transfer.")
    transfer.add_argument("--change-key", type=Signing.from_file, required=True,
                          help="The private key where any remaining coins are sent to.")
    transfer.add_argument("target", nargs='*', metavar=("TARGET_KEY AMOUNT"),
                          type=parse_targets(),
                          help="The private key(s) whose coins should be used for the transfer.")
    args = parser.parse_args()

    url = "http://localhost:{}/".format(args.miner_port)
    s = requests.session()

    if args.command == 'show-transactions':
        for key in args.key:
            for trans in get_transactions(s, url, key):
                print(trans.to_json_compatible())
    elif args.command == 'show-balance':
        total = 0
        for pubkey, balance in show_balance(s, url, args.key):
            print("{}: {}".format(hexlify(pubkey.as_bytes()), balance))
            total += balance
        print()
        print("total: {}".format(total))
    elif args.command == 'show-network':
        for [k, v] in network_info(s, url):
            print("{}\t{}".format(k, v))
    elif args.command == 'transfer':
        if len(args.target) % 2:
            print("Missing amount to transfer for last target key.\n", file=sys.stderr)
            parser.parse_args(["--help"])
        targets = [TransactionTarget(k, a) for k, a in zip(args.target[::2], args.target[1::2])]
        build_transaction(s, url, args.private_key, targets, args.change_key)
    else:
        print("You need to specify what to do.\n", file=sys.stderr)
        parser.parse_args(["--help"])

if __name__ == '__main__':
    main()
