import unittest
import socket
import threading
import time
import sys
import json
from pathlib import Path

# Add the src directory to the Python path
src_path = str(Path(__file__).parent.parent)
if src_path not in sys.path:
    sys.path.append(src_path)

from src.client import ChatClient
from src.wire_protocols.json_wire_protocol import WireProtocol

class MockSocket:
    def __init__(self):
        self.sent_data = []
        self.receive_data = []
        self.closed = False

    def sendall(self, data):
        self.sent_data.append(data)

    def recv(self, bufsize):
        if self.receive_data:
            return self.receive_data.pop(0)
        return b""

    def close(self):
        self.closed = True

    def shutdown(self, how):
        pass

class TestChatClient(unittest.TestCase):
    def setUp(self):
        self.client = ChatClient("localhost", 5452)
        self.client.socket = MockSocket()
        self.client.wire_protocol = WireProtocol(self.client.socket)

    def tearDown(self):
        if self.client:
            self.client.close()

    def test_account_creation_username(self):
        self.client.account_creation_username("testuser")
        sent_data = self.client.socket.sent_data[0].decode('utf-8').strip()
        self.assertIn("create_account_username", sent_data)
        self.assertIn("testuser", sent_data)

    def test_account_creation_password(self):
        self.client.account_creation_password("testuser", "testpass")
        sent_data = self.client.socket.sent_data[0].decode('utf-8').strip()
        self.assertIn("create_account_password", sent_data)
        self.assertIn("testuser", sent_data)
        self.assertIn("testpass", sent_data)

    def test_login(self):
        self.client.login("testuser", "testpass")
        sent_data = self.client.socket.sent_data[0].decode('utf-8').strip()
        self.assertIn("login", sent_data)
        self.assertIn("testuser", sent_data)
        self.assertIn("testpass", sent_data)
        self.assertEqual(self.client.current_user, "testuser")

    def test_send_message(self):
        self.client.current_user = "sender"
        self.client.send_message("recipient", "Hello!")
        sent_data = self.client.socket.sent_data[0].decode('utf-8').strip()
        self.assertIn("send_message", sent_data)
        self.assertIn("sender", sent_data)
        self.assertIn("recipient", sent_data)
        self.assertIn("Hello!", sent_data)

    def test_send_message_no_login(self):
        self.client.current_user = None
        self.client.send_message("recipient", "Hello!")
        self.assertEqual(len(self.client.socket.sent_data), 0)

    def test_delete_account(self):
        self.client.current_user = "testuser"
        self.client.delete_account()
        sent_data = self.client.socket.sent_data[0].decode('utf-8').strip()
        self.assertIn("delete_account", sent_data)
        self.assertIn("testuser", sent_data)
        self.assertIsNone(self.client.current_user)

    def test_list_accounts(self):
        self.client.list_accounts()
        sent_data = self.client.socket.sent_data[0].decode('utf-8').strip()
        self.assertIn("list_accounts", sent_data)

    def test_close(self):
        self.client.close()
        self.assertFalse(self.client.running)
        self.assertTrue(self.client.socket.closed)

    def test_retrieve_unread_count(self):
        """Test retrieving unread message count"""
        self.client.current_user = "testuser"
        self.client.retrieve_number_of_unread_messages()
        sent_data = self.client.socket.sent_data[0].decode('utf-8').strip()
        self.assertIn("retrieve_unread_count", sent_data)
        self.assertIn("testuser", sent_data)

    def test_retrieve_unread_count_no_login(self):
        """Test retrieving unread count when not logged in"""
        self.client.current_user = None
        self.client.retrieve_number_of_unread_messages()
        self.assertEqual(len(self.client.socket.sent_data), 0)

    def test_load_unread_messages(self):
        """Test loading unread messages"""
        self.client.current_user = "testuser"
        self.client.load_unread_messages()
        sent_data = self.client.socket.sent_data[0].decode('utf-8').strip()
        self.assertIn("load_unread_messages", sent_data)
        self.assertIn("testuser", sent_data)

    def test_load_read_messages(self):
        """Test loading read messages"""
        self.client.current_user = "testuser"
        self.client.load_read_messages()
        sent_data = self.client.socket.sent_data[0].decode('utf-8').strip()
        self.assertIn("load_read_messages", sent_data)
        self.assertIn("testuser", sent_data)

    def test_delete_messages(self):
        """Test deleting messages"""
        self.client.current_user = "testuser"
        message_ids = ["msg1", "msg2"]
        self.client.delete_messages(message_ids)
        sent_data = self.client.socket.sent_data[0].decode('utf-8').strip()
        self.assertIn("delete_messages", sent_data)
        self.assertIn("testuser", sent_data)
        for msg_id in message_ids:
            self.assertIn(msg_id, sent_data)

    def test_delete_messages_no_login(self):
        """Test deleting messages when not logged in"""
        self.client.current_user = None
        self.client.delete_messages(["msg1"])
        self.assertEqual(len(self.client.socket.sent_data), 0)

    def test_quit(self):
        """Test quitting/logging out"""
        self.client.current_user = "testuser"
        self.client.quit()
        sent_data = self.client.socket.sent_data[0].decode('utf-8').strip()
        self.assertIn("quit", sent_data)
        self.assertIn("testuser", sent_data)
        self.assertIsNone(self.client.current_user)

    def test_receive_response(self):
        """Test receiving response from server"""
        # Prepare mock response
        response = {
            "op_code": "ok",
            "payload": {
                "message": "Test message"
            }
        }
        response_data = (json.dumps(response) + "\n").encode("utf-8")
        self.client.socket.receive_data.append(response_data)
        
        # Start listening thread
        self.client.start()
        time.sleep(0.1)  # Give thread time to start
        
        # Check if response was received
        received = self.client.wire_protocol.receive()
        self.assertEqual(received, response)
        
        # Stop listening thread
        self.client.running = False

    def test_error_handling(self):
        """Test error handling for various scenarios"""
        # Test connection error
        self.client.socket.receive_data = []  # Empty receive data to simulate connection error
        self.client.start()
        time.sleep(0.1)  # Give thread time to start
        
        # The client should handle the connection error gracefully
        self.assertFalse(self.client.running)
        
        # Test invalid JSON response
        self.client = ChatClient("localhost", 5452)  # Reset client
        self.client.socket = MockSocket()
        self.client.wire_protocol = WireProtocol(self.client.socket)
        self.client.socket.receive_data.append(b"invalid json\n")
        
        self.client.start()
        time.sleep(0.1)
        
        # The client should handle the invalid JSON gracefully
        self.assertFalse(self.client.running)

if __name__ == '__main__':
    unittest.main()
