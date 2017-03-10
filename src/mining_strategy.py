from datetime import datetime

from .block import Block
from .merkle import merkle_tree
from .transaction import Transaction, TransactionTarget

from Crypto.PublicKey import RSA

__all__ = ['create_block']

def create_block(blockchain, unconfirmed_transactions, reward_pubkey):
    """
    Creates a new block that can be mined.
    """
    head = blockchain.head

    transactions = set()
    for t in unconfirmed_transactions:
        if t.verify(blockchain, transactions):
            # TODO: choose most profitable of conflicting transactions
            transactions.add(t)


    reward = blockchain.compute_blockreward(head)
    trans = Transaction([], [TransactionTarget(reward_pubkey, reward)], [], iv=head.hash)
    transactions.add(trans)

    return Block.create(blockchain, list(transactions))
