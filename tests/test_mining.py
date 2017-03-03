from .mock_protocol import MockProtocol
from src.mining import Miner
from src.block import GENESIS_BLOCK
from src.crypto import Signing
from src.transaction import Transaction, TransactionInput, TransactionTarget

from time import sleep

reward_key = Signing.generatePrivateKey()

proto = MockProtocol()
miner1 = Miner(proto, reward_key)
miner2 = Miner(proto, reward_key)
miner2.chain_changed()



sleep(5)
#proto.fake_block_received(GENESIS_BLOCK)
strans1 = miner2.chainbuilder.primary_block_chain.head.transactions[0]
strans1 = TransactionInput(strans1.get_hash(), 0)
strans2 = miner2.chainbuilder.primary_block_chain.head.transactions[0]
strans2 = TransactionInput(strans2.get_hash(), 0)
trans = Transaction([strans1, strans2], [])
trans.sign([reward_key, reward_key])
miner2.chainbuilder.new_transaction_received(trans)
sleep(5)
print(len(miner2.chainbuilder.primary_block_chain.blocks))
