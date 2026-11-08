"""trader_core.proto_decoder - Pure Python Upstox V3 MarketDataFeed Protobuf Decoder.

Decodes Upstox V3 WebSocket binary Protobuf frames into structured dictionaries
and normalized Tick objects without external pip dependencies (compatible with Python 3.8+).
"""

from __future__ import annotations

from dataclasses import dataclass
import struct
from typing import Any, Dict, List, Optional, Tuple, Union


class ProtobufDecodeError(ValueError):
    """Raised when incoming binary data cannot be decoded as valid Protobuf."""


# Protobuf wire types
WIRE_VARINT = 0
WIRE_64BIT = 1
WIRE_LENGTH_DELIMITED = 2
WIRE_START_GROUP = 3  # deprecated
WIRE_END_GROUP = 4    # deprecated
WIRE_32BIT = 5


def decode_varint(data: bytes, offset: int) -> Tuple[int, int]:
    """Decode a varint from data at offset.

    Returns (value, new_offset).
    """
    res = 0
    shift = 0
    length = len(data)
    while True:
        if offset >= length:
            raise ProtobufDecodeError(
                "Unexpected end of buffer while reading varint"
            )
        b = data[offset]
        offset += 1
        res |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
        if shift > 70:
            raise ProtobufDecodeError("Varint overflow: exceeds 70 bits")
    return res, offset


def encode_varint(val: int) -> bytes:
    """Encode an integer as a protobuf varint."""
    if val < 0:
        val = (1 << 64) + val
    out = bytearray()
    while val > 0x7F:
        out.append((val & 0x7F) | 0x80)
        val >>= 7
    out.append(val & 0x7F)
    return bytes(out)


def decode_tag(data: bytes, offset: int) -> Tuple[int, int, int]:
    """Decode tag: returns (field_number, wire_type, new_offset)."""
    key, offset = decode_varint(data, offset)
    field_number = key >> 3
    wire_type = key & 0x07
    if wire_type not in (
        WIRE_VARINT,
        WIRE_64BIT,
        WIRE_LENGTH_DELIMITED,
        WIRE_32BIT,
    ):
        raise ProtobufDecodeError(
            f"Invalid or unsupported wire type: {wire_type}"
        )
    return field_number, wire_type, offset


def encode_tag(field_number: int, wire_type: int) -> bytes:
    """Encode tag as varint."""
    return encode_varint((field_number << 3) | wire_type)


def skip_field(data: bytes, offset: int, wire_type: int) -> int:
    """Skip an unknown field based on its wire type."""
    if wire_type == WIRE_VARINT:
        _, offset = decode_varint(data, offset)
        return offset
    elif wire_type == WIRE_64BIT:
        if offset + 8 > len(data):
            raise ProtobufDecodeError("Truncated 64-bit field")
        return offset + 8
    elif wire_type == WIRE_LENGTH_DELIMITED:
        length, offset = decode_varint(data, offset)
        if offset + length > len(data):
            raise ProtobufDecodeError("Truncated length-delimited field")
        return offset + length
    elif wire_type == WIRE_32BIT:
        if offset + 4 > len(data):
            raise ProtobufDecodeError("Truncated 32-bit field")
        return offset + 4
    else:
        raise ProtobufDecodeError(
            f"Cannot skip unknown wire type: {wire_type}"
        )


# --- Upstox V3 Message Decoders ---

