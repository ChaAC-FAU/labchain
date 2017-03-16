""" Defines the contents of newly mined blocks. """

from typing import List

from .block import Block
from .transaction import Transaction, TransactionTarget

__all__ = ['create_block']

def create_block(blockchain: 'Blockchain', unconfirmed_transactions: 'List[Transaction]',
                 reward_pubkey: 'Signing') -> 'Block':
    """
    Creates a new block that can be mined.

    :param blockchain: The blockchain on top of which the new block should fit.
    :param unconfirmed_transactions: The transactions that should be considered for inclusion in
                                     this block.
    :param reward_pubkey: The key that should receive block rewards.
    """
    transactions = set()
    for t in unconfirmed_transactions:
        if t.verify(blockchain, transactions):
            # TODO: choose most profitable of conflicting transactions
            transactions.add(t)


    reward = blockchain.compute_blockreward_next_block()
    fees = sum(t.get_transaction_fee(blockchain) for t in transactions)
    trans = Transaction([], [TransactionTarget(reward_pubkey, reward + fees)], [], iv=blockchain.head.hash)
    transactions.add(trans)

    return Block.create(blockchain, list(transactions))

from .blockchain import Blockchain
from .crypto import Signing
