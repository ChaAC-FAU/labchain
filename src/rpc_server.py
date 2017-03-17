""" The RPC functionality the miner provides for the wallet. """

import json

import flask

from .chainbuilder import ChainBuilder
from .persistence import Persistence
from .crypto import Signing
from .transaction import TransactionInput

def rpc_server(port: int, chainbuilder: ChainBuilder, persist: Persistence):
    """ Runs the RPC server (forever). """

    app = flask.Flask(__name__)

    @app.route("/network-info", methods=['GET'])
    def get_network_info():
        """ Returns the connected peers. """
        return json.dumps([list(peer.peer_addr)[:2] for peer in chainbuilder.protocol.peers if peer.is_connected])

    @app.route("/new-transaction", methods=['PUT'])
    def send_transaction():
        """ Sends a transaction to the network, and uses it for mining. """
        chainbuilder.protocol.received("transaction", flask.request.json, None, 0)
        return b""

    @app.route("/show-balance", methods=['POST'])
    def show_balance():
        """ Returns the balance of a number of public keys. """
        pubkeys = {Signing.from_json_compatible(pk): i for (i, pk) in enumerate(flask.request.json)}
        amounts = [0 for _ in pubkeys.values()]
        for output in chainbuilder.primary_block_chain.unspent_coins.values():
            if output.recipient_pk in pubkeys:
                amounts[pubkeys[output.recipient_pk]] += output.amount

        return json.dumps(amounts)

    @app.route("/build-transaction", methods=['POST'])
    def build_transaction():
        """
        Returns the transaction inputs that can be used to build a transaction with a certain
        amount from some public keys.
        """
        sender_pks = {
                Signing.from_json_compatible(o): i
                    for i, o in enumerate(flask.request.json['sender-pubkeys'])
        }
        amount = flask.request.json['amount']

        inputs = []
        used_keys = []
        for (inp, output) in chainbuilder.primary_block_chain.unspent_coins.items():
            if output.recipient_pk in sender_pks:
                amount -= output.amount
                inputs.append(inp.to_json_compatible())
                used_keys.append(sender_pks[output.recipient_pk])
                if amount <= 0:
                    break

        if amount > 0:
            inputs = []
            used_keys = []

        return json.dumps({
            "inputs": inputs,
            "remaining_amount": -amount,
            "key_indices": used_keys,
        })


    @app.route("/transactions", methods=['POST'])
    def get_transactions_for_key():
        """ Returns all transactions involving a certain public key. """
        key = Signing(flask.request.data)
        transactions = set()
        outputs = set()
        chain = chainbuilder.primary_block_chain
        for b in chain.blocks:
            for t in b.transactions:
                for i, target in enumerate(t.targets):
                    if target.recipient_pk == key:
                        transactions.add(t)
                        outputs.add(TransactionInput(t.get_hash(), i))
        for b in chain.blocks:
            for t in b.transactions:
                for inp in t.inputs:
                    if inp in outputs:
                        transactions.add(t)

        return json.dumps([t.to_json_compatible() for t in transactions])

    app.run(port=port)