def decode_ltpc(data: bytes) -> Dict[str, Any]:
    """Decode LTPC message:

    1: ltp (double)
    2: ltt (int64)
    3: ltq (int64)
    4: cp (double)
    """
    res: Dict[str, Any] = {}
    offset = 0
    length = len(data)
    while offset < length:
        field_num, wire_type, offset = decode_tag(data, offset)
        if field_num == 1 and wire_type == WIRE_64BIT:
            if offset + 8 > length:
                raise ProtobufDecodeError("Truncated double for ltp")
            res["ltp"] = struct.unpack("<d", data[offset:offset + 8])[0]
            offset += 8
        elif field_num == 2 and wire_type == WIRE_VARINT:
            res["ltt"], offset = decode_varint(data, offset)
        elif field_num == 3 and wire_type == WIRE_VARINT:
            res["ltq"], offset = decode_varint(data, offset)
        elif field_num == 4 and wire_type == WIRE_64BIT:
            if offset + 8 > length:
                raise ProtobufDecodeError("Truncated double for cp")
            res["cp"] = struct.unpack("<d", data[offset:offset + 8])[0]
            offset += 8
        else:
            offset = skip_field(data, offset, wire_type)
    return res


def decode_quote(data: bytes) -> Dict[str, Any]:
    """Decode Quote message (market depth level):

    1: bq (int32)
    2: bp (double)
    3: bno (int32)
    4: aq (int32)
    5: ap (double)
    6: ano (int32)
    """
    res: Dict[str, Any] = {}
    offset = 0
    length = len(data)
    while offset < length:
        field_num, wire_type, offset = decode_tag(data, offset)
        if field_num == 1 and wire_type == WIRE_VARINT:
            res["bq"], offset = decode_varint(data, offset)
        elif field_num == 2 and wire_type == WIRE_64BIT:
            if offset + 8 > length:
                raise ProtobufDecodeError("Truncated double for bp")
            res["bp"] = struct.unpack("<d", data[offset:offset + 8])[0]
            offset += 8
        elif field_num == 3 and wire_type == WIRE_VARINT:
            res["bno"], offset = decode_varint(data, offset)
        elif field_num == 4 and wire_type == WIRE_VARINT:
            res["aq"], offset = decode_varint(data, offset)
        elif field_num == 5 and wire_type == WIRE_64BIT:
            if offset + 8 > length:
                raise ProtobufDecodeError("Truncated double for ap")
            res["ap"] = struct.unpack("<d", data[offset:offset + 8])[0]
            offset += 8
        elif field_num == 6 and wire_type == WIRE_VARINT:
            res["ano"], offset = decode_varint(data, offset)
        else:
            offset = skip_field(data, offset, wire_type)
    return res


def decode_market_level(data: bytes) -> Dict[str, Any]:
    """Decode MarketLevel message:

    1: bidAskQuote (repeated Quote)
    """
    quotes: List[Dict[str, Any]] = []
    offset = 0
    length = len(data)
    while offset < length:
        field_num, wire_type, offset = decode_tag(data, offset)
        if field_num == 1 and wire_type == WIRE_LENGTH_DELIMITED:
            sub_len, offset = decode_varint(data, offset)
            if offset + sub_len > length:
                raise ProtobufDecodeError("Truncated Quote message")
            quotes.append(decode_quote(data[offset:offset + sub_len]))
            offset += sub_len
        else:
            offset = skip_field(data, offset, wire_type)
    return {"bidAskQuote": quotes}


def decode_ohlc(data: bytes) -> Dict[str, Any]:
    """Decode OHLC message:

    1: interval (string)
    2: open (double)
    3: high (double)
    4: low (double)
    5: close (double)
    6: volume (int32/int64)
    7: ts (int64)
    """
    res: Dict[str, Any] = {}
    offset = 0
    length = len(data)
    while offset < length:
        field_num, wire_type, offset = decode_tag(data, offset)
        if field_num == 1 and wire_type == WIRE_LENGTH_DELIMITED:
            sub_len, offset = decode_varint(data, offset)
            if offset + sub_len > length:
                raise ProtobufDecodeError("Truncated string in OHLC")
            res["interval"] = data[offset:offset + sub_len].decode(
                "utf-8", errors="replace"
            )
            offset += sub_len
        elif field_num in (2, 3, 4, 5) and wire_type == WIRE_64BIT:
            if offset + 8 > length:
                raise ProtobufDecodeError(
                    f"Truncated double for field {field_num}"
                )
            val = struct.unpack("<d", data[offset:offset + 8])[0]
            name = {2: "open", 3: "high", 4: "low", 5: "close"}[field_num]
            res[name] = val
            offset += 8
        elif field_num == 6 and wire_type == WIRE_VARINT:
            res["volume"], offset = decode_varint(data, offset)
        elif field_num == 7 and wire_type == WIRE_VARINT:
            res["ts"], offset = decode_varint(data, offset)
        else:
            offset = skip_field(data, offset, wire_type)
    return res


