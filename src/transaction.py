from collections import namedtuple
from binascii import hexlify, unhexlify
from .blockchain import Blockchain
from .block import Block

from .crypto import get_hasher, Signing

__all__ = ['TransactionTarget', 'TransactionInput', 'Transaction']

TransactionTarget = namedtuple("TransactionTarget", ["recipient_pk", "amount"])
""" The recipient of a transaction ('coin'). """

TransactionInput = namedtuple("TransactionInput", ["transaction_hash", "output_idx"])
""" One transaction input (pointer to 'coin'). """

from typing import List
SigningListType = List[Signing]


class Transaction:

    def __init__(self, inputs: list, targets: list, signatures:list=None, iv:bytes=None):
        self.inputs = inputs
        self.targets = targets
        self.signatures = signatures or []
        # The IV is used to differentiate block reward transactions.
        # These have no inputs and therefore would otherwise hash to the
        # same value, when the target is identical.
        # Reuse of IVs leads to inaccessible coins.
        self.iv = iv

    def to_json_compatible(self):
        val = {}
        val['inputs'] = []
        for inp in self.inputs:
            val['inputs'].append({
                'transaction_hash': hexlify(inp.transaction_hash).decode(),
                'output_idx': inp.output_idx,
            })
        val['targets'] = []
        for targ in self.targets:
            val['targets'].append({
                'recipient_pk': hexlify(targ.recipient_pk.as_bytes()).decode(),
                'amount': targ.amount,
            })
        val['signatures'] = []
        for sig in self.signatures:
            val['signatures'].append(hexlify(sig).decode())
        if self.iv is not None:
            val['iv'] = hexlify(self.iv).decode()
        return val

    @classmethod
    def from_json_compatible(cls, obj: dict):
        inputs = []
        for inp in obj['inputs']:
            inputs.append(TransactionInput(unhexlify(inp['transaction_hash']),
                                           int(inp['output_idx'])))
        targets = []
        for targ in obj['targets']:
            targets.append(TransactionTarget(Signing(unhexlify(targ['recipient_pk'])),
                                           int(targ['amount'])))
        signatures = []
        for sig in obj['signatures']:
            signatures.append(unhexlify(sig))

        iv = unhexlify(obj['iv']) if 'iv' in obj else None
        return cls(inputs, targets, signatures, iv)


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

    def sign(self, private_keys: SigningListType):
        """
        Sign this transaction with the given private keys. The private keys need
        to be in the same order as the inputs.
        """
        for private_key in private_keys:
            self.signatures.append(private_key.sign(self.get_hash()))

    def _verify_signatures(self, chain: Blockchain):
        """ Verify that all inputs are signed and the signatures are valid. """
        if len(self.signatures) != len(self.inputs):
            return False

        for (s, i) in zip(self.signatures, self.inputs):
            if not self._verify_single_sig(s, i, chain):
                return False
        return True

    def _verify_single_sig(self, sig: str, inp: TransactionInput, chain: Blockchain):
        """ Verifies the signature on a single input. """
        trans = chain.get_transaction_by_hash(inp.transaction_hash)
        if trans is None:
            return False
        sender_pk = trans.targets[inp.output_idx].recipient_pk
        return sender_pk.verify_sign(self.get_hash(), sig)


    def _verify_single_spend(self, chain: Blockchain, other_trans: set, prev_block: Block):
        """ Verifies that all inputs have not been spent yet. """
        inp_set = set(self.inputs)
        if len(self.inputs) != len(inp_set):
            return False
        other_inputs = {i for t in other_trans for i in t.inputs}
        if other_inputs.intersection(inp_set):
            return False

        for i in self.inputs:
            if not chain.is_coin_still_valid(i, prev_block):
                return False
        return True

    def verify(self, chain: Blockchain, other_trans:set, prev_block:Block=None):
        """ Verifies that this transaction is completely valid. """
        return self._verify_single_spend(chain, other_trans, prev_block) and self._verify_signatures(chain)
