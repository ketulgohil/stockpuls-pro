"""trader_core.dashboard.relay - WebSocket relay helpers for the cockpit.

Pure stdlib RFC 6455 WebSocket frame encoding/decoding used by the
UpstoxStreamTransport and dashboard relay server.
"""

from __future__ import annotations

import base64
import os
import struct
from typing import Optional, Tuple, Union


def encode_ws_frame(
    payload: Union[bytes, str],
    opcode: int = 1,
    mask: bool = True,
) -> bytes:
    """Encode a WebSocket data frame (RFC 6455)."""
    if isinstance(payload, str):
        payload = payload.encode("utf-8")

    fin = 0x80
    b1 = fin | opcode

    has_mask = 0x80 if mask else 0
    length = len(payload)

    if length <= 125:
        header = bytes([b1, has_mask | length])
    elif length <= 65535:
        header = bytes([b1, has_mask | 126]) + struct.pack(">H", length)
    else:
        header = bytes([b1, has_mask | 127]) + struct.pack(">Q", length)

    if mask:
        mask_key = os.urandom(4)
        masked = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
        return header + mask_key + masked
    return header + payload


def decode_ws_frame(data: bytes) -> Tuple[int, bytes, bool]:
    """Decode a WebSocket data frame.

    Returns (opcode, payload, is_final).
    """
    if len(data) < 2:
        raise ValueError("WebSocket frame too short")

    b1 = data[0]
    b2 = data[1]

    is_final = bool(b1 & 0x80)
    opcode = b1 & 0x0F
    has_mask = bool(b2 & 0x80)
    length = b2 & 0x7F

    offset = 2
    if length == 126:
        if len(data) < offset + 2:
            raise ValueError("Truncated 16-bit length")
        length = struct.unpack(">H", data[offset:offset + 2])[0]
        offset += 2
    elif length == 127:
        if len(data) < offset + 8:
            raise ValueError("Truncated 64-bit length")
        length = struct.unpack(">Q", data[offset:offset + 8])[0]
        offset += 8

    mask_key = None
    if has_mask:
        if len(data) < offset + 4:
            raise ValueError("Truncated mask key")
        mask_key = data[offset:offset + 4]
        offset += 4

    payload = data[offset:offset + length]
    if len(payload) < length:
        raise ValueError("Truncated payload")

    if mask_key is not None:
        payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))

    return opcode, payload, is_final


def read_ws_frame(sock) -> Optional[Tuple[int, bytes, bool]]:
    """Read a single WebSocket frame from a socket.

    Returns (opcode, payload, is_final) or None on clean close.
    """
    import socket

    # Read header (2 bytes minimum)
    header = b""
    while len(header) < 2:
        try:
            chunk = sock.recv(2 - len(header))
        except socket.timeout:
            return None
        if not chunk:
            return None
        header += chunk

    b1 = header[0]
    b2 = header[1]

    is_final = bool(b1 & 0x80)
    opcode = b1 & 0x0F
    has_mask = bool(b2 & 0x80)
    length = b2 & 0x7F

    if length == 126:
        length_bytes = b""
        while len(length_bytes) < 2:
            chunk = sock.recv(2 - len(length_bytes))
            if not chunk:
                return None
            length_bytes += chunk
        length = struct.unpack(">H", length_bytes)[0]
    elif length == 127:
        length_bytes = b""
        while len(length_bytes) < 8:
            chunk = sock.recv(8 - len(length_bytes))
            if not chunk:
                return None
            length_bytes += chunk
        length = struct.unpack(">Q", length_bytes)[0]

    mask_key = None
    if has_mask:
        mask_key = b""
        while len(mask_key) < 4:
            chunk = sock.recv(4 - len(mask_key))
            if not chunk:
                return None
            mask_key += chunk

    payload = b""
    while len(payload) < length:
        chunk = sock.recv(min(4096, length - len(payload)))
        if not chunk:
            return None
        payload += chunk

    if mask_key is not None:
        payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))

    return opcode, payload, is_final