def decode_market_ohlc(data: bytes) -> Dict[str, Any]:
    """Decode MarketOHLC message:

    1: ohlc (repeated OHLC)
    """
    bars: List[Dict[str, Any]] = []
    offset = 0
    length = len(data)
    while offset < length:
        field_num, wire_type, offset = decode_tag(data, offset)
        if field_num == 1 and wire_type == WIRE_LENGTH_DELIMITED:
            sub_len, offset = decode_varint(data, offset)
            if offset + sub_len > length:
                raise ProtobufDecodeError("Truncated OHLC message")
            bars.append(decode_ohlc(data[offset:offset + sub_len]))
            offset += sub_len
        else:
            offset = skip_field(data, offset, wire_type)
    return {"ohlc": bars}


def decode_market_full_feed(data: bytes) -> Dict[str, Any]:
    """Decode MarketFullFeed message:

    1: ltpc (LTPC)
    2: marketLevel (MarketLevel)
    3: optionGreeks (OptionGreeks)
    4: marketOHLC (MarketOHLC)
    5: eFeedDetails (ExtendedFeedDetails)
    """
    res: Dict[str, Any] = {}
    offset = 0
    length = len(data)
    while offset < length:
        field_num, wire_type, offset = decode_tag(data, offset)
        if field_num == 1 and wire_type == WIRE_LENGTH_DELIMITED:
            sub_len, offset = decode_varint(data, offset)
            if offset + sub_len > length:
                raise ProtobufDecodeError(
                    "Truncated LTPC in MarketFullFeed"
                )
            res["ltpc"] = decode_ltpc(data[offset:offset + sub_len])
            offset += sub_len
        elif field_num == 2 and wire_type == WIRE_LENGTH_DELIMITED:
            sub_len, offset = decode_varint(data, offset)
            if offset + sub_len > length:
                raise ProtobufDecodeError(
                    "Truncated MarketLevel in MarketFullFeed"
                )
            res["marketLevel"] = decode_market_level(
                data[offset:offset + sub_len]
            )
            offset += sub_len
        elif field_num == 4 and wire_type == WIRE_LENGTH_DELIMITED:
            sub_len, offset = decode_varint(data, offset)
            if offset + sub_len > length:
                raise ProtobufDecodeError(
                    "Truncated MarketOHLC in MarketFullFeed"
                )
            res["marketOHLC"] = decode_market_ohlc(
                data[offset:offset + sub_len]
            )
            offset += sub_len
        else:
            offset = skip_field(data, offset, wire_type)
    return res


def decode_index_full_feed(data: bytes) -> Dict[str, Any]:
    """Decode IndexFullFeed message:

    1: ltpc (LTPC)
    2: marketOHLC (MarketOHLC)
    3: lastClose (double)
    4: yh (double)
    5: yl (double)
    """
    res: Dict[str, Any] = {}
    offset = 0
    length = len(data)
    while offset < length:
        field_num, wire_type, offset = decode_tag(data, offset)
        if field_num == 1 and wire_type == WIRE_LENGTH_DELIMITED:
            sub_len, offset = decode_varint(data, offset)
            if offset + sub_len > length:
                raise ProtobufDecodeError("Truncated LTPC in IndexFullFeed")
            res["ltpc"] = decode_ltpc(data[offset:offset + sub_len])
            offset += sub_len
        elif field_num == 2 and wire_type == WIRE_LENGTH_DELIMITED:
            sub_len, offset = decode_varint(data, offset)
            if offset + sub_len > length:
                raise ProtobufDecodeError(
                    "Truncated MarketOHLC in IndexFullFeed"
                )
            res["marketOHLC"] = decode_market_ohlc(
                data[offset:offset + sub_len]
            )
            offset += sub_len
        elif field_num in (3, 4, 5) and wire_type == WIRE_64BIT:
            if offset + 8 > length:
                raise ProtobufDecodeError(
                    "Truncated double in IndexFullFeed"
                )
            val = struct.unpack("<d", data[offset:offset + 8])[0]
            name = {3: "lastClose", 4: "yh", 5: "yl"}[field_num]
            res[name] = val
            offset += 8
        else:
            offset = skip_field(data, offset, wire_type)
    return res


