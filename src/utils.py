from struct import pack
from .config import *

import datetime


def int_to_bytes(val: int) -> bytes:
    """ Turns an (arbitrarily long) integer into a bytes sequence. """
    l = val.bit_length() + 1
    # we need to include the length in the hash in some way, otherwise e.g.
    # the numbers (0xffff, 0x00) would be encoded identically to (0xff, 0xff00)
    return pack("<Q", l) + val.to_bytes(l, 'little', signed=True)


def compute_blockreward_next_block(block_num: int) -> int:
    """ Compute the block reward that is expected for the block following this chain's `head`. """
    half_lives = block_num // REWARD_HALF_LIFE
    reward = GENESIS_REWARD // (2 ** half_lives)
    return reward


def compute_lock_time(seconds_to_wait: int) -> datetime:
    return datetime.datetime.utcnow() + datetime.timedelta(seconds=seconds_to_wait)
