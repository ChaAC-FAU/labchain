"""
The chain builder maintains the current longest confirmed (primary) block chain as well as
only partially downloaded longer chains that might become the new primary block chain once
completed and verified. Also maintains a list of (unconfirmed) transactions that are valid
but not yet part of the primary block chain, or valid once another unconfirmed transaction
becomes valid.

Received blocks that cannot be shown to be invalid on *any* block chain are stored in a block
cache (from which for the moment they are never evicted), so that they do not need to be requested
from other peers over and over again.


For the process of building new primary block chains, block requests are used. These are maintained
in a dict indexed by the hash of the next block that is required for the block request to make
progress. Each block request stores a list of partial block chains that all depend on the same
next block, and the time of the last download request, so that these requests can be retried and
at some point aborted when no progress is made.

While not strictly necessary, the block requests are also used when the block can be found in the
block cache. In that case they are immediately fulfilled until the block chains can be built or a
block is missing in the cache, which then will be requested from the peers.

Partial chains are completed once their next block is the head of a so called `checkpoint`. These
checkpoints are snapshots of the primary block chain at various points in its history. For a chain
of length `N`, the number of checkpoints is always kept between `2*log_2(N)` and `log_2(N)`, with
most checkpoints being relatively recent. There also is always one checkpoint with only the genesis
block.
"""

import binascii
import threading
import logging
import math
from typing import List, Dict, Callable, Optional
from datetime import datetime

from .config import *
from .block import Block
from .blockchain import Blockchain, GENESIS_BLOCK, GENESIS_BLOCK_HASH
from .protocol import Protocol

__all__ = ['ChainBuilder']


class BlockRequest:
    """
    Stores information about a pending block request and the partial chains that depend on it.

    :ivar partial_chains: The partial chains that wait for this request. These partial chains are
                          ordered by age, youngest first.
    :vartype partial_chains: List[List[Block]]
    :ivar _last_update: The time and date of the last block request to our peers.
    :vartype _last_update: datetime
    :ivar _request_count: The number of requests to our peers we have sent.
    :vartype _request_count: int
    """

    def __init__(self):
        self.partial_chains = [[]]
        self.clear()

    def clear(self):
        """ Clears the download count and last update time of this request. """
        self._last_update = datetime(1970, 1, 1)
        self._request_count = 0

    def send_request(self, protocol: 'Protocol'):
        """ Sends a request for the next required block to the given `protocol`. """
        self._request_count += 1
        self._last_update = datetime.utcnow()
        protocol.send_block_request(self.partial_chains[0][-1].prev_block_hash)
        logging.debug("asking for another block %d (attempt %d)", max(len(r) for r in self.partial_chains),
                      self._request_count)

    def timeout_reached(self) -> bool:
        """ Returns a bool indicating whether all attempts to download this block have failed. """
        return self._request_count > BLOCK_REQUEST_RETRY_COUNT

    def checked_retry(self, protocol: 'Protocol'):
        """
        Retries sending this request, if no response was received for a certain time or if no
        request was sent yet.
        """

        if self._last_update + BLOCK_REQUEST_RETRY_INTERVAL < datetime.utcnow():
            if self._request_count >= BLOCK_REQUEST_RETRY_COUNT:
                self._request_count += 1
            else:
                self.send_request(protocol)


