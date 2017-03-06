__all__ = ['Blockchain']

class Blockchain:
    def __init__(self, blocks: list):
        self.blocks = blocks
        assert self.blocks[0].height == 0
        self.block_indices = {block.hash: i for (i, block) in enumerate(blocks)}

    def get_transaction_by_hash(self, hash_val: bytes):
        """
        Returns a transaction from its hash, or None.
        """
        # TODO: build a hash table with this info
        for block in self.blocks[::-1]:
            for trans in block.transactions:
                if trans.get_hash() == hash_val:
                    return trans
        return None

    def is_coin_still_valid(self, transaction_input, prev_block=None):
        """
        Validates that the coins that were sent in the transaction identified
        by `transaction_hash_val` to the nth receiver (n=output_idx) have not been
        spent before the given block.
        """
        if prev_block is None:
            prev_block = self.head

        idx = self.block_indices[prev_block.hash]
        assert self.blocks[idx] is prev_block
        for block in self.blocks[idx::-1]:
            for trans in block.transactions:
                if transaction_input in trans.inputs:
                    return False
        return True

    def get_block_by_hash(self, hash_val):
        """
        Returns a block by its hash value, or None if it cannot be found.
        """
        return self.blocks[self.block_indices.get(hash_val)]

    def verify_all_transactions(self):
        """
        Verify the transactions in all blocks in this chain.
        """
        for block in self.blocks:
            if not block.verify_transactions(self):
                return False
        return True

    @property
    def head(self):
        """ The head of this block chain. """
        return self.blocks[-1]

    def compute_difficulty(self):
        """ Compute the desired difficulty for the next block. """
        # TODO: dynamic calculation
        # TODO: verify difficulty in new blocks
        return self.head.difficulty

    def compute_blockreward(self, prev_block):
        assert prev_block is not None
        reward = 1000
        l = self.block_indices[prev_block.hash]
        while l > 0:
            l = l - 10000
            reward = reward // 2
        return reward
