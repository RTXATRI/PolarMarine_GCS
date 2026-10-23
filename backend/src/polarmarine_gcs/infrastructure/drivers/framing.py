from __future__ import annotations

import binascii
import json
import struct
from typing import Any

IPC_MAX_PAYLOAD = 1024 * 1024
SERIAL_MAX_JSON = 32 * 1024
RECORD_SEPARATOR = 0x1E
LINE_FEED = 0x0A
TAB = 0x09


class FrameError(ValueError):
    pass


def encode_ipc_message(message: dict[str, Any]) -> bytes:
    payload = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(payload) > IPC_MAX_PAYLOAD:
        raise FrameError("IPC payload exceeds 1 MiB")
    return struct.pack(">I", len(payload)) + payload


class IpcFrameDecoder:
    def __init__(self, *, max_payload: int = IPC_MAX_PAYLOAD) -> None:
        self.max_payload = max_payload
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[dict[str, Any]]:
        self._buffer.extend(data)
        messages: list[dict[str, Any]] = []
        while len(self._buffer) >= 4:
            length = struct.unpack(">I", self._buffer[:4])[0]
            if length > self.max_payload:
                self._buffer.clear()
                raise FrameError(f"IPC payload length {length} exceeds limit")
            if len(self._buffer) < length + 4:
                break
            payload = bytes(self._buffer[4 : length + 4])
            del self._buffer[: length + 4]
            try:
                value = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise FrameError("Invalid IPC JSON payload") from exc
            if not isinstance(value, dict):
                raise FrameError("IPC message must be a JSON object")
            messages.append(value)
        return messages


def encode_serial_record(message: dict[str, Any]) -> bytes:
    payload = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return encode_serial_payload(payload)


def encode_serial_payload(payload: bytes) -> bytes:
    if len(payload) > SERIAL_MAX_JSON:
        raise FrameError("Serial JSON exceeds 32 KiB")
    try:
        payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FrameError("Serial JSON is not valid UTF-8") from exc
    checksum = f"{binascii.crc32(payload) & 0xFFFFFFFF:08X}".encode("ascii")
    return bytes((RECORD_SEPARATOR,)) + payload + bytes((TAB,)) + checksum + bytes((LINE_FEED,))


class SerialRecordDecoder:
    """Streaming parser for RS + JSON + TAB + CRC32 + LF records."""

    def __init__(self, *, max_json: int = SERIAL_MAX_JSON) -> None:
        self.max_json = max_json
        self._buffer = bytearray()
        self.discarded_records = 0

    def feed(self, data: bytes) -> list[dict[str, Any]]:
        self._buffer.extend(data)
        messages: list[dict[str, Any]] = []
        while self._buffer:
            start = self._buffer.find(RECORD_SEPARATOR)
            if start < 0:
                self._buffer.clear()
                break
            if start:
                del self._buffer[:start]
            next_start = self._buffer.find(RECORD_SEPARATOR, 1)
            end = self._buffer.find(LINE_FEED, 1)
            if next_start >= 0 and (end < 0 or next_start < end):
                del self._buffer[:next_start]
                self.discarded_records += 1
                continue
            if end < 0:
                if len(self._buffer) > self.max_json + 11:
                    del self._buffer[0]
                    self.discarded_records += 1
                break
            record = bytes(self._buffer[1:end])
            del self._buffer[: end + 1]
            message = self._decode_record(record)
            if message is None:
                self.discarded_records += 1
            else:
                messages.append(message)
        return messages

    def _decode_record(self, record: bytes) -> dict[str, Any] | None:
        separator = record.rfind(bytes((TAB,)))
        if separator <= 0:
            return None
        payload = record[:separator]
        checksum = record[separator + 1 :]
        if len(payload) > self.max_json or len(checksum) != 8:
            return None
        if any(value not in b"0123456789ABCDEF" for value in checksum):
            return None
        expected = f"{binascii.crc32(payload) & 0xFFFFFFFF:08X}".encode("ascii")
        if checksum != expected:
            return None
        try:
            value = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None
