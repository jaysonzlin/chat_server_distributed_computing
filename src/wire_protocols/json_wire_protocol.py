#!/usr/bin/env python3
"""
json_wire_protocol.py

This module implements the JSON wire protocol for a simple chat application.
Every message includes a protocol version (which is always 1) and an op_code
which is the name of the action. The messages are sent over sockets as JSON
objects, each terminated by a newline character.
"""

import json
import socket
from typing import Any, Dict, List

# ----------------------------------------------------------------------
# WireProtocol Class
# ----------------------------------------------------------------------
class WireProtocol:
    """
    Provides methods to send and receive JSON messages over a socket.
    Each message is encoded as UTF-8 and terminated by a newline ('\n').
    """

    def __init__(self, sock: socket.socket) -> None:
        """
        Initialize with an already-connected socket.
        """
        self.sock = sock
        self.recv_buffer = b""

    def send(self, message: Dict[str, Any]) -> None:
        """
        Send a dictionary as a JSON message over the socket.
        
        Args:
            message: The dictionary to send.
        """
        json_data = json.dumps(message) + "\n"
        self.sock.sendall(json_data.encode("utf-8"))

    def receive(self) -> Dict[str, Any]:
        """
        Receive a complete JSON message (terminated by a newline) from the socket.
        
        Returns:
            The deserialized JSON object as a Python dictionary.
            
        Raises:
            ConnectionError: If the connection is closed before a full message is received.
        """
        while b"\n" not in self.recv_buffer:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("Socket closed before a complete message was received")
            self.recv_buffer += chunk

        line, self.recv_buffer = self.recv_buffer.split(b"\n", 1)
        return json.loads(line.decode("utf-8"))

# ----------------------------------------------------------------------
# Request message helper functions
# ----------------------------------------------------------------------

def create_account_username_request_msg(username: str) -> Dict[str, Any]:
    """Create a request message for checking username availability."""
    return {
        "op_code": "create_account_username",
        "payload": {
            "username": username
        }
    }

def create_account_password_request_msg(username: str, password: str) -> Dict[str, Any]:
    """Create a request message for creating an account with password."""
    return {
        "op_code": "create_account_password",
        "payload": {
            "username": username,
            "password": password
        }
    }

def login_request_msg(username: str, password: str) -> Dict[str, Any]:
    """Create a login request message."""
    return {
        "op_code": "login",
        "payload": {
            "username": username,
            "password": password
        }
    }

def send_message_request_msg(sender: str, recipient: str, message: str) -> Dict[str, Any]:
    """Create a request message for sending a message."""
    return {
        "op_code": "send_message",
        "payload": {
            "sender": sender,
            "recipient": recipient,
            "message": message
        }
    }

def retrieve_unread_count_request_msg(username: str) -> Dict[str, Any]:
    """Create a request message for retrieving unread message count."""
    return {
        "op_code": "retrieve_unread_count",
        "payload": {
            "username": username
        }
    }

def load_unread_messages_request_msg(username: str, number_of_messages: int = 10) -> Dict[str, Any]:
    """Create a request message for loading unread messages."""
    return {
        "op_code": "load_unread_messages",
        "payload": {
            "username": username,
            "number_of_messages": number_of_messages
        }
    }

def load_read_messages_request_msg(username: str, number_of_messages: int = 10) -> Dict[str, Any]:
    """Create a request message for loading read messages."""
    return {
        "op_code": "load_read_messages",
        "payload": {
            "username": username,
            "number_of_messages": number_of_messages
        }
    }

def delete_messages_request_msg(username: str, message_ids: List[str]) -> Dict[str, Any]:
    """Create a request message for deleting messages."""
    return {
        "op_code": "delete_messages",
        "payload": {
            "username": username,
            "message_ids": message_ids
        }
    }

def delete_account_request_msg(username: str) -> Dict[str, Any]:
    """Create a request message for deleting an account."""
    return {
        "op_code": "delete_account",
        "payload": {
            "username": username
        }
    }

def list_accounts_request_msg() -> Dict[str, Any]:
    """Create a request message for listing all accounts."""
    return {
        "op_code": "list_accounts",
        "payload": {}
    }

def quit_request_msg(username: str) -> Dict[str, Any]:
    """Create a request message for quitting/logging out."""
    return {
        "op_code": "quit",
        "payload": {
            "username": username
        }
    }

# ----------------------------------------------------------------------
# JSON Protocol Response Message Constructor Functions
# Each response includes:
#   - protocol_version (always 1)
#   - op_code: the name of the action or response type
#   - payload: the response data
# ----------------------------------------------------------------------

