""" Implementation of the P2P protocol. """

import json
import socket
import socketserver
import logging
from threading import Thread, Lock
from queue import Queue, PriorityQueue
from binascii import unhexlify, hexlify
from typing import Callable, List


__all__ = ['Protocol', 'PeerConnection', 'MAX_PEERS', 'HELLO_MSG']

MAX_PEERS = 10
""" The maximum number of peers that we connect to."""

HELLO_MSG = b"bl0ckch41n"
""" The hello message two peers use to make sure they are speaking the same protocol. """

# TODO: set this centrally
logging.basicConfig(level=logging.INFO)
socket.setdefaulttimeout(30)

class PeerConnection:
    """
    Handles the low-level socket connection to one other peer.
    :ivar peer_addr: The self-reported address one can use to connect to this peer.
    :ivar param: The self-reported address one can use to connect to this peer.
    :ivar _sock_addr: The address our socket is or will be connected to.
    :ivar socket: The socket object we use to communicate with our peer.
    :param sock: A socket object we should use to communicate with our peer.
    :ivar proto: The Protocol instance this peer connection belongs to.
    :ivar is_connected: A boolean indicating the current connection status.
    :ivar outgoing_msgs: A queue of messages we want to send to this peer.
    """

    def __init__(self, peer_addr: tuple, proto: 'Protocol', sock: socket.socket=None):
        self.peer_addr = None
        self._sock_addr = peer_addr
        self.socket = sock
        self.proto = proto
        self.is_connected = False
        self.outgoing_msgs = Queue()

        Thread(target=self.run, daemon=True).start()

    def send_peers(self):
        """ Sends all known peers to this peer. """
        for peer in self.proto.peers:
            if peer.peer_addr is not None:
                self.send_msg("peer", list(peer.peer_addr))

    def run(self):
        """
        Creates a connection, handles the handshake, then hands off to the reader and writer threads.

        Does not return until the writer thread does.
        """
        if self.socket is None:
            logging.info("connecting to peer %s", repr(self._sock_addr))
            self.socket = socket.create_connection(self._sock_addr)
        self.socket.sendall(HELLO_MSG)
        if self.socket.recv(len(HELLO_MSG)) != HELLO_MSG:
            return
        self.is_connected = True

        self.send_msg("myport", self.proto.server.server_address[1])
        self.send_msg("block", self.proto._primary_block)
        self.send_peers()

        # TODO: broadcast this new peer to our current peers, under certain circumstances

        Thread(target=self.reader_thread, daemon=True).start()
        self.writer_thread()

    def close_on_error(fn: Callable):
        """ A decorator that closes both threads if one dies. """

        def wrapper(self, *args, **kwargs):
            try:
                fn(self, *args, **kwargs)
            except Exception:
                logging.exception("exception in reader/writer thread")

            self.close()

        return wrapper

    def close(self):
        """ Closes the connection to this peer. """

        if not self.is_connected:
            return

        logging.info("closing connection to peer %s", self._sock_addr)
        while not self.outgoing_msgs.empty():
            self.outgoing_msgs.get_nowait()
        self.outgoing_msgs.put(None)
        self.is_connected = False
        if self in self.proto.peers:
            self.proto.peers.remove(self)
        self.socket.close()

    def send_msg(self, msg_type: str, msg_param):
        """
        Sends a message to this peer.

        :msg_type: The type of message.
        :msg_param: the JSON-compatible parameter of this message
        """

        if not self.is_connected:
            return
        self.outgoing_msgs.put({'msg_type': msg_type, 'msg_param': msg_param})

    @close_on_error
    def writer_thread(self):
        """ The writer thread takes messages from our message queue and sends them to the peer. """
        while True:
            item = self.outgoing_msgs.get()
            if item is None:
                break
            logging.debug("sending %s", item['msg_type'])
            data = json.dumps(item, indent=4).encode()
            self.socket.sendall(str(len(data)).encode() + b"\n")
            self.socket.sendall(data)
            self.outgoing_msgs.task_done()

    @close_on_error
    def reader_thread(self):
        """
        The reader thread reads messages from the socket and passes them to the protocol to handle.
        """
        while True:
            buf = b""
            while not buf or buf[-1] != ord('\n'):
                try:
                    tmp = self.socket.recv(1)
                except socket.timeout as e:
                    if buf:
                        raise e
                    continue

                if not tmp:
                    return
                buf += tmp
            length = int(buf)
            logging.debug("expecting json obj of length %d", length)
            buf = bytearray(length)
            read = 0
            while length > read:
                tmp = self.socket.recv_into(memoryview(buf)[read:])
                if not tmp:
                    return
                read += tmp

            obj = json.loads(buf.decode())
            msg_type = obj['msg_type']
            msg_param = obj['msg_param']
            logging.debug("received %s", obj['msg_type'])

            if msg_type == 'myport':
                self.peer_addr = (self._sock_addr[0],) + (int(msg_param),) + self._sock_addr[2:]
            else:
                self.proto.received(msg_type, msg_param, self)


