""" Cryptographic primitives. """

from Crypto.Signature import PKCS1_v1_5
from Crypto.Hash import SHA512

def get_hasher():
    """ Returns a object that you can use for hashing. Currently SHA512, swap it out for something if you feel like it! """
    return SHA512.new()

MAX_HASH = (1 << 512) - 1

def verify_sign(hashed_value, signature, pub_key):
    """ Verify a signature for a already hashed value and a public key. """
    ver = PKCS1_v1_5.new(pub_key)
    return ver.verify(hashed_value, signature)

def sign(hashed_value, priv_key):
    """ Sign a hashed value with a private key. """
    signer = PKCS1_v1_5.new(priv_key)
    return signer.sign(hashed_value)
