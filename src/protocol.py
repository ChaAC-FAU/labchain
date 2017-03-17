"""
Implementation of the P2P protocol.

The protocol is text-based and works over TCP. Once a TCP connection is established, there is no
difference between server and client. Both sides start by sending a fixed `HELLO_MSG` to make sure
they speak the same protocol. After that, they can send any number of messages.

Messages start with a length (ending with a new-line), followed by the JSON-encoded contents of
the message of that length. On the top level, the sent JSON values are always dicts, with a
'msg_type' key indicating the kind of message and a 'msg_param' key containing a type-specific
payload.

To make sure that the peer acting as a TCP server in a connection knows how to reach the TCP client,
there is a 'myport' message containing the TCP port where a peer listens for incoming connections.

For other message types, you can look at the `received_*` methods of `Protocol`.
"""

import json
import socket
import socketserver
import logging
from collections import namedtuple
from threading import Thread, Lock
from queue import Queue, PriorityQueue
from binascii import unhexlify, hexlify
from uuid import UUID, uuid4
from typing import Callable, List, Optional

from .block import GENESIS_BLOCK_HASH


__all__ = ['Protocol', 'PeerConnection', 'MAX_PEERS', 'HELLO_MSG']

MAX_PEERS = 10
""" The maximum number of peers that we connect to."""

HELLO_MSG = b"bl0ckch41n" + hexlify(GENESIS_BLOCK_HASH)[:30] + b"\n"
"""
The hello message two peers use to make sure they are speaking the same protocol. Contains the
genesis block hash, so that communication of incompatible forks of the program is less likely to
succeed.
"""

SOCKET_TIMEOUT = 30
""" The socket timeout for P2P connections. """

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
        self._sent_uuid = str(uuid4())
        self.outgoing_msgs = Queue()
        self._close_lock = Lock()

        Thread(target=self.run, daemon=True).start()

    def send_peers(self):
        """ Sends all known peers to this peer. """
        logging.debug("%s > peer *", self.peer_addr)
        for peer in self.proto.peers:
            if peer.peer_addr is not None:
                self.send_msg("peer", list(peer.peer_addr))

    def run(self):
        """
        Creates a connection, handles the handshake, then hands off to the reader and writer threads.

        Does not return until the writer thread does.
        """
        try:
            if self.socket is None:
                logging.info("connecting to peer %s", repr(self._sock_addr))
                self.socket = socket.create_connection(self._sock_addr, SOCKET_TIMEOUT)
            else:
                self.socket.settimeout(SOCKET_TIMEOUT)
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.socket.sendall(HELLO_MSG)
            if self.socket.recv(len(HELLO_MSG)) != HELLO_MSG:
                raise OSError("peer talks a different protocol")
        except OSError as e:
            self.proto.received("disconnected", None, self)
            if self.socket is not None:
                self.socket.close()
            raise e
        self.is_connected = True

        self.send_msg("myport", self.proto.server.server_address[1])
        self.send_msg("block", self.proto._primary_block)
        self.send_msg("id", self._sent_uuid)
        self.send_peers()

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

        with self._close_lock:
            if not self.is_connected:
                return

            logging.info("closing connection to peer %s", self._sock_addr)

            while not self.outgoing_msgs.empty():
                self.outgoing_msgs.get_nowait()
            self.outgoing_msgs.put(None)
            self.is_connected = False
            self.proto.received("disconnected", None, self, 3)

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
            data = json.dumps(item, indent=4).encode() + b"\n"
            self.socket.sendall(str(len(data)).encode() + b"\n" + data)
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

            self.proto.received(msg_type, msg_param, self)


