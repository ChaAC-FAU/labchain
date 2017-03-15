""" Definitions of blocks, and the genesis block. """

from datetime import datetime, timedelta
from binascii import hexlify, unhexlify
from struct import pack
import json
import logging
import math

from .merkle import merkle_tree
from .crypto import get_hasher

__all__ = ['Block', 'GENESIS_BLOCK', 'GENESIS_BLOCK_HASH']

class Block:
    """
    A block.

    :ivar hash: The hash value of this block.
    :vartype hash: bytes
    :ivar prev_block_hash: The hash of the previous block.
    :vartype prev_block_hash: bytes
    :ivar merkle_root_hash: The hash of the merkle tree root of the transactions in this block.
    :vartype merkle_root_hash: bytes
    :ivar time: The time when this block was created.
    :vartype time: datetime
    :ivar nonce: The nonce in this block that was required to achieve the proof of work.
    :vartype nonce: int
    :ivar height: The height (accumulated difficulty) of this block.
    :vartype height: int
    :ivar received_time: The time when we received this block.
    :vartype received_time: datetime
    :ivar difficulty: The difficulty of this block.
    :vartype difficulty: int
    :ivar transactions: The list of transactions in this block.
    :vartype transactions: List[Transaction]
    """

    def __init__(self, hash_val, prev_block_hash, time, nonce, height, received_time, difficulty, transactions, merkle_root_hash=None):
        self.hash = hash_val
        self.prev_block_hash = prev_block_hash
        self.merkle_root_hash = merkle_root_hash
        self.time = time
        self.nonce = nonce
        self.height = height
        self.received_time = received_time
        self.difficulty = difficulty
        self.transactions = transactions

    def to_json_compatible(self):
        """ Returns a JSON-serializable representation of this object. """
        val = {}
        val['hash'] = hexlify(self.hash).decode()
        val['prev_block_hash'] = hexlify(self.prev_block_hash).decode()
        val['merkle_root_hash'] = hexlify(self.merkle_root_hash).decode()
        val['time'] = self.time.strftime("%Y-%m-%dT%H:%M:%S.%f UTC")
        val['nonce'] = self.nonce
        val['height'] = self.height
        val['difficulty'] = self.difficulty
        val['transactions'] = [t.to_json_compatible() for t in self.transactions]
        return val

    @classmethod
    def from_json_compatible(cls, val):
        """ Create a new block from its JSON-serializable representation. """
        from .transaction import Transaction
        return cls(unhexlify(val['hash']),
                   unhexlify(val['prev_block_hash']),
                   datetime.strptime(val['time'], "%Y-%m-%dT%H:%M:%S.%f UTC"),
                   int(val['nonce']),
                   int(val['height']),
                   datetime.utcnow(),
                   int(val['difficulty']),
                   [Transaction.from_json_compatible(t) for t in list(val['transactions'])],
                   unhexlify(val['merkle_root_hash']))

    @classmethod
    def create(cls, blockchain: 'Blockchain', transactions: list, ts=None):
        """
        Create a new block for a certain blockchain, containing certain transactions.
        """
        tree = merkle_tree(transactions)
        difficulty = blockchain.compute_difficulty()
        if ts is None:
            ts = datetime.utcnow()
        if ts <= blockchain.head.time:
            ts = blockchain.head.time + timedelta(microseconds=1)
        return Block(None, blockchain.head.hash, ts, 0, blockchain.head.height + difficulty,
                     None, difficulty, transactions, tree.get_hash())

    def __str__(self):
        return json.dumps(self.to_json_compatible(), indent=4)

    def verify_merkle(self):
        """ Verify that the merkle root hash is correct for the transactions in this block. """
        return merkle_tree(self.transactions).get_hash() == self.merkle_root_hash

    @staticmethod
    def _int_to_bytes(val: int) -> bytes:
        """ Turns an (arbitrarily long) integer into a bytes sequence. """
        l = val.bit_length() + 1
        # we need to include the length in the hash in some way, otherwise e.g.
        # the numbers (0xffff, 0x00) would be encoded identically to (0xff, 0xff00)
        return pack("<Q", l) + val.to_bytes(l, 'little', signed=True)

    def get_partial_hash(self):
        """
        Computes a hash over the contents of this block, except for the nonce. The proof of
        work can use this partial hash to efficiently try different nonces. Other uses should
        use :any:`get_hash` to get the complete hash.
        """
        hasher = get_hasher()
        hasher.update(self.prev_block_hash)
        hasher.update(self.merkle_root_hash)
        hasher.update(self.time.strftime("%Y-%m-%dT%H:%M:%S.%f UTC").encode())
        hasher.update(self._int_to_bytes(self.difficulty))
        return hasher

    def finish_hash(self, hasher):
        """
        Finishes the hash in `hasher` with the nonce in this block. The proof of
        work can use this function to efficiently try different nonces. Other uses should
        use :any:`get_hash` to get the complete hash in one step.
        """
        hasher.update(self._int_to_bytes(self.nonce))
        return hasher.digest()

    def get_hash(self):
        """ Compute the hash of the header data. This is not necessarily the received hash value for this block! """
        hasher = self.get_partial_hash()
        return self.finish_hash(hasher)

    def verify_difficulty(self):
        """ Verify that the hash value is correct and fulfills its difficulty promise. """
        # TODO: move this some better place
        if self.hash != self.get_hash():
            logging.warning("block has invalid hash value")
            return False
        if self.hash == GENESIS_BLOCK_HASH:
            return True
        if not verify_proof_of_work(self):
            logging.warning("block does not satisfy proof of work")
            return False
        return True

    def verify_prev_block(self, chain: 'Blockchain'):
        """ Verify the previous block pointer points to a valid block in the given block chain. """
        if self.hash == GENESIS_BLOCK_HASH:
            return True
        prev = chain.get_block_by_hash(self.prev_block_hash)
        if prev is None:
            logging.warning("Previous block is missing in the block chain.")
            return False
        if self.difficulty != chain.compute_difficulty(prev):
            logging.warning("Block has wrong difficulty.")
            return False
        if prev.height + self.difficulty != self.height:
            logging.warning("Block has wrong height.")
            return False
        return True

    def verify_transactions(self, chain: 'Blockchain'):
        """ Verify all transaction in this block are valid in the given block chain. """
        if self.hash == GENESIS_BLOCK_HASH:
            return True

        mining_reward = None

        prev_block = chain.get_block_by_hash(self.prev_block_hash)
        assert prev_block is not None

        trans_set = set(self.transactions)
        for t in self.transactions:
            if not t.inputs:
                if mining_reward is not None:
                    logging.warning("block has more than one reward transaction")
                    return False
                mining_reward = t

            if not t.verify(chain, trans_set - {t}, prev_block):
                return False
        if mining_reward is not None:
            fees = sum(t.get_transaction_fee(chain) for t in self.transactions if t is not mining_reward)
            reward = chain.compute_blockreward(chain.get_block_by_hash(self.prev_block_hash))
            used = sum(t.amount for t in mining_reward.targets)
            if used > fees + reward:
                logging.warning("mining reward is too large")
                return False
        return True

    def verify_time(self, chain: 'Blockchain'):
        """
        Verifies that blocks are not from far in the future, but always a bit younger
        than the previous block.
        """
        if self.hash == GENESIS_BLOCK_HASH:
            return True

        if self.time - timedelta(hours=2) > datetime.utcnow():
            logging.warning("discarding block because it is from the far future")
            return False
        prev_block = chain.get_block_by_hash(self.prev_block_hash)
        assert prev_block is not None
        if self.time <= prev_block.time:
            logging.warning("discarding block because it is younger than its predecessor")
            return False
        return True

    def verify(self, chain: 'Blockchain'):
        """ Verifies this block contains only valid data consistent with the given block chain. """
        if self.height == 0 and self.hash != GENESIS_BLOCK_HASH:
            logging.warning("only the genesis block may have height=0")
            return False
        return self.verify_difficulty() and self.verify_merkle() and self.verify_prev_block(chain) \
                and self.verify_transactions(chain) and self.verify_time(chain)

from .proof_of_work import verify_proof_of_work, GENESIS_DIFFICULTY, DIFFICULTY_BLOCK_INTERVAL, \
        DIFFICULTY_TARGET_TIMEDELTA


GENESIS_BLOCK = Block(b"",
        "None; {} {}".format(DIFFICULTY_BLOCK_INTERVAL, DIFFICULTY_TARGET_TIMEDELTA).encode(),
        datetime(2017, 3, 3, 10, 35, 26, 922898), 0, 0, datetime.utcnow(), GENESIS_DIFFICULTY, [],
        merkle_tree([]).get_hash())
GENESIS_BLOCK_HASH = GENESIS_BLOCK.get_hash()
GENESIS_BLOCK.hash = GENESIS_BLOCK_HASH

from .blockchain import Blockchain