class ChainBuilder:
    """
    The chain builder maintains the current longest confirmed (primary) block chain as well as
    only partially downloaded longer chains that might become the new primary block chain once
    completed and verified. Also maintains a list of (unconfirmed) transactions that are valid
    but not yet part of the primary block chain, or valid once another unconfirmed transaction
    becomes valid.

    :ivar primary_block_chain: The longest fully validated block chain we know of.
    :vartype primary_block_chain: Blockchain
    :ivar _block_requests: A dict from block hashes to lists of partial chains waiting for that block.
    :vartype _block_requests: Dict[bytes, BlockRequest]
    :ivar block_cache: A cache of received blocks, not bound to any one specific block chain.
    :vartype block_cache: Dict[bytes, Block]
    :ivar unconfirmed_transactions: Known transactions that are not part of the primary block chain.
    :vartype unconfirmed_transactions: Dict[bytes, Transaction]
    :ivar chain_change_handlers: Event handlers that get called when we find out about a new primary
                                 block chain.unconfirmed_transactions
    :vartype chain_change_handlers: List[Callable]
    :ivar transaction_change_handlers: Event handlers that get called when we find out about a new
                                       transaction.
    :vartype transaction_change_handlers: List[Callable]
    :ivar protocol: The protocol instance used by this chain builder.
    :vartype protocol: Protocol
    """

    def __init__(self, protocol: 'Protocol'):
        self.primary_block_chain = Blockchain()
        self._block_requests = {}
        self._blockchain_checkpoints = {GENESIS_BLOCK_HASH: self.primary_block_chain}

        self.block_cache = {GENESIS_BLOCK_HASH: GENESIS_BLOCK}
        self.unconfirmed_transactions = {}

        # Adding the tx from Genesis block to unspent coins
        for tx in GENESIS_BLOCK.transactions:
            for i, target in enumerate(tx.targets):
                if target.is_pay_to_pubkey or target.is_pay_to_pubkey_lock:
                    self.primary_block_chain.unspent_coins[(tx.get_hash(), i)] = target

        # TODO: we want this to be sorted by some function of rewards and age
        # TODO: we want two lists, one with known valid, unapplied transactions, the other with all known transactions (with some limit)

        self.chain_change_handlers = []
        self.transaction_change_handlers = []

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

        def input_ok(inp):
            return (inp.transaction_hash, inp.output_idx) in self.primary_block_chain.unspent_coins or \
                   inp.transaction_hash in self.unconfirmed_transactions

        if hash_val not in self.unconfirmed_transactions and \
                all(input_ok(inp) for inp in transaction.inputs):
            self.unconfirmed_transactions[hash_val] = transaction
            self.protocol.broadcast_transaction(transaction)
            for handler in self.transaction_change_handlers:
                handler()

    def _new_primary_block_chain(self, chain: 'Blockchain'):
        """ Does all the housekeeping that needs to be done when a new longest chain is found. """
        logging.info("new primary block chain with height %d with current difficulty %d", len(chain.blocks),
                     chain.head.difficulty)
        self._assert_thread_safety()
        self.primary_block_chain = chain
        todelete = set()
        for (hash_val, trans) in self.unconfirmed_transactions.items():
            if not trans.validate_tx(chain.unspent_coins):
                todelete.add(hash_val)
        for hash_val in todelete:
            del self.unconfirmed_transactions[hash_val]

        for handler in self.chain_change_handlers:
            handler()

        self._retry_expired_requests()
        self._clean_block_requests()

        # TODO: restore valid transactions from the old primary block chain

        self.protocol.broadcast_primary_block(chain.head)

    def _build_blockchain(self, checkpoint: 'Blockchain', blocks: 'List[Block]'):
        def checkpoint_hashes(chain):
            chain_len = len(chain.blocks)
            idx = 0
            yield GENESIS_BLOCK_HASH
            while chain_len > 1:
                cp = 2 ** (math.floor(math.log(chain_len, 2) - 1))
                idx += cp
                yield chain.blocks[idx].hash
                chain_len = chain_len - cp

        chain = checkpoint
        checkpoints = self._blockchain_checkpoints.copy()
        for b in blocks:
            next_chain = chain.try_append(b)
            if next_chain is None:
                logging.warning("invalid block")
                break
                # TODO we need to figure out why the miner stops after an invalid block!
            chain = next_chain
            checkpoints[chain.head.hash] = chain

        if chain.head.height <= self.primary_block_chain.head.height:
            logging.warning("discarding shorter chain")
            return

        for hash_val in checkpoints.keys() - set(checkpoint_hashes(next_chain)):
            del checkpoints[hash_val]
        self._blockchain_checkpoints = checkpoints
        self._new_primary_block_chain(chain)

    def _retry_expired_requests(self):
        """ Sends new block requests to our peers for unanswered pending requests. """
        for request in self._block_requests.values():
            request.checked_retry(self.protocol)

    def _clean_block_requests(self):
        """
        Deletes partial chains and block requests when they are shorter than the primary block
        chain or all download attempts failed.
        """
        # TODO: call this regularly when not mining
        block_requests = {}
        for block_hash, request in self._block_requests.items():
            if request.timeout_reached():
                logging.info("giving up on a block")
                continue

            new_requests = []
            for partial_chain in request.partial_chains:
                if partial_chain[0].height > self.primary_block_chain.head.height:
                    new_requests.append(partial_chain)
            if new_requests:
                request.partial_chains = new_requests
                block_requests[block_hash] = request
        self._block_requests = block_requests

    def new_block_received(self, block: 'Block'):
        """ Event handler that is called by the network layer when a block is received. """
        self._assert_thread_safety()

        if (block.hash in self.block_cache) or (not block.verify_difficulty()) or (not block.verify_merkle()):
            return

        self.block_cache[block.hash] = block

        self._retry_expired_requests()

        if block.hash not in self._block_requests:
            self._block_requests[block.hash] = BlockRequest()
        else:
            return

        request = self._block_requests[block.hash]
        del self._block_requests[block.hash]

        while True:
            for partial_chain in request.partial_chains:
                partial_chain.append(block)
            if (block.prev_block_hash not in self.block_cache) or (
                    block.prev_block_hash in self._blockchain_checkpoints):
                break
            block = self.block_cache[block.prev_block_hash]

        if block.prev_block_hash in self._block_requests:
            chains = request.partial_chains
            request = self._block_requests[block.prev_block_hash]
            request.partial_chains.extend(chains)
        else:
            request.clear()
            self._block_requests[block.prev_block_hash] = request

        if block.prev_block_hash in self._blockchain_checkpoints:
            del self._block_requests[block.prev_block_hash]
            checkpoint = self._blockchain_checkpoints[block.prev_block_hash]
            for partial_chain in request.partial_chains:
                self._build_blockchain(checkpoint, partial_chain[::-1])
        request.checked_retry(self.protocol)
