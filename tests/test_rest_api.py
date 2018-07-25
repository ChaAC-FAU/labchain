from datetime import datetime


from src.protocol import Protocol
from src.chainbuilder import ChainBuilder
from src.rpc_server import rpc_server
from _thread import start_new_thread
from tests.utils import *
from src.rpc_server import shutdown_server
from tests.test_verifications import block_test

from Crypto.PublicKey import RSA

import requests

sess = requests.Session()
host = "http://localhost:{}/"
port = 2345

NUMBER_FIELDS_IN_BLOCK = 9

def start_server(chain):
    """builds a chainbuilder from a Blockchain, appends and starts a rpc server"""
    proto = Protocol([], GENESIS_BLOCK, 1337)
    chainbuilder = ChainBuilder(proto)

    chainbuilder.primary_block_chain = chain

    return start_new_thread(rpc_server, (port, chainbuilder, None))

def rpc_test(count):
    """starts the rpc server, runs a test and stopps the server"""
    def decorator(fn):
        @block_test()
        def wrapper(gen_chain):
            chain = gen_chain
            key = Key.generate_private_key()
            for i in range(count):
                reward_trans = Transaction([], [TransactionTarget(key, chain.compute_blockreward_next_block())], datetime.now())
                chain = extend_blockchain(chain, [reward_trans])
            start_server(chain)
            fn(chain)
            res = sess.get(host.format(port) + 'shutdown')
            assert res.text == 'Server shutting down...'
        return wrapper
    return decorator


def get_path(path):
    """endpoint link"""
    res = sess.get(host.format(port) + path)
    assert (res.status_code == 200), "Could not reach endpoint " + path
    return res

def get_explorer(path):
    """adds path to explorer"""
    return get_path("explorer/"+path)

def get_statistics(path):
    """adds statistics to path"""
    return get_explorer("statistics/"+path)

@rpc_test(10)
def test_explorer_availability(chain):
    """explorer check for addresses, transcactions, blocks, lasttransactions, lastblocks, blockat"""
    get_explorer('addresses')
    get_explorer('transactions')
    get_explorer('blocks')

    get_explorer('lasttransactions/10')
    get_explorer('lastblocks/10')
    get_explorer('blockat/10')

@rpc_test(10)
def test_statistics_availability(chain):
    """statistics check for hashrate, tps, totalblocks, difficulty, blocktime"""
    get_statistics('hashrate')
    get_statistics('tps')
    get_statistics('totalblocks')
    get_statistics('difficulty')
    get_statistics('blocktime')
    

  

def check_address_data(address):
    """check for sender and receiver"""
    assert 'received' in address, "response object does not contain a received"
    assert 'sent' in address, "response object does not contain a sent"



@rpc_test(1)
def test_address_data(chain):
    """gets the first address and checks the closer information"""
    hash = get_explorer("addresses").json()[0]
    res = get_explorer("sortedtransactions/" + hash)

    res_json = res.json()

    check_address_data(res_json)

    
def checkblock_data(block):
    """blockcheck for nonce, id, difficulty, height, prev_block_hash, transactions, time, merkle_root_hash, hash"""
    assert len(block) == NUMBER_FIELDS_IN_BLOCK, "Wrong number of Fields in response object"
    assert 'nonce' in block, "response object does not contain a nonce"
    assert 'id' in block, "response object does not contain a id"
    assert 'difficulty' in block, "response object does not contain a difficulty"
    assert 'height' in block, "response object does not contain a height"
    assert 'prev_block_hash' in block, "response object does not contain a prev_block_hash"
    assert 'transactions' in block, "response object does not contain a transactions"
    assert 'time' in block, "response object does not contain a time"
    assert 'merkle_root_hash' in block, "response object does not contain a merkle_root_hash"
    assert 'hash' in block, "response object does not contain a hash"


@rpc_test(1)
def test_lastblocks_block_data(chain):
    """checks the blockdata"""
    res = get_explorer('lastblocks/10')

    res_json = res.json()
    assert len(res_json) == 2, "Incorrect count of Blocks"

    block = res_json[0]
    checkblock_data(block)



@rpc_test(1)
def test_transactions_data(chain):
    """check in transaction for hash, block_id, targets, timestamp, number_confirmations, block_hash, signatures, inputs"""
    res = sess.get(host.format(port) + 'explorer/transactions')
    assert (res.status_code == 200)

    res_json = res.json()
    assert len(res_json) == 1, "Incorrect count of transactions"

    transaction = res_json[0]
    assert len(transaction) == 8, "Wrong number of Fields in resonse object"

    assert 'hash' in transaction, "response object does not contain a hash"
    assert 'block_id' in transaction, "response object does not contain a block_id"
    assert 'targets' in transaction, "response object does not contain targets"
    assert 'timestamp' in transaction, "response object does not contain a timestamp"
    assert 'number_confirmations' in transaction, "response object does not contain a number_confirmations"
    assert 'block_hash' in transaction, "response object does not contain a block_hash"
    assert 'signatures' in transaction, "response object does not contain signatures"
    assert 'inputs' in transaction, "response object does not contain inputs"

    assert len(transaction["inputs"]) == len(transaction["signatures"]), "Difference in amount of signatures and inputs"



def check_data_count(subpath):
    """checks the correctness of the count from the subpath"""
    @rpc_test(10)
    def inner(chain):
        path = "explorer/"+subpath
        url = host.format(port) + path + "/" +str(5)
        res = sess.get(url)
        assert (res.status_code == 200), url

        res_json = res.json()
        assert len(res_json) == 5, "Incorrect count of " + subpath

        url = host.format(port) + path + "/" + str(20)
        res = sess.get(url)
        assert (res.status_code == 200), url

        res_json = res.json()
        if(subpath == "lastblocks"):
            assert len(res_json) == 11, "Incorrect count of " + subpath
        if(subpath == "lasttransactions"):
            assert len(res_json) == 10, "Incorrect count of " + subpath
    inner()

def test_blocks_count():
    check_data_count("lastblocks")

def test_transactions_count():
    check_data_count("lasttransactions")