def decode_full_feed(data: bytes) -> Dict[str, Any]:
    """Decode FullFeed message:

    1: marketFF (MarketFullFeed)
    2: indexFF (IndexFullFeed)
    """
    res: Dict[str, Any] = {}
    offset = 0
    length = len(data)
    while offset < length:
        field_num, wire_type, offset = decode_tag(data, offset)
        if field_num == 1 and wire_type == WIRE_LENGTH_DELIMITED:
            sub_len, offset = decode_varint(data, offset)
            if offset + sub_len > length:
                raise ProtobufDecodeError("Truncated marketFF")
            res["marketFF"] = decode_market_full_feed(
                data[offset:offset + sub_len]
            )
            offset += sub_len
        elif field_num == 2 and wire_type == WIRE_LENGTH_DELIMITED:
            sub_len, offset = decode_varint(data, offset)
            if offset + sub_len > length:
                raise ProtobufDecodeError("Truncated indexFF")
            res["indexFF"] = decode_index_full_feed(
                data[offset:offset + sub_len]
            )
            offset += sub_len
        else:
            offset = skip_field(data, offset, wire_type)
    return res


def decode_feed(data: bytes) -> Dict[str, Any]:
    """Decode Feed message:

    1: ltpc (LTPC)
    2: ff (FullFeed)
    3: oc (OptionChain)
    """
    res: Dict[str, Any] = {}
    offset = 0
    length = len(data)
    while offset < length:
        field_num, wire_type, offset = decode_tag(data, offset)
        if field_num == 1 and wire_type == WIRE_LENGTH_DELIMITED:
            sub_len, offset = decode_varint(data, offset)
            if offset + sub_len > length:
                raise ProtobufDecodeError("Truncated ltpc in Feed")
            res["ltpc"] = decode_ltpc(data[offset:offset + sub_len])
            offset += sub_len
        elif field_num == 2 and wire_type == WIRE_LENGTH_DELIMITED:
            sub_len, offset = decode_varint(data, offset)
            if offset + sub_len > length:
                raise ProtobufDecodeError("Truncated ff in Feed")
            res["ff"] = decode_full_feed(data[offset:offset + sub_len])
            offset += sub_len
        else:
            offset = skip_field(data, offset, wire_type)
    return res


def decode_feeds_entry(data: bytes) -> Tuple[str, Dict[str, Any]]:
    """Decode FeedsEntry map entry:

    1: key (string)
    2: value (Feed)
    """
    key = ""
    val: Dict[str, Any] = {}
    offset = 0
    length = len(data)
    while offset < length:
        field_num, wire_type, offset = decode_tag(data, offset)
        if field_num == 1 and wire_type == WIRE_LENGTH_DELIMITED:
            sub_len, offset = decode_varint(data, offset)
            if offset + sub_len > length:
                raise ProtobufDecodeError("Truncated map key")
            key = data[offset:offset + sub_len].decode(
                "utf-8", errors="replace"
            )
            offset += sub_len
        elif field_num == 2 and wire_type == WIRE_LENGTH_DELIMITED:
            sub_len, offset = decode_varint(data, offset)
            if offset + sub_len > length:
                raise ProtobufDecodeError("Truncated map value")
            val = decode_feed(data[offset:offset + sub_len])
            offset += sub_len
        else:
            offset = skip_field(data, offset, wire_type)
    return key, val


