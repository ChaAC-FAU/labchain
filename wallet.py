#!/usr/bin/env python3

"""
The wallet allows a user to query account balance, send money, and get status information about a
miner.
"""

__all__ = []

import argparse
import sys
from datetime import datetime
from binascii import hexlify
from io import IOBase
from typing import List, Union, Callable, Tuple, Optional

import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")

from src.transaction import TransactionTarget
from src.crypto import Key
from src.rpc_client import RPCClient


def parse_targets() -> Callable[[str], Union[Key, int]]:
    """
    Parses transaction targets from the command line: the first value is a path to a key, the
    second an amount and so on.
    """
    start = True

    def parse(val):
        nonlocal start
        if start:
            val = Key.from_file(val)
        else:
            val = int(val)
        start = not start
        return val

    return parse


def private_signing(path: str) -> Key:
    """ Parses a path to a private key from the command line. """
    val = Key.from_file(path)
    if not val.has_private:
        raise ValueError("The specified key is not a private key.")
    return val


def wallet_file(path: str) -> Tuple[List[Key], str]:
    """
    Parses the wallet from the command line.

    Returns a tuple with a list of keys from the wallet and the path to the wallet (for write
    operations).
    """
    try:
        with open(path, "rb") as f:
            contents = f.read()
    except FileNotFoundError:
        return [], path
    return list(Key.read_many_private(contents)), path


def main():
    parser = argparse.ArgumentParser(description="Wallet.")
    parser.add_argument("--miner-port", default=40203, type=int,
                        help="The RPC port of the miner to connect to.")
    parser.add_argument("--wallet", type=wallet_file, default=([], None),
                        help="The wallet file containing the private keys to use.")
    subparsers = parser.add_subparsers(dest="command")

    balance = subparsers.add_parser("create-address",
                                    help="Creates new addresses and stores their secret keys in the wallet.")
    balance.add_argument("file", nargs="+", type=argparse.FileType("wb"),
                         help="Path to a file where the address should be stored.")

    balance = subparsers.add_parser("show-balance",
                                    help="Shows the current balance of the public key "
                                         "stored in the specified file.")
    balance.add_argument("key", nargs="*", type=Key.from_file)

    trans = subparsers.add_parser("show-transactions",
                                  help="Shows all transactions involving the public key "
                                       "stored in the specified file.")
    trans.add_argument("key", nargs="*", type=Key.from_file)

    subparsers.add_parser("show-network",
                          help="Prints networking information about the miner.")

    transfer = subparsers.add_parser("transfer", help="Transfer money.")
    transfer.add_argument("--private-key", type=private_signing,
                          default=[], action="append", required=False,
                          help="The private key(s) whose coins should be used for the transfer.")
    transfer.add_argument("--change-key", type=Key.from_file, required=False,
                          help="The private key where any remaining coins are sent to.")
    transfer.add_argument("--transaction-fee", type=int, default=1,
                          help="The transaction fee you want to pay to the miner.")
    transfer.add_argument("target", nargs='*', metavar=("TARGET_KEY AMOUNT"),
                          type=parse_targets(),
                          help="The private key(s) whose coins should be used for the transfer.")

    args = parser.parse_args()

    rpc = RPCClient(args.miner_port)

    def show_transactions(keys: List[Key]):
        for key in keys:
            for trans in rpc.get_transactions(key):
                print(trans.to_json_compatible())
            print()

    def create_address(wallet_keys: List[Key], wallet_path: str, output_files: List[IOBase]):
        keys = [Key.generate_private_key() for _ in output_files]
        Key.write_many_private(wallet_path, wallet_keys + keys)
        for fp, key in zip(output_files, keys):
            fp.write(key.as_bytes())
            fp.close()

    def show_balance(keys: List[Key]):
        total = 0
        for pubkey, balance in rpc.show_balance(keys):
            print("{}: {}".format(hexlify(pubkey.as_bytes()), balance))
            total += balance
        print()
        print("total: {}".format(total))

    def network_info():
        for k, v in rpc.network_info():
            print("{}\t{}".format(k, v))

    def transfer(tx_targets: List[TransactionTarget], change_key: Optional[Key],
                 wallet_keys: List[Key], wallet_path: str, priv_keys: List[Key]):

        if not change_key:
            change_key = Key.generate_private_key()
            Key.write_many_private(wallet_path, wallet_keys + [change_key])

        timestamp = datetime.utcnow()
        tx = rpc.build_transaction(priv_keys, tx_targets, change_key, args.transaction_fee, timestamp)
        rpc.send_transaction(tx)

    def get_keys(keys: List[Key]) -> List[Key]:
        """
        Returns a combined list of keys from the `keys` and the wallet. Shows an error if empty.
        """
        all_keys = keys + args.wallet[0]
        if not all_keys:
            print("missing key or wallet", file=sys.stderr)
            parser.parse_args(["--help"])
        return all_keys

    if args.command == 'show-transactions':
        show_transactions(get_keys(args.key))
    elif args.command == "create-address":
        if not args.wallet[1]:
            print("no wallet specified", file=sys.stderr)
            parser.parse_args(["--help"])
        create_address(*args.wallet, args.file)
    elif args.command == 'show-balance':
        show_balance(get_keys(args.key))
    elif args.command == 'show-network':
        network_info()
    elif args.command == 'transfer':
        if len(args.target) % 2:
            print("Missing amount to transfer for last target key.\n", file=sys.stderr)
            parser.parse_args(["--help"])
        if not args.change_key and not args.wallet[0]:
            print("You need to specify either --wallet or --change-key.\n", file=sys.stderr)
            parser.parse_args(["--help"])
        targets = [TransactionTarget(TransactionTarget.pay_to_pubkey(k), a) for k, a in
                   zip(args.target[::2], args.target[1::2])]
        transfer(targets, args.change_key, *args.wallet, get_keys(args.private_key))
    else:
        print("You need to specify what to do.\n", file=sys.stderr)
        parser.parse_args(["--help"])


if __name__ == '__main__':
    main()
