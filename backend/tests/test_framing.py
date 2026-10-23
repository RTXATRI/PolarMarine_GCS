from __future__ import annotations

import json
import struct

from hypothesis import given
from hypothesis import strategies as st

from polarmarine_gcs.domain.sequences import SequenceDisposition, SequenceTracker
from polarmarine_gcs.infrastructure.drivers.framing import (
    FrameError,
    IpcFrameDecoder,
    SerialRecordDecoder,
    encode_ipc_message,
    encode_serial_payload,
    encode_serial_record,
)


@given(st.dictionaries(st.text(min_size=1, max_size=12), st.integers(), max_size=8))
def test_serial_round_trip_survives_every_split(message: dict[str, int]) -> None:
    frame = encode_serial_record(message)
    for split in range(len(frame) + 1):
        decoder = SerialRecordDecoder()
        assert decoder.feed(frame[:split]) + decoder.feed(frame[split:]) == [message]


def test_serial_parser_handles_noise_glued_frames_crc_error_and_resynchronization() -> None:
    valid_a = encode_serial_record({"sequence": 1})
    corrupt = bytearray(encode_serial_record({"sequence": 2}))
    corrupt[-3] = ord("0") if corrupt[-3] != ord("0") else ord("1")
    valid_b = encode_serial_record({"sequence": 3})
    decoder = SerialRecordDecoder()
    messages = decoder.feed(b"noise" + valid_a + bytes(corrupt) + b"junk" + valid_b)
    assert messages == [{"sequence": 1}, {"sequence": 3}]
    assert decoder.discarded_records >= 1


def test_serial_parser_drops_oversize_record_and_finds_next_record() -> None:
    decoder = SerialRecordDecoder(max_json=16)
    oversized = bytes((0x1E,)) + b"x" * 30
    assert decoder.feed(oversized + encode_serial_record({"ok": True})) == [{"ok": True}]


def test_serial_crc_covers_only_json_bytes() -> None:
    payload = json.dumps({"text": "极地"}, ensure_ascii=False, separators=(",", ":")).encode()
    frame = encode_serial_payload(payload)
    assert frame[0] == 0x1E and frame[-1] == 0x0A
    assert frame[-10] == 0x09
    assert frame[-9:-1].decode().isalnum()


def test_ipc_decoder_handles_half_and_glued_frames() -> None:
    first = encode_ipc_message({"type": "one"})
    second = encode_ipc_message({"type": "two"})
    decoder = IpcFrameDecoder()
    assert decoder.feed(first[:2]) == []
    assert decoder.feed(first[2:] + second) == [{"type": "one"}, {"type": "two"}]


def test_ipc_decoder_rejects_a_payload_larger_than_one_mibibyte() -> None:
    decoder = IpcFrameDecoder()
    try:
        decoder.feed(struct.pack(">I", 1024 * 1024 + 1))
    except FrameError as exc:
        assert "exceeds" in str(exc)
    else:
        raise AssertionError("Oversize frame was accepted")


def test_sequence_tracker_accepts_uint32_rollover_and_rejects_old_data() -> None:
    tracker = SequenceTracker()
    assert tracker.observe("link-a", 0xFFFFFFFE) is SequenceDisposition.NEW
    assert tracker.observe("link-a", 0xFFFFFFFF) is SequenceDisposition.NEW
    assert tracker.observe("link-a", 0) is SequenceDisposition.NEW
    assert tracker.observe("link-a", 0) is SequenceDisposition.DUPLICATE
    assert tracker.observe("link-a", 0xFFFFFFFF) is SequenceDisposition.OUT_OF_ORDER
