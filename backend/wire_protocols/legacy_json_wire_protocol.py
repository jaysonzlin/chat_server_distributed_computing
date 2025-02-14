#!/usr/bin/env python3
"""
json_wire_protocol.py

This module implements the wire protocol for a simple chat application.
Communication is performed using JSON messages over sockets, with one JSON
object per line (newline-delimited).
"""

import json
import socket
from typing import Any, Dict, List


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
        # Ensure the entire message is sent.
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

        # Split out the first full message (line)
        line, self.recv_buffer = self.recv_buffer.split(b"\n", 1)
        return json.loads(line.decode("utf-8"))


# --- Protocol Message Constructors ---

def create_account_msg(username: str, password_hash: str) -> Dict[str, Any]:
    """
    Constructs a message for creating an account.
    
    The password should be hashed before calling this function.
    """
    return {
        "action": "create_account",
        "username": username,
        "password_hash": password_hash
    }


def login_msg(username: str, password_hash: str) -> Dict[str, Any]:
    """
    Constructs a message for logging in.
    """
    return {
        "action": "login",
        "username": username,
        "password_hash": password_hash
    }


def list_accounts_msg(pattern: str = "*", page: int = 0) -> Dict[str, Any]:
    """
    Constructs a message to list accounts.
    
    Args:
        pattern: A wildcard pattern to filter accounts.
        page: The page number for pagination (if many accounts exist).
    """
    return {
        "action": "list_accounts",
        "pattern": pattern,
        "page": page
    }


def send_message_msg(recipient: str, message_text: str) -> Dict[str, Any]:
    """
    Constructs a message to send a text message to a recipient.
    
    Args:
        recipient: The username of the message recipient.
        message_text: The text message.
    """
    return {
        "action": "send_message",
        "recipient": recipient,
        "message": message_text
    }


def read_messages_msg(num_messages: int) -> Dict[str, Any]:
    """
    Constructs a message to request delivery of a specific number of messages.
    
    Args:
        num_messages: The number of messages to be retrieved.
    """
    return {
        "action": "read_messages",
        "number": num_messages
    }


def delete_messages_msg(message_ids: List[int]) -> Dict[str, Any]:
    """
    Constructs a message to delete one or more messages.
    
    Args:
        message_ids: A list of message identifiers to delete.
    """
    return {
        "action": "delete_messages",
        "message_ids": message_ids
    }


def delete_account_msg(username: str) -> Dict[str, Any]:
    """
    Constructs a message to delete an account.
    
    Semantics regarding unread messages should be handled appropriately
    by the server.
    """
    return {
        "action": "delete_account",
        "username": username
    }


# --- Example Usage ---
if __name__ == "__main__":
    # This example demonstrates how to use the WireProtocol class.
    # For a complete application, the socket should be connected to the server.
    # Here, we create a dummy loopback socket pair for demonstration.
    import threading

    def server_simulator(server_sock: socket.socket):
        wp_server = WireProtocol(server_sock)
        try:
            while True:
                message = wp_server.receive()
                print("[Server] Received:", message)
                # Echo back a simple response with a status.
                response = {"status": "ok", "action": message.get("action")}
                wp_server.send(response)
        except ConnectionError:
            print("[Server] Connection closed.")

    # Create a pair of connected sockets
    server_sock, client_sock = socket.socketpair()

    # Start the server simulator in a separate thread
    server_thread = threading.Thread(target=server_simulator, args=(server_sock,), daemon=True)
    server_thread.start()

    # Client side using the WireProtocol
    wp_client = WireProtocol(client_sock)

    # Example: Create an account
    msg = create_account_msg("alice", "hashed_password_example")
    wp_client.send(msg)
    print("[Client] Sent:", msg)
    response = wp_client.receive()
    print("[Client] Received:", response)

    # Example: Send a message
    msg = send_message_msg("bob", "Hello Bob!")
    wp_client.send(msg)
    print("[Client] Sent:", msg)
    response = wp_client.receive()
    print("[Client] Received:", response)

    # Close the sockets
    client_sock.close()
    server_sock.close()
