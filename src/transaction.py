""" Defines transactions and their inputs and outputs. """

import logging

from datetime import datetime, timezone
from collections import namedtuple
from binascii import hexlify, unhexlify
from typing import List, Optional

import src.utils as utils

from .scriptinterpreter import ScriptInterpreter

from .crypto import get_hasher, Key

__all__ = ['TransactionTarget', 'TransactionInput', 'Transaction']


class TransactionTarget(namedtuple("TransactionTarget", ["pubkey_script", "amount"])):
    """
    The recipient of a transaction ('coin').
    
    :ivar pubkey_script: The output script of a transaction.
    :vartype pubkey_script: string
    :ivar amount: The amount sent.
    :vartype amount: int
    """

    @classmethod
    def from_json_compatible(cls, obj):
        """ Creates a new object of this class, from a JSON-serializable representation. """
        return cls(str(obj['pubkey_script']), int(obj['amount']))

    def to_json_compatible(self):
        """ Returns a JSON-serializable representation of this object. """
        return {
            'pubkey_script': self.pubkey_script,
            'amount': self.amount
        }

    @classmethod
    def burn(self, data:bytes) -> str:
        """ Returns a OP_RETURN script"""
        data = hexlify(data).decode()
        return data + " OP_RETURN"

    @classmethod
    def pay_to_pubkey(self, recipient_pk: Key) -> str:
        """ Returns a standard pay-to-pubkey script """
        keystr = recipient_pk.to_json_compatible()
        return keystr + " OP_CHECKSIG"

    @classmethod
    def pay_to_pubkey_lock(self, recipient_pk: Key, lock_time: datetime) -> str:
        """ Returns a pay-to-pubkey script with a lock-time """
        keystr = recipient_pk.to_json_compatible()
        return str(lock_time.replace(tzinfo=timezone.utc).timestamp()) + " OP_CHECKLOCKTIME " + keystr + " OP_CHECKSIG"

    @property
    def get_pubkey(self) -> Optional[Key]:
        """ Returns the public key of the target for a standard PAY_TO_PUBKEY transaction"""
        if self.is_pay_to_pubkey_lock:
            return Key.from_json_compatible(self.pubkey_script[
                                            self.pubkey_script.find("OP_CHECKLOCKTIME") + 17:self.pubkey_script.find(
                                                "OP_CHECKSIG") - 1])
        elif self.is_pay_to_pubkey:
            return Key.from_json_compatible(self.pubkey_script[:self.pubkey_script.find(" ")])

        return None

    @property
    def is_pay_to_pubkey(self) -> bool:
        op = self.pubkey_script[self.pubkey_script.find(" ") + 1:]
        return op == "OP_CHECKSIG"

    @property
    def is_pay_to_pubkey_lock(self) -> bool:
        # TODO it needs to check if the strings are in the correct position within the script
        # op1 = self.pubkey_script[:self.pubkey_script.find(" "):]
        # op2 = self.pubkey_script[self.pubkey_script.find("OP_CHECKLOCKTIME"):]
        return ("OP_CHECKSIG" in self.pubkey_script) and ("OP_CHECKLOCKTIME" in self.pubkey_script)

    @property
    def has_data(self) -> bool:
        op = self.pubkey_script[self.pubkey_script.find(" ") + 1:]
        return op == "OP_RETURN"

    @property
    def is_locked(self) -> bool:
        if self.is_pay_to_pubkey_lock:
            timestamp = datetime.utcfromtimestamp(float(self.pubkey_script[:self.pubkey_script.find(" ")]))
            return timestamp > datetime.utcnow()
        return False


class TransactionInput(namedtuple("TransactionInput", ["transaction_hash", "output_idx", "sig_script"])):
    """
    One transaction input (pointer to 'coin').

    :ivar transaction_hash: The hash of the transaction that you are trying to spend.
    :vartype transaction_hash: bytes
    :ivar output_idx: The index into `Transaction.targets` of the `transaction_hash`.
    :vartype output_idx: int
    :ivar sig_script: The script redeeming the output point by output_idx of the transaction pointed by transaction_hash
    :vartype sig_script: string
    """

    def collides(self, other):
        if self.transaction_hash == other.transaction_hash:
            return self.output_idx == other.output_idx

    @property
    def is_coinbase(self):
        return self.output_idx == -1

    @classmethod
    def from_json_compatible(cls, obj):
        """ Creates a new object of this class, from a JSON-serializable representation. """
        return cls(unhexlify(obj['transaction_hash']), int(obj['output_idx']), str(obj['sig_script']))

    def to_json_compatible(self):
        """ Returns a JSON-serializable representation of this object. """
        return {
            'transaction_hash': hexlify(self.transaction_hash).decode(),
            'output_idx': self.output_idx,
            'sig_script': self.sig_script
        }


