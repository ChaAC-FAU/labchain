from proof_of_work import ProofOfWork
from chainbuilder import ChainBuilder
from threading import Thread
import mining_strategy
from time import sleep

class Miner:
    def __init__(self):
        self.chainbuilder = ChainBuilder()
        self.chainbuilder.chain_change_handlers.append(self.chain_changed)
        self.is_mining = False
        self.cur_miner = None
        Thread(target=self._miner_thread, daemon=True).start()

    def _miner_thread(self):
        while True:
            miner = self.cur_miner
            if miner is None:
                sleep(1)
            else:
                success = miner.run()

    def start_mining(self, block):
        """ Start mining on a new block. """
        if self.cur_miner:
            self.cur_miner.abort()
        self.cur_miner = ProofOfWork(block)

    def stop_mining(self):
        """ Stop all mining. """
        if self.cur_miner:
            self.cur_miner.abort()
            self.cur_miner = None

    def chain_changed(self):
        """
        Used as a event handler on the chainbuilder. It is called when the
        primary chain changes.
        """
        chain = self.chainbuilder.primary_block_chain
        block = mining_strategy.create_block(chain, self.chainbuilder.unconfirmed_transactions)
        self.start_mining(block)
