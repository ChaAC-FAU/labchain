""" The RPC functionality the miner provides for the wallet and the blockchain explorer.
All REST-API calls are defined here. """

import binascii
import json
import time
from binascii import hexlify
from datetime import datetime
from sys import maxsize

import flask
from flask_api import status

from .chainbuilder import ChainBuilder
from .crypto import Key
from .persistence import Persistence
from .config import DIFFICULTY_BLOCK_INTERVAL
from .transaction import TransactionInput

time_format = "%d.%m.%Y %H:%M:%S"  # Defines the format string of timestamps in local time.
app = flask.Flask(__name__)
cb = None
pers = None
QUERY_PARAMETER_LIMIT = maxsize


def datetime_from_utc_to_local(utc_datetime):
    """ Converts UTC timestamp to local timezone. """
    now_timestamp = time.time()
    offset = datetime.fromtimestamp(now_timestamp) - datetime.utcfromtimestamp(now_timestamp)
    return utc_datetime + offset


def rpc_server(port: int, chainbuilder: ChainBuilder, persist: Persistence):
    """ Runs the RPC server (forever). """
    global cb
    cb = chainbuilder
    global pers
    pers = persist

    app.run(port=port)


@app.route("/network-info", methods=['GET'])
def get_network_info():
    """ Returns the connected peers.
    Route: `\"/network-info\"`.
    HTTP Method: `'GET'`
    """
    return json.dumps([list(peer.peer_addr)[:2] for peer in cb.protocol.peers if peer.is_connected])


@app.route("/new-transaction", methods=['PUT'])
def send_transaction():
    """
    Sends a transaction to the network, and uses it for mining.
    Route: `\"/new-transaction\"`.
    HTTP Method: `'PUT'`
    """
    cb.protocol.received("transaction", flask.request.json, None, 0)
    return b""


@app.route("/show-balance", methods=['POST'])
def show_balance():
    """
    Returns the balance of a number of public keys.
    Route: `\"/show-balance\"`.
    HTTP Method: `'POST'`
    """
    pubkeys = {Key.from_json_compatible(pk): i for (i, pk) in enumerate(flask.request.json)}
    amounts = [0 for _ in pubkeys.values()]
    for output in cb.primary_block_chain.unspent_coins.values():
        if output.get_pubkey in pubkeys:
            amounts[pubkeys[output.get_pubkey]] += output.amount

    return json.dumps(amounts)


@app.route("/build-transaction", methods=['POST'])
def build_transaction():
    """
    Returns the transaction inputs that can be used to build a transaction with a certain
    amount from some public keys.
    Route: `\"/build-transaction\"`.
    HTTP Method: `'POST'`
    """
    sender_pks = {
        Key.from_json_compatible(o): i
        for i, o in enumerate(flask.request.json['sender-pubkeys'])
    }
    amount = flask.request.json['amount']

    # TODO maybe give preference to the coins that are already unlocked  when creating a transaction!

    inputs = []
    used_keys = []
    for (inp, output) in cb.primary_block_chain.unspent_coins.items():
        if (output.get_pubkey in sender_pks) and (
        not output.is_locked):  # here we check is the amount is not locked before creating a Tx
            amount -= output.amount
            temp_input = TransactionInput(inp[0], inp[1], "empty sig_script")
            inputs.append(temp_input.to_json_compatible())
            used_keys.append(sender_pks[output.get_pubkey])
            if amount <= 0:
                break

    if amount > 0:
        inputs = []
        used_keys = []

    return json.dumps({
        "inputs": inputs,
        "remaining_amount": -amount,
        "key_indices": used_keys,
    })


@app.route("/transactions", methods=['POST'])
def get_transactions_for_key():
    """
    Returns all transactions involving a certain public key.
    Route: `\"/transactions\"`.
    HTTP Method: `'POST'`
    """
    key = Key(flask.request.data)
    transactions = set()
    outputs = set()
    chain = cb.primary_block_chain
    for b in chain.blocks:
        for t in b.transactions:
            for i, target in enumerate(t.targets):
                if target.get_pubkey == key:
                    transactions.add(t)
                    outputs.add((t.get_hash(), i))

    for b in chain.blocks:
        for t in b.transactions:
            for inp in t.inputs:
                if (inp.transaction_hash, inp.output_idx) in outputs:
                    transactions.add(t)

    return json.dumps([t.to_json_compatible() for t in transactions])


