"""
chat_server.py

A single-request chat server that:
- Uses a global 'user_db' dict (persisted with shelve) to store user info.
- Uses a global 'active_connections' dict { username: wire_protocol } for ephemeral references.
- If recipient is offline, message is stored with read=False.
- If recipient is online, message is stored with read=True, and a refresh_request is sent to the recipient.
"""

from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent))

import socket
import threading
import hashlib
import uuid
import datetime
import shelve

import os

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_path not in sys.path:
    sys.path.append(backend_path)

from src.wire_protocols.json_wire_protocol import (
     error_response_msg, ok_response_msg, 
    exists_response_msg, refresh_request_msg, unread_count_response_msg,
    messages_response_msg, account_list_response_msg
)

from src.wire_protocols.custom_wire_protocol import WireProtocol
# from backend.wire_protocols.custom_wire_protocol import WireProtocol

DATABASE_FILE = "chat_server_data.db"

# Global dictionary for persistent user data (loaded/saved to shelve).
db_shelve = None
user_db = None

# Global lock to ensure single-request handling (only one thread in critical section).
server_lock = threading.Lock()

# Global ephemeral dictionary: who is currently online? { username: wire_protocol }
active_connections = {}


def init_database():
    """
    Open (or create) the shelve file and load user_db.
    Mark all users offline at startup.
    """
    global db_shelve, user_db
    db_shelve = shelve.open(DATABASE_FILE, writeback=True)
    if "user_db" not in db_shelve:
        db_shelve["user_db"] = {}
    user_db = db_shelve["user_db"]

    # Mark all users offline at startup
    for username in user_db:
        user_db[username]["session_status"] = "offline"


def save_database():
    """
    Persist user_db to shelve.
    """
    global db_shelve, user_db
    db_shelve["user_db"] = user_db
    db_shelve.sync()


def close_database():
    """
    Close the shelve.
    """
    global db_shelve
    if db_shelve is not None:
        db_shelve.close()
        db_shelve = None


def hash_password(username: str, password: str) -> str:
    """
    Returns a SHA256 hash of username+password.
    """
    return hashlib.sha256((username + password).encode()).hexdigest()


def create_message_object(sender: str, recipient: str, message: str) -> dict:
    """
    Create a new message dict with default read=False.
    """
    return {
        "message_id": str(uuid.uuid4()),
        "recipient": recipient,
        "sender": sender,
        "message": message,
        "read": False,
        "timestamp": datetime.datetime.now().isoformat()
    }


def server_send(wire_protocol: WireProtocol, response: dict):
    """
    Helper: print and send a response to a client's wire_protocol.
    """
    print(f"[SERVER] Sending response: {response}")
    wire_protocol.send(response)


def send_error(wire_protocol: WireProtocol, message: str):
    """
    Helper: send an error response to client using 'op_code'='error' 
    and putting everything else in 'payload'.
    """
    server_send(wire_protocol, error_response_msg(message))


# ----------------------------------------------------------------------
# Handler Functions
# ----------------------------------------------------------------------


def handle_account_creation_username(wire_protocol: WireProtocol, payload: dict):
    username = payload.get("username")
    if username in user_db:
        response = exists_response_msg("Username already exists. Please provide password.")
    else:
        response = ok_response_msg("Username available for creation.")

    server_send(wire_protocol, response)
    print("[SERVER] user_db after handle_account_creation_username:")
    print(user_db)


def handle_account_creation_password(wire_protocol: WireProtocol, payload: dict):
    username = payload.get("username")
    password = payload.get("password")

    if username not in user_db:
        user_db[username] = {
            "hashed_password": hash_password(username, password),
            "session_status": "offline",
            "messages": []
        }
        save_database()

        response = ok_response_msg("Account created successfully.")
        server_send(wire_protocol, response)
    else:
        send_error(wire_protocol, "Account creation failed. Username already in use.")


def handle_login(wire_protocol: WireProtocol, payload: dict):
    username = payload.get("username")
    password = payload.get("password")

    if username in user_db:
        expected_hash = user_db[username]["hashed_password"]
        if expected_hash == hash_password(username, password):
            user_db[username]["session_status"] = "online"
            save_database()

            # Store ephemeral reference in active_connections
            active_connections[username] = wire_protocol

            response = ok_response_msg("Login successful.")
            server_send(wire_protocol, response)
        else:
            send_error(wire_protocol, "Incorrect password.")
    else:
        send_error(wire_protocol, "Username does not exist.")


def handle_retrieve_unread_count(wire_protocol: WireProtocol, payload: dict):
    username = payload.get("username")
    if username in user_db and user_db[username]["session_status"] == "online":
        unread_count = sum(1 for msg in user_db[username]["messages"] if not msg["read"])
        response = unread_count_response_msg(unread_count)
        server_send(wire_protocol, response)
    else:
        send_error(wire_protocol, "User not online or does not exist.")


def handle_send_message(wire_protocol: WireProtocol, payload: dict):
    sender = payload.get("sender")
    recipient = payload.get("recipient")
    message = payload.get("message")

    # Verify sender exists and is online
    if sender not in user_db or user_db[sender]["session_status"] != "online":
        send_error(wire_protocol, "Sender is not online or does not exist.")
        return

    # Verify recipient exists
    if recipient not in user_db:
        send_error(wire_protocol, f"Recipient '{recipient}' does not exist.")
        return

    # Create and store the message
    msg_obj = create_message_object(sender, recipient, message)
    
    # If recipient is online, mark as read and send refresh request
    if user_db[recipient]["session_status"] == "online":
        msg_obj["read"] = True

    # Store message in recipient's messages
    user_db[recipient]["messages"].append(msg_obj)
    save_database()

    # Send success response to sender
    response_to_sender = ok_response_msg("Message sent successfully.")
    server_send(wire_protocol, response_to_sender)

    # If recipient is online, send them a refresh request
    if user_db[recipient]["session_status"] == "online":
        recipient_wire = active_connections.get(recipient)
        if recipient_wire:
            refresh_msg = refresh_request_msg()
            server_send(recipient_wire, refresh_msg)