def decode_market_data_feed(data: bytes) -> Dict[str, Any]:
    """Decode root FeedResponse message:

    1: type (enum Type: 0 = initial_feed, 1 = live_feed)
    2: feeds (map<string, Feed>)
    3: currentTs (int64)
    """
    if not isinstance(data, (bytes, bytearray)):
        raise ProtobufDecodeError("Expected bytes or bytearray")

    res: Dict[str, Any] = {
        "type": "initial_feed",
        "feeds": {},
    }
    offset = 0
    length = len(data)
    type_map = {0: "initial_feed", 1: "live_feed"}

    while offset < length:
        field_num, wire_type, offset = decode_tag(data, offset)
        if field_num == 1 and wire_type == WIRE_VARINT:
            val, offset = decode_varint(data, offset)
            res["type"] = type_map.get(val, f"unknown_type_{val}")
        elif field_num == 2 and wire_type == WIRE_LENGTH_DELIMITED:
            sub_len, offset = decode_varint(data, offset)
            if offset + sub_len > length:
                raise ProtobufDecodeError("Truncated feeds entry")
            k, v = decode_feeds_entry(data[offset:offset + sub_len])
            if k:
                res["feeds"][k] = v
            offset += sub_len
        elif field_num == 3 and wire_type == WIRE_VARINT:
            res["currentTs"], offset = decode_varint(data, offset)
        elif field_num == 4 and wire_type == WIRE_LENGTH_DELIMITED:
            sub_len, offset = decode_varint(data, offset)
            if offset + sub_len > length:
                raise ProtobufDecodeError("Truncated market_status entry")
            ms_raw = data[offset:offset + sub_len]
            # Parse repeated marketStatus entries (field 1: exchange, field 2: status)
            ms_offset = 0
            ms_len = len(ms_raw)
            status_map = {
                0: "CLOSED",
                1: "PRE_OPEN",
                2: "NORMAL_OPEN",
                3: "POST_CLOSE",
            }
            market_statuses = res.setdefault("market_status", {})
            while ms_offset < ms_len:
                f_n, w_t, ms_offset = decode_tag(ms_raw, ms_offset)
                if w_t == WIRE_LENGTH_DELIMITED:
                    entry_len, ms_offset = decode_varint(ms_raw, ms_offset)
                    entry_end = ms_offset + entry_len
                    e_offset = ms_offset
                    exch = ""
                    st_val = 0
                    while e_offset < entry_end:
                        fn_e, wt_e, e_offset = decode_tag(ms_raw, e_offset)
                        if fn_e == 1 and wt_e == WIRE_LENGTH_DELIMITED:
                            l_e, e_offset = decode_varint(ms_raw, e_offset)
                            exch = ms_raw[e_offset:e_offset + l_e].decode(
                                "utf-8", "replace"
                            )
                            e_offset += l_e
                        elif fn_e == 2 and wt_e == WIRE_VARINT:
                            st_val, e_offset = decode_varint(ms_raw, e_offset)
                        else:
                            e_offset = skip_field(ms_raw, e_offset, wt_e)
                    if exch:
                        market_statuses[exch] = status_map.get(
                            st_val, str(st_val)
                        )
                    ms_offset = entry_end
                else:
                    ms_offset = skip_field(ms_raw, ms_offset, w_t)
            offset += sub_len
        else:
            offset = skip_field(data, offset, wire_type)

    return res


# --- Encoders for Testing & Simulation ---

def _encode_length_delimited(field_number: int, content: bytes) -> bytes:
    tag = encode_tag(field_number, WIRE_LENGTH_DELIMITED)
    length = encode_varint(len(content))
    return tag + length + content


