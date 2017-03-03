from datetime import datetime

from .block import Block
from .merkle import merkle_tree
from .transaction import Transaction, TransactionTarget

from Crypto.PublicKey import RSA

def create_block(blockchain, unconfirmed_transactions, reward_pubkey):
    """
    Creates a new block that can be mined.
    """
    head = blockchain.head

    transactions = list(unconfirmed_transactions)
    reward = blockchain.compute_blockreward(head)
    trans = Transaction([], [TransactionTarget(reward_pubkey, reward)], [], iv=head.hash)
    transactions.append(trans)

    tree = merkle_tree(transactions)
    difficulty = blockchain.compute_difficulty()
    return Block(None, head.hash, datetime.now(), 0, head.height + difficulty,
                 None, difficulty, tree.get_hash(), transactions)
