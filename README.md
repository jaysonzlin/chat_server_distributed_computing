# Chat Server Application

A distributed chat server application that supports both GUI and CLI interfaces. Users can create accounts, send messages, and manage their chat history.

https://youtu.be/Lq4skFlbjKA?si=3zvkBfErAt3WHU1Z

## Running the Application

### Option 1: GUI Interface

1. Start the server:
```bash
python src/chat_server.py
```

2. Launch individual GUI client(s):
```bash
python src/client_gui.py
```

3. Use the GUI to:
   - Create a new account
   - Log in with existing credentials
   - Send messages to other users
   - View and manage your message history
   - Delete messages
   - Log out when done

### Option 2: CLI Interface

1. Start the server:
```bash
python src/chat_server.py
```

2. Launch the CLI client:
```bash
python src/client.py
```

3. Available CLI commands:
   - `create <username>`: Create a new account
   - `login <username> <password>`: Log in to existing account
   - `send <recipient> <message>`: Send a message
   - `unread`: View unread message count
   - `messages`: View all messages
   - `delete <message_id>`: Delete a specific message
   - `quit`: Log out and exit

## Running Tests

To run all tests:
```bash
python -m unittest discover tests
```

To run specific test files:
```bash
python -m unittest tests/test_chat_server.py
python -m unittest tests/test_client.py
python -m unittest tests/test_json_wire_protocol.py
```

## Architecture

The application uses a client-server architecture with:
- JSON-based wire protocol and custom-based wire protocol for communication
- Persistent storage using Python's shelve module
- Thread-safe message handling
- Support for both synchronous and asynchronous message delivery
