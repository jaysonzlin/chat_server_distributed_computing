# client.py

"""
client.py

A chat client that:
- Connects to the server using JSON WireProtocol.
- Tracks current_user for login sessions.
- If it receives 'refresh_request', it automatically calls load_read_messages(10).
- Now runs an interactive loop so multiple clients can run simultaneously.
  Press Ctrl+C in any client to quit that client alone.
"""

import socket
import threading
import sys
import os
from typing import Optional, List, Dict

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_path not in sys.path:
    sys.path.append(backend_path)
from src.wire_protocols.json_wire_protocol import (
    error_response_msg, ok_response_msg,
    create_account_username_request_msg, create_account_password_request_msg,
    login_request_msg, send_message_request_msg, retrieve_unread_count_request_msg,
    load_unread_messages_request_msg, load_read_messages_request_msg,
    delete_messages_request_msg, delete_account_request_msg,
   list_accounts_request_msg, quit_request_msg
)
from src.wire_protocols.custom_wire_protocol import WireProtocol

class ChatClient:
    def __init__(self, host="127.0.0.1", port=5452):
        self.host = host
        self.port = port
        self.socket = None
        self.wire_protocol = None
        self.listening_thread = None
        self.running = False
        self.current_user = None

    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))
        self.wire_protocol = WireProtocol(self.socket)
        self.running = True

        # Start a separate thread to listen for server responses/push notifications.
        self.listening_thread = threading.Thread(target=self.listen, daemon=False)
        self.listening_thread.start()

    def listen(self):
        """
        Continuously receives responses (or push messages) from the server.
        If we see a 'refresh_request', we automatically load read messages.
        """
        while self.running:
            try:
                response = self.wire_protocol.receive()
                if not self.running:
                    break
                self.handle_server_response(response)
            except (ConnectionError, OSError):
                print("[CLIENT] Socket closed or error in listen().")
                break

        print("[CLIENT] Listening thread terminating.")

    def handle_server_response(self, response: dict):
        print("[SERVER RESPONSE]", response)
        op_code = response.get("op_code")
        if op_code == "refresh_request":
            # Automatically refresh read messages to see newly arrived message
            self.load_read_messages(10)

    def _send(self, request: dict):
        print(f"[CLIENT] Sending request: {request}")
        self.wire_protocol.send(request)

    def close(self):
        """
        Stop running, close the socket, and wait for the listening thread to finish.
        """
        self.running = False
        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.socket.close()

        if self.listening_thread and self.listening_thread.is_alive():
            self.listening_thread.join()

    #
    # ------------------ Client API Methods ------------------
    #
    def account_creation_username(self, username: str):
        request = create_account_username_request_msg(username)
        self._send(request)

    def account_creation_password(self, username: str, password: str):
        request = create_account_password_request_msg(username, password)
        self._send(request)

    def login(self, username: str, password: str):
        self.current_user = username
        request = login_request_msg(username, password)
        self._send(request)

    def send_message(self, recipient: str, message: str):
        if not self.current_user:
            print("[CLIENT WARNING] No user is logged in.")
            return
        request = send_message_request_msg(self.current_user, recipient, message)
        self._send(request)

    def read_message(self, message_id: str):
        if not self.current_user:
            print("[CLIENT WARNING] No user is logged in.")
            return
        # No request helper function for read_message, keeping the original implementation
        request = {
            "op_code": "read_message",
            "payload": {
                "username": self.current_user,
                "message_id": message_id
            }
        }
        self._send(request)

    def load_unread_messages(self, n=5):
        if not self.current_user:
            print("[CLIENT WARNING] No user is logged in.")
            return
        request = load_unread_messages_request_msg(self.current_user, n)
        self._send(request)

    def load_read_messages(self, n=5):
        if not self.current_user:
            print("[CLIENT WARNING] No user is logged in.")
            return
        request = load_read_messages_request_msg(self.current_user, n)
        self._send(request)

    def delete_messages(self, message_ids: list):
        if not self.current_user:
            print("[CLIENT WARNING] No user is logged in.")
            return
        request = delete_messages_request_msg(self.current_user, message_ids)
        self._send(request)

    def delete_account(self):
        if not self.current_user:
            print("[CLIENT WARNING] No user is logged in.")
            return
        request = delete_account_request_msg(self.current_user)
        self._send(request)
        self.current_user = None

    def list_accounts(self):
        request = list_accounts_request_msg()
        self._send(request)

    def retrieve_number_of_unread_messages(self):
        if not self.current_user:
            print("[CLIENT WARNING] No user is logged in.")
            return
        request = retrieve_unread_count_request_msg(self.current_user)
        self._send(request)

    def quit(self):
        """
        Mark user offline (if logged in), then close.
        """
        if self.current_user:
            request = quit_request_msg(self.current_user)
            self._send(request)
            self.current_user = None

        self.close()
        print("[CLIENT] Disconnected from server.")


