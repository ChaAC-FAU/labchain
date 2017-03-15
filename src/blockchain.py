""" Definition of block chains. """

__all__ = ['Blockchain']
import logging
from datetime import timedelta
from fractions import Fraction
from typing import List, Dict, Optional

class Blockchain:
    """
    A block chain: a ordrered list of blocks.

    :ivar blocks: The blocks in this chain, oldest first.
    :vartype blocks: List[Block]
    :ivar block_indices: A dictionary allowing efficient lookup of the index of a block in this
                         block chain by its hash value.
    :vartype block_indices: Dict[bytes, int]
    :ivar unspent_coins: A dictionary mapping from (allowed/available) transaction inputs
                         to the transaction output that created this coin.
    :vartype unspent_coins: Dict[TransactionInput, TransactionTarget]
    """

    def __init__(self):
        self.blocks = [GENESIS_BLOCK]
        assert self.blocks[0].height == 0
        self.block_indices = {GENESIS_BLOCK_HASH: 0}
        assert not GENESIS_BLOCK.transactions
        self.unspent_coins = {}

    def try_append(self, block: 'Block') -> 'Optional[Blockchain]':
        unspent_coins = self.unspent_coins.copy()

        for t in block.transactions:
            for inp in t.inputs:
                if inp not in unspent_coins:
                    logging.warning("Aborting computation of unspent transactions because a transaction spent an unavailable coin.")
                    return None
                del unspent_coins[inp]
            for i, target in enumerate(t.targets):
                unspent_coins[TransactionInput(t.get_hash(), i)] = target

        chain = Blockchain()
        chain.unspent_coins = unspent_coins
        chain.blocks = self.blocks + [block]
        chain.block_indices = self.block_indices.copy()
        chain.block_indices[block.hash] = len(self.blocks)

        if not block.verify(chain):
            return None

        return chain

    def get_transaction_by_hash(self, hash_val: bytes) -> 'Optional[Transaction]':
        """ Returns a transaction from its hash, or None. """
        # TODO: build a hash table with this info
        for block in self.blocks[::-1]:
            for trans in block.transactions:
                if trans.get_hash() == hash_val:
                    return trans
        return None

    def is_coin_still_valid(self, transaction_input: 'TransactionInput',
                            prev_block: 'Block'=None) -> bool:
        """
        Validates that the coins that were sent in the transaction identified
        by `transaction_hash_val` to the nth receiver (n=output_idx) have not been
        spent before the given block.

        :param transaction_input: The coin to check.
        :param prev_block: The youngest block in this block chain that should be considered for
                           the validation.
        """
        if prev_block is None or prev_block is self.head:
            return transaction_input in self.unspent_coins

        idx = self.block_indices[prev_block.hash]
        assert self.blocks[idx] is prev_block
        for block in self.blocks[idx::-1]:
            for trans in block.transactions:
                if transaction_input in trans.inputs:
                    return False
        return True

    def get_block_by_hash(self, hash_val: bytes) -> 'Optional[Block]':
        """ Returns a block by its hash value, or None if it cannot be found. """
        idx = self.block_indices.get(hash_val)
        if idx is None:
            return None
        return self.blocks[idx]

    def verify_all_transactions(self) -> bool:
        """ Verify the transactions in all blocks in this chain. """
        for block in self.blocks:
            if not block.verify_transactions(self):
                return False
        return True

    def verify_all(self) -> bool:
        """ Verify all blocks in this block chain. """
        return all(block.verify(self) for block in self.blocks)

    @property
    def head(self):
        """
        The head of this block chain.

        :rtype: Block
        """
        return self.blocks[-1]

    def compute_difficulty(self, prev_block: 'Block'=None) -> int:
        """ Compute the desired difficulty for the block after `prev_block` (defaults to `head`). """
        BLOCK_INTERVAL = 120
        BLOCK_TARGET_TIMEDELTA = Fraction(int(timedelta(minutes=1).total_seconds() * 1000 * 1000))

        if prev_block is None:
            prev_block = self.head

        block_idx = self.block_indices[prev_block.hash] + 1
        if block_idx % BLOCK_INTERVAL != 0:
            return prev_block.difficulty

        duration = prev_block.time - self.blocks[block_idx - BLOCK_INTERVAL].time
        duration = Fraction(int(duration.total_seconds() * 1000 * 1000))

        prev_difficulty = Fraction(prev_block.difficulty)
        hash_rate = prev_difficulty * BLOCK_INTERVAL / duration

        new_difficulty = hash_rate * BLOCK_TARGET_TIMEDELTA / BLOCK_INTERVAL

        if new_difficulty < self.blocks[0].difficulty:
            new_difficulty = self.blocks[0].difficulty

        return int(new_difficulty)

    def compute_blockreward(self, prev_block: 'Block') -> int:
        """ Compute the block reward that is expected for the block following `prev_block`. """
        assert prev_block is not None
        reward = 1000
        l = self.block_indices[prev_block.hash]
        while l > 0:
            l = l - 10000
            reward = reward // 2
        return reward

from .block import Block, GENESIS_BLOCK, GENESIS_BLOCK_HASH
from .transaction import TransactionInput, Transaction
