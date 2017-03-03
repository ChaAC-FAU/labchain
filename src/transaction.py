from collections import namedtuple

from .crypto import get_hasher, Signing

""" The recipient of a transaction ('coin'). """
TransactionTarget = namedtuple("TransactionTarget", ["recipient_pk", "amount"])
""" One transaction input (pointer to 'coin'). """
TransactionInput = namedtuple("TransactionInput", ["transaction_hash", "output_idx"])



class Transaction:

    def __init__(self, inputs, targets, signatures=None, iv=None):
        self.inputs = inputs
        self.targets = targets
        self.signatures = signatures or []
        # The IV is used to differentiate block reward transactions.
        # These have no inputs and therefore would otherwise hash to the
        # same value, when the target is identical.
        # Reuse of IVs leads to inaccessible coins.
        self.iv = iv

    def get_hash(self):
        """ Hash this transaction. Returns raw bytes. """
        h = get_hasher()
        if self.iv is not None:
            h.update(self.iv)
        for target in self.targets:
            h.update(str(target.amount).encode())
            h.update(target.recipient_pk.as_bytes())
        for inp in self.inputs:
            h.update(inp.transaction_hash)
            h.update(str(inp.output_idx).encode())
        return h.digest()

    def sign(self, private_keys):
        """
        Sign this transaction with the given private keys. The private keys need
        to be in the same order as the inputs.
        """
        for private_key in private_keys:
            self.signatures.append(private_key.sign(self.get_hash()))

    def _verify_signatures(self, chain):
        """ Verify that all inputs are signed and the signatures are valid. """
        if len(self.signatures) != len(self.inputs):
            return False

        for (s, i) in zip(self.signatures, self.inputs):
            if not self._verify_single_sig(s, i, chain):
                return False
        return True

    def _verify_single_sig(self, sig, inp, chain):
        """ Verifies the signature on a single input. """
        trans = chain.get_transaction_by_hash(inp.transaction_hash)
        sender_pk = trans.targets[inp.output_idx].recipient_pk
        return sender_pk.verify_sign(self.get_hash(), sig)


    def _verify_single_spend(self, chain, prev_block):
        """ Verifies that all inputs have not been spent yet. """
        for i in self.inputs:
            if not chain.is_coin_still_valid(i, prev_block):
                return False
        return True

    def verify(self, chain, prev_block=None):
        """ Verifies that this transaction is completely valid. """
        return self._verify_single_spend(chain, prev_block) and self._verify_signatures(chain)
