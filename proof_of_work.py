from crypto import MAX_HASH

def verify_proof_of_work(block):
    """ Verify the proof of work on a block. """
    return int.from_bytes(block.hash, byteorder='little', signed=False) > block.difficulty

GENESIS_DIFFICULTY = MAX_HASH - (MAX_HASH // 1000)

class ProofOfWork:
    def __init__(self, block):
        self.stopped = False
        self.block = block
        self.success = False

    def abort(self)
        self.stopped = True

    def run(self):
        """
        Perform the proof of work on a block, until cond.stopped becomes True or the proof of work was sucessful.
        """
        hasher = self.block.get_partial_hash()
        while not self.stopped:
            for _ in range(1000):
                h = hasher.copy()
                h.update(self.block.nonce)
                self.block.hash = h.digest()
                if verify_proof_of_work(self.block):
                    return True
                self.block.nonce += 1
        return False
