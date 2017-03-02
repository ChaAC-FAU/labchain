from collections import namedtuple
from crypto import get_hasher, sign, verify_sign

TransactionTarget = namedtuple("TransactionTarget", ["recipient_pk", "amount"])
TransactionInput = namedtuple("TransactionInput", ["transaction_hash", "output_idx"])



class Transaction:
    def __init__(self, inputs, targets, signatures=None):
        self.inputs = inputs
        self.targets = targets
        self.signatures = signatures or []

    def get_hash(self):
        """ Hash this transaction. Returns raw bytes. """
        h = get_hasher()
        for target in self.targets:
            h.update(target.amount)
            h.update(target.recipient_pk)
        for inp in self.inputs:
            h.update(inp)
        return h.digest()

    def sign(self, private_key):
        """ Sign this transaction with a private key. You need to call this in the same order as the inputs. """
        self.signatures.append(sign(self.get_hash(), private_key))

    def _verify_signatures(self, chain):
        """ Verify that all inputs are signed and the signatures are valid. """
        if len(self.signatures) != len(self.inputs)
            return False

        for (s, i) in zip(self.signatures, self.inputs):
            if not self._verify_single_sig(s, i, chain):
                return False
        return True

    def _verify_single_sig(self, sig, inp, chain):
        """ Verifies the signature on a single input. """
        trans = chain.get_transaction_by_hash(inp.transaction_hash)
        sender_pk = trans.targets[inp.output_idx]
        return verify_sign(self.get_hash(), sig)


    def _verify_single_spend(self, chain):
        """ Verifies that all inputs have not been spent yet. """
        for i in self.inputs:
            if not chain.is_coin_still_valid(i.transaction_hash, i.output_idx):
                return False
        return True

    def verify(self, chain):
        """ Verifies that this transaction is completely valid. """
        return self._verify_single_spend(chain) and self._verify_signatures(chain)