def encode_ltpc(ltpc_dict: Dict[str, Any]) -> bytes:
    out = bytearray()
    if "ltp" in ltpc_dict:
        out.extend(encode_tag(1, WIRE_64BIT))
        out.extend(struct.pack("<d", float(ltpc_dict["ltp"])))
    if "ltt" in ltpc_dict:
        out.extend(encode_tag(2, WIRE_VARINT))
        out.extend(encode_varint(int(ltpc_dict["ltt"])))
    if "ltq" in ltpc_dict:
        out.extend(encode_tag(3, WIRE_VARINT))
        out.extend(encode_varint(int(ltpc_dict["ltq"])))
    if "cp" in ltpc_dict:
        out.extend(encode_tag(4, WIRE_64BIT))
        out.extend(struct.pack("<d", float(ltpc_dict["cp"])))
    return bytes(out)


def encode_quote(quote: Dict[str, Any]) -> bytes:
    out = bytearray()
    if "bq" in quote:
        out.extend(encode_tag(1, WIRE_VARINT))
        out.extend(encode_varint(int(quote["bq"])))
    if "bp" in quote:
        out.extend(encode_tag(2, WIRE_64BIT))
        out.extend(struct.pack("<d", float(quote["bp"])))
    if "bno" in quote:
        out.extend(encode_tag(3, WIRE_VARINT))
        out.extend(encode_varint(int(quote["bno"])))
    if "aq" in quote:
        out.extend(encode_tag(4, WIRE_VARINT))
        out.extend(encode_varint(int(quote["aq"])))
    if "ap" in quote:
        out.extend(encode_tag(5, WIRE_64BIT))
        out.extend(struct.pack("<d", float(quote["ap"])))
    if "ano" in quote:
        out.extend(encode_tag(6, WIRE_VARINT))
        out.extend(encode_varint(int(quote["ano"])))
    return bytes(out)


def encode_ohlc(ohlc: Dict[str, Any]) -> bytes:
    out = bytearray()
    if "interval" in ohlc:
        interval_b = ohlc["interval"].encode("utf-8")
        out.extend(_encode_length_delimited(1, interval_b))
    if "open" in ohlc:
        out.extend(encode_tag(2, WIRE_64BIT))
        out.extend(struct.pack("<d", float(ohlc["open"])))
    if "high" in ohlc:
        out.extend(encode_tag(3, WIRE_64BIT))
        out.extend(struct.pack("<d", float(ohlc["high"])))
    if "low" in ohlc:
        out.extend(encode_tag(4, WIRE_64BIT))
        out.extend(struct.pack("<d", float(ohlc["low"])))
    if "close" in ohlc:
        out.extend(encode_tag(5, WIRE_64BIT))
        out.extend(struct.pack("<d", float(ohlc["close"])))
    if "volume" in ohlc:
        out.extend(encode_tag(6, WIRE_VARINT))
        out.extend(encode_varint(int(ohlc["volume"])))
    if "ts" in ohlc:
        out.extend(encode_tag(7, WIRE_VARINT))
        out.extend(encode_varint(int(ohlc["ts"])))
    return bytes(out)


def encode_market_full_feed(mff: Dict[str, Any]) -> bytes:
    out = bytearray()
    if "ltpc" in mff:
        out.extend(_encode_length_delimited(1, encode_ltpc(mff["ltpc"])))
    if "marketLevel" in mff:
        ml_bytes = bytearray()
        for q in mff["marketLevel"].get("bidAskQuote", []):
            ml_bytes.extend(_encode_length_delimited(1, encode_quote(q)))
        out.extend(_encode_length_delimited(2, bytes(ml_bytes)))
    if "marketOHLC" in mff:
        mohlc_bytes = bytearray()
        for bar in mff["marketOHLC"].get("ohlc", []):
            mohlc_bytes.extend(_encode_length_delimited(1, encode_ohlc(bar)))
        out.extend(_encode_length_delimited(4, bytes(mohlc_bytes)))
    return bytes(out)