class SocketServer(socketserver.TCPServer):
    """
    A TCP socketserver that calls does not close the connections on its own.
    """

    allow_reuse_address = True
    """ Make sure the server can be restarted without delays. """

    def serve_forever_bg(self):
        """ Runs the server forever in a background thread. """

        logging.info("listening on %s", self.server_address)
        Thread(target=self.serve_forever, daemon=True).start()

    def close_request(self, request):
        pass

    def shutdown_request(self, request):
        pass

class Protocol:
    """
    Manages connections to our peers. Allows sending messages to them and has event handlers
    for handling messages from other peers.

    :ivar block_receive_handlers: Event handlers that get called when a new block is received.
    :vartype block_receive_handlers: List[Callable]
    :ivar trans_receive_handlers: Event handlers that get called when a new transaction is received.
    :vartype trans_receive_handlers: List[Callable]
    :ivar block_request_handlers: Event handlers that get called when a block request is received.
    :vartype block_request_handlers: List[Callable]
    :ivar peers: The peers we are connected to.
    :vartype peers: List[PeerConnection]
    """

    def __init__(self, bootstrap_peers: 'List[tuple]',
                 primary_block: 'Block', listen_port: int=0, listen_addr: str=""):
        """
        :param bootstrap_peers: network addresses of peers where we bootstrap the P2P network from
        :param primary_block: the head of the primary block chain
        :param listen_port: the port where other peers should be able to reach us
        :param listen_addr: the address where other peers should be able to reach us
        """

        self.block_receive_handlers = []
        self.trans_receive_handlers = []
        self.block_request_handlers = []
        self._primary_block = primary_block.to_json_compatible()
        self.peers = []
        self._callback_queue = PriorityQueue()
        self._callback_counter = 0
        self._callback_counter_lock = Lock()

        class IncomingHandler(socketserver.BaseRequestHandler):
            """ Handler for incoming P2P connections. """
            proto = self
            def handle(self):
                logging.info("connection from peer %s", repr(self.client_address))
                if len(self.proto.peers) > MAX_PEERS:
                    logging.warning("too many connections: rejecting peer %s",
                                    repr(self.client_address))
                    self.request.close()
                    # TODO: separate limits for incoming and outgoing connections
                    return

                conn = PeerConnection(self.client_address, self.proto, self.request)
                self.proto.peers.append(conn)
        self.server = SocketServer((listen_addr, listen_port), IncomingHandler)
        self.server.serve_forever_bg()

        # we want to do this only after we opened our listening socket
        self.peers.extend([PeerConnection(peer, self) for peer in bootstrap_peers])

        Thread(target=self._main_thread, daemon=True).start()

    def broadcast_primary_block(self, block: 'Block'):
        """ Notifies all peers and local listeners of a new primary block. """
        self._primary_block = block.to_json_compatible()
        for peer in self.peers:
            peer.send_msg("block", self._primary_block)
        self.received('block', self._primary_block, None, 0)

    def broadcast_transaction(self, trans: 'Transaction'):
        """ Notifies all peers and local listeners of a new transaction. """
        for peer in self.peers:
            peer.send_msg("transaction", trans.to_json_compatible())

    def received(self, msg_type: str, msg_param, peer: PeerConnection, prio: int=1):
        """
        Called by a PeerConnection when a new message was received.

        :param msg_type: The message type identifier.
        :param msg_param: The JSON-compatible object that was received.
        :param peer: The peer who sent us the message.
        :param prio: The priority of the message. (Should be lower for locally generated events
                     than for remote events, to make sure self-mined blocks get handled first.)
        """
        with self._callback_counter_lock:
            counter = self._callback_counter + 1
            self._callback_counter = counter
        self._callback_queue.put((prio, counter, msg_type, msg_param, peer))

    def _main_thread(self):
        """ The main loop of the one thread where all incoming events are handled. """
        while True:
            _, _, msg_type, msg_param, peer = self._callback_queue.get()
            try:
                getattr(self, 'received_' + msg_type)(msg_param, peer)
            except:
                logging.exception("unhandled exception in event handler")
                try:
                    peer.close()
                except OSError:
                    pass

    def received_peer(self, peer_addr: list, _):
        """ Information about a peer has been received. """

        peer_addr = tuple(peer_addr)
        if len(self.peers) >= MAX_PEERS:
            return

        for peer in self.peers:
            if peer.peer_addr == peer_addr:
                return

        # TODO: if the other peer also just learned of us, we can end up with two connections (one from each direction)
        self.peers.append(PeerConnection(peer_addr, self))

    def received_getblock(self, block_hash: str, peer: PeerConnection):
        """ We received a request for a new block from a certain peer. """
        for handler in self.block_request_handlers:
            block = handler(unhexlify(block_hash))
            if block is not None:
                peer.send_msg("block", block.to_json_compatible())
                break

    def received_block(self, block: dict, _):
        """ Someone sent us a block. """
        for handler in self.block_receive_handlers:
            handler(Block.from_json_compatible(block))

    def received_transaction(self, transaction: dict, _):
        """ Someone sent us a transaction. """
        for handler in self.trans_receive_handlers:
            handler(Transaction.from_json_compatible(transaction))

    def send_block_request(self, block_hash: bytes):
        """ Sends a request for a block to all our peers. """
        for peer in self.peers:
            peer.send_msg("getblock", hexlify(block_hash).decode())

from .block import Block
from .transaction import Transaction
