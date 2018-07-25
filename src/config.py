from datetime import timedelta

GENESIS_REWARD = 1000
""" The reward that is available for the first `REWARD_HALF_LIFE` blocks, starting with the genesis block. """

REWARD_HALF_LIFE = 10000
""" The number of blocks until the block reward is halved. """

BLOCK_REQUEST_RETRY_INTERVAL = timedelta(minutes=1)
""" The approximate interval after which a block request will be retried. """
BLOCK_REQUEST_RETRY_COUNT = 3
""" The number of failed requests of a block until we give up and delete the depending partial chains. """

GENESIS_DIFFICULTY = (1 << 256) - 1
"""
The difficulty of the genesis block.

It is directly used for comparison with the hash and thus we start with the smallest possible difficulty which is the maximal possible hash value.
Thus, everything bellow is a valid proof of work
"""

DIFFICULTY_BLOCK_INTERVAL = 5
""" The number of blocks between difficulty changes. """
DIFFICULTY_TARGET_TIMEDELTA = timedelta(seconds=60)
""" The time span that it should approximately take to mine `DIFFICULTY_BLOCK_INTERVAL` blocks.  """

