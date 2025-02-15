import pytest
import socket

# Import the functions and class from your module.
# Adjust the import path if needed.
from custom_wire_protocol import (
    varint_encode,
    varint_decode,
    pack_two_nibbles,
    unpack_two_nibbles,
    get_fields,
    WireProtocol,
    field_names,
    op_code_to_number,
)


class FakeSocket:
    """
    A fake socket class for testing that simulates basic recv, sendall, and timeout functionality.
    """
    def __init__(self, recv_bytes: bytes = b""):
        self.recv_buffer = recv_bytes
        self.sent_data = b""
        self.timeout = None

    def settimeout(self, timeout: float):
        self.timeout = timeout

    def recv(self, n: int) -> bytes:
        # Return up to n bytes from the buffer
        data = self.recv_buffer[:n]
        self.recv_buffer = self.recv_buffer[n:]
        return data

    def sendall(self, data: bytes) -> None:
        self.sent_data += data


def test_varint_encode_decode():
    """Test that numbers can be encoded then decoded correctly."""
    test_numbers = [0, 1, 127, 128, 300, 123456]
    for number in test_numbers:
        encoded = varint_encode(number)
        decoded, num_bytes = varint_decode(encoded)
        assert decoded == number
        assert num_bytes == len(encoded)


def test_varint_decode_incomplete():
    """Test that an incomplete varint byte sequence raises a ValueError."""
    incomplete = b'\x80'  # high-bit set but no following byte
    with pytest.raises(ValueError):
        varint_decode(incomplete)


def test_pack_unpack_two_nibbles():
    """Test that packing then unpacking two 4-bit values returns the originals."""
    test_values = [
        (0, 0),
        (1, 15),
        (15, 0),
        (15, 15),
        (7, 3),
    ]
    for type_val, field_idx in test_values:
        packed = pack_two_nibbles(type_val, field_idx)
        unpacked = unpack_two_nibbles(packed)
        assert unpacked == (type_val, field_idx)


def test_pack_two_nibbles_invalid():
    """Test that invalid nibble values raise a ValueError."""
    with pytest.raises(ValueError):
        pack_two_nibbles(16, 0)
    with pytest.raises(ValueError):
        pack_two_nibbles(0, 16)


def test_get_fields():
    """Test that get_fields removes the 'protocol_version' and 'op_code' keys."""
    message = {
        "protocol_version": 1,
        "op_code": 2,
        "username": "user",
        "hashed_password": "pass"
    }
    fields = get_fields(message)
    assert "protocol_version" not in fields
    assert "op_code" not in fields
    assert "username" in fields
    assert "hashed_password" in fields


def test_wire_protocol_send():
    """
    Test that WireProtocol.send builds the expected message bytes.
    
    For this test the message is:
      op_code: "login" (which should map to 2)
      payload: contains two string fields: "username" and "hashed_password"
    
    The expected format is:
      magic number (1 byte) +
      op_code (varint) +
      payload_length (varint) +
      field_data (for each field, the type nibble, field length as varint, and the value)
    """
    fake_socket = FakeSocket()
    protocol = WireProtocol(fake_socket)
    message = {
        "op_code": "login",  # op_code 'login' should map to 2 per op_code_to_number
        "payload": {
            "username": "testuser",
            "hashed_password": "hashvalue"
        }
    }
    protocol.send(message)
    sent_data = fake_socket.sent_data

    # Build expected bytes step by step.
    # Magic number is always 29.
    magic_number = (29).to_bytes(1, "big")
    # op_code: for "login", the mapping returns 2, encoded as a varint.
    op_code = varint_encode(op_code_to_number["login"])  # should be b'\x02'
    
    # For each field in the payload, the send() function does:
    # - For a string field:
    #    pack_two_nibbles(1, field_names[field]) +
    #    varint_encode(len(UTF8 encoded string)) +
    #    UTF8 encoded string
    username_field = pack_two_nibbles(1, field_names["username"])  # field_names["username"] is 0 → b'\x10'
    username_encoded = "testuser".encode("utf-8")
    username_length = varint_encode(len(username_encoded))  # len("testuser") == 8 → b'\x08'
    username_field_data = username_field + username_length + username_encoded

    password_field = pack_two_nibbles(1, field_names["hashed_password"])  # field_names["hashed_password"] is 1 → b'\x11'
    password_encoded = "hashvalue".encode("utf-8")
    password_length = varint_encode(len(password_encoded))  # len("hashvalue") == 9 → b'\x09'
    password_field_data = password_field + password_length + password_encoded

    field_data = username_field_data + password_field_data
    payload_length = len(field_data)
    payload_length_encoded = varint_encode(payload_length)

    expected_message = magic_number + op_code + payload_length_encoded + field_data
    assert sent_data == expected_message


def test_wire_protocol_receive():
    """
    Test that WireProtocol.receive returns the expected dictionary.
    
    To do this, we construct a fake received byte stream with:
      - magic number (29)
      - op_code (varint for 2)
      - payload_length (varint encoded to 2 bytes)
      - field_data (constructed as a valid field for a string field)
    
    For this test we craft a field representing a "username" string field.
    We choose the string length such that its varint encoding takes 2 bytes.
    (For example, 197 encodes to 2 bytes.)
    """
    # Create a field for "username":
    # 1. The type nibble for a string is 1 and field index for "username" is field_names["username"] (0).
    field_header = pack_two_nibbles(1, field_names["username"])
    # 2. Choose a string of length 197 so that its length encoding takes 2 bytes.
    L = 197
    username_str = "a" * L
    username_encoded = username_str.encode("utf-8")
    length_encoded = varint_encode(len(username_encoded))  # should be 2 bytes for 197
    # 3. field_data for this field:
    field_data = field_header + length_encoded + username_encoded

    # Ensure that the total field_data length is 1 + 2 + 197 = 200 bytes.
    payload_length = len(field_data)
    assert payload_length == 200

    # Construct the complete message:
    # - magic number: 29
    # - op_code: for op_code number 2 → varint_encode(2)
    # - payload_length: varint_encode(200) which for 200 will be 2 bytes.
    magic_number = (29).to_bytes(1, "big")
    op_code = varint_encode(2)  # b'\x02'
    payload_length_encoded = varint_encode(payload_length)  # Should produce 2 bytes because 200 >= 128

    message_bytes = magic_number + op_code + payload_length_encoded + field_data

    fake_socket = FakeSocket(recv_bytes=message_bytes)
    protocol = WireProtocol(fake_socket)
    received = protocol.receive()

    # The receive() function returns a dictionary with op_code, payload_length, and a "received" status.
    assert received["op_code"] == 2
    assert received["payload_length"] == payload_length
    assert received["status"] == "received"
