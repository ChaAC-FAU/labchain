"""
The chain builder maintains the current longest confirmed (primary) block chain as well as one
candidate for an even longer chain that it attempts to download and verify.
"""

import threading
import logging
from typing import List, Dict, Callable, Optional
from datetime import datetime

from .block import GENESIS_BLOCK, GENESIS_BLOCK_HASH, Block
from .blockchain import Blockchain

__all__ = ['ChainBuilder']

class PartialChain:
    def __init__(self):
        self.blocks = []
        self.last_update = datetime.utcnow()
        # TODO: delete partial chains after some time

class ChainBuilder:
    """
    Maintains the current longest confirmed (primary) block chain as well as one candidate for an
    even longer chain that it attempts to download and verify.

    :ivar primary_block_chain: The longest fully validated block chain we know of.
    :vartype primary_block_chain: Blockchain
    :ivar _block_requests: A dict from block hashes to lists of partial chains waiting for that block.
    :vartype _block_requests: Dict[bytes, List[PartialChain]]
    :ivar block_cache: A cache of received blocks, not bound to any one specific block chain.
    :vartype block_cache: Dict[bytes, Block]
    :ivar unconfirmed_transactions: Known transactions that are not part of the primary block chain.
    :vartype unconfirmed_transactions: Dict[bytes, Transaction]
    :ivar chain_change_handlers: Event handlers that get called when we find out about a new primary
                                 block chain.
    :vartype chain_change_handlers: List[Callable]
    :ivar protocol: The protocol instance used by this chain builder.
    :vartype protocol: Protocol
    """

    def __init__(self, protocol):
        self.primary_block_chain = Blockchain()
        self._block_requests = {}
        # TODO: delete some old checkpoints
        self._blockchain_checkpoints = { GENESIS_BLOCK_HASH: self.primary_block_chain }

        self.block_cache = { GENESIS_BLOCK_HASH: GENESIS_BLOCK }
        self.unconfirmed_transactions = {}
        # TODO: we want this to be sorted by some function of rewards and age
        # TODO: we want two lists, one with known valid, unapplied transactions, the other with all known transactions (with some limit)

        self.chain_change_handlers = []

        protocol.block_receive_handlers.append(self.new_block_received)
        protocol.trans_receive_handlers.append(self.new_transaction_received)
        protocol.block_request_handlers.append(self.block_request_received)
        self.protocol = protocol

        self._thread_id = None

    def _assert_thread_safety(self):
        if self._thread_id is None:
            self._thread_id = threading.get_ident()
        assert self._thread_id == threading.get_ident()

    def block_request_received(self, block_hash: bytes) -> 'Optional[Block]':
        """ Our event handler for block requests in the protocol. """
        self._assert_thread_safety()
        return self.block_cache.get(block_hash)

    def new_transaction_received(self, transaction: 'Transaction'):
        """ Event handler that is called by the network layer when a transaction is received. """
        self._assert_thread_safety()
        hash_val = transaction.get_hash()
        if self.primary_block_chain.get_transaction_by_hash(hash_val) is None and \
                hash_val not in self.unconfirmed_transactions:
            self.unconfirmed_transactions[hash_val] = transaction
            self.protocol.broadcast_transaction(transaction)

    def _new_primary_block_chain(self, chain: 'Blockchain'):
        """ Does all the housekeeping that needs to be done when a new longest chain is found. """
        logging.info("new primary block chain with height %d with current difficulty %d", len(chain.blocks), chain.head.difficulty)
        self._assert_thread_safety()
        self.primary_block_chain = chain
        todelete = set()
        for (hash_val, trans) in self.unconfirmed_transactions.items():
            if not trans.verify(chain, set()):
                todelete.add(hash_val)
        for hash_val in todelete:
            del self.unconfirmed_transactions[hash_val]

        for handler in self.chain_change_handlers:
            handler()

        self._blockchain_checkpoints[chain.head.hash] = chain

        # stop trying to build shorter block chains
        block_requests = {}
        for block_hash, requests in self._block_requests.items():
            new_requests = []
            for partial_chain in requests:
                if partial_chain.blocks[0].height > chain.head.height:
                    new_requests.append(partial_chain)
            if new_requests:
                block_requests[block_hash] = new_requests
        self._block_requests = block_requests

        self.protocol.broadcast_primary_block(chain.head)

    def new_block_received(self, block: 'Block'):
        """ Event handler that is called by the network layer when a block is received. """
        self._assert_thread_safety()
        if block.hash in self.block_cache or not block.verify_difficulty() or \
                not block.verify_merkle():
            return
        self.block_cache[block.hash] = block

        if block.hash not in self._block_requests:
            if block.height > self.primary_block_chain.head.height:
                self._block_requests.setdefault(block.hash, []).append(PartialChain())
            else:
                return

        requests = self._block_requests[block.hash]
        del self._block_requests[block.hash]
        while True:
            for partial_chain in requests:
                partial_chain.blocks.append(block)
                partial_chain.last_update = datetime.utcnow()
            if block.prev_block_hash not in self.block_cache or block.prev_block_hash in self._blockchain_checkpoints:
                break
            block = self.block_cache[block.prev_block_hash]
        self._block_requests.setdefault(block.prev_block_hash, []).extend(requests)

        if block.prev_block_hash in self._blockchain_checkpoints:
            winner = self.primary_block_chain
            for partial_chain in requests:
                chain = self._blockchain_checkpoints[block.prev_block_hash]
                for b in partial_chain.blocks[::-1]:
                    next_chain = chain.try_append(b)
                    if next_chain is None:
                        break
                    chain = next_chain
                if chain.head.height > winner.head.height:
                    winner = chain
            if winner is not self.primary_block_chain:
                self._new_primary_block_chain(winner)
        else:
            # TODO: only do this if we have no pending requests for this block
            self.protocol.send_block_request(block.prev_block_hash)
            logging.debug("asking for another block %d", max(len(r.blocks) for r in requests))
            self._block_requests[block.prev_block_hash] = requests


from .protocol import Protocol
from .block import Block
from .transaction import Transaction
