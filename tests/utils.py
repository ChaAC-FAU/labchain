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

def trans_as_input(trans, out_idx=0):
    assert len(trans.targets) > out_idx
    return TransactionInput(trans.get_hash(), out_idx)

def new_trans(old_trans, out_idx=0):
    amount = old_trans.targets[out_idx].amount
    key = Signing.generate_private_key()
    trans = Transaction([trans_as_input(old_trans, out_idx)],
                        [TransactionTarget(key, amount)])
    trans.sign([old_trans.targets[out_idx].recipient_pk])
    return trans
