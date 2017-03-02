

class Blockchain:
    def get_transaction_by_hash(self, hash_val):
        """
        Returns a transaction from its hash, or None.
        """
        pass

    def is_coin_still_valid(self, transaction_hash_val, output_idx):
        """
        Validates that the coins that were sent in the transaction identified
        by `transaction_hash_val` to the nth receiver (n=output_idx) have not been
        spent yet.
        """
        pass

    def get_block_by_hash(self, hash_val):
        """
        Returns a block by its hash value, or None if it cannot be found.
        """
        pass


    @getter
    def head(self):
        return self.blocks[-1]
