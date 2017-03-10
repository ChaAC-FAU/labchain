from src.protocol import Protocol
from src.mining import Miner
from src.block import GENESIS_BLOCK
from src.crypto import Signing
from src.transaction import Transaction, TransactionInput, TransactionTarget

from time import sleep

reward_key = Signing.generatePrivateKey()

proto1 = Protocol([], GENESIS_BLOCK, 1337)
proto2 = Protocol([("127.0.0.1", 1337)], GENESIS_BLOCK, 1338)
miner1 = Miner(proto1, reward_key)
miner2 = Miner(proto2, reward_key)
miner2.start_mining()
miner1.start_mining()



sleep(5)
strans1 = miner2.chainbuilder.primary_block_chain.blocks[20].transactions[0]
strans1 = TransactionInput(strans1.get_hash(), 0)
trans = Transaction([strans1], [])
trans.sign([reward_key])
print(trans.verify(miner1.chainbuilder.primary_block_chain, set()))
proto2.received('transaction', trans.to_json_compatible(), None)
sleep(5)
print(len(miner1.chainbuilder.primary_block_chain.blocks))
print(len(miner2.chainbuilder.primary_block_chain.blocks))
hashes1 = [b.hash for b in miner1.chainbuilder.primary_block_chain.blocks[:70]]
hashes2 = [b.hash for b in miner2.chainbuilder.primary_block_chain.blocks[:70]]
print(hashes1 == hashes2)

print(trans.verify(miner1.chainbuilder.primary_block_chain, set()))
