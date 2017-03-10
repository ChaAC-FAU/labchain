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

    transactions = list(transactions)
    tree = merkle_tree(transactions)
    difficulty = blockchain.compute_difficulty()
    return Block(None, head.hash, datetime.now(), 0, head.height + difficulty,
                 None, difficulty, transactions, tree.get_hash())