def error_response_msg(message: str) -> Dict[str, Any]:
    """
    Constructs an error response message.
    
    Args:
        message: The error message to send.
    """
    return {
        "op_code": "error",
        "payload": {
            "message": message
        }
    }

def ok_response_msg(message: str = "Operation successful.") -> Dict[str, Any]:
    """
    Constructs a success response message.
    
    Args:
        message: Optional success message.
    """
    return {
        "op_code": "ok",
        "payload": {
            "message": message
        }
    }

def exists_response_msg(message: str = "Resource already exists.") -> Dict[str, Any]:
    """
    Constructs an exists response message.
    
    Args:
        message: Optional exists message.
    """
    return {
        "op_code": "exists",
        "payload": {
            "message": message
        }
    }

def refresh_request_msg() -> Dict[str, Any]:
    """
    Constructs a refresh request message.
    """
    return {
        "op_code": "refresh_request",
        "payload": {}
    }

def unread_count_response_msg(count: int) -> Dict[str, Any]:
    """
    Constructs a response for unread message count.
    
    Args:
        count: The number of unread messages.
    """
    return {
        "op_code": "ok",
        "payload": {
            "count": count
        }
    }

def messages_response_msg(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Constructs a response containing messages.
    
    Args:
        messages: List of message objects.
    """
    return {
        "op_code": "ok",
        "payload": {
            "messages": messages
        }
    }

def account_list_response_msg(accounts: List[str]) -> Dict[str, Any]:
    """
    Constructs a response containing list of accounts.
    
    Args:
        accounts: List of usernames.
    """
    return {
        "op_code": "ok",
        "payload": {
            "accounts": accounts
        }
    }

# ----------------------------------------------------------------------
# Example Usage
# ----------------------------------------------------------------------
if __name__ == "__main__":
    # This example demonstrates how to use the JSON wire protocol.
    # For demonstration purposes, we create a pair of connected sockets.
    import threading

    def server_simulator(server_sock: socket.socket):
        wp_server = WireProtocol(server_sock)
        try:
            while True:
                message = wp_server.receive()
                print("[Server] Received:", message)
                # Echo back a simple response with a status.
                response = {"status": "ok", "op_code": message.get("op_code")}
                wp_server.send(response)
        except ConnectionError:
            print("[Server] Connection closed.")

    # Create a pair of connected sockets for testing.
    server_sock, client_sock = socket.socketpair()

    # Start the server simulator in a separate thread.
    server_thread = threading.Thread(target=server_simulator, args=(server_sock,), daemon=True)
    server_thread.start()

    # Client side using the WireProtocol.
    wp_client = WireProtocol(client_sock)

    # Example: Create an account
    msg = account_creation_msg("alice", "secure_hashed_password")
    wp_client.send(msg)
    print("[Client] Sent:", msg)
    response = wp_client.receive()
    print("[Client] Received:", response)

    # Example: Log in
    msg = login_msg("alice", "secure_hashed_password")
    wp_client.send(msg)
    print("[Client] Sent:", msg)
    response = wp_client.receive()
    print("[Client] Received:", response)

    # Example: Retrieve number of unread messages
    msg = retrieve_unread_count_msg("alice")
    wp_client.send(msg)
    print("[Client] Sent:", msg)
    response = wp_client.receive()
    print("[Client] Received:", response)

    # Example: Retrieve unread messages (request 5 messages)
    msg = retrieve_unread_messages_msg("alice", 5)
    wp_client.send(msg)
    print("[Client] Sent:", msg)
    response = wp_client.receive()
    print("[Client] Received:", response)

    # Example: Retrieve read messages
    msg = retrieve_read_messages_msg("alice")
    wp_client.send(msg)
    print("[Client] Sent:", msg)
    response = wp_client.receive()
    print("[Client] Received:", response)

    # Example: Send a message (now including the message content)
    msg = send_message_msg("alice", "bob", "Hello Bob, how are you?")
    wp_client.send(msg)
    print("[Client] Sent:", msg)
    response = wp_client.receive()
    print("[Client] Received:", response)

    # Example: Delete messages with IDs [101, 102]
    msg = delete_messages_msg("bob", [101, 102])
    wp_client.send(msg)
    print("[Client] Sent:", msg)
    response = wp_client.receive()
    print("[Client] Received:", response)

    # Example: Delete an account
    msg = delete_account_msg("alice")
    wp_client.send(msg)
    print("[Client] Sent:", msg)
    response = wp_client.receive()
    print("[Client] Received:", response)

    # Close the sockets
    client_sock.close()
    server_sock.close()
