import unittest
import os
import sys
import socket
import threading
import time
from pathlib import Path

# Add the src directory to the Python path
src_path = str(Path(__file__).parent.parent)
if src_path not in sys.path:
    sys.path.append(src_path)

from src.chat_server import (
    hash_password, create_message_object,
    handle_account_creation_username, handle_account_creation_password,
    handle_login, handle_send_message, handle_load_unread_messages,
    handle_delete_messages, handle_quit, handle_retrieve_unread_count,
    init_database, close_database, user_db, DATABASE_FILE, save_database
)

class MockWireProtocol:
    def __init__(self):
        self.sent_messages = []
        self.socket = None

    def send(self, message):
        self.sent_messages.append(message)

class TestChatServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test database file"""
        global DATABASE_FILE
        cls.original_db_file = DATABASE_FILE
        DATABASE_FILE = "test_chat_server_data.db"

    def setUp(self):
        """Initialize database before each test"""
        global user_db
        # Remove any existing database files
        try:
            os.remove(DATABASE_FILE)
        except OSError:
            pass
        # Initialize fresh database
        init_database()

    def tearDown(self):
        """Clean up after each test"""
        close_database()
        try:
            os.remove(DATABASE_FILE)
        except OSError:
            pass

    @classmethod
    def tearDownClass(cls):
        """Restore original database file name"""
        global DATABASE_FILE
        DATABASE_FILE = cls.original_db_file

    def test_hash_password(self):
        """Test password hashing"""
        hash1 = hash_password("user1", "pass1")
        hash2 = hash_password("user1", "pass1")
        hash3 = hash_password("user2", "pass1")
        
        self.assertEqual(hash1, hash2)  # Same user+pass should give same hash
        self.assertNotEqual(hash1, hash3)  # Different user should give different hash
        self.assertTrue(isinstance(hash1, str))  # Hash should be string
        self.assertEqual(len(hash1), 64)  # SHA256 produces 64 char hex string

    def test_create_message_object(self):
        """Test message object creation"""
        msg = create_message_object("sender", "recipient", "Hello!")
        
        self.assertEqual(msg["sender"], "sender")
        self.assertEqual(msg["recipient"], "recipient")
        self.assertEqual(msg["message"], "Hello!")
        self.assertTrue("message_id" in msg)
        self.assertTrue("timestamp" in msg)

    def test_account_creation(self):
        """Test account creation flow"""
        wp = MockWireProtocol()
        global user_db
        
        # Test account creation with username first
        handle_account_creation_username(wp, {"username": "newuser"})
        self.assertTrue(len(wp.sent_messages) > 0)
        self.assertEqual(wp.sent_messages[0]["op_code"], "ok")
        
        # Test account creation with password
        handle_account_creation_password(wp, {"username": "newuser", "password": "newpass"})
        save_database()  # Save changes
        self.assertEqual(wp.sent_messages[1]["op_code"], "ok")
        self.assertTrue("newuser" in user_db)
        self.assertEqual(user_db["newuser"]["session_status"], "offline")

        # Test creating account with existing username
        handle_account_creation_username(wp, {"username": "newuser"})
        save_database()  # Save changes
        self.assertEqual(wp.sent_messages[2]["op_code"], "exists")

        # Test creating account with existing username and password
        handle_account_creation_password(wp, {"username": "newuser", "password": "newpass"})
        save_database()  # Save changes
        self.assertEqual(wp.sent_messages[3]["op_code"], "error")

    def test_login(self):
        """Test login functionality"""
        wp = MockWireProtocol()
        global user_db
        
        # Create a test user first
        handle_account_creation_username(wp, {"username": "testuser"})
        save_database()  # Save changes
        handle_account_creation_password(wp, {"username": "testuser", "password": "testpass"})
        save_database()  # Save changes
        
        # Test successful login
        handle_login(wp, {"username": "testuser", "password": "testpass"})
        save_database()  # Save changes
        self.assertEqual(wp.sent_messages[-1]["op_code"], "ok")
        self.assertEqual(user_db["testuser"]["session_status"], "online")

        # Test login with wrong password
        handle_login(wp, {"username": "testuser", "password": "wrongpass"})
        save_database()  # Save changes
        self.assertEqual(wp.sent_messages[-1]["op_code"], "error")

        # Test login with non-existent user
        handle_login(wp, {"username": "nonexistent", "password": "testpass"})
        save_database()  # Save changes
        self.assertEqual(wp.sent_messages[-1]["op_code"], "error")

    def test_send_message(self):
        """Test sending messages between users"""
        wp = MockWireProtocol()
        global user_db
        
        # Create sender and recipient accounts
        handle_account_creation_username(wp, {"username": "sender"})
        save_database()  # Save changes
        handle_account_creation_password(wp, {"username": "sender", "password": "pass"})
        save_database()  # Save changes
        handle_account_creation_username(wp, {"username": "recipient"})
        save_database()  # Save changes
        handle_account_creation_password(wp, {"username": "recipient", "password": "pass"})
        save_database()  # Save changes
        
        # Login sender
        handle_login(wp, {"username": "sender", "password": "pass"})
        save_database()  # Save changes
        
        # Send message
        handle_send_message(wp, {
            "sender": "user1",
            "recipient": "user2",
            "message": "Hello!"
        })
        self.assertTrue(len(wp.sent_messages) > 0)
        self.assertEqual(wp.sent_messages[0]["op_code"], "ok")
        
        # Test retrieving unread count
        handle_retrieve_unread_count(wp, {
            "username": "user2"
        })
        self.assertTrue(len(wp.sent_messages) > 1)
        self.assertEqual(wp.sent_messages[1]["op_code"], "ok")
        
        # Test loading unread messages
        handle_load_unread_messages(wp, {
            "username": "user2"
        })
        self.assertTrue(len(wp.sent_messages) > 2)
        self.assertEqual(wp.sent_messages[2]["op_code"], "ok")
        
        # Test deleting messages
        handle_delete_messages(wp, {
            "username": "user2",
            "message_ids": ["test_id"]
        })
        self.assertTrue(len(wp.sent_messages) > 3)
        self.assertEqual(wp.sent_messages[3]["op_code"], "ok")

    def test_quit_handler(self):
        """Test quit functionality"""
        wp = MockWireProtocol()
        wp.socket = None  # Mock socket
        
        # Create test user first
        user_db["user1"] = {
            "hashed_password": hash_password("user1", "pass1"),
            "session_status": "online",
            "messages": []
        }
        save_database()
        
        # Test quit - should succeed
        handle_quit(wp, {"username": "user1"})
        self.assertTrue(len(wp.sent_messages) > 0)
        self.assertEqual(wp.sent_messages[0]["op_code"], "ok")

if __name__ == '__main__':
    unittest.main()
