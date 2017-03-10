""" Functionality for mining new blocks. """

from threading import Thread
from time import sleep
from typing import Optional

from .proof_of_work import ProofOfWork
from .chainbuilder import ChainBuilder
from . import mining_strategy

__all__ = ['Miner']

def _yield():
    sleep(0)

class Miner:
    """
    Management of a background thread that mines for new blocks.

    :ivar proto: The protocol where newly mined blocks will be sent to.
    :vartype proto: Protocol
    :ivar chainbuilder: The chain builder used by :any:`start_mining` to find the primary chain.
    :vartype chainbuilder: ChainBuilder
    :ivar _cur_miner: The proof of work we're currently working on.
    :vartype _cur_miner: Optional[ProofOfWork]
    :ivar reward_pubkey: The public key to which mining fees and block rewards should be sent to.
    :vartype reward_pubkey: Signing
    """

    def __init__(self, proto, reward_pubkey):
        self.proto = proto
        self.chainbuilder = ChainBuilder(proto)
        self.chainbuilder.chain_change_handlers.append(self.start_mining)
        self._cur_miner = None
        self.reward_pubkey = reward_pubkey
        Thread(target=self._miner_thread, daemon=True).start()

    def _miner_thread(self):
        while True:
            miner = self._cur_miner
            if miner is None:
                # TODO: condition variable
                _yield()
            else:
                block = miner.run()
                self._cur_miner = None
                if block is not None:
                    self.proto.broadcast_primary_block(block)

    def start_mining(self):
        """ Start mining on a new block. """
        self.stop_mining()

        chain = self.chainbuilder.primary_block_chain
        transactions = self.chainbuilder.unconfirmed_transactions.values()
        block = mining_strategy.create_block(chain, transactions, self.reward_pubkey)
        self._cur_miner = ProofOfWork(block)

    def stop_mining(self):
        """ Stop all mining. """
        if self._cur_miner:
            self._cur_miner.abort()
            self._cur_miner = None

from .protocol import Protocol
from .chainbuilder import ChainBuilder
from .crypto import Signing
