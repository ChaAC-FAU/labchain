class ChainBuilder:
    confirmed_block_chain = None
    unconfirmed_block_chain = []

    block_cache = {}
    unconfirmed_transactions = {}


    def new_transaction_received(self, transaction):
        hash_val = transaction.get_hash()
        if block_chain.get_transaction_by_hash(hash_val) is None:
           unconfirmed_transactions[hash_val] = transaction

    def get_next_unconfirmed_block(self):
        """  """
        unc = self.unconfirmed_block_chain
        while unc[-1].prev_block_hash in self.block_cache:
            unc.append(self.block_cache[unc[-1].prev_block_hash])

        if unc[-1].height == 0:
            # TODO: create and verify this block chain
            self.unconfirmed_block_chain = []
        else:
            # TODO: download next block

    def new_block_received(self, block):
        if not block.verify_difficulty() or block.hash in self.block_cache:
            return
        self.block_cache[block.hash] = block

        if self.unconfirmed_block_chain:
            if self.unconfirmed_block_chain[-1].prev_block_hash == block.hash:
                self.unconfirmed_block_chain.append(block)
                self.get_next_unconfirmed_block()
            else if self.unconfirmed_block_chain[0].hash == block.prev_block_hash:
                self.unconfirmed_block_chain.insert(0, block)

            if block.height > self.unconfirmed_block_chain[0].height and block.height > self.confirmed_block_chain.get_height():
                self.unconfirmed_block_chain = [block]
                self.get_next_unconfirmed_block()
        elif block.height > self.confirmed_block_chain.get_height():
            self.unconfirmed_block_chain = [block]
            self.get_next_unconfirmed_block()

