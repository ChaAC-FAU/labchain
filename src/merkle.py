""" Functionality for creating a Merkle tree. """

import json
from binascii import hexlify
from itertools import zip_longest

from treelib import Node, Tree

from .crypto import get_hasher

__all__ = ['merkle_tree', 'MerkleNode']

class MerkleNode:
    """
    A hash tree node, pointing to a leaf value or another node.

    :ivar v1: The first child of this node.
    :ivar v2: The second child of this node.
    """

    def __init__(self, v1, v2):
        self.v1 = v1
        self.v1_hash = b'' if v1 is None else v1.get_hash()
        self.v2 = v2
        self.v2_hash = b'' if v2 is None else v2.get_hash()

    def get_hash(self) -> bytes:
        """ Compute the hash of this node. """
        hasher = get_hasher()
        hasher.update(self.v1_hash)
        hasher.update(self.v2_hash)
        return hasher.digest()

    def _get_tree(self, tree, parent):
        """ Recursively build a treelib tree for nice pretty printing. """
        tree.create_node(hexlify(self.get_hash())[:36].decode() + "...", self, parent)
        if isinstance(self.v1, MerkleNode):
            self.v1._get_tree(tree, self)
        elif self.v1 is not None:
            tree.create_node(str(self.v1), str(self.v1), self)
        if isinstance(self.v2, MerkleNode):
            self.v2._get_tree(tree, self)
        elif self.v2 is not None:
            tree.create_node(str(self.v2), str(self.v2), self)

    def __str__(self):
        tree = Tree()
        self._get_tree(tree, None)
        return str(tree)

def merkle_tree(values: list) -> MerkleNode:
    """
    Constructs a Merkle tree from a list of values.

    All `values` need to support a method `get_hash()`.
    """

    if not values:
        return MerkleNode(None, None)

    while len(values) > 1:
        nodes = []
        for (v1, v2) in zip_longest(values[0::2], values[1::2]):
            nodes.append(MerkleNode(v1, v2))

        values = nodes

    return values[0]