@app.route("/explorer/sortedtransactions/<string:key>", methods=['GET'])
def get_sorted_transactions_for_key(key):
    """
    Returns all transactions involving a certain public key.
    Route: `\"/explorer/sortedtransactions/<string:key>\"`.
    HTTP Method: `'GET'`
    """
    key = Key(binascii.unhexlify(key))
    all_transactions = {}
    received_transactions = []
    sent_transactions = []

    outputs = set()
    chain = cb.primary_block_chain
    for b in chain.blocks:
        for t in b.transactions:
            for i, target in enumerate(t.targets):
                if target.get_pubkey == key:
                    received_transactions.append(t.to_json_compatible())
                    outputs.add((t.get_hash(), i))

    for b in chain.blocks:
        for t in b.transactions:
            for inp in t.inputs:
                if (inp.transaction_hash, inp.output_idx) in outputs:
                    sent_transactions.append(t.to_json_compatible())

    for t in sent_transactions:
        t['timestamp'] = datetime_from_utc_to_local(datetime.strptime(t['timestamp'],
                                                                      "%Y-%m-%dT%H:%M:%S.%f UTC")).strftime(
            time_format)

    for t in received_transactions:
        t['timestamp'] = datetime_from_utc_to_local(datetime.strptime(t['timestamp'],
                                                                      "%Y-%m-%dT%H:%M:%S.%f UTC")).strftime(
            time_format)

    all_transactions["sent"] = sent_transactions
    all_transactions["received"] = received_transactions

    return json.dumps(all_transactions)


@app.route("/explorer/addresses", methods=['GET'])
def get_addresses():
    """
    Returns all addresses in the blockchain.
    Route: `\"/explorer/addresses\"`.
    HTTP Method: `'GET'`
    """
    addresses = set()
    chain = cb.primary_block_chain
    for b in chain.blocks:
        for t in b.transactions:
            for i, target in enumerate(t.targets):
                addresses.add(hexlify(target.get_pubkey.as_bytes()).decode())
    if len(addresses) != 0:
        return json.dumps([a for a in addresses])

    return json.dumps("Resource not found."), status.HTTP_404_NOT_FOUND


@app.route("/explorer/show-balance", methods=['POST'])
def show_single_balance():
    """
    Returns the balance of a public key.
    Route: `\"/explorer/show-balance\"`
    HTTP Method: `'POST'`
    """
    key = Key(flask.request.data)
    amount = 0
    for output in cb.primary_block_chain.unspent_coins.values():
        if output.get_pubkey == key:
            amount += output.amount
    result = {"credit": amount}

    return json.dumps(result)


@app.route("/explorer/lasttransactions/<int:amount>", methods=['GET'])
def get_last_transactions(amount):
    """
    Returns last transactions. Number is specified in `amount`.
    Route: `\"/explorer/lasttransactions/<int:amount>\"`
    HTTP Method: `'GET'`
    """
    last_transactions = []
    counter = 0

    unconfirmed_tx = cb.unconfirmed_transactions

    for (key, value) in unconfirmed_tx.items():
        if counter < amount:
            val = value.to_json_compatible()
            val['block_id'] = "Pending.."
            val['block_hash'] = ""
            val['number_confirmations'] = 0
            val['timestamp'] = datetime_from_utc_to_local(datetime.strptime(val['timestamp'],
                                                                            "%Y-%m-%dT%H:%M:%S.%f UTC")).strftime(
                time_format)
            last_transactions.append(val)
            counter += 1
        else:
            break

    last_confirmed_transactions = []
    chain = cb.primary_block_chain
    for b in reversed(chain.blocks):
        if not counter < amount:
            break
        for t in reversed(b.transactions):
            if counter < amount:
                trans = t.to_json_compatible()
                block = b.to_json_compatible()
                trans['block_id'] = block['id']
                trans['block_hash'] = block['hash']
                trans['number_confirmations'] = chain.head.id - int(block['id'])
                trans['timestamp'] = datetime_from_utc_to_local(datetime.strptime(trans['timestamp'],
                                                                                  "%Y-%m-%dT%H:%M:%S.%f UTC")).strftime(
                    time_format)

                last_confirmed_transactions.append(trans)
                counter += 1
            else:
                break

    last_transactions.extend(last_confirmed_transactions)
    return json.dumps(last_transactions)


@app.route("/explorer/transactions", methods=['GET'])
def get_transactions():
    """
    Returns all transactions.
    Route: `\"/explorer/transactions\"`
    HTTP Method: `'GET'`
    """
    transactions = []
    chain = cb.primary_block_chain
    for b in reversed(chain.blocks):
        for t in reversed(b.transactions):
            trans = t.to_json_compatible()
            block = b.to_json_compatible()
            trans['block_id'] = block['id']
            trans['block_hash'] = block['hash']
            trans['number_confirmations'] = chain.head.id - int(block['id'])
            transactions.append(trans)
    for t in transactions:
        t['timestamp'] = datetime_from_utc_to_local(datetime.strptime(t['timestamp'],
                                                                      "%Y-%m-%dT%H:%M:%S.%f UTC")).strftime(
            time_format)
    return json.dumps(transactions)