def handle_load_unread_messages(wire_protocol: WireProtocol, payload: dict):
    username = payload.get("username")
    number = payload.get("number_of_messages", 10)

    if username in user_db and user_db[username]["session_status"] == "online":
        unread_messages = [
            msg for msg in user_db[username]["messages"]
            if not msg["read"]
        ][:number]
        response = messages_response_msg(unread_messages)
        server_send(wire_protocol, response)
    else:
        send_error(wire_protocol, "User not online or does not exist.")


def handle_load_read_messages(wire_protocol: WireProtocol, payload: dict):
    username = payload.get("username")
    number = payload.get("number_of_messages", 10)

    if username in user_db and user_db[username]["session_status"] == "online":
        read_messages = [
            msg for msg in user_db[username]["messages"]
            if msg["read"]
        ][:number]
        response = messages_response_msg(read_messages)
        server_send(wire_protocol, response)
    else:
        send_error(wire_protocol, "User not online or does not exist.")


def handle_delete_messages(wire_protocol: WireProtocol, payload: dict):
    username = payload.get("username")
    message_ids = payload.get("message_ids", [])

    if username in user_db and user_db[username]["session_status"] == "online":
        # Filter out messages with the specified IDs
        user_db[username]["messages"] = [
            msg for msg in user_db[username]["messages"]
            if msg["message_id"] not in message_ids
        ]
        save_database()

        response = ok_response_msg("Messages deleted successfully.")
        server_send(wire_protocol, response)
    else:
        send_error(wire_protocol, "User not online or does not exist.")


def handle_delete_account(wire_protocol: WireProtocol, payload: dict):
    username = payload.get("username")

    if username in user_db:
        # Remove from active connections if online
        if username in active_connections:
            del active_connections[username]
        # Remove from user database
        del user_db[username]
        save_database()

        response = ok_response_msg("Account deleted successfully.")
        server_send(wire_protocol, response)
    else:
        send_error(wire_protocol, "User account not found.")


def handle_list_accounts(wire_protocol: WireProtocol, payload: dict):
    response = account_list_response_msg(list(user_db.keys()))
    server_send(wire_protocol, response)


def handle_quit(wire_protocol: WireProtocol, payload: dict):
    username = payload.get("username")
    if username in user_db:
        user_db[username]["session_status"] = "offline"
        if username in active_connections:
            del active_connections[username]
        save_database()
        response = ok_response_msg("Logged out successfully.")
        server_send(wire_protocol, response)
    else:
        send_error(wire_protocol, "User not found.")


# ----------------------------------------------------------------------
# Main client_handler
# ----------------------------------------------------------------------


def client_handler(conn: socket.socket, addr: tuple):
    wire_protocol = WireProtocol(conn)
    try:
        while True:
            request = wire_protocol.receive()
            print(f"[SERVER] Received request from {addr}: {request}")

            op_code = request.get("op_code")
            payload = request.get("payload", {})

            with server_lock:
                if op_code == "create_account_username":
                    handle_account_creation_username(wire_protocol, payload)
                elif op_code == "create_account_password":
                    handle_account_creation_password(wire_protocol, payload)
                elif op_code == "login":
                    handle_login(wire_protocol, payload)
                elif op_code == "retrieve_unread_count":
                    handle_retrieve_unread_count(wire_protocol, payload)
                elif op_code == "send_message":
                    handle_send_message(wire_protocol, payload)
                elif op_code == "read_message":
                    handle_read_message(wire_protocol, payload)
                elif op_code == "load_unread_messages":
                    handle_load_unread_messages(wire_protocol, payload)
                elif op_code == "load_read_messages":
                    handle_load_read_messages(wire_protocol, payload)
                elif op_code == "delete_messages":
                    handle_delete_messages(wire_protocol, payload)
                elif op_code == "delete_account":
                    handle_delete_account(wire_protocol, payload)
                elif op_code == "list_accounts":
                    handle_list_accounts(wire_protocol, payload)
                elif op_code == "quit":
                    handle_quit(wire_protocol, payload)
                    break
                else:
                    send_error(wire_protocol, f"Unknown op_code: {op_code}")

                print("[INFO] user_db:")
                print(user_db)

    except (ConnectionError, OSError) as e:
        print(f"[INFO] Connection with {addr} ended or socket error occurred.")
        print(f"[SERVER] the error was {e}")
    finally:
        conn.close()


def start_server(host="127.0.0.1", port=5452):
    init_database()
    print("[INFO] user_db:")
    print(user_db)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen(5)
    print(f"[INFO] Server listening on {host}:{port} ...")

    try:
        while True:
            conn, addr = server_socket.accept()
            print(f"[INFO] Connection from {addr}")
            thread = threading.Thread(
                target=client_handler, args=(conn, addr), daemon=False)
            thread.start()
    except KeyboardInterrupt:
        print("[INFO] Server shutting down.")
    finally:
        close_database()
        server_socket.close()


if __name__ == "__main__":
    start_server()
