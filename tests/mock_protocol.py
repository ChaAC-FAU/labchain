from src.mining import Miner

class MockProtocol:
    def __init__(self):
        self.block_receive_handlers = []
        self.trans_receive_handlers = []

    def fake_block_received(self, block):
        for handler in self.block_receive_handlers:
            handler(block)

    def fake_trans_received(self, trans):
        for handler in self.trans_receive_handlers:
            handler(trans)

    def broadcast_mined_block(self, block):
        self.fake_block_received(block)
