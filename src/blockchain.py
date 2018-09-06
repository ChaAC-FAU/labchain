""" Definition of block chains. """

__all__ = ['Blockchain', 'GENESIS_BLOCK']
import logging

from binascii import hexlify

from collections import namedtuple

from typing import Optional

from datetime import datetime

from .merkle import merkle_tree
from .block import Block

from .config import *
from .utils import compute_blockreward_next_block

# If you want to add transactions to the genesis block you can create a Transaction object and include it in the list below (after GENESIS_TARGET)
GENESIS_BLOCK = Block("None; {} {}".format(DIFFICULTY_BLOCK_INTERVAL, DIFFICULTY_TIMEDELTA).encode(),
                      datetime(2017, 3, 3, 10, 35, 26, 922898), 0, 0, datetime.utcnow(), GENESIS_TARGET,
                      [], merkle_tree([]).get_hash(), 0)

GENESIS_BLOCK_HASH = GENESIS_BLOCK.hash


class Blockchain:
    """
    A block chain: a ordered, immutable list of valid blocks. The only way to create a blockchain
    instance is the constructor, which will create a block chain containing only the genesis block,
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
        self.unspent_coins = {}
        self.total_difficulty = 0

    def try_append(self, block: 'Block') -> 'Optional[Blockchain]':
        """
        If `block` is valid on top of this chain, returns a new blockchain including that block.
        Otherwise, it returns `None`.
        """

        if not block.verify(self.head, self.compute_target_next_block(), self.unspent_coins, self.block_indices,
                            compute_blockreward_next_block(self.head.height)):
            return None

        unspent_coins = self.unspent_coins.copy()

        for t in block.transactions:
            for inp in t.inputs:
                if inp.is_coinbase:
                    continue

                # the checks for tx using the same inputs are already done in the block.verify method
                unspent_coins.pop((inp.transaction_hash, inp.output_idx), None)

            for i, target in enumerate(t.targets):
                if target.is_pay_to_pubkey or target.is_pay_to_pubkey_lock:
                    unspent_coins[(t.get_hash(), i)] = target

        chain = Blockchain()
        chain.unspent_coins = unspent_coins
        chain.blocks = self.blocks + [block]
        chain.block_indices = self.block_indices.copy()
        chain.block_indices[block.hash] = len(self.blocks)
        chain.total_difficulty = self.total_difficulty + GENESIS_TARGET - block.target

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

    def compute_target_next_block(self) -> int:
        """ Compute the desired target for the block following this chain's `head`. """
        should_duration = DIFFICULTY_TIMEDELTA.total_seconds()

        if (self.head.height % DIFFICULTY_BLOCK_INTERVAL != 0) or (self.head.height == 0):
            return self.head.target

        past_block = self.blocks[self.head.height - DIFFICULTY_BLOCK_INTERVAL]
        last_duration = (self.head.time - past_block.time).total_seconds()
        diff_adjustment_factor = last_duration / should_duration
        prev_target = self.head.target
        new_target = prev_target * diff_adjustment_factor

        # the genesis target was very easy, making it easier means there was a pause
        # in mining, so we start over with the initial target
        if new_target > self.blocks[0].target:
            new_target = self.blocks[0].target

        return int(new_target)
