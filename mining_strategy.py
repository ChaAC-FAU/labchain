from block import Block
from datetime import datetime
from merkle import merkle_tree

def create_block(blockchain, unconfirmed_transactions):
    """
    Creates a new block that can be mined.
    """
    tree = merkle_tree(unconfirmed_transactions)
    head = blockchain.head
    difficulty = blockchain.compute_difficulty()
    return Block(None, head.hash, datetime.now(), 0, head.height + difficulty,
                 None, difficulty, tree.get_hash(), unconfirmed_transactions)
