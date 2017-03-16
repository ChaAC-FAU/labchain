""" Defines transactions and their inputs and outputs. """

import logging
from collections import namedtuple
from binascii import hexlify, unhexlify
from typing import List, Set

from .crypto import get_hasher, Signing

__all__ = ['TransactionTarget', 'TransactionInput', 'Transaction']

TransactionTarget = namedtuple("TransactionTarget", ["recipient_pk", "amount"])
"""
The recipient of a transaction ('coin').

:ivar recipient_pk: The public key of the recipient.
:vartype recipient_pk: Signing
:ivar amount: The amount sent to `recipient_pk`.
:vartype amount: int
"""


class TransactionInput(namedtuple("TransactionInput", ["transaction_hash", "output_idx"])):
    """
    One transaction input (pointer to 'coin').

    :ivar transaction_hash: The hash of the transaction that sent money to the sender.
    :vartype transaction_hash: bytes
    :ivar output_idx: The index into `Transaction.targets` of the `transaction_hash`.
    :vartype output_idx: int
    """

    @classmethod
    def from_json_compatible(cls, obj):
        """ Creates a new object of this class, from a JSON-serializable representation. """
        return cls(unhexlify(obj['transaction_hash']), int(obj['output_idx']))

    def to_json_compatible(self):
        """ Returns a JSON-serializable representation of this object. """
        return {
            'transaction_hash': hexlify(self.transaction_hash).decode(),
            'output_idx': self.output_idx,
        }


class Transaction:
    """
    A transaction.

    :ivar inputs: The inputs of this transaction. Empty in the case of block reward transactions.
    :vartype inputs: List[TransactionInput]
    :ivar targets: The targets of this transaction.
    :vartype targets: List[TransactionTarget]
    :ivar signatures: Signatures for each input. Must be in the same order as `inputs`. Filled
                      by :func:`sign`.
    :vartype signatures: List[bytes]
    :ivar iv: The IV is used to differentiate block reward transactions.  These have no inputs and
              therefore would otherwise hash to the same value, when the target is identical.
              Reuse of IVs leads to inaccessible coins.
    :vartype iv: bytes
    """

    def __init__(self, inputs: 'List[TransactionInput]', targets: 'List[TransactionTarget]',
                 signatures: 'List[bytes]'=None, iv: bytes=None):
        self.inputs = inputs
        self.targets = targets
        self.signatures = signatures or []
        self.iv = iv
        self._hash = None

    def to_json_compatible(self):
        """ Returns a JSON-serializable representation of this object. """
        val = {}
        val['inputs'] = []
        for inp in self.inputs:
            val['inputs'].append(inp.to_json_compatible())
        val['targets'] = []
        for targ in self.targets:
            val['targets'].append({
                'recipient_pk': targ.recipient_pk.to_json_compatible(),
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
        """ Creates a new object of this class, from a JSON-serializable representation. """
        inputs = []
        for inp in obj['inputs']:
            inputs.append(TransactionInput.from_json_compatible(inp))
        targets = []
        for targ in obj['targets']:
            if targ['amount'] <= 0:
                raise ValueError("invalid amount")
            targets.append(TransactionTarget(Signing.from_json_compatible(targ['recipient_pk']),
                                             int(targ['amount'])))
        signatures = []
        for sig in obj['signatures']:
            signatures.append(unhexlify(sig))

        iv = unhexlify(obj['iv']) if 'iv' in obj else None
        return cls(inputs, targets, signatures, iv)


    def get_hash(self) -> bytes:
        """ Hash this transaction. Returns raw bytes. """
        if self._hash is None:
            h = get_hasher()
            if self.iv is not None:
                h.update(self.iv)

            h.update(Block._int_to_bytes(len(self.targets)))
            for target in self.targets:
                h.update(Block._int_to_bytes(target.amount))
                h.update(target.recipient_pk.as_bytes())

            h.update(Block._int_to_bytes(len(self.inputs)))
            for inp in self.inputs:
                h.update(inp.transaction_hash)
                h.update(Block._int_to_bytes(inp.output_idx))

            self._hash = h.digest()
        return self._hash

    def sign(self, private_keys: 'List[Signing]'):
        """
        Sign this transaction with the given private keys. The private keys need
        to be in the same order as the inputs.
        """
        for private_key in private_keys:
            self.signatures.append(private_key.sign(self.get_hash()))

    def _verify_signatures(self, chain: 'Blockchain'):
        """ Verifies that all inputs are signed and the signatures are valid. """
        if len(self.signatures) != len(self.inputs):
            logging.warning("wrong number of signatures")
            return False

        for (s, i) in zip(self.signatures, self.inputs):
            if not self._verify_single_sig(s, i, chain):
                return False
        return True

    def _verify_single_sig(self, sig: bytes, inp: TransactionInput, chain: 'Blockchain') -> bool:
        """ Verifies the signature on a single input. """
        outp = chain.unspent_coins.get(inp)
        if outp is None:
            logging.warning("Referenced transaction input could not be found.")
            return False
        if not outp.recipient_pk.verify_sign(self.get_hash(), sig):
            logging.warning("Transaction signature does not verify.")
            return False
        return True

    def _verify_single_spend(self, chain: 'Blockchain', other_trans: set) -> bool:
        """ Verifies that all inputs have not been spent yet. """
        inp_set = set(self.inputs)
        if len(self.inputs) != len(inp_set):
            logging.warning("Transaction may not spend the same coin twice.")
            return False
        other_inputs = {i for t in other_trans for i in t.inputs}
        if other_inputs.intersection(inp_set):
            logging.warning("Transaction may not spend the same coin as another transaction in the"
                            " same block.")
            return False

        if any(i not in chain.unspent_coins for i in self.inputs):
            logging.debug("Transaction refers to a coin that was already spent.")
            return False
        return True

    def get_transaction_fee(self, chain: 'Blockchain'):
        """ Computes the transaction fees this transaction provides. """
        if not self.inputs:
            return 0 # block reward transaction pays no fees

        input_amount = sum(chain.unspent_coins[inp].amount for inp in self.inputs)
        output_amount = sum(outp.amount for outp in self.targets)
        return input_amount - output_amount

    def _verify_amounts(self, chain: 'Blockchain') -> bool:
        """
        Verifies that transaction fees are non-negative and output amounts are positive.
        """
        if self.get_transaction_fee(chain) < 0:
            logging.warning("Transferred amounts are larger than the inputs.")
            return False
        if any(outp.amount <= 0 for outp in self.targets):
            logging.warning("Transferred amounts must be positive.")
            return False
        return True

    def verify(self, chain: 'Blockchain', other_trans: 'Set[Transaction]') -> bool:
        """ Verifies that this transaction is completely valid. """
        return self._verify_single_spend(chain, other_trans) and \
               self._verify_signatures(chain) and self._verify_amounts(chain)

from .blockchain import Blockchain
from .block import Block
