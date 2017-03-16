from datetime import datetime

import src.proof_of_work
import src.block

from src.block import *
from src.blockchain import *
from src.crypto import *
from src.transaction import *

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")

def extend_blockchain(chain, trans:list=None, verify_res=True):
    ts = datetime.utcfromtimestamp(0)
    new_block = Block.create(chain, trans, ts)
    new_block.hash = new_block.get_hash()
    new_chain = chain.try_append(new_block)
    assert (new_chain is not None) == verify_res
    return new_chain

def create_block(chain, **manipulate_fields):
    block = Block.create(chain, [], chain.head.time)
    block.hash = b""
    obj = block.to_json_compatible()
    for k, v in manipulate_fields.items():
        assert k != "hash", "manipulating hash not supported"
        assert k in obj, "setting an unknown field is useless"
        obj[k] = v
    block = Block.from_json_compatible(obj)
    block.hash = block.get_hash()
    return block

def trans_as_input(trans, out_idx=0):
    assert len(trans.targets) > out_idx
    return TransactionInput(trans.get_hash(), out_idx)

def new_trans(old_trans, out_idx=0, fee=0):
    amount = old_trans.targets[out_idx].amount - fee
    key = Signing.generate_private_key()
    trans = Transaction([trans_as_input(old_trans, out_idx)],
                        [TransactionTarget(key, amount)])
    trans.sign([old_trans.targets[out_idx].recipient_pk])
    return trans