@app.route("/explorer/transaction/<string:hash>", methods=['GET'])
def get_transaction_from_hash(hash):
    """
    Returns a transaction with specified hash.
    Route: `\"/explorer/transaction/<string:hash>\"`
    HTTP Method: `'GET'`
    """
    chain = cb.primary_block_chain
    for b in chain.blocks:
        for t in b.transactions:
            if hexlify(t.get_hash()).decode() == hash:
                trans = t.to_json_compatible()
                block = b.to_json_compatible()
                trans['block_id'] = block['id']
                trans['block_hash'] = block['hash']
                trans['number_confirmations'] = chain.head.id - int(block['id'])
                trans['timestamp'] = datetime_from_utc_to_local(datetime.strptime(trans['timestamp'],
                                                                                  "%Y-%m-%dT%H:%M:%S.%f UTC")).strftime(
                    time_format)
                trans['fee'] = t.get_past_transaction_fee(chain)
                return json.dumps(trans)

    unconfirmed_tx = cb.unconfirmed_transactions
    for (key, value) in unconfirmed_tx.items():
        if hexlify(key).decode() == hash:
            trans = value.to_json_compatible()
            trans['block_id'] = ""
            trans['block_hash'] = "Pending..."
            trans['timestamp'] = datetime_from_utc_to_local(datetime.strptime(trans['timestamp'],
                                                                              "%Y-%m-%dT%H:%M:%S.%f UTC")).strftime(
                time_format)
            trans['fee'] = t.get_past_transaction_fee(chain)
            return json.dumps(trans)

    return json.dumps("Resource not found."), status.HTTP_404_NOT_FOUND


@app.route("/explorer/blocks", methods=['GET'])
def get_blocks():
    """
    Returns all blocks in the blockchain.
    Route: `\"/explorer/blocks\"`
    HTTP Method: `'GET'`
    """
    chain = cb.primary_block_chain
    result = []
    for o in reversed(chain.blocks):
        block = o.to_json_compatible()
        block['time'] = datetime_from_utc_to_local(datetime.strptime(block['time'],
                                                                     "%Y-%m-%dT%H:%M:%S.%f UTC")).strftime(
            time_format)
        result.append(block)
    return json.dumps(result)


@app.route("/explorer/lastblocks/<int:amount>", methods=['GET'])
def get_blocks_amount(amount):
    """
    Returns the latest number of blocks in the blockchain.
    Route: `\"/explorer/lastblocks/<int:amount>\"`
    HTTP Method: `'GET'`
    """
    result = []
    chain = cb.primary_block_chain
    counter = 0
    for b in reversed(chain.blocks):
        block = b.to_json_compatible()
        block['time'] = datetime_from_utc_to_local(datetime.strptime(block['time'],
                                                                     "%Y-%m-%dT%H:%M:%S.%f UTC")).strftime(
            time_format)
        result.append(block)
        counter += 1
        if counter >= amount:
            break
    return json.dumps(result)


@app.route("/explorer/blockat/<int:at>", methods=['GET'])
def get_block_at(at):
    """
    Returns block at postion from zero in the blockchain.
    Route: `\"/explorer/blockat/<int:at>\"`
    HTTP Method: `'GET'`
    """
    chain = cb.primary_block_chain
    result = chain.blocks[at].to_json_compatible()

    result['time'] = datetime_from_utc_to_local(datetime.strptime(result['time'],
                                                                  "%Y-%m-%dT%H:%M:%S.%f UTC")).strftime(
        time_format)

    return json.dumps(result)


@app.route("/explorer/block/<string:hash>", methods=['GET'])
def get_blocks_hash(hash):
    """
    Returns block with given hash from the blockchain.
    Route: `\"/explorer/block/<string:hash>\"`
    HTTP Method: `'GET'`
    """
    chain = cb.primary_block_chain
    for b in chain.blocks:
        if hexlify(b.hash).decode() == hash:
            block = b.to_json_compatible()
            block['time'] = datetime_from_utc_to_local(datetime.strptime(block['time'],
                                                                         "%Y-%m-%dT%H:%M:%S.%f UTC")).strftime(
                time_format)
            return json.dumps(block)

    return json.dumps("Resource not found."), status.HTTP_404_NOT_FOUND


