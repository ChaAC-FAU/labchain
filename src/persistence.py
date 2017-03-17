""" Functionality for storing and retrieving the miner state on disk. """

import json
import os
import os.path
import tempfile
import gzip
import time
from io import TextIOWrapper
from threading import Condition, Thread
from datetime import timedelta

PERSISTENCE_MIN_INTERVAL = timedelta(seconds=5)

class Persistence:
    """
    Functionality for storing and retrieving the miner state on disk.

    :param path: The path to the storage location. """#TODO
    """:param chainbuilder: The chainbuilder to persist.
    """
    def __init__(self, path: str, chainbuilder: 'ChainBuilder'):
        self.chainbuilder = chainbuilder
        self.proto = chainbuilder.protocol
        self.path = path
        self._store_cond = Condition()
        self._store_data = None

        chainbuilder.chain_change_handlers.append(self.store)
        chainbuilder.transaction_change_handlers.append(self.store)
        self._loading = False

        Thread(target=self._store_thread, daemon=True).start()

    def load(self):
        """ Loads data from disk. """
        self._loading = True
        try:
            with gzip.open(self.path, "r") as f:
                obj = json.load(TextIOWrapper(f))
            for block in obj['blocks']:
                self.proto.received("block", block, None, 2)
            for trans in obj['transactions']:
                self.proto.received("transaction", trans, None, 2)
            for peer in obj["peers"]:
                self.proto.received("peer", peer, None, 2)
        finally:
            self._loading = False

    def store(self):
        """
        Asynchronously stores current data to disk.

        Used as an event handler in the chainbuilder.
        """
        if self._loading:
            return

        chain = self.chainbuilder.primary_block_chain
        trans = self.chainbuilder.unconfirmed_transactions.copy()
        peers = [list(peer.peer_addr) for peer in self.proto.peers if peer.is_connected and peer.peer_addr is not None]

        with self._store_cond:
            self._store_data = chain, trans, peers
            self._store_cond.notify()

    def _store_thread(self):
        while True:
            with self._store_cond:
                while self._store_data is None:
                    self._store_cond.wait()
                chain, trans, peers = self._store_data
                self._store_data = None

            obj = {
                "blocks": [b.to_json_compatible() for b in chain.blocks[::-1]],
                "transactions": [t.to_json_compatible() for t in trans.values()],
                "peers": peers,
            }

            with tempfile.NamedTemporaryFile(dir=os.path.dirname(self.path), mode="wb", delete=False) as tmpf:
                try:
                    with TextIOWrapper(gzip.open(tmpf, mode="w")) as f:
                        json.dump(obj, f, indent=4)
                    tmpf.close()
                    os.rename(tmpf.name, self.path)
                except Exception as e:
                    os.unlink(tmpf.name)
                    raise e
            time.sleep(PERSISTENCE_MIN_INTERVAL.total_seconds())

from .chainbuilder import ChainBuilder
