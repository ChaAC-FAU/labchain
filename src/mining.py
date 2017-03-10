""" Functionality for mining new blocks. """

from threading import Thread, Condition
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
        self.chainbuilder.chain_change_handlers.append(self._chain_changed)
        self._cur_miner = None
        self.reward_pubkey = reward_pubkey
        self._stopped = False
        self._miner_cond = Condition()
        Thread(target=self._miner_thread, daemon=True).start()

    def _miner_thread(self):
        def wait_for_miner():
            with self._miner_cond:
                while self._cur_miner is None:
                    if self._stopped:
                        return None
                    self._miner_cond.wait()
                return self._cur_miner

        while True:
            miner = wait_for_miner()
            if miner is None:
                return
            block = miner.run()
            with self._miner_cond:
                if self._cur_miner == miner:
                    self._cur_miner = None
            if block is not None:
                self.proto.broadcast_primary_block(block)

    def start_mining(self):
        """ Start mining on a new block. """
        chain = self.chainbuilder.primary_block_chain
        transactions = self.chainbuilder.unconfirmed_transactions.values()
        block = mining_strategy.create_block(chain, transactions, self.reward_pubkey)
        with self._miner_cond:
            self._stop_mining_for_now()
            self._cur_miner = ProofOfWork(block)
            self._miner_cond.notify()

    def _chain_changed(self):
        if not self._stopped:
            self.start_mining()

    def _stop_mining_for_now(self):
        if self._cur_miner:
            self._cur_miner.abort()

    def stop_mining(self):
        """ Stop all mining. """
        self._stopped = True
        with self._miner_cond:
            self._stop_mining_for_now()
            self._cur_miner = None
            self._miner_cond.notify()

from .protocol import Protocol
from .chainbuilder import ChainBuilder
from .crypto import Signing
