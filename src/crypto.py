""" Generic functions for the cryptographic primitives used in this project. """

import os
import os.path
import tempfile
import random
import string
from binascii import hexlify, unhexlify
from typing import Iterator, Iterable

from Crypto.Signature import PKCS1_PSS
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA

# TODO upgrade to ecdsa at https://pypi.org/project/fastecdsa/

__all__ = ['get_hasher', 'Key']


def get_hasher():
    """ Returns a object that you can use for hashing, compatible to the `hashlib` interface. """
    return SHA256.new()


def get_random_int(length: int) -> int:
    rnd = random.SystemRandom()
    return rnd.randint(0, (2 ** length) - 1)


class Key:
    """
    Functionality for creating and verifying signatures, and their public/private keys.

    :param byte_repr: The bytes serialization of a public key.
    """

    def __init__(self, byte_repr: bytes):
        self.rsa = RSA.importKey(byte_repr)

    def verify_sign(self, hashed_value: bytes, signature: bytes) -> bool:
        """ Verify a signature for an already hashed value and a public key. """
        ver = PKCS1_PSS.new(self.rsa)
        h = get_hasher()
        h.update(hashed_value)
        return ver.verify(h, signature)

    def sign(self, hashed_value: bytes) -> bytes:
        """ Sign a hashed value with this private key. """
        signer = PKCS1_PSS.new(self.rsa)
        h = get_hasher()
        h.update(hashed_value)
        return signer.sign(h)

    @classmethod
    def generate_private_key(cls):
        """ Generate a new private key. """
        return Key(RSA.generate(1024).exportKey())

    @classmethod
    def from_file(cls, path):
        """ Reads a private or public key from the file at `path`. """
        with open(path, 'rb') as f:
            return cls(f.read())

    def as_bytes(self, include_priv: bool = False) -> bytes:
        """ Serialize this key to a `bytes` value. """
        if include_priv:
            return self.rsa.exportKey()
        else:
            return self.rsa.publickey().exportKey()

    def to_json_compatible(self):
        """ Returns a JSON-serializable representation of this object. """
        return hexlify(self.as_bytes()).decode()

    @classmethod
    def from_json_compatible(cls, obj):
        """ Creates a new object of this class, from a JSON-serializable representation. """
        return cls(unhexlify(obj))

    def __eq__(self, other: 'Key'):
        if not other:
            return False
        else:
            return self.rsa.e == other.rsa.e and self.rsa.n == other.rsa.n

    def __hash__(self):
        return hash((self.rsa.e, self.rsa.n))

    @property
    def has_private(self) -> bool:
        """
        Returns a bool value indicating whether this instance has a private key that can be used to
        sign things.
        """
        return self.rsa.has_private()

    @classmethod
    def read_many_private(cls, file_contents: bytes) -> 'Iterator[Key]':
        """ Reads many private keys from the (binary) contents of a file written with `write_many_private`. """
        end = b"-----END RSA PRIVATE KEY-----"
        for key in file_contents.strip().split(end):
            if not key:
                continue

            key = key.lstrip() + end
            yield cls(key)

    @staticmethod
    def write_many_private(path: str, keys: 'Iterable[Key]'):
        """ Writes the private keys in `keys` to the file at `path`. """
        dirname = os.path.dirname(path) or "."
        with tempfile.NamedTemporaryFile("wb", delete=False, dir=dirname) as fp:
            try:
                for key in keys:
                    fp.write(key.as_bytes(include_priv=True) + b"\n")

                fp.flush()
                os.fsync(fp.fileno())

                os.rename(fp.name, path)
            except Exception as e:
                os.unlink(fp.name)
                raise e

        fd = os.open(dirname, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