class Transaction:
    """
    A transaction as it was received from the network or a block. To check that this transaction is
    valid on top of a block chain and in combination with a set of different transactions (from the
    same block), you can call the `verify` method.

    :ivar inputs: The inputs of this transaction. Empty in the case of block reward transactions.
    :vartype inputs: List[TransactionInput]
    :ivar targets: The targets of this transaction.
    :vartype targets: List[TransactionTarget]
    :ivar iv: The IV is used to differentiate block reward transactions.  These have no inputs and
              therefore would otherwise hash to the same value, when the target is identical.
              Reuse of IVs leads to inaccessible coins.
    :vartype iv: bytes
    :ivar timestamp: The time when the transaction was created.
    :vartype timestamp: datetime
    """

    def __init__(self, inputs: 'List[TransactionInput]', targets: 'List[TransactionTarget]', timestamp: 'datetime',
                 iv: bytes = None):
        self.inputs = inputs
        self.targets = targets
        self.timestamp = timestamp
        self.iv = iv
        self._hash = None

    def to_json_compatible(self):
        """ Returns a JSON-serializable representation of this object. """
        val = {}
        val['hash'] = hexlify(self.get_hash()).decode()
        val['inputs'] = []
        for inp in self.inputs:
            val['inputs'].append(inp.to_json_compatible())
        val['targets'] = []
        for targ in self.targets:
            val['targets'].append(targ.to_json_compatible())
        val['timestamp'] = self.timestamp.strftime("%Y-%m-%dT%H:%M:%S.%f UTC")
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
            targets.append(TransactionTarget.from_json_compatible(targ))
        timestamp = datetime.strptime(obj['timestamp'], "%Y-%m-%dT%H:%M:%S.%f UTC")
        iv = unhexlify(obj['iv']) if 'iv' in obj else None
        return cls(inputs, targets, timestamp, iv)

    def get_hash(self) -> bytes:
        """ Hash this transaction. Returns raw bytes. """
        if self._hash is None:
            h = get_hasher()
            if self.iv is not None:
                h.update(self.iv)

            h.update(utils.int_to_bytes(len(self.targets)))
            for target in self.targets:
                h.update(utils.int_to_bytes(target.amount))
                h.update(target.pubkey_script.encode())

            h.update(utils.int_to_bytes(len(self.inputs)))
            for inp in self.inputs:
                h.update(inp.transaction_hash)
                h.update(utils.int_to_bytes(inp.output_idx))

            self._hash = h.digest()
        return self._hash

    def sign(self, signing_key: Key):
        return hexlify(signing_key.sign(self.get_hash())).decode()

    def get_transaction_fee(self, unspent_coins: dict):
        """ Computes the transaction fees this transaction provides. """
        if self.inputs[0].is_coinbase:
            return 0  # block reward transaction pays no fees
        try:
            input_amount = sum(unspent_coins[(inp.transaction_hash, inp.output_idx)].amount for inp in self.inputs)
            output_amount = sum(outp.amount for outp in self.targets)
            return input_amount - output_amount
        except:
            logging.warning("Transaction input is not in unspent coins. Transaction is invalid or spent.")
            raise ValueError('Transaction input not found.')

    def _verify_amounts(self) -> bool:
        """
        Verifies that transaction fees are non-negative and output amounts are positive.
        """
        if any(outp.amount < 0 for outp in self.targets):
            return False
        return True

    def validate_tx(self, unspent_coins: dict) -> bool:
        """
        Validate the transaction
        """
        if not (self._verify_amounts()):
            return False

        for inp in self.inputs:
            coinbase = inp.is_coinbase
            if coinbase and len(self.inputs) > 1:
                logging.warning("A coinbase transaction can only have one coinbase.")
                return False
            elif coinbase:
                return True

            if (inp.transaction_hash, inp.output_idx) not in unspent_coins:
                return False  # ("The input is not in the unspent transactions database!")


            script = ScriptInterpreter(inp.sig_script,
                                           unspent_coins[(inp.transaction_hash, inp.output_idx)].pubkey_script,
                                           self.get_hash())

            if not script.execute_script():
                return False

        # ensures that can't spend more coins than there are input coins
        return self.get_transaction_fee(unspent_coins) >= 0



    def check_tx_collision(self, other_tx):
        for tx in other_tx:
            for inp_other in tx.inputs:
                for inp_self in self.inputs:
                    if inp_self.collides(inp_other):
                        return True
        return False
