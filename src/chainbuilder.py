from .block import GENESIS_BLOCK, GENESIS_BLOCK_HASH
from .blockchain import Blockchain

import threading

__all__ = ['ChainBuilder']

class ChainBuilder:
    """
    Maintains the current longest confirmed (primary) block chain as well as one candidate for an even longer
    chain that it attempts to download and verify.
    """

    def __init__(self, protocol):
        self.primary_block_chain = Blockchain([GENESIS_BLOCK])
        self.unconfirmed_block_chain = []

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

    def block_request_received(self, block_hash):
        self._assert_thread_safety()
        return self.block_cache.get(block_hash)

    def new_transaction_received(self, transaction):
        """ Event handler that is called by the network layer when a transaction is received. """
        self._assert_thread_safety()
        hash_val = transaction.get_hash()
        if self.primary_block_chain.get_transaction_by_hash(hash_val) is None:
           self.unconfirmed_transactions[hash_val] = transaction

    def _new_primary_block_chain(self, chain):
        """
        Does all the housekeeping that needs to be done when a new longest chain is found.
        """
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

    def get_next_unconfirmed_block(self):
        """
        Helper function that tries to complete the unconfirmed chain,
        possibly asking the network layer for more blocks.
        """
        self._assert_thread_safety()
        unc = self.unconfirmed_block_chain
        while unc[-1].prev_block_hash in self.block_cache:
            unc.append(self.block_cache[unc[-1].prev_block_hash])


        if unc[-1].height == 0:
            chain = Blockchain(unc[::-1])
            if chain.verify_all_transactions():
                self._new_primary_block_chain(chain)
            self.unconfirmed_block_chain = []
        else:
            self.protocol.send_block_request(unc[-1].prev_block_hash)

    def new_block_received(self, block):
        """ Event handler that is called by the network layer when a block is received. """
        self._assert_thread_safety()
        if not block.verify_difficulty() or not block.verify_merkle() or block.hash in self.block_cache:
            return
        self.block_cache[block.hash] = block

        if self.unconfirmed_block_chain:
            if self.unconfirmed_block_chain[-1].prev_block_hash == block.hash:
                self.unconfirmed_block_chain.append(block)
                self.get_next_unconfirmed_block()
            elif self.unconfirmed_block_chain[0].hash == block.prev_block_hash:
                self.unconfirmed_block_chain.insert(0, block)

        if (not self.unconfirmed_block_chain or block.height > self.unconfirmed_block_chain[0].height) and \
                block.height > self.primary_block_chain.head.height:
            self.unconfirmed_block_chain = [block]
            self.get_next_unconfirmed_block()

