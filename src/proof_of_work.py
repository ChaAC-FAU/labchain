""" Implementation and verification of the proof of work. """

import logging

from datetime import timedelta
from typing import Optional
from datetime import datetime

from .block import Block

from .config import *


__all__ = ['GENESIS_DIFFICULTY', 'ProofOfWork']


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
        self.init_time = 0

    def abort(self):
        """ Aborts execution of this proof of work. """
        self.stopped = True

    def run(self) -> 'Optional[Block]':
        """
        Perform the proof of work on a block, until `stopped` becomes True or the proof of
        work was successful.
        """
        self.init_time = datetime.now()
        hasher = self.block.get_partial_hash()
        while not self.stopped:
            for _ in range(1000):
                self.block.hash = self.block.finish_hash(hasher.copy())
                if self.block.verify_proof_of_work():
                    return self.block
                self.block.nonce += 1
        return None
