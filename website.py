#!/usr/bin/env python3

"""
The website starts the blockchain explorer, reachable as default under `localhost:80`. The blockchain explorer launches
its own non-mining miner to get access to the blockchain.
"""

import argparse
import requests
import binascii
import miner
from flask import Flask, render_template
from _thread import start_new_thread
from flask import abort

app = Flask(__name__)
sess = requests.Session()
host = "http://localhost:{}/"
url = ""
QUERY_PARAMETER_AVERAGE_LENGTH = 10


def main():
    """
    Takes arguments: `rpc-port`: The port number where the Blockchain Explorer can find an RPC server. Default is: `40203`
    `bootstrap-peer`: Address of other P2P peers in the network. If not supplied, no non-mining miner will be started.
    `listen-address`: The IP address where the P2P server should bind to. `listen-port`: The port where the P2P server should listen.
    Defaults a dynamically assigned port.
    """
    parser = argparse.ArgumentParser(description="Blockchain Explorer.")
    parser.add_argument("--rpc-port", type=int, default=40203,
                        help="The port number where the Blockchain Explorer can find an RPC server.")
    parser.add_argument("--bootstrap-peer",
                        help="Address of other P2P peers in the network.")
    parser.add_argument("--listen-address", default="",
                        help="The IP address where the P2P server should bind to.")
    parser.add_argument("--listen-port", default=0, type=int,
                        help="The port where the P2P server should listen. Defaults a dynamically assigned port.")

    args = parser.parse_args()

    global url
    url = host.format(args.rpc_port)

    if (args.bootstrap_peer):
        start_new_thread(miner.start_listener, (args.rpc_port, args.bootstrap_peer, args.listen_port, args.listen_address))  # Starts the miner.
        app.run(host='0.0.0.0', port=80)  # Starts the flask server for the blockchain explorer
    else:
        parser.parse_args(["--help"])


def append_sender_to_transaction(transaction):
    """ Reads the transaction inputs for the supplied transaction and adds the senders to the JSON objects. """
    pks = []
    for inp in transaction["inputs"]:
        res = sess.get(url + 'explorer/transaction/' + inp["transaction_hash"])
        output_idx = inp["output_idx"]
        pks.append(res.json()["targets"][output_idx]["recipient_pk"])

    counter = 0
    result = []
    for inp in transaction["inputs"]:
        dict = {"input": inp, "signature": transaction["signatures"][counter]}
        result.append(dict)
        counter += 1

    transaction["inp"] = result
    transaction["senders"] = pks


@app.route("/")
def index():
    """ Index page of the blockchain explorer. Shows statistics, last blocks and last transactions.
        Route: `\"/\"`. """
    data = {}
    data["blocks"] = sess.get(url + 'explorer/lastblocks/10').json()
    data["statistics"] = get_statistics()
    transactions = sess.get(url + 'explorer/lasttransactions/5').json()
    for transaction in transactions:
        append_sender_to_transaction(transaction)
    data["transactions"] = transactions
    return render_template('index.html', data=data)


@app.route("/blocks")
@app.route("/blocks/<int:amount>")
def blocklist(amount=10):
    """ Lists all blocks from the blockchain. Optional takes argument as amount of blocks to just return
     the last amount blocks.
        Route: `\"/blocks/<optional: int:amount>\"`. """
    blocks = sess.get(url + 'explorer/lastblocks/' + str(amount)).json()
    if len(blocks) < amount:
        return render_template('blocklist.html', data=blocks)
    else:
        return render_template('blocklist.html', data=blocks, nextamount=amount * 2)


@app.route("/block/<string:hash>")
def block(hash):
    """ Lists information about the specified block.
    Route: `\"/block/<string:hash>\"`. """
    resp = sess.get(url + 'explorer/block/' + hash)
    if resp.status_code == 404:
        return render_template('not_found.html', data={'type': 'Block', 'hash': hash})
    resp.raise_for_status()
    json_obj = resp.json()

    for transaction in json_obj["transactions"]:
        append_sender_to_transaction(transaction)

    return render_template('block.html', data=json_obj)


