.. blockchain documentation master file, created by
   sphinx-quickstart on Mon Mar  6 15:54:51 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to blockchain's documentation!
======================================


Executables
***********

.. list-table::
    :stub-columns: 1
    :widths: 10 90

    * - miner
      - .. automodule:: miner
    * - wallet
      - .. automodule:: wallet


Source Code Documentation
*************************

.. autosummary::
    :toctree: _autosummary

    src.blockchain
    src.block
    src.chainbuilder
    src.crypto
    src.merkle
    src.mining
    src.mining_strategy
    src.proof_of_work
    src.protocol
    src.transaction
    src.persistence

Tests
*****
To run the tests, just run the `pytest` command.


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

