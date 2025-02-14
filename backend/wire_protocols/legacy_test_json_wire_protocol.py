#!/usr/bin/env python3
"""
test_wire_protocol.py

This module provides unittests for the wire_protocol module.
It tests both the protocol message constructor functions and the
WireProtocol class’s send/receive methods.
"""

import unittest
import socket
from backend.wire_protocols.legacy_json_wire_protocol import (
    WireProtocol,
    create_account_msg,
    login_msg,
    list_accounts_msg,
    send_message_msg,
    read_messages_msg,
    delete_messages_msg,
    delete_account_msg,
)


class TestProtocolMessageConstructors(unittest.TestCase):
    """Test the helper functions that construct protocol messages."""

    def test_create_account_msg(self):
        result = create_account_msg("alice", "hashed_password")
        expected = {
            "action": "create_account",
            "username": "alice",
            "password_hash": "hashed_password",
        }
        self.assertEqual(result, expected)

    def test_login_msg(self):
        result = login_msg("bob", "hashed_pw")
        expected = {"action": "login", "username": "bob", "password_hash": "hashed_pw"}
        self.assertEqual(result, expected)

    def test_list_accounts_msg_defaults(self):
        result = list_accounts_msg()
        expected = {"action": "list_accounts", "pattern": "*", "page": 0}
        self.assertEqual(result, expected)

    def test_list_accounts_msg_custom(self):
        result = list_accounts_msg("a*", 2)
        expected = {"action": "list_accounts", "pattern": "a*", "page": 2}
        self.assertEqual(result, expected)

    def test_send_message_msg(self):
        result = send_message_msg("bob", "Hello Bob!")
        expected = {"action": "send_message", "recipient": "bob", "message": "Hello Bob!"}
        self.assertEqual(result, expected)

    def test_read_messages_msg(self):
        result = read_messages_msg(5)
        expected = {"action": "read_messages", "number": 5}
        self.assertEqual(result, expected)

    def test_delete_messages_msg(self):
        result = delete_messages_msg([1, 2, 3])
        expected = {"action": "delete_messages", "message_ids": [1, 2, 3]}
        self.assertEqual(result, expected)

    def test_delete_account_msg(self):
        result = delete_account_msg("charlie")
        expected = {"action": "delete_account", "username": "charlie"}
        self.assertEqual(result, expected)


class TestWireProtocolSendReceive(unittest.TestCase):
    """
    Test the WireProtocol class’s send/receive methods using
    a pair of connected sockets (socketpair).
    """

    def setUp(self):
        # Create a pair of connected sockets for testing.
        self.sock1, self.sock2 = socket.socketpair()
        self.wp1 = WireProtocol(self.sock1)
        self.wp2 = WireProtocol(self.sock2)

    def tearDown(self):
        # Close the sockets after each test.
        try:
            self.sock1.close()
        except Exception:
            pass
        try:
            self.sock2.close()
        except Exception:
            pass

    def test_send_receive_single_message(self):
        """Test that a message sent from one end is received correctly at the other end."""
        test_message = {"action": "test", "data": "Hello World"}
        self.wp1.send(test_message)
        received = self.wp2.receive()
        self.assertEqual(test_message, received)

    def test_send_receive_multiple_messages(self):
        """Test sending multiple messages consecutively."""
        msg1 = {"action": "test", "data": "first"}
        msg2 = {"action": "test", "data": "second"}
        self.wp1.send(msg1)
        self.wp1.send(msg2)
        received1 = self.wp2.receive()
        received2 = self.wp2.receive()
        self.assertEqual(msg1, received1)
        self.assertEqual(msg2, received2)

    def test_incomplete_message_raises_connection_error(self):
        """
        Test that if an incomplete JSON message is sent (i.e. without the terminating newline)
        and the sender closes the connection, the receiver raises a ConnectionError.
        """
        incomplete_message = b'{"action": "test"'
        # Send an incomplete message directly on the underlying socket.
        self.sock1.send(incomplete_message)
        # Close the sender's socket to simulate connection closure.
        self.sock1.close()
        with self.assertRaises(ConnectionError):
            self.wp2.receive()


if __name__ == "__main__":
    unittest.main()
