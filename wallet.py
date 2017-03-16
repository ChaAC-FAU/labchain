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

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")

from src.block import Block
from src.blockchain import Blockchain
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

def build_transaction(sess, url, source_keys, targets, change_key, transaction_fee):
    resp = sess.post(url + "build-transaction", data=json.dumps({
            "sender-pubkeys": [k.to_json_compatible() for k in source_keys],
            "amount": sum(t.amount for t in targets) + transaction_fee,
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

def wallet_file(path):
    try:
        with open(path, "rb") as f:
            contents = f.read()
    except FileNotFoundError:
        return [], path
    return list(Signing.read_many_private(contents)), path

def main():
    parser = argparse.ArgumentParser(description="Wallet.")
    parser.add_argument("--miner-port", default=40203, type=int,
                        help="The RPC port of the miner to connect to.")
    parser.add_argument("--wallet", type=wallet_file, default=([],None),
                        help="The wallet file containing the private keys to use.")
    subparsers = parser.add_subparsers(dest="command")

    balance = subparsers.add_parser("create-address",
                                    help="Creates new addresses and stores their secret keys in the wallet.")
    balance.add_argument("file", nargs="+", type=argparse.FileType("wb"),
                         help="Path to a file where the address should be stored.")

    balance = subparsers.add_parser("show-balance",
                                    help="Shows the current balance of the public key "
                                         "stored in the specified file.")
    balance.add_argument("key", nargs="*", type=Signing.from_file)

    trans = subparsers.add_parser("show-transactions",
                                  help="Shows all transactions involving the public key "
                                       "stored in the specified file.")
    trans.add_argument("key", nargs="*", type=Signing.from_file)

    subparsers.add_parser("show-network",
                          help="Prints networking information about the miner.")

    transfer = subparsers.add_parser("transfer", help="Transfer money.")
    transfer.add_argument("--private-key", type=private_signing,
                          default=[], action="append", required=False,
                          help="The private key(s) whose coins should be used for the transfer.")
    transfer.add_argument("--change-key", type=Signing.from_file, required=False,
                          help="The private key where any remaining coins are sent to.")
    transfer.add_argument("--transaction-fee", type=int, default=0,
                          help="The transaction fee you want to pay to the miner.")
    transfer.add_argument("target", nargs='*', metavar=("TARGET_KEY AMOUNT"),
                          type=parse_targets(),
                          help="The private key(s) whose coins should be used for the transfer.")
    args = parser.parse_args()

    url = "http://localhost:{}/".format(args.miner_port)
    s = requests.session()

    def get_keys(keys):
        all_keys = keys + args.wallet[0]
        if not all_keys:
            print("missing key or wallet", file=sys.stderr)
            parser.parse_args(["--help"])
        return all_keys

    if args.command == 'show-transactions':
        for key in get_keys(args.key):
            for trans in get_transactions(s, url, key):
                print(trans.to_json_compatible())
            print()
    elif args.command == "create-address":
        if not args.wallet[1]:
            print("no wallet specified", file=sys.stderr)
            parser.parse_args(["--help"])

        keys = [Signing.generate_private_key() for _ in args.file]
        Signing.write_many_private(args.wallet[1], args.wallet[0] + keys)
        for fp, key in zip(args.file, keys):
            fp.write(key.as_bytes())
            fp.close()
    elif args.command == 'show-balance':
        total = 0
        for pubkey, balance in show_balance(s, url, get_keys(args.key)):
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
        change_key = args.change_key
        if not change_key:
            get_keys([]) # shows error if no wallet
            change_key = Signing.generate_private_key()
            Signing.write_many_private(args.wallet[1], args.wallet[0] + [change_key])

        build_transaction(s, url, get_keys(args.private_key), targets, change_key, args.transaction_fee)
    else:
        print("You need to specify what to do.\n", file=sys.stderr)
        parser.parse_args(["--help"])

if __name__ == '__main__':
    main()