def main():
    """
    Interactive client main loop.
    Run multiple instances of this client in different terminals,
    each connecting to the same server. 
    Press Ctrl+C in any client to quit just that one.
    """
    client = ChatClient()
    client.connect()
    print("[CLIENT] Connected to chat server.\n")

    print("Available commands (type one per line, or 'help' to repeat this list):\n")
    print("  help")
    print("  login <username> <password>")
    print("  create <username>")
    print("  createpass <username> <password>")
    print("  send <recipient> <message text>")
    print("  read <message_id>")
    print("  unread <count>")
    print("  readmessages <count>")
    print("  delete <message_id1> <message_id2> ...")
    print("  deleteaccount")
    print("  list")
    print("  unreadcount")
    print("  quit   (or press Ctrl+C)")

    try:
        while True:
            cmd_line = input("\n[CLIENT] Enter command: ").strip()
            if not cmd_line:
                continue

            parts = cmd_line.split()
            cmd = parts[0].lower()

            if cmd == "help":
                print("\nCommands:")
                print("  help")
                print("  login <username> <password>")
                print("  create <username>")
                print("  createpass <username> <password>")
                print("  send <recipient> <message text>")
                print("  read <message_id>")
                print("  unread <count>")
                print("  readmessages <count>")
                print("  delete <message_id1> <message_id2> ...")
                print("  deleteaccount")
                print("  list")
                print("  unreadcount")
                print("  quit   (or press Ctrl+C)")
                continue

            if cmd == "login":
                if len(parts) < 3:
                    print("[CLIENT] Usage: login <username> <password>")
                else:
                    username, password = parts[1], parts[2]
                    client.login(username, password)

            elif cmd == "create":
                if len(parts) < 2:
                    print("[CLIENT] Usage: create <username>")
                else:
                    username = parts[1]
                    client.account_creation_username(username)

            elif cmd == "createpass":
                if len(parts) < 3:
                    print("[CLIENT] Usage: createpass <username> <password>")
                else:
                    username, password = parts[1], parts[2]
                    client.account_creation_password(username, password)

            elif cmd == "send":
                if len(parts) < 3:
                    print("[CLIENT] Usage: send <recipient> <message text>")
                else:
                    recipient = parts[1]
                    message_text = " ".join(parts[2:])
                    client.send_message(recipient, message_text)

            elif cmd == "read":
                if len(parts) < 2:
                    print("[CLIENT] Usage: read <message_id>")
                else:
                    message_id = parts[1]
                    client.read_message(message_id)

            elif cmd == "unread":
                if len(parts) < 2:
                    print("[CLIENT] Usage: unread <number_of_messages>")
                else:
                    n = int(parts[1])
                    client.load_unread_messages(n)

            elif cmd == "readmessages":
                if len(parts) < 2:
                    print("[CLIENT] Usage: readmessages <number_of_messages>")
                else:
                    n = int(parts[1])
                    client.load_read_messages(n)

            elif cmd == "delete":
                if len(parts) < 2:
                    print("[CLIENT] Usage: delete <message_id1> <message_id2> ...")
                else:
                    message_ids = parts[1:]
                    client.delete_messages(message_ids)

            elif cmd == "deleteaccount":
                client.delete_account()

            elif cmd == "list":
                client.list_accounts()

            elif cmd == "unreadcount":
                client.retrieve_number_of_unread_messages()

            elif cmd in ("quit", "exit"):
                break

            else:
                print("[CLIENT] Unknown command. Type 'help' to see available commands.")

    except KeyboardInterrupt:
        print("\n[CLIENT] Caught Ctrl+C, shutting down...")

    finally:
        client.quit()
        sys.exit(0)

if __name__ == "__main__":
    main()
