import unittest
import json
from typing import Dict, Any
from src.wire_protocols.json_wire_protocol import (
    WireProtocol, create_account_username_request_msg,
    create_account_password_request_msg, login_request_msg,
    send_message_request_msg, retrieve_unread_count_request_msg,
    load_unread_messages_request_msg, load_read_messages_request_msg,
    delete_messages_request_msg, delete_account_request_msg,
    list_accounts_request_msg, quit_request_msg
)

class MockSocket:
    def __init__(self):
        self.sent_data = []
        self.recv_data = []

    def send(self, data: bytes) -> int:
        self.sent_data.append(data)
        return len(data)

    def sendall(self, data: bytes) -> None:
        self.sent_data.append(data)

    def recv(self, bufsize: int) -> bytes:
        if self.recv_data:
            return self.recv_data.pop(0)
        return b""

class TestJsonWireProtocol(unittest.TestCase):
    def setUp(self):
        self.mock_socket = MockSocket()
        self.wire_protocol = WireProtocol(self.mock_socket)

    def test_message_construction(self):
        """Test message construction functions"""
        # Test account creation username request
        msg = create_account_username_request_msg("testuser")
        self.assertEqual(msg["protocol_version"], 1)
        self.assertEqual(msg["op_code"], "create_account_username")
        self.assertEqual(msg["payload"]["username"], "testuser")

        # Test account creation password request
        msg = create_account_password_request_msg("testuser", "testpass")
        self.assertEqual(msg["protocol_version"], 1)
        self.assertEqual(msg["op_code"], "create_account_password")
        self.assertEqual(msg["payload"]["username"], "testuser")
        self.assertEqual(msg["payload"]["password"], "testpass")

        # Test login request
        msg = login_request_msg("testuser", "testpass")
        self.assertEqual(msg["protocol_version"], 1)
        self.assertEqual(msg["op_code"], "login")
        self.assertEqual(msg["payload"]["username"], "testuser")
        self.assertEqual(msg["payload"]["password"], "testpass")

        # Test send message request
        msg = send_message_request_msg("sender", "recipient", "Hello!")
        self.assertEqual(msg["protocol_version"], 1)
        self.assertEqual(msg["op_code"], "send_message")
        self.assertEqual(msg["payload"]["sender"], "sender")
        self.assertEqual(msg["payload"]["recipient"], "recipient")
        self.assertEqual(msg["payload"]["message"], "Hello!")

    def test_multiple_messages(self):
        """Test sending and receiving multiple messages"""
        # Prepare mock responses
        response1 = {"op_code": "ok", "payload": {"message": "Message 1"}}
        response2 = {"op_code": "ok", "payload": {"message": "Message 2"}}
        
        self.mock_socket.recv_data = [
            (json.dumps(response1) + "\n").encode("utf-8"),
            (json.dumps(response2) + "\n").encode("utf-8")
        ]

        # Send multiple messages
        msg1 = create_account_username_request_msg("user1")
        msg2 = create_account_username_request_msg("user2")

        self.wire_protocol.send(msg1)
        self.wire_protocol.send(msg2)

        # Receive responses
        recv1 = self.wire_protocol.receive()
        recv2 = self.wire_protocol.receive()

        # Verify responses
        self.assertEqual(recv1, response1)
        self.assertEqual(recv2, response2)

    def test_send_receive_with_special_chars(self):
        """Test sending and receiving messages with special characters"""
        # Test message with special characters
        special_msg = send_message_request_msg(
            "user1",
            "user2",
            "Hello! 👋 This is a test with special chars: áéíóú 你好"
        )

        # Prepare mock response
        response = {
            "op_code": "ok",
            "payload": {
                "message": "Message received with special chars: 👋 áéíóú 你好"
            }
        }
        self.mock_socket.recv_data = [(json.dumps(response) + "\n").encode("utf-8")]

        # Send and receive
        self.wire_protocol.send(special_msg)
        received = self.wire_protocol.receive()

        # Verify the message was properly encoded and decoded
        self.assertEqual(received, response)

    def test_connection_closed(self):
        self.mock_socket.recv_data = [b""]
        with self.assertRaises(ConnectionError):
            self.wire_protocol.receive()

    def test_account_creation_message(self):
        msg = create_account_password_request_msg("testuser", "testpass")
        self.assertEqual(msg["protocol_version"], 1)
        self.assertEqual(msg["op_code"], "create_account_password")
        self.assertEqual(msg["payload"]["username"], "testuser")
        self.assertEqual(msg["payload"]["password"], "testpass")

    def test_login_message(self):
        msg = login_request_msg("testuser", "testpass")
        self.assertEqual(msg["protocol_version"], 1)
        self.assertEqual(msg["op_code"], "login")
        self.assertEqual(msg["payload"]["username"], "testuser")
        self.assertEqual(msg["payload"]["password"], "testpass")

    def test_send_message_msg(self):
        msg = send_message_request_msg("sender", "recipient", "Hello!")
        self.assertEqual(msg["protocol_version"], 1)
        self.assertEqual(msg["op_code"], "send_message")
        self.assertEqual(msg["payload"]["sender"], "sender")
        self.assertEqual(msg["payload"]["recipient"], "recipient")
        self.assertEqual(msg["payload"]["message"], "Hello!")

if __name__ == '__main__':
    unittest.main()