@app.route("/addresses/")
def addresses():
    """ Lists all addresses found in the blockchain as sender or receiver of a transaction.
    Route: `\"/addresses\"`. """
    resp = sess.get(url + 'explorer/addresses')
    resp.raise_for_status()

    return render_template('addresses.html', data=resp.json())


def try_get_json(addr):
    try:
        resp = sess.get(url + addr)
    except:
        abort(404)
        # return render_template('not_found.html', data={'type': 'Address', 'hash': addr})

    if resp.status_code == 404:
        abort(404)
        # return render_template('not_found.html', data={'type': 'Address', 'hash': addr})
    resp.raise_for_status()
    json_obj = resp.json()
    return json_obj


@app.route("/address/<string:addr>")
def address(addr):
    """ Lists information about the specified address. """

    json_obj = try_get_json('explorer/sortedtransactions/' + addr)

    for tr in json_obj["sent"]:
        append_sender_to_transaction(tr)

    for tr in json_obj["received"]:
        for target in tr["targets"]:
            if (target["recipient_pk"]) != addr:
                tr["targets"].remove(target)
        append_sender_to_transaction(tr)

    resp_credit = sess.post(url + 'explorer/show-balance', data=binascii.unhexlify(addr),
                            headers={"Content-Type": "application/json"})
    resp_credit.raise_for_status()

    json_obj["credit"] = resp_credit.json()["credit"]
    json_obj["hash"] = addr
    return render_template('address.html', data=json_obj)


@app.route("/transactions")
@app.route("/transactions/<int:amount>")
def transactions(amount=10):
    """ Lists all transactions from the blockchain. Optional takes argument as amount of transactions to just return
     the last amount transactions.
    Route: `\"/transactions/<optional: int:amount>\"`. """
    resp = sess.get(url + 'explorer/lasttransactions/' + str(amount))
    resp.raise_for_status()
    transactions = resp.json()

    for transaction in transactions:
        append_sender_to_transaction(transaction)

    if (len(transactions) < amount):
        return render_template('transactions.html', data_array=transactions)
    else:
        return render_template('transactions.html', data_array=transactions, nextamount=amount * 2)


@app.route("/transaction/<string:hash>")
def transaction(hash):
    """ Lists information about the specified transaction.
    Route: `\"/transaction/<string:hash>\"`. """
    resp = sess.get(url + 'explorer/transaction/' + hash)
    if resp.status_code == 404:
        return render_template('not_found.html', data={'type': 'Transaction', 'hash': hash})

    resp.raise_for_status()

    json_obj = resp.json()

    append_sender_to_transaction(json_obj)

    return render_template('transaction.html', transaction=json_obj)


def get_statistics():
    """ Lists all calculated statistics about the blockchain and its network. """
    resp_blocktime = sess.get(url + 'explorer/statistics/blocktime')
    resp_blocktime.raise_for_status()

    resp_totalblocks = sess.get(url + 'explorer/statistics/totalblocks')
    resp_totalblocks.raise_for_status()

    resp_difficulty = sess.get(url + 'explorer/statistics/target')
    resp_difficulty.raise_for_status()

    resp_hashrate = sess.get(url + 'explorer/statistics/hashrate?length=' + str(QUERY_PARAMETER_AVERAGE_LENGTH))
    resp_hashrate.raise_for_status()

    resp_tps = sess.get(url + 'explorer/statistics/tps?length=' + str(QUERY_PARAMETER_AVERAGE_LENGTH))
    resp_tps.raise_for_status()

    result = {"blocktime": resp_blocktime.json(), "totalblocks": resp_totalblocks.json(),
              "target": resp_difficulty.json(), "hashrate": resp_hashrate.json(), "tps": resp_tps.json()}
    return result


@app.route("/statistics")
def statistics():
    """ Shows all calculated statistics about the blockchain and its network.
    Route: `\"/statistics\"`. """
    return render_template('statistics.html', data=get_statistics())


@app.route("/about")
def about():
    """ Shows the 'About'-Page.
    Route: `\"/about\"`. """
    return render_template('about.html')

if __name__ == '__main__':
    main()
