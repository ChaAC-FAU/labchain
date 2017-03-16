""" The RPC functionality used by the wallet to talk to the miner application. """

import json
from typing import List, Tuple, Iterator

import requests

from .transaction import Transaction, TransactionTarget, TransactionInput
from .crypto import Signing


class RPCClient:
    """ The RPC methods used by the wallet to talk to the miner application. """

    def __init__(self, miner_port: int):
        self.sess = requests.Session()
        self.url = "http://localhost:{}/".format(miner_port)

    def send_transaction(self, transaction: Transaction):
        """ Sends a transaction to the miner. """
        resp = self.sess.put(self.url + 'new-transaction', data=json.dumps(transaction.to_json_compatible()),
                        headers={"Content-Type": "application/json"})
        resp.raise_for_status()

    def network_info(self) -> List[Tuple[str, int]]:
        """ Returns the peers connected to the miner. """
        resp = self.sess.get(self.url + 'network-info')
        resp.raise_for_status()
        return [tuple(peer) for peer in resp.json()]

    def get_transactions(self, pubkey: Signing) -> List[Transaction]:
        """ Returns all transactions involving a certain public key. """
        resp = self.sess.post(self.url + 'transactions', data=pubkey.as_bytes(),
                         headers={"Content-Type": "application/json"})
        resp.raise_for_status()
        return [Transaction.from_json_compatible(t) for t in resp.json()]

    def show_balance(self, pubkeys: List[Signing]) -> Iterator[Tuple[Signing, int]]:
        """ Returns the balance of a number of public keys. """
        resp = self.sess.post(self.url + "show-balance", data=json.dumps([pk.to_json_compatible() for pk in pubkeys]),
                         headers={"Content-Type": "application/json"})
        resp.raise_for_status()
        return zip(pubkeys, resp.json())

    def build_transaction(self, source_keys: List[Signing], targets: List[TransactionTarget],
                          change_key: Signing, transaction_fee: int) -> Transaction:
        """
        Builds a transaction sending money from `source_keys` to `targets`, sending any change to the
        key `change_key` and a transaction fee `transaction_fee` to the miner.
        """
        resp = self.sess.post(self.url + "build-transaction", data=json.dumps({
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
        return trans
