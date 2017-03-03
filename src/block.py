from datetime import datetime
from binascii import hexlify

from .merkle import merkle_tree
from .crypto import get_hasher
from .proof_of_work import verify_proof_of_work, GENESIS_DIFFICULTY

class Block:
    """ A block. """

    def __init__(self, hash_val, prev_block_hash, time, nonce, height, received_time, difficulty, merkle_root_hash=None, transactions=None):
        self.hash = hash_val
        self.prev_block_hash = prev_block_hash
        self.merkle_root_hash = merkle_root_hash
        self.time = time
        self.nonce = nonce
        self.height = height
        self.received_time = received_time
        self.difficulty = difficulty
        self.transactions = transactions

    def __str__(self):
        return """Block {}
    Previous Block: {}
    Merkle Hash: {}
    Time: {}
    Nonce: {:x}
    Height: {}
    Received Time: {}
    Difficulty: {:x}""".format(hexlify(self.hash), hexlify(self.prev_block_hash), hexlify(self.merkle_root_hash), self.time, self.nonce, self.height, self.received_time, self.difficulty)


    def verify_merkle(self):
        """ Verify that the merkle root hash is correct for the transactions in this block. """
        return merkle_tree(self.transactions).get_hash() == self.merkle_root_hash

    def get_partial_hash(self):
        hasher = get_hasher()
        hasher.update(self.prev_block_hash)
        hasher.update(self.merkle_root_hash)
        hasher.update(str(self.time.timestamp()).encode())
        hasher.update(str(self.difficulty).encode())
        return hasher

    def get_hash(self):
        """ Compute the hash of the header data. This is not necessarily the received hash value for this block! """
        hasher = self.get_partial_hash()
        hasher.update(str(self.nonce).encode()) # for mining we want to get a copy of hasher here
        return hasher.digest()

    def verify_difficulty(self):
        """ Verify that the hash value is correct and fulfills its difficulty promise. """
        # TODO: move this some better place
        if self.hash != self.get_hash():
            return False
        return verify_proof_of_work(self)

    def verify_prev_block(self, chain):
        """ Verify the previous block pointer points to a valid block in the given block chain. """
        return chain.get_block_by_hash(chain) is not None

    def verify_transactions(self, chain):
        """ Verify all transaction in this block are valid in the given block chain. """
        mining_reward = None
        # TODO: mining fees and variable block rewards
        for t in self.transactions:
            if not t.inputs:
                if mining_reward is not None:
                    return False
                mining_reward = t

            if not t.verify(chain):
                return False
        if mining_reward is not None:
            if sum(map(lambda t: t.amount, mining_reward.targets)) > chain.compute_blockreward(chain.get_block_by_hash(self.prev_block_hash)):
                return False
        return True

    def verify(self, chain):
        """ Verifies this block contains only valid data consistent with the given block chain. """
        if self.height == 0:
            return self.hash == GENESIS_BLOCK_HASH
        return self.verify_difficulty() and self.verify_merkle() and self.verify_prev_block(chain) and self.verify_transactions(chain)

GENESIS_BLOCK = Block(b"", b"None", datetime(2017, 3, 3, 10, 35, 26, 922898),
                      0, 0, datetime.now(), GENESIS_DIFFICULTY, merkle_tree([]).get_hash(), [])
GENESIS_BLOCK_HASH = GENESIS_BLOCK.get_hash()
GENESIS_BLOCK.hash = GENESIS_BLOCK_HASH
