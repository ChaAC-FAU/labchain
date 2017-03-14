import json
import os
import os.path
import tempfile


class Persistence:
    def __init__(self, path: str, chainbuilder: 'ChainBuilder'):
        self.chainbuilder = chainbuilder
        self.proto = chainbuilder.protocol
        self.path = path

        chainbuilder.chain_change_handlers.append(self.store)
        self._loading = False

    def load(self):
        self._loading = True
        try:
            with open(self.path, "r") as f:
                obj = json.load(f)
            for block in obj['blocks']:
                self.proto.received("block", block, None, 2)
            for trans in obj['transactions']:
                self.proto.received("transaction", trans, None, 2)
            for peer in obj["peers"]:
                self.proto.received("peer", peer, None, 2)
        finally:
            self._loading = False

    def store(self):
        if self._loading:
            return

        obj = {
            "blocks": [b.to_json_compatible() for b in self.chainbuilder.primary_block_chain.blocks[::-1]],
            "transactions": [t.to_json_compatible() for t in self.chainbuilder.unconfirmed_transactions.values()],
            "peers": [list(peer.peer_addr) for peer in self.proto.peers if peer.is_connected and peer.peer_addr is not None],
        }
        with tempfile.NamedTemporaryFile(dir=os.path.dirname(self.path), delete=False, mode="w") as f:
            try:
                json.dump(obj, f, indent=4)
                f.close()
                os.rename(f.name, self.path)
            except Exception as e:
                os.unlink(f.name)
                raise e