@app.route("/explorer/statistics/hashrate", methods=['GET'])
def get_hashrate():
    """
    Returns the total amount of blocks.
    Route: `\"/explorer/statistics/hashrate\"`
    HTTP Method: `'GET'`
    """
    parameter = flask.request.args.get('length')
    if (parameter != None and isinstance(parameter, int)) and parameter > 0 and parameter < QUERY_PARAMETER_LIMIT:
        user_input_length = parameter
    else:
        user_input_length = DIFFICULTY_BLOCK_INTERVAL
    chain = cb.primary_block_chain

    if chain.head.id <= user_input_length:
        if (len(chain.blocks)) <= 2:
            return json.dumps(0)
        user_input_length = len(chain.blocks) - 1

    block_hashrate = []

    for i in range(user_input_length):
        first_block = chain.blocks[-i - 1]
        second_block = chain.blocks[-i - 2]
        first_time = first_block.time
        second_time = second_block.time
        difficulty = first_block.difficulty
        time_difference = abs((first_time - second_time).seconds)
        if time_difference == 0:
            time_difference = 1
        hashrate = (difficulty / time_difference)
        block_hashrate.append(hashrate)

    block_hashrate_sum = 0
    for i in block_hashrate:
        block_hashrate_sum += i

    block_hashrate_avg = block_hashrate_sum / len(block_hashrate)

    if block_hashrate_avg >= 1000000000:
        return json.dumps("%.1f" % (block_hashrate_avg / 1000000000) + " Gh/s")
    if block_hashrate_avg >= 1000000:
        return json.dumps("%.1f" % (block_hashrate_avg / 1000000) + " Mh/s")
    if block_hashrate_avg >= 1000:
        return json.dumps("%.1f" % (block_hashrate_avg / 1000) + " Kh/s")

    return json.dumps("%.2f" % block_hashrate_avg)  # Returns float formatted with only 2 decimals


@app.route("/explorer/statistics/tps", methods=['GET'])
def get_tps():
    """
    Returns the average transaction rate over the last <length>- query parameter blocks.
    Route: `\"/explorer/statistics/tps\"`
    HTTP Method: `'GET'`
    """
    parameter = flask.request.args.get('length')
    if (parameter != None and isinstance(parameter, int)) and parameter > 0 and parameter < QUERY_PARAMETER_LIMIT:
        user_input_length = parameter
    else:
        user_input_length = DIFFICULTY_BLOCK_INTERVAL

    chain = cb.primary_block_chain
    if chain.head.id <= user_input_length:
        # if only genesis block exists, no transacions have been made
        if (len(chain.blocks)) <= 1:
            return json.dumps(0)
        first_block = chain.head
        # use block after genesis block, because genesis block has hard-coded timestamp
        second_block = chain.blocks[1]
        first_time = first_block.time
        second_time = second_block.time
    else:
        first_block = chain.head
        second_block = chain.blocks[- 1 - user_input_length]
        first_time = first_block.time
        second_time = second_block.time

    transactions = 0
    for i in range(user_input_length):
        transactions += len(chain.blocks[-1 - i].transactions)

    time_difference = abs((first_time - second_time).seconds)
    if time_difference == 0:
        time_difference = 1

    tps = transactions / time_difference

    return json.dumps("%.2f" % tps)  # Returns float formatted with only 2 decimals


@app.route("/explorer/statistics/totalblocks", methods=['GET'])
def get_total_blocks():
    """
    Returns the total amount of blocks.
    Route: `\"/explorer/statistics/totalblocks\"`
    HTTP Method: `'GET'`
    """
    chain = cb.primary_block_chain
    total_blocks = len(chain.blocks)

    return json.dumps(total_blocks)


@app.route("/explorer/statistics/difficulty", methods=['GET'])
def get_difficulty():
    """
    Returns the current difficulty.
    Route: `\"/explorer/statistics/difficulty\"`
    HTTP Method: `'GET'`
    """
    chain = cb.primary_block_chain
    current_difficulty = chain.head.difficulty

    return json.dumps(current_difficulty)


@app.route("/explorer/statistics/blocktime", methods=['GET'])
def get_blocktime():
    """
    Returns the average time between two blocks.
    Route: `\"/explorer/statistics/blocktime\"`
    HTTP Method: `'GET'`
    """
    chain = cb.primary_block_chain
    current_block = chain.head

    if len(chain.blocks) < 2:
        return json.dumps(0)

    second_block = chain.blocks[1]

    current_timestamp = current_block.time
    second_timestamp = second_block.time
    time_difference = abs((current_timestamp - second_timestamp).seconds)
    total_blocks = int(get_total_blocks()) - 1

    blocktime = time_difference / total_blocks

    return json.dumps("%.2f" % blocktime)  # Returns float formatted with only 2 decimals


@app.route('/shutdown', methods=['POST', 'GET'])
def shutdown():
    """
    Shuts down the RPC-Server.
    Route: `\"/shutdown\"`
    HTTP Method: `'GET'/'POST'`
    """
    shutdown_server()
    return 'Server shutting down...'


def shutdown_server():
    """
    Shuts down flask. Needed for pytests.
    """
    func = flask.request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
