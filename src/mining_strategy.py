""" Defines the contents of newly mined blocks. """

from typing import List

from .block import Block

from datetime import datetime
from .utils import compute_blockreward_next_block

from .blockchain import Blockchain
from .crypto import Key

from .transaction import Transaction, TransactionTarget, TransactionInput

__all__ = ['create_block']


def create_block(blockchain: 'Blockchain', unconfirmed_transactions: 'List[Transaction]',
                 reward_pubkey: 'Key') -> 'Block':
    """
    Creates a new block that can be mined.

    :param blockchain: The blockchain on top of which the new block should fit.
    :param unconfirmed_transactions: The transactions that should be considered for inclusion in
                                     this block.
    :param reward_pubkey: The key that should receive block rewards.
    """

    # sort the uncorfirmed transactions by the transaction fee amount
    sorted_unconfirmed_tx = sorted(unconfirmed_transactions,
                                   key=lambda tx: tx.get_transaction_fee(blockchain.unspent_coins), reverse=True)

    transactions = []
    for t in sorted_unconfirmed_tx:
        if t.validate_tx(blockchain.unspent_coins) and not t.check_tx_collision(transactions):
            transactions.append(t)

    reward = compute_blockreward_next_block(blockchain.head.height)
    fees = sum(t.get_transaction_fee(blockchain.unspent_coins) for t in transactions)

    trans = Transaction([TransactionInput(bytes(32), -1, "")], [TransactionTarget(TransactionTarget.pay_to_pubkey(reward_pubkey), fees + reward)],
                        datetime.utcnow(), iv=blockchain.head.hash)

    transactions.insert(0, trans)  # add coinbase tx to the first position

    return Block.create(blockchain.compute_target_next_block(), blockchain.head, transactions)
