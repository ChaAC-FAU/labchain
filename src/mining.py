""" Functionality for mining new blocks. """

import json
import os
import sys
import signal
import time
import select
from threading import Thread, Condition
from typing import Optional, Callable, Tuple, List

from .proof_of_work import ProofOfWork
from .chainbuilder import ChainBuilder
from .block import Block
from . import mining_strategy

__all__ = ['Miner']



signal.signal(signal.SIGCHLD, signal.SIG_IGN)

def exit_on_pipe_close(pipe):
    """ Waits until the pipe `pipe` can no longer be used, then kills this process. """
    poller = select.poll()
    poller.register(pipe, select.POLLERR)
    poller.poll()
    os._exit(1)


def start_process(func: Callable) -> Tuple[int, int]:
    """
    Starts a function in a forked process, and writes its result to a pipe.

    :param func: The function the background process should run.
    :rval: A tuple of the pipe where the result will be written to and the process id of the
           forked process.
    """
    rx, wx = os.pipe()
    pid = os.fork()
    if pid == 0: # child
        try:
            os.close(0)
            os.closerange(3, wx)
            os.closerange(wx + 1, 2**16)

            Thread(target=exit_on_pipe_close, args=(wx,), daemon=True).start()

            res = func().to_json_compatible()
            with os.fdopen(wx, "w") as fp:
                json.dump(res, sys.stdout)
                json.dump(res, fp)
        except Exception:
            import traceback
            traceback.print_exc()
            os._exit(1)
        os._exit(0)
    else: # parent
        os.close(wx)
        return rx, pid

def wait_for_result(pipes: List[int], cls: type):
    """
    Waits for one of the pipes in `pipes` to become ready, reads a JSON object from that pipe
    and calls `cls.from_json_compatible()` to build the return value.
    All pipes are closed once this function returns.

    :param pipes: The list of pipes to wait for.
    :param cls: The class (with a `from_json_compatible` method) to return instances of.
    :rtype: An instance of `cls`.
    """
    ready, _, _ = select.select(pipes, [], [])
    for p in pipes:
        if p != ready[0]:
            os.close(p)

    with os.fdopen(ready[0], "r") as fp:
        return cls.from_json_compatible(json.load(fp))

class Miner:
    """
    Management of a background process that mines for new blocks.

    The miner process is forked for each new proof of work that needs to be performed. The
    completed block is sent back JSON-serialized through a pipe that is opened for that purpose.
    When that pipe is closed by the parent process prematurely, the proof of work process knows it
    is no longer needed and exits.

    To start the mining process, `start_mining` needs to be called once. After that, the mining
    will happen automatically, with the mined block switching every time the chainbuilder finds a
    new primary block chain.

    To stop the mining process, there is the `shutdown` method. Once stopped, mining cannot be
    resumed (except by creating a new `Miner`).

    :ivar proto: The protocol where newly mined blocks will be sent to.
    :vartype proto: Protocol
    :ivar chainbuilder: The chain builder used by :any:`start_mining` to find the primary chain.
    :vartype chainbuilder: ChainBuilder
    :ivar _cur_miner_pipes: Pipes where worker processes will write their results to.
    :vartype _cur_miner_pipes: Optional[List[int]]
    :ivar _cur_miner_pids: Process ids of our worker processes.
    :vartype _cur_miner_pids: List[int]
    :ivar reward_pubkey: The public key to which mining fees and block rewards should be sent to.
    :vartype reward_pubkey: Signing
    """

    def __init__(self, proto, reward_pubkey):
        self.proto = proto
        self.chainbuilder = ChainBuilder(proto)
        self.chainbuilder.chain_change_handlers.append(self._chain_changed)
        self._cur_miner_pids = []
        self._cur_miner_pipes = None
        self.reward_pubkey = reward_pubkey
        self._stopped = False
        self._started = False
        self._miner_cond = Condition()

    def _miner_thread(self):
        def wait_for_miner():
            with self._miner_cond:
                while self._cur_miner_pipes is None:
                    if self._stopped:
                        return None, None
                    self._miner_cond.wait()
                pipes = self._cur_miner_pipes
                pids = self._cur_miner_pids
                self._cur_miner_pipes = None
                return pipes, pids

        while True:
            rxs, pids = wait_for_miner()
            if rxs is None:
                return

            try:
                block = wait_for_result(rxs, Block)
                self.proto.broadcast_primary_block(block)
            except json.JSONDecodeError:
                pass

            with self._miner_cond:
                if self._cur_miner_pids == pids:
                    for pid in pids:
                        try:
                            os.kill(pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    self._cur_miner_pids = []

    def start_mining(self):
        """ Start mining on a new block. """
        with self._miner_cond:
            if not self._started:
                Thread(target=self._miner_thread, daemon=True).start()
            self._started = True
            # TODO: accessing the chainbuilder is problematic if start_mining was not called from the protocol's main thread
            chain = self.chainbuilder.primary_block_chain
            transactions = self.chainbuilder.unconfirmed_transactions.values()
            block = mining_strategy.create_block(chain, transactions, self.reward_pubkey)
            self._stop_mining_for_now()
            self._cur_miner_pipes = []

            miner = ProofOfWork(block)
            rx, pid = start_process(miner.run)
            self._cur_miner_pids.append(pid)
            self._cur_miner_pipes.append(rx)

            self._miner_cond.notify()

    def _chain_changed(self):
        if not self._stopped and self._started:
            self.start_mining()

    def _stop_mining_for_now(self):
        for pid in self._cur_miner_pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        self._cur_miner_pids = []

    def shutdown(self):
        """ Stop all mining. """
        self._stopped = True
        with self._miner_cond:
            self._stop_mining_for_now()
            self._miner_cond.notify()
        self.chainbuilder.chain_change_handlers.remove(self._chain_changed)

from .protocol import Protocol
from .chainbuilder import ChainBuilder
from .crypto import Signing
