""" Definition of block chains. """

__all__ = ['Blockchain']
import logging
from fractions import Fraction
from typing import List, Dict, Optional

from .proof_of_work import DIFFICULTY_BLOCK_INTERVAL, DIFFICULTY_TARGET_TIMEDELTA

GENESIS_REWARD = 1000
""" The reward that is available for the first `REWARD_HALF_LIFE` blocks, starting with the genesis block. """

REWARD_HALF_LIFE = 10000
""" The number of blocks until the block reward is halved. """

class Blockchain:
    """
    A block chain: a ordered, immutable list of valid blocks. The only ways to create a blockchain
    instance are the constructor, which will create a block chain containing only the genesis block,
    and the `try_append` method which creates a new block chain only if the given block is valid on
    top of `self`.

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
        """
        If `block` is valid on top of this chain, returns a new block chain including that block.
        Otherwise, it returns `None`.
        """

        if not block.verify(self):
            return None

        unspent_coins = self.unspent_coins.copy()

        for t in block.transactions:
            for inp in t.inputs:
                assert inp in unspent_coins, "Aborting computation of unspent transactions because a transaction spent an unavailable coin."
                del unspent_coins[inp]
            for i, target in enumerate(t.targets):
                unspent_coins[TransactionInput(t.get_hash(), i)] = target

        chain = Blockchain()
        chain.unspent_coins = unspent_coins
        chain.blocks = self.blocks + [block]
        chain.block_indices = self.block_indices.copy()
        chain.block_indices[block.hash] = len(self.blocks)

        return chain

    def get_block_by_hash(self, hash_val: bytes) -> 'Optional[Block]':
        """ Returns a block by its hash value, or None if it cannot be found. """
        idx = self.block_indices.get(hash_val)
        if idx is None:
            return None
        return self.blocks[idx]

    @property
    def head(self):
        """
        The head of this block chain.

        :rtype: Block
        """
        return self.blocks[-1]

    def compute_difficulty_next_block(self) -> int:
        """ Compute the desired difficulty for the block following this chain's `head`. """
        target_timedelta = Fraction(int(DIFFICULTY_TARGET_TIMEDELTA.total_seconds() * 1000 * 1000))

        block_idx = len(self.blocks)
        if block_idx % DIFFICULTY_BLOCK_INTERVAL != 0:
            return self.head.difficulty

        duration = self.head.time - self.blocks[block_idx - DIFFICULTY_BLOCK_INTERVAL].time
        duration = Fraction(int(duration.total_seconds() * 1000 * 1000))

        prev_difficulty = Fraction(self.head.difficulty)
        hash_rate = prev_difficulty * DIFFICULTY_BLOCK_INTERVAL / duration

        new_difficulty = hash_rate * target_timedelta / DIFFICULTY_BLOCK_INTERVAL

        # the genesis difficulty was very easy, dropping below it means there was a pause
        # in mining, so let's start with a new difficulty!
        if new_difficulty < self.blocks[0].difficulty:
            new_difficulty = self.blocks[0].difficulty

        return int(new_difficulty)

    def compute_blockreward_next_block(self) -> int:
        """ Compute the block reward that is expected for the block following this chain's `head`. """
        half_lives = len(self.blocks) // REWARD_HALF_LIFE
        reward = GENESIS_REWARD // (2 ** half_lives)

        return reward

from .block import Block, GENESIS_BLOCK, GENESIS_BLOCK_HASH
from .transaction import TransactionInput, Transaction
