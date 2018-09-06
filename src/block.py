""" Definitions of blocks, and the genesis block. """

from datetime import datetime
from binascii import hexlify, unhexlify

import json
import logging

import src.utils as utils

from .config import *
from .merkle import merkle_tree
from .crypto import get_hasher

__all__ = ['Block']

class Block:
    """
    A block: a container for all the data associated with a block.

    To figure out whether the block is valid on top of a block chain, there are a few `verify`
    methods. Without calling these, you must assume the block was crafted maliciously.

    :ivar hash: The hash value of this block.
    :vartype hash: bytes
    :ivar id: The ID of this block. Genesis-Block has the ID '0'.
    :vartype id: int
    :ivar prev_block_hash: The hash of the previous block.
    :vartype prev_block_hash: bytes
    :ivar merkle_root_hash: The hash of the merkle tree root of the transactions in this block.
    :vartype merkle_root_hash: bytes
    :ivar time: The time when this block was created.
    :vartype time: datetime
    :ivar nonce: The nonce in this block that was required to achieve the proof of work.
    :vartype nonce: int
    :ivar height: The height (accumulated target) of this block.
    :vartype height: int
    :ivar received_time: The time when we received this block.
    :vartype received_time: datetime
    :ivar target: The target of this block.
    :vartype target: int
    :ivar transactions: The list of transactions in this block.
    :vartype transactions: List[Transaction]
    """

    # TODO: Check if  "id" is really needed. Should be the same as "height".

    def __init__(self, prev_block_hash, time, nonce, height, received_time, target, transactions,
                 merkle_root_hash=None, id=None):
        self.id = id
        self.prev_block_hash = prev_block_hash
        self.merkle_root_hash = merkle_root_hash
        self.time = time
        self.nonce = nonce
        self.height = height
        self.received_time = received_time
        self.target = target
        self.transactions = transactions
        self._hash = self._get_hash()

    @property
    def hash(self):
        return self._hash

    @hash.setter
    def hash(self, value):
        self._hash = value

    def to_json_compatible(self):
        """ Returns a JSON-serializable representation of this object. """
        val = {}
        val['id'] = self.id
        val['hash'] = hexlify(self._hash).decode()
        val['prev_block_hash'] = hexlify(self.prev_block_hash).decode()
        val['merkle_root_hash'] = hexlify(self.merkle_root_hash).decode()
        val['time'] = self.time.strftime("%Y-%m-%dT%H:%M:%S.%f UTC")
        val['nonce'] = self.nonce
        val['height'] = self.height
        val['target'] = self.target
        val['transactions'] = [t.to_json_compatible() for t in self.transactions]
        return val

    @classmethod
    def from_json_compatible(cls, val):
        """ Create a new block from its JSON-serializable representation. """
        from .transaction import Transaction
        return cls(unhexlify(val['prev_block_hash']),
                   datetime.strptime(val['time'], "%Y-%m-%dT%H:%M:%S.%f UTC"),
                   int(val['nonce']),
                   int(val['height']),
                   datetime.utcnow(),
                   int(val['target']),
                   [Transaction.from_json_compatible(t) for t in list(val['transactions'])],
                   unhexlify(val['merkle_root_hash']),
                   int(val['id']))

    @classmethod
    def create(cls, chain_difficulty: int, prev_block: 'Block', transactions: list, ts=None):
        """
        Create a new block for a certain blockchain, containing certain transactions.
        """
        tree = merkle_tree(transactions)
        difficulty = chain_difficulty
        id = prev_block.height + 1
        if ts is None:
            ts = datetime.utcnow()
        if ts <= prev_block.time:
            ts = prev_block.time + timedelta(microseconds=1)
        return Block(prev_block.hash, ts, 0, prev_block.height + 1,
                     None, difficulty, transactions, tree.get_hash(), id)

    def __str__(self):
        return json.dumps(self.to_json_compatible(), indent=4)

    def get_partial_hash(self):
        """
        Computes a hash over the contents of this block, except for the nonce. The proof of
        work can use this partial hash to efficiently try different nonces. Other uses should
        use `hash` to get the complete hash.
        """
        hasher = get_hasher()
        hasher.update(self.prev_block_hash)
        hasher.update(self.merkle_root_hash)
        hasher.update(self.time.strftime("%Y-%m-%dT%H:%M:%S.%f UTC").encode())
        hasher.update(utils.int_to_bytes(self.target))
        return hasher

    def finish_hash(self, hasher):
        """
        Finishes the hash in `hasher` with the nonce in this block. The proof of
        work can use this function to efficiently try different nonces. Other uses should
        use `hash` to get the complete hash in one step.
        """
        hasher.update(utils.int_to_bytes(self.nonce))
        return hasher.digest()

    def _get_hash(self):
        """ Compute the hash of the header data. This is not necessarily the received hash value for this block! """
        hasher = self.get_partial_hash()
        return self.finish_hash(hasher)

    def verify_merkle(self):
        """ Verify that the merkle root hash is correct for the transactions in this block. """
        return merkle_tree(self.transactions).get_hash() == self.merkle_root_hash

    def verify_proof_of_work(self):
        """ Verify the proof of work on a block. """
        return int.from_bytes(self._hash, 'big') < self.target

    def verify_difficulty(self):
        """ Verifies that the hash value is correct and fulfills its target promise. """
        if not self.verify_proof_of_work():
            logging.warning("block does not satisfy proof of work")
            return False
        return True

    def verify_prev_block(self, prev_block: 'Block', chain_target: int):
        """ Verifies that the previous block pointer points to the head of the given blockchain and target and height are correct. """
        if prev_block.hash != self.prev_block_hash:
            logging.warning("Previous block is not head of the block chain.")
            return False

        if self.target != chain_target:
            logging.warning("Block has wrong target.")
            return False
        if prev_block.height + 1 != self.height:
            logging.warning("Block has wrong height.")
            return False
        return True

    def verify_block_transactions(self, unspent_coins: dict, reward: int):
        """ Verifies that all transaction in this block are valid in the given blockchain. """
        mining_rewards = []
        all_inputs = []
        for t in self.transactions:
            all_inputs += t.inputs
            if t.inputs[0].is_coinbase:
                if len(mining_rewards) > 1:
                    logging.warning("block has more than one coinbase transaction")
                    return False
                mining_rewards.append(t)

            if not t.validate_tx(unspent_coins):
                return False

        fees = sum(t.get_transaction_fee(unspent_coins) for t in self.transactions)
        actual_reward_and_fees = sum(t.amount for t in mining_rewards[0].targets)

        if actual_reward_and_fees > reward + fees:
            warn = "{} is different than specified({})".format(actual_reward_and_fees, reward+fees)
            logging.error(warn)
            return False

        if not self._verify_input_consistency(all_inputs):
            return False

        return True

    def _verify_input_consistency(self, tx_inputs: 'List[TransactionInputs]'):
        """"Verify that all the transactions in the transaction list are not spending from a same input transaction and index"""
        tx_inp = [(i.transaction_hash, i.output_idx) for i in tx_inputs]
        return len(tx_inp) == len(set(tx_inp))

    def verify_time(self, head_time: datetime):
        """
        Verifies that blocks are not from far in the future, but a bit younger
        than the head of `chain`.
        """
        if self.time - timedelta(hours=2) > datetime.utcnow():
            logging.warning("discarding block because it is from the far future")
            return False
        if self.time <= head_time:
            logging.warning("discarding block because it is younger than its predecessor")
            return False
        return True

    def verify(self, prev_block: 'Block', chain_difficulty: int, unspent_coins: dict, chain_indices: dict, reward: int):
        """
        Verifies that this block contains only valid data and can be applied on top of the block
        chain `chain`.
        """
        assert self._hash not in chain_indices
        if self.height == 0:
            logging.warning("only the genesis block may have height=0")
            return False

        return self.verify_difficulty() and self.verify_merkle() and self.verify_prev_block(prev_block,
                                                                                            chain_difficulty) \
               and self.verify_time(prev_block
                                    .time) and self.verify_block_transactions(unspent_coins, reward)
