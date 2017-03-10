from .proof_of_work import ProofOfWork
from .chainbuilder import ChainBuilder
from . import mining_strategy
from .protocol import Protocol

from threading import Thread
from time import sleep

__all__ = ['Miner']

class Miner:
    def __init__(self, proto, reward_pubkey):
        self.proto = proto
        self.chainbuilder = ChainBuilder(proto)
        self.chainbuilder.chain_change_handlers.append(self.start_mining)
        self.is_mining = False
        self.cur_miner = None
        self.reward_pubkey = reward_pubkey
        Thread(target=self._miner_thread, daemon=True).start()

    def _miner_thread(self):
        while True:
            miner = self.cur_miner
            if miner is None:
                sleep(0)
            else:
                block = miner.run()
                self.cur_miner = None
                if block is not None:
                    self.proto.broadcast_primary_block(block)

    def start_mining(self):
        """ Start mining on a new block. """
        self.stop_mining()

        chain = self.chainbuilder.primary_block_chain
        transactions = self.chainbuilder.unconfirmed_transactions
        block = mining_strategy.create_block(chain, transactions, self.reward_pubkey)
        self.cur_miner = ProofOfWork(block)

    def stop_mining(self):
        """ Stop all mining. """
        if self.cur_miner:
            self.cur_miner.abort()
            self.cur_miner = None
