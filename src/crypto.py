""" Generic functions for the cryptographic primitives used in this project. """

from Crypto.Signature import PKCS1_PSS
from Crypto.Hash import SHA512
from Crypto.PublicKey import RSA

__all__ = ['get_hasher', 'Signing', 'MAX_HASH']

def get_hasher():
    """ Returns a object that you can use for hashing, compatible to the `hashlib` interface. """
    return SHA512.new()


MAX_HASH = (1 << 512) - 1 # the largest possible hash value


class Signing:
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
        return Signing(RSA.generate(3072).exportKey())

    def as_bytes(self, include_priv: bool=False) -> bytes:
        """ Serialize this key to a `bytes` value. """
        if include_priv:
            return self.rsa.exportKey()
        else:
            return self.rsa.publickey().exportKey()

    def __eq__(self, other: 'Signing'):
        # TODO: it's possible that the same key has multiple different representations
        return self.as_bytes() == other.as_bytes()