def encode_feed(feed: Dict[str, Any]) -> bytes:
    out = bytearray()
    if "ltpc" in feed:
        out.extend(_encode_length_delimited(1, encode_ltpc(feed["ltpc"])))
    elif "ff" in feed:
        ff = feed["ff"]
        ff_bytes = bytearray()
        if "marketFF" in ff:
            ff_bytes.extend(
                _encode_length_delimited(1, encode_market_full_feed(ff["marketFF"]))
            )
        out.extend(_encode_length_delimited(2, bytes(ff_bytes)))
    return bytes(out)


def encode_feeds_entry(key: str, feed: Dict[str, Any]) -> bytes:
    out = bytearray()
    key_b = key.encode("utf-8")
    out.extend(_encode_length_delimited(1, key_b))
    feed_b = encode_feed(feed)
    out.extend(_encode_length_delimited(2, feed_b))
    return bytes(out)


def encode_market_data_feed(feed_response: Dict[str, Any]) -> bytes:
    """Encode a feed response dictionary into Protobuf wire-format bytes."""
    out = bytearray()
    # Tag 1: type
    type_str = feed_response.get("type", "live_feed")
    type_val = 1 if type_str == "live_feed" else 0
    out.extend(encode_tag(1, WIRE_VARINT))
    out.extend(encode_varint(type_val))

    # Tag 2: feeds map
    for k, v in feed_response.get("feeds", {}).items():
        entry_b = encode_feeds_entry(k, v)
        out.extend(_encode_length_delimited(2, entry_b))

    # Tag 3: currentTs
    if "currentTs" in feed_response:
        out.extend(encode_tag(3, WIRE_VARINT))
        out.extend(encode_varint(int(feed_response["currentTs"])))

    return bytes(out)


# --- Normalized Tick Dataclass & Extractor ---

@dataclass
class Tick:
    instrument_key: str
    ltp: float
    ltt: int  # Last traded time in ms
    ltq: int  # Last traded quantity
    cp: float  # Close price
    ohlc: Optional[List[Dict[str, Any]]] = None
    depth: Optional[List[Dict[str, Any]]] = None
    raw: Optional[Dict[str, Any]] = None


def extract_ticks(data_or_dict: Union[bytes, Dict[str, Any]]) -> Dict[str, Tick]:
    """Extract normalized Tick objects from raw bytes or a decoded dictionary."""
    if isinstance(data_or_dict, (bytes, bytearray)):
        decoded = decode_market_data_feed(bytes(data_or_dict))
    elif isinstance(data_or_dict, dict):
        decoded = data_or_dict
    else:
        raise ProtobufDecodeError("Expected bytes or dict")

    ticks: Dict[str, Tick] = {}
    for key, feed_item in decoded.get("feeds", {}).items():
        ltpc = None
        ohlc = None
        depth = None

        if "ltpc" in feed_item:
            ltpc = feed_item["ltpc"]
        elif "ff" in feed_item:
            ff = feed_item["ff"]
            if "marketFF" in ff:
                mff = ff["marketFF"]
                ltpc = mff.get("ltpc")
                if "marketOHLC" in mff:
                    ohlc = mff["marketOHLC"].get("ohlc")
                if "marketLevel" in mff:
                    depth = mff["marketLevel"].get("bidAskQuote")
            elif "indexFF" in ff:
                iff = ff["indexFF"]
                ltpc = iff.get("ltpc")
                if "marketOHLC" in iff:
                    ohlc = iff["marketOHLC"].get("ohlc")

        if ltpc and "ltp" in ltpc:
            ticks[key] = Tick(
                instrument_key=key,
                ltp=float(ltpc.get("ltp", 0.0)),
                ltt=int(ltpc.get("ltt", 0)),
                ltq=int(ltpc.get("ltq", 0)),
                cp=float(ltpc.get("cp", 0.0)),
                ohlc=ohlc,
                depth=depth,
                raw=feed_item,
            )

    return ticks
