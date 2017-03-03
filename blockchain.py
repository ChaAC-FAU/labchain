
class Blockchain:
    def __init__(self, blocks):
        self.blocks = blocks
        assert self.blocks[0].height == 0
        self.blocks_by_hash = {block.hash: block for block in blocks}

    def get_transaction_by_hash(self, hash_val):
        """
        Returns a transaction from its hash, or None.
        """
        for block in self.blocks[prev_block.height::-1]:
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

        assert self.blocks[prev_block.height] is prev_block
        for block in self.blocks[prev_block.height::-1]:
            for trans in block.transactions:
                if transaction_input in trans.inputs:
                    return False
        return True

    def get_block_by_hash(self, hash_val):
        """
        Returns a block by its hash value, or None if it cannot be found.
        """
        return self.blocks_by_hash.get(hash_val)

    def verify_all_transactions(self):
        """
        Verify the transactions in all blocks in this chain.
        """
        for block in self.blocks:
            block.verify_transactions(self)


    @getter
    def head(self):
        """ The head of this block chain. """
        return self.blocks[-1]

    def compute_difficulty(self):
        """ Compute the desired difficulty for the next block. """
        # TODO: dynamic calculation
        # TODO: verify difficulty in new blocks
        return self.head.difficulty
