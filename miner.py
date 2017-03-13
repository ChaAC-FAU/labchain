#!/usr/bin/env python3

""" The executable that participates in the P2P network and optionally mines new blocks. """

__all__ = []

import argparse
import json
from urllib.parse import urlparse

import flask
app = flask.Flask(__name__)

from src.crypto import Signing
from src.protocol import Protocol
from src.block import GENESIS_BLOCK
from src.chainbuilder import ChainBuilder
from src.mining import Miner
from src.transaction import TransactionInput

def parse_addr_port(val):
    url = urlparse("//" + val)
    assert url.scheme == ''
    assert url.path == ''
    assert url.params == ''
    assert url.query == ''
    assert url.fragment == ''
    assert url.port is not None
    assert url.hostname is not None
    return (url.hostname, url.port)

def rpc_server(port, chainbuilder):
    @app.route("/network-info", methods=['GET'])
    def get_network_info():
        return json.dumps([list(peer.peer_addr)[:2] for peer in chainbuilder.protocol.peers if peer.is_connected])

    @app.route("/new-transaction", methods=['PUT'])
    def send_transaction():
        chainbuilder.protocol.received("transaction", flask.request.json, None, 0)
        return b""

    @app.route("/show-balance", methods=['POST'])
    def show_balance():
        pubkeys = {Signing.from_json_compatible(pk): i for (i, pk) in enumerate(flask.request.json)}
        amounts = [0 for _ in pubkeys.values()]
        for output in chainbuilder.primary_block_chain.unspent_coins.values():
            if output.recipient_pk in pubkeys:
                amounts[pubkeys[output.recipient_pk]] += output.amount

        return json.dumps(amounts)

    @app.route("/build-transaction", methods=['POST'])
    def build_transaction():
        sender_pks = {Signing.from_json_compatible(o): i for i, o in enumerate(flask.request.json['sender-pubkeys'])}
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
        key = Signing(flask.request.data)
        transactions = set()
        outputs = set()
        for b in chainbuilder.primary_block_chain.blocks:
            for t in b.transactions:
                for i, target in enumerate(t.targets):
                    if target.recipient_pk == key:
                        transactions.add(t)
                        outputs.add(TransactionInput(t.get_hash(), i))
        for b in chainbuilder.primary_block_chain.blocks:
            for t in b.transactions:
                for inp in t.inputs:
                    if inp in outputs:
                        transactions.add(t)

        return json.dumps([t.to_json_compatible() for t in transactions])

    app.run(port=port)

def main():
    parser = argparse.ArgumentParser(description="Blockchain Miner.")
    parser.add_argument("--listen-address", default="",
                        help="The IP address where the P2P server should bind to.")
    parser.add_argument("--listen-port", default=0, type=int,
                        help="The port where the P2P server should listen. Defaults a dynamically assigned port.")
    parser.add_argument("--mining-pubkey", type=argparse.FileType('rb'),
                        help="The public key where mining rewards should be sent to. No mining is performed if this is left unspecified.")
    parser.add_argument("--bootstrap-peer", action='append', type=parse_addr_port, default=[],
                        help="Addresses of other P2P peers in the network.")
    parser.add_argument("--rpc-port", type=int, default=40203,
                        help="The port number where the wallet can find an RPC server.")

    args = parser.parse_args()

    proto = Protocol(args.bootstrap_peer, GENESIS_BLOCK, args.listen_port, args.listen_address)
    if args.mining_pubkey is not None:
        pubkey = Signing(args.mining_pubkey.read())
        args.mining_pubkey.close()
        miner = Miner(proto, pubkey)
        miner.start_mining()
        chainbuilder = miner.chainbuilder
    else:
        chainbuilder = ChainBuilder(proto)

    rpc_server(args.rpc_port, chainbuilder)

if __name__ == '__main__':
    main()
