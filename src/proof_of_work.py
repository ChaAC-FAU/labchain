""" Implementation and verification of the proof of work. """

from typing import Optional

from .crypto import MAX_HASH

__all__ = ['verify_proof_of_work', 'GENESIS_DIFFICULTY', 'ProofOfWork']

def verify_proof_of_work(block: 'Block'):
    """ Verify the proof of work on a block. """
    return int.from_bytes(block.hash, byteorder='little', signed=False) > (MAX_HASH - MAX_HASH // block.difficulty)

GENESIS_DIFFICULTY = 1000
"""
The difficulty of the genesis block.

Right now this is the average required number of hashes to compute one valid block.
"""

class ProofOfWork:
    """
    Allows performing (and aborting) a proof of work.

    :ivar stopped: A flag that is set to `True` to abort the `run` operation.
    :vartype stopped: bool
    :ivar block: The block on which the proof of work should be performed.
    :param block: The block on which the proof of work should be performed.
    :vartype block: Block
    :ivar success: A flag indication whether the proof of work was successful or not.
    :vartype success: bool
    """

    def __init__(self, block: 'Block'):
        self.stopped = False
        self.block = block
        self.success = False

    def abort(self):
        """ Aborts execution of this proof of work. """
        self.stopped = True

    def run(self) -> 'Optional[Block]':
        """
        Perform the proof of work on a block, until `stopped` becomes True or the proof of
        work was successful.
        """
        hasher = self.block.get_partial_hash()
        while not self.stopped:
            for _ in range(1000):
                self.block.hash = self.block.finish_hash(hasher.copy())
                if verify_proof_of_work(self.block):
                    return self.block
                self.block.nonce += 1
        return None

from .block import Block
