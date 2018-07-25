from time import sleep
import logging
#logging.basicConfig(level=logging.DEBUG)

from src.protocol import Protocol
from src.mining import Miner
from src.block import GENESIS_BLOCK
from src.crypto import Key
from src.transaction import Transaction, TransactionInput, TransactionTarget
from datetime import datetime

def test_proto():
    reward_key = Key.generate_private_key()

    proto1 = Protocol([], GENESIS_BLOCK, 1337)
    proto2 = Protocol([("127.0.0.1", 1337)], GENESIS_BLOCK, 1338)
    miner1 = Miner(proto1, reward_key)
    miner2 = Miner(proto2, reward_key)
    miner2.start_mining()
    miner1.start_mining()

    try:
        sleep(5)
        target_key = Key.generate_private_key()
        chain = miner1.chainbuilder.primary_block_chain
        reward_trans = chain.blocks[20].transactions[0]

        trans_in = TransactionInput(reward_trans.get_hash(), 0)
        trans_targ = TransactionTarget(target_key, reward_trans.targets[0].amount)

        trans = Transaction([trans_in], [trans_targ], datetime.utcnow())
        trans.sign([reward_key])

        assert trans.verify(chain, set()), "transaction should be valid"

        proto1.received('transaction', trans.to_json_compatible(), None)
        print("============Transaction=============")

        sleep(10)

        chain_len1 = len(miner1.chainbuilder.primary_block_chain.blocks)
        chain_len2 = len(miner2.chainbuilder.primary_block_chain.blocks)
        print("Length of chain of miner 1: {}".format(chain_len1))
        print("Length of chain of miner 2: {}".format(chain_len2))
    finally:
        miner1.shutdown()
        miner2.shutdown()

    assert max(chain_len1, chain_len2) * 90 // 100 < min(chain_len1, chain_len2), "chain lengths are VERY different"

    chain1 = miner1.chainbuilder.primary_block_chain
    hashes1 = [b.hash for b in chain1.blocks[:chain_len1 * 90 // 100]]
    hashes2 = [b.hash for b in miner2.chainbuilder.primary_block_chain.blocks[:chain_len1 * 90 // 100]]
    assert hashes1 == hashes2, "first 90% of chains should be identical"

    assert not trans.verify(miner1.chainbuilder.primary_block_chain, set()), "inserted transaction should be spent and therefore invalid"

    assert TransactionInput(trans.get_hash(), 0) in chain1.unspent_coins, "someone spent our coins?"
