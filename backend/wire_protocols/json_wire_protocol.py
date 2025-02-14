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
# JSON Protocol Message Constructor Functions
# Each message includes:
#   - protocol_version (always 1)
#   - op_code: the name of the action
# ----------------------------------------------------------------------

def account_creation_msg(username: str, password: str) -> Dict[str, Any]:
    """
    Constructs a message for creating an account.
    
    Inputs:
        username: The user's login name.
        password: The user's password (assumed to be hashed or secured as needed).
    """
    return {
        "protocol_version": 1,
        "op_code": "account_creation",
        "username": username,
        "password": password,
    }

def login_msg(username: str, password: str) -> Dict[str, Any]:
    """
    Constructs a message for logging in.
    
    Inputs:
        username: The user's login name.
        password: The user's password (assumed to be hashed or secured as needed).
    """
    return {
        "protocol_version": 1,
        "op_code": "login",
        "username": username,
        "password": password,
    }

def retrieve_unread_count_msg(username: str) -> Dict[str, Any]:
    """
    Constructs a message to retrieve the number of unread messages.
    
    Inputs:
        username: The user's login name.
    """
    return {
        "protocol_version": 1,
        "op_code": "retrieve_unread_count",
        "username": username,
    }

def retrieve_unread_messages_msg(username: str, number: int) -> Dict[str, Any]:
    """
    Constructs a message to retrieve unread messages.
    
    Inputs:
        username: The user's login name.
        number: The number of unread messages to retrieve.
    """
    return {
        "protocol_version": 1,
        "op_code": "retrieve_unread_messages",
        "username": username,
        "number": number,
    }

def retrieve_read_messages_msg(username: str) -> Dict[str, Any]:
    """
    Constructs a message to retrieve read messages.
    
    Inputs:
        username: The user's login name.
    """
    return {
        "protocol_version": 1,
        "op_code": "retrieve_read_messages",
        "username": username,
    }

def send_message_msg(sender_username: str, recipient_username: str, message: str) -> Dict[str, Any]:
    """
    Constructs a message for sending a message.
    
    Inputs:
        sender_username: The username of the sender.
        recipient_username: The username of the recipient.
        message: The text content of the message.
    """
    return {
        "protocol_version": 1,
        "op_code": "send_message",
        "sender_username": sender_username,
        "recipient_username": recipient_username,
        "message": message,
    }

def delete_messages_msg(username: str, message_ids: List[int]) -> Dict[str, Any]:
    """
    Constructs a message to delete one or more messages.
    
    Inputs:
        username: The recipient's (or user's) login name.
        message_ids: A list of message identifiers to delete.
    """
    return {
        "protocol_version": 1,
        "op_code": "delete_messages",
        "username": username,
        "message_ids": message_ids,
    }

def delete_account_msg(username: str) -> Dict[str, Any]:
    """
    Constructs a message to delete an account.
    
    Inputs:
        username: The user's login name.
    """
    return {
        "protocol_version": 1,
        "op_code": "delete_account",
        "username": username,
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
                response = {"protocol_version": 1, "status": "ok", "op_code": message.get("op_code")}
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