class SocketServer(socketserver.TCPServer):
    """ A TCP socketserver that does not close connections when the handler returns. """

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

    _dummy_peer = namedtuple("DummyPeerConnection", ["peer_addr"])("self")
    """
    A dummy peer for messages that are injected by this program, not received from a remote peer.
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
        obj = block.to_json_compatible()

        if self._primary_block == obj:
            logging.debug("not broadcasting block again")
            return

        logging.debug("* > block %s", hexlify(block.hash))
        self._primary_block = obj

        for peer in self.peers:
            peer.send_msg("block", obj)
        self.received('block', obj, None, 0)

    def broadcast_transaction(self, trans: 'Transaction'):
        """ Notifies all peers and local listeners of a new transaction. """
        logging.debug("* > transaction %s", hexlify(trans.get_hash()))
        for peer in self.peers:
            peer.send_msg("transaction", trans.to_json_compatible())

    def received(self, msg_type: str, msg_param, peer: Optional[PeerConnection], prio: int=1):
        """
        Called by a PeerConnection when a new message was received.

        :param msg_type: The message type identifier.
        :param msg_param: The JSON-compatible object that was received.
        :param peer: The peer who sent us the message.
        :param prio: The priority of the message. (Should be lower for locally generated events
                     than for remote events, to make sure self-mined blocks get handled first.)
        """

        if peer is None:
            peer = self._dummy_peer

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
                    if peer is not self._dummy_peer:
                        peer.close()
                except OSError:
                    pass

    def received_id(self, uuid: str, sender: PeerConnection):
        """
        A unique connection id was received. We use this to detect and close connections to
        ourselves.

        TODO: detect duplicate connections to other peers (needs TLS or something similar)
        """
        logging.debug("%s < id %s", sender.peer_addr, uuid)
        for peer in self.peers:
            if peer._sent_uuid == uuid:
                peer.close()
                sender.close()
                break

    def received_peer(self, peer_addr: list, sender):
        """ Information about a peer has been received. """

        peer_addr = tuple(peer_addr)
        logging.debug("%s < peer %s", sender.peer_addr, peer_addr)
        if len(self.peers) >= MAX_PEERS:
            # TODO: maintain list of known, not connected peers
            return

        for peer in self.peers:
            if peer.peer_addr == peer_addr:
                return

        # TODO: if the other peer also just learned of us, we can end up with two connections (one from each direction)
        self.peers.append(PeerConnection(peer_addr, self))

    def received_myport(self, port: int, sender: PeerConnection):
        logging.debug("%s < myport %s", sender.peer_addr, port)
        addr = sender.socket.getpeername()
        sender.peer_addr = (addr[0],) + (int(port),) + addr[2:]

        for peer in self.peers:
            if peer.is_connected and peer is not sender:
                if peer.peer_addr == sender.peer_addr:
                    sender.close()
                else:
                    logging.debug("%s > peer %s", peer.peer_addr, sender.peer_addr)
                    peer.send_msg("peer", list(sender.peer_addr))

    def received_getblock(self, block_hash: str, peer: PeerConnection):
        """ We received a request for a new block from a certain peer. """
        logging.debug("%s < getblock %s", peer.peer_addr, block_hash)
        for handler in self.block_request_handlers:
            block = handler(unhexlify(block_hash))
            if block is not None:
                peer.send_msg("block", block.to_json_compatible())
                break

    def received_block(self, block: dict, sender: PeerConnection):
        """ Someone sent us a block. """
        block = Block.from_json_compatible(block)
        logging.debug("%s < block %s", sender.peer_addr, hexlify(block.hash))
        for handler in self.block_receive_handlers:
            handler(block)

    def received_transaction(self, transaction: dict, sender: PeerConnection):
        """ Someone sent us a transaction. """
        transaction = Transaction.from_json_compatible(transaction)
        logging.debug("%s < transaction %s", sender.peer_addr, hexlify(transaction.get_hash()))
        for handler in self.trans_receive_handlers:
            handler(transaction)

    def received_disconnected(self, _, peer: PeerConnection):
        """
        Removes a disconnected peer from our list of connected peers.

        (Not actually a message received from the peer, but a message sent by the reader or writer
        thread to the main thread.)
        """
        if not peer.is_connected:
            self.peers.remove(peer)

    def send_block_request(self, block_hash: bytes):
        """ Sends a request for a block to all our peers. """
        logging.debug("* > getblock %s", hexlify(block_hash))
        for peer in self.peers:
            peer.send_msg("getblock", hexlify(block_hash).decode())

from .block import Block
from .transaction import Transaction
