from src.mining import Miner
import json
from enum import Enum
import socket
from threading import Thread
import logging
from queue import Queue

MAX_PEERS = 10
HELLO_MSG = b"bl0ckch41n"

socket.setdefaulttimeout(30)

Messages = Enum("Messages", "peers getblock block transaction")

class PeerConnection:
    def __init__(self, peer, proto, socket=None):
        self.peer = peer
        self.socket = None
        self.proto = proto
        self.is_connected = False
        self.outgoing_msgs = Queue()
        Thread.start(target=self.run, daemon=True)

    def run(self):
        if self.socket is not None:
            self.socket = socket.create_connection(self.peer)
        self.socket.sendall(HELLO_MSG)
        if self.socket.recv(len(HELLO_MSG)) != HELLO_MSG:
            return
        self.is_connected = True
        Thread.start(target=self.close_on_error, args=(self.reader_thread,))
        self.close_on_error(self.writer_thread)

    def close_on_error(self, cmd):
        try:
            cmd()
        except Exception:
            logging.exception()
        while not self.outgoing_msgs.empty():
            self.outgoing_msgs.get_nowait()
        self.outgoing_msgs.put(None)
        self.is_connected = False
        self.socket.close()

    def writer_thread(self):
        while True:
            item = self.outgoing_msgs.get()
            if item is None:
                break
            self.socket.sendall(str(len(item)).encode() + b"\n")
            self.socket.sendall(item)
            self.outgoing_msgs.task_done()

    def reader_thread(self):
        while True:
            buf = b""
            while not buf or buf[-1] != '\n':
                tmp = self.socket.recv(1)
                if not tmp:
                    return
                buf += tmp
            length = int(buf)
            buf = bytearray(length)
            read = 0
            while length > read:
                tmp = self.socket.recv_into(buf[read:])
                if not tmp:
                    return
                read += tmp

            success = self.proto.received(buf, self)
            if not success:
                return

class IncomingHandler(socketserver.BaseRequestHandler):
    def handle(self):
        pass

class Protocol:
    def __init__(self, bootstrap_peer):
        self.block_receive_handlers = []
        self.trans_receive_handlers = []
        socketserver.TCPServer((HOST, PORT), MyTCPHandler)
        self.peers = [PeerConnection(bootstrap_peer)]

    def block_received(self, block):
        for handler in self.block_receive_handlers:
            handler(block)

    def broadcast_mined_block(self, block):
        self.fake_block_received(block)

    def received(self, msg, peer):
        try:
            obj = json.loads(msg.decode())
            msg_type = obj['msg_type']
            msg_param = obj['msg_params']
        except KeyError:
            return False
        except UnicodeDecodeError:
            return False
        except json.JSONDecodeError:
            return False
        getattr(self, 'received_' + msg_type)(msg_param)
        return True
    def received_peers(self, peer_list):
        pass
    def received_getblock(self, block_hash):
        pass
    def received_block(self, block):
        pass
    def received_transaction(self, transaction):
        pass
