from src.logger import get_logger
import socket
import sys
from typing import Any, Dict
import os
sys.path.append(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

logger = get_logger(__file__)


def varint_encode(number: int) -> bytes:
    """
    Encode a number as a varint (variable-length integer).

    Args:
        number: The number to encode.

    Returns:
        The encoded varint as a bytes object.
    """
    result = bytearray()
    # While there are more than 7 bits left in number...
    while number >= 0x80:
        # Take the lowest 7 bits of number and set the high bit to indicate more bytes follow.
        result.append((number & 0x7F) | 0x80)
        number >>= 7
    # The last byte, with high bit cleared.
    result.append(number)
    return bytes(result)


def varint_decode(data: bytes) -> int:
    """
    Decode a varint (variable-length integer) from a bytes object.

    Args:
        data: The bytes object to decode.

    Returns:
        The decoded varint as an integer.

    Raises:
        ValueError: If the provided data does not contain a complete varint.
    """
    result = 0
    shift = 0
    num_bytes = 0
    for byte in data:
        # Add the lower 7 bits of the current byte, shifted appropriately.
        result |= (byte & 0x7F) << shift
        num_bytes += 1
        # If the high bit is not set, we're done.
        if (byte & 0x80) == 0:
            return result, num_bytes
        shift += 7

    # If we run out of bytes before finding a byte with the high bit clear,
    # the varint is incomplete.
    raise ValueError("Incomplete varint byte sequence.")


# unique field names
field_names = {
    "username": 0,
    "hashed_password": 1,
    "session_status": 2,
    "messages": 3,
    "message_id": 4,
    "recipient": 5,
    "sender": 6,
    "message": 7,
    "read": 8,
    "timestamp": 9,
    "password": 10
}


field_names_reverse_mapping = {
    0: "username",
    1: "hashed_password",
    2: "session_status",
    3: "messages",
    4: "message_id",
    5: "recipient",
    6: "sender",
    7: "message",
    8: "read",
    9: "timestamp",
    10: "number_of_messages",
    11: "message_ids",
    12: "status"
}

field_names_mapping = {
    "username": 0,
    "hashed_password": 1,
    "session_status": 2,
    "messages": 3,
    "message_id": 4,
    "recipient": 5,
    "sender": 6,
    "message": 7,
    "read": 8,
    "timestamp": 9,
    "number_of_messages": 10,
    "message_ids": 11,
    "status": 12,
    "unread_count": 13
}

op_code_to_fields = {
    "create_account_username": ["username"],
    "create_account_password": ["username", "hashed_password"],
    "login": ["username", "hashed_password"],
    "retrieve_unread_count": ["username"],
    "send_message": ["sender", "recipient", "message"],
    "read_message": ["username", "message_id"],
    "load_unread_messages": ["username", "number_of_messages"],
    "load_read_messages": ["username", "messages", "number_of_messages"],
    "delete_messages": ["username", "message_ids"],
    "delete_account": ["username"],
    "list_accounts": [],
    "quit": ["username"],
    "refresh_request": ["message"],  # Server push notification
    "error": ["message"],
    "exists": ["message"],
    "ok": ["message", "unread_count", "message_id", "messages", "deleted_message_ids",
           "accounts"]
}

op_code_to_number = {
    "create_account_username": 0,
    "create_account_password": 1,
    "login": 2,
    "retrieve_unread_count": 3,
    "send_message": 4,
    "read_message": 5,
    "load_unread_messages": 6,
    "load_read_messages": 7,
    "delete_messages": 8,
    "delete_account": 9,
    "list_accounts": 10,
    "quit": 11,
    "refresh_request": 12,
    "error": 13,
    "exists": 14,
    "ok": 15,
    "refresh_request": 16
}


def pack_two_nibbles(type_value, field_name_index):
    if not (0 <= type_value <= 15 and 0 <= field_name_index <= 15):
        raise ValueError("Both numbers must be between 0 and 15 (inclusive).")

    # Shift first number left by 4 bits and combine with second number
    byte_value = (type_value << 4) | field_name_index

    # Convert to bytes
    return bytes([byte_value])


def unpack_two_nibbles(byte_value: bytes) -> tuple[int, int]:
    """
    Unpack a byte into two 4-bit numbers (nibbles).

    Args:
        byte_value: A single byte containing two 4-bit numbers

    Returns:
        A tuple of (type_value, field_name_index) where each is a 4-bit number (0-15)
    """
    if len(byte_value) != 1:
        raise ValueError("Input must be exactly one byte")

    # Convert bytes to int and extract nibbles
    value = byte_value[0]
    type_value = (value >> 4) & 0x0F  # Get upper 4 bits
    field_name_index = value & 0x0F    # Get lower 4 bits

    return (type_value, field_name_index)


def get_fields(message):
    # Create a new dict excluding protocol_version and op_code
    return {key: value for key, value in message.items()
            if key not in ['protocol_version', 'op_code']}


class WireProtocol:
    def recv_exact(self, n: int, timeout: float = 500000.0) -> bytes:
        """Ensure exactly n bytes are read from the socket with a timeout."""
        self.sock.settimeout(timeout)  # Set a timeout on the socket
        data = b""
        try:
            while len(data) < n:
                chunk = self.sock.recv(n - len(data))
                if not chunk:
                    raise ConnectionError(
                        "Socket closed while trying to read data.")
                data += chunk
            return data
        except socket.timeout:
            raise TimeoutError(
                f"Timeout: Expected {n} bytes but only received {len(data)} bytes.")

    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self.recv_buffer = b""

    def send(self, message: Dict[str, Any]) -> None:
        """
        Send a dictionary as bytes over the socket.

        Args:
            message: The dictionary to send.
        """
        print(f"\n[SEND] Starting to send message: {message}")
        magic_number = (29).to_bytes(1, "big")
        # protocol_version = varint_encode(message['protocol_version'])
        print("[SEND] message['op_code'] is ", message["op_code"])
        op_code_number = op_code_to_number[message['op_code']]
        op_code = varint_encode(op_code_number)
        print(
            f"[SEND] Op code: {message['op_code']} (number: {op_code_number}, encoded: {op_code})")

        fields = get_fields(message['payload'])
        print(f"[SEND] Fields to encode: {fields}")
        field_data = b""
        for field in fields:
            value = fields[field]
            print(
                f"\n[SEND] Processing field '{field}' with value: {value} (type: {type(value)})")
            if isinstance(value, int):
                # For integers, encode as varint
                field_data += pack_two_nibbles(0,
                                               field_names_reverse_mapping[field])
                encoded_int = varint_encode(value)
                num_bytes = len(encoded_int)
                encoded_num_bytes = varint_encode(num_bytes)
                field_data += encoded_num_bytes
                field_data += encoded_int
                print(
                    f"[SEND] Encoded integer: {encoded_int}, length: {num_bytes} bytes")
            elif isinstance(value, str):
                # For strings, encode length as varint followed by UTF-8 bytes
                print(f"[SEND] String field '{field}' - Raw value: {value}")
                field_data += pack_two_nibbles(1, field_names[field])
                print(
                    f"[SEND] Added type nibble (1) and field name index ({field_names[field]})")
                encoded_str = value.encode('utf-8')
                print(f"[SEND] UTF-8 encoded string: {encoded_str}")
                num_bytes = len(encoded_str)
                encoded_num_bytes = varint_encode(num_bytes)
                print(
                    f"[SEND] String length {num_bytes} encoded as varint: {encoded_num_bytes}")
                field_data += encoded_num_bytes
                field_data += encoded_str
                print(f"[SEND] Encoded string length: {num_bytes} bytes")
            elif isinstance(value, list) and all(isinstance(x, str) for x in value):
                # For list of strings, first encode list length, then each string
                field_data += pack_two_nibbles(2,
                                               field_names_reverse_mapping[field])
                field_data += varint_encode(len(value))
                for item in value:
                    encoded_item = item.encode('utf-8')
                    field_data += varint_encode(len(encoded_item)
                                                ) + encoded_item
                print(f"[SEND] Encoded list with {len(value)} items")
            else:
                raise ValueError(
                    f"Unsupported field type for {field}: {type(value)}")

        payload_length = len(field_data)
        payload_length_bytes = varint_encode(payload_length)
        print(f"\n[SEND] Total payload length: {payload_length} bytes")
        custom_data = b"".join(
            [magic_number, op_code, payload_length_bytes, field_data])
        print(f"[SEND] Final message size: {len(custom_data)} bytes")
        self.sock.sendall(custom_data)
        print("[SEND] Message sent successfully\n")
        print("[SEND] Final message is ", custom_data)

    def receive(self) -> Dict[str, Any]:
        """
        Receive bytes over the socket and return the decoded dictionary.

        Returns:
            The decoded dictionary.
        """
        print("\n[RECEIVE] Starting to receive message")
        # magic number
        magic_number_candidate = self.recv_exact(1)
        try:
            if not magic_number_candidate:
                print("[RECEIVE] Error: No data available for magic number")
                raise Exception("No data available for magic number")
        except Exception as e:
            logger.error(f"[Client] Error: {e}")
            print(f"[RECEIVE] Client Error: {e}")

        try:
            if magic_number_candidate != (29).to_bytes(1, "big"):
                print(
                    f"[RECEIVE] Invalid magic number received: {magic_number_candidate}")
                raise ConnectionError("Invalid magic number")
            else:
                logger.info("Correct magic number!")
                print("[RECEIVE] Correct magic number received")
        except ConnectionError as e:
            logger.error(f"[Client] ConnectionError: {e}")
            print(f"[RECEIVE] Connection Error: {e}")

        # protocol header
        try:
            # protocol version (1 byte)
            decoded_message = {}
            # protocol_version_bytes = self.sock.recv(1)
            # if not protocol_version_bytes:
            #     raise Exception("No data available for protocol version")
            # protocol_version, _ = varint_decode(protocol_version_bytes)
            # logger.info(f"Protocol version: {protocol_version}")
            # decoded_message['protocol_version'] = protocol_version

            # op code (1 byte)
            op_code_bytes = self.recv_exact(1)
            if not op_code_bytes:
                print("[RECEIVE] Error: No data available for op code")
                raise Exception("No data available for op code")
            op_code, _ = varint_decode(op_code_bytes)
            print(f"[RECEIVE] Op code decoded: {op_code}")
            decoded_message['op_code'] = op_code

            # payload length (varint)
            payload_length_bytes = self.recv_exact(1)
            if not payload_length_bytes:
                print("[RECEIVE] Error: No data available for payload length")
                raise Exception("No data available for payload length")
            payload_length, _ = varint_decode(payload_length_bytes)
            print(f"[RECEIVE] Payload length decoded: {payload_length} bytes")
            decoded_message['payload_length'] = payload_length

            # field data
            field_data = self.recv_exact(payload_length)
            if not field_data:
                print("[RECEIVE] Error: No data available for field data")
                raise Exception("No data available for field data")

            print(f"[RECEIVE] Received {len(field_data)} bytes of field data")
            type_value = None
            field_name_index = None
            field_length = None
            i = 0
            while i < len(field_data):
                if type_value is None:
                    byte = field_data[i]
                    type_value, field_name_index = unpack_two_nibbles(bytes([byte]))
                    print(f"[RECEIVE] Field type: {type_value}, Field name index: {field_name_index}")
                    i += 1
                elif field_length is None:
                    field_length, num_bytes = varint_decode(field_data[i:])
                    print(f"[RECEIVE] Field length: {field_length}, Number of bytes: {num_bytes}")
                    i += num_bytes
                else:
                    if type_value == 0:  # int
                        value, num_bytes = varint_decode(field_data[i:])
                        print(f"[RECEIVE] Decoded integer value: {value}")
                        i += num_bytes
                    elif type_value == 1:  # string
                        value = field_data[i:i+field_length].decode('utf-8')
                        print(f"[RECEIVE] Decoded string value: {value}")
                        i += field_length
                    elif type_value == 2:  # List[str]
                        value = []
                        print(f"[RECEIVE] Decoding list with {field_length} items")
                        for j in range(field_length):
                            str_len, num_bytes = varint_decode(field_data[i:])
                            i += num_bytes
                            value.append(field_data[i:i+str_len].decode('utf-8'))
                            i += str_len
                        print(f"[RECEIVE] Decoded list value: {value}")
                    else:
                        print(f"[RECEIVE] Error: Invalid type value: {type_value}")
                        raise Exception("Invalid type value")
        except Exception as e:
            logger.error(f"[Client] Error reading protocol header: {e}")
            print(f"[RECEIVE] Error reading protocol header: {e}")

        print(f"[RECEIVE] Successfully decoded message: {decoded_message}\n")
        return {
            "op_code": op_code,
            "payload_length": payload_length,
            "status": "received"
        }
