#!/usr/bin/env python3

import argparse
from urllib.parse import urlparse
from src.crypto import Signing
from src.protocol import Protocol
from src.block import GENESIS_BLOCK

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

def main():
    parser = argparse.ArgumentParser(description="Blockchain Miner.")
    parser.add_argument("--listen-address", default="",
                        help="The IP address where the P2P server should bind to.")
    parser.add_argument("--listen-port", default=0, type=int,
                        help="The port where the P2P server should listen. Defaults a dynamically assigned port.")
    parser.add_argument("--mining-pubkey", type=argparse.FileType('rb'),
                        help="The public key where mining rewards should be sent to. No mining is performed if this is left unspecified.")
    parser.add_argument("--bootstrap-peer", action='append', type=parse_addr_port,
                        help="Addresses of other P2P peers in the network.")

    args = parser.parse_args()

    proto = Protocol(args.bootstrap_peer, GENESIS_BLOCK, args.listen_port, args.listen_address)
    if args.mining_pubkey is not None:
        pubkey = Signing(args.mining_pubkey.read())
        args.mining_pubkey.close()
        miner = Miner(proto, pubkey)
        miner.start_mining()

    # TODO: start RPC
    import time
    while True:
        time.sleep(2**31)

if __name__ == '__main__':
    main()
