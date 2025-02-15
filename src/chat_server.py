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

from src.wire_protocols.custom_wire_protocol import WireProtocol

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
    response = {
        "op_code": "error",
        "payload": {
            "message": message
        }
    }
    server_send(wire_protocol, response)


# ----------------------------------------------------------------------
# Handler Functions
# ----------------------------------------------------------------------


def handle_account_creation_username(wire_protocol: WireProtocol, payload: dict):
    username = payload.get("username")
    if username in user_db:
        response = {
            "op_code": "exists",  # Instead of "status": "exists"
            "payload": {
                "message": "Username already exists. Please provide password."
            }
        }
    else:
        response = {
            "op_code": "ok",  # Instead of "status": "ok"
            "payload": {
                "message": "Username available for creation."
            }
        }

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

        response = {
            "op_code": "ok",
            "payload": {
                "message": "Account created successfully."
            }
        }
        server_send(wire_protocol, response)
    else:
        send_error(wire_protocol,
                   "Account creation failed. Username already in use.")



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

            response = {
                "op_code": "ok",
                "payload": {
                    "message": "Login successful."
                }
            }
            server_send(wire_protocol, response)
        else:
            send_error(wire_protocol, "Incorrect password.")
    else:
        send_error(wire_protocol, "Username does not exist.")


def handle_retrieve_unread_count(wire_protocol: WireProtocol, payload: dict):
    username = payload.get("username")

    if username not in user_db or user_db[username]["session_status"] != "online":
        send_error(wire_protocol, "User not online or does not exist.")
        return

    messages = user_db[username]["messages"]
    unread_count = sum(not m["read"] for m in messages)

    response = {
        "op_code": "ok",
        "payload": {
            "unread_count": unread_count
        }
    }
    server_send(wire_protocol, response)


def handle_send_message(wire_protocol: WireProtocol, payload: dict):
    """
    If recipient is offline => read=False (default).
    If recipient is online => read=True, push refresh_request.
    """
    sender = payload.get("sender")
    recipient = payload.get("recipient")
    message_text = payload.get("message")

    # Validate sender is online
    if sender not in user_db or user_db[sender]["session_status"] != "online":
        send_error(wire_protocol, "Sender is not online or does not exist.")
        return

    # Validate recipient
    if recipient not in user_db:
        send_error(wire_protocol, f"Recipient '{recipient}' does not exist.")
        return

    message_obj = create_message_object(sender, recipient, message_text)

    # If recipient is online, set read=True
    if user_db[recipient]["session_status"] == "online":
        message_obj["read"] = True

    # Append to recipient's messages
    user_db[recipient]["messages"].append(message_obj)
    save_database()

    # Acknowledge to sender
    response_to_sender = {
        "op_code": "ok",
        "payload": {
            "message": "Message sent successfully.",
            "message_id": message_obj["message_id"]
        }
    }
    server_send(wire_protocol, response_to_sender)

    # If recipient is online, push a "refresh_request"
    if user_db[recipient]["session_status"] == "online":
        recipient_wire = active_connections.get(recipient)
        if recipient_wire:
            refresh_msg = {
                "op_code": "refresh_request",
                "payload": {
                    "message": "You have a new message. Please refresh."
                }
            }
            server_send(recipient_wire, refresh_msg)


def handle_read_message(wire_protocol: WireProtocol, payload: dict):
    """
    Mark a single message as read given message_id and username.
    """
    username = payload.get("username")
    message_id = payload.get("message_id")

    if username not in user_db or user_db[username]["session_status"] != "online":
        send_error(wire_protocol, "User not online or does not exist.")
        return

    user_messages = user_db[username]["messages"]
    target_message = None
    for msg in user_messages:
        if msg["message_id"] == message_id:
            target_message = msg
            break

    if not target_message:
        send_error(wire_protocol, f"Message with ID {message_id} not found.")
        return

    target_message["read"] = True
    save_database()

    response = {
        "op_code": "ok",
        "payload": {
            "message": f"Message {message_id} marked as read."
        }
    }
    server_send(wire_protocol, response)


def handle_load_unread_messages(wire_protocol: WireProtocol, payload: dict):
    """
    Returns up to n unread messages, does NOT mark them as read.
    """
    username = payload.get("username")
    n = payload.get("number_of_messages", 5)

    if username not in user_db or user_db[username]["session_status"] != "online":
        send_error(wire_protocol, "User not online or does not exist.")
        return

    all_messages = user_db[username]["messages"]
    unread = [m for m in all_messages if not m["read"]]
    sorted_unread = sorted(unread, key=lambda m: m["timestamp"], reverse=True)
    requested_msgs = sorted_unread[:n]

    response = {
        "op_code": "ok",
        "payload": {
            "messages": requested_msgs
        }
    }
    server_send(wire_protocol, response)


def handle_load_read_messages(wire_protocol: WireProtocol, payload: dict):
    """
    Returns up to n read messages.
    """
    username = payload.get("username")
    n = payload.get("number_of_messages", 5)

    if username not in user_db or user_db[username]["session_status"] != "online":
        send_error(wire_protocol, "User not online or does not exist.")
        return

    all_messages = user_db[username]["messages"]
    read_msgs = [m for m in all_messages if m["read"]]
    sorted_read = sorted(read_msgs, key=lambda m: m["timestamp"], reverse=True)
    requested_msgs = sorted_read[:n]

    response = {
        "op_code": "ok",
        "payload": {
            "messages": requested_msgs
        }
    }
    server_send(wire_protocol, response)


def handle_delete_messages(wire_protocol: WireProtocol, payload: dict):
    username = payload.get("username")
    message_ids = payload.get("message_ids") or []

    if username not in user_db or user_db[username]["session_status"] != "online":
        send_error(wire_protocol, "User not online or does not exist.")
        return

    user_messages = user_db[username]["messages"]
    deleted = []
    remaining = []

    for msg in user_messages:
        if msg["message_id"] in message_ids:
            deleted.append(msg["message_id"])
        else:
            remaining.append(msg)

    user_db[username]["messages"] = remaining
    save_database()

    response = {
        "op_code": "ok",
        "payload": {
            "deleted_message_ids": deleted
        }
    }
    server_send(wire_protocol, response)


def handle_delete_account(wire_protocol: WireProtocol, payload: dict):
    username = payload.get("username")

    if username in user_db:
        del user_db[username]
        save_database()

        response = {
            "op_code": "ok",
            "payload": {
                "message": f"Account '{username}' deleted successfully."
            }
        }
        server_send(wire_protocol, response)
    else:
        send_error(wire_protocol, "User account not found.")


def handle_list_accounts(wire_protocol: WireProtocol, payload: dict):
    """
    Return the list of all usernames, no login required.
    """
    all_usernames = list(user_db.keys())
    response = {
        "op_code": "ok",
        "payload": {
            "accounts": all_usernames
        }
    }
    server_send(wire_protocol, response)


def handle_quit(wire_protocol: WireProtocol, payload: dict):
    username = payload.get("username")

    if username in user_db:
        user_db[username]["session_status"] = "offline"
        save_database()

        response = {
            "op_code": "ok",
            "payload": {
                "message": f"User '{username}' marked as offline."
            }
        }
        server_send(wire_protocol, response)

        # Remove ephemeral reference if present
        if username in active_connections:
            del active_connections[username]
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