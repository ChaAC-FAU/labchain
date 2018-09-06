from datetime import timedelta

GENESIS_REWARD = 1000
""" The reward that is available for the first `REWARD_HALF_LIFE` blocks, starting with the genesis block. """

REWARD_HALF_LIFE = 10000
""" The number of blocks until the block reward is halved. """

BLOCK_REQUEST_RETRY_INTERVAL = timedelta(seconds=30)
""" The approximate interval after which a block request will be retried. """
BLOCK_REQUEST_RETRY_COUNT = 3
""" The number of failed requests of a block until we give up and delete the depending partial chains. """

GENESIS_TARGET = (1 << 256) - 1
"""
The target of the genesis block.

It is directly used for comparison with the hash and thus we start with the smallest possible target which is the maximal possible hash value.
Thus, everything bellow is a valid proof of work
"""

DIFFICULTY_BLOCK_INTERVAL = 10
""" The number of blocks between target changes. """

DIFFICULTY_TIMEDELTA = timedelta(seconds=6)
""" The time span that it should approximately take to mine `DIFFICULTY_BLOCK_INTERVAL` blocks.  """
