"""Compact append-only trace storage and a streaming JSONL decoder.

Version 1 stores UTF-8 JSON lines in one raw DEFLATE stream. Every appended
record ends with Z_SYNC_FLUSH, making all completed records readable before the
writer closes. The four-byte flush marker also detects a torn final write.
Existing plain JSONL traces remain readable without conversion.
"""

from __future__ import annotations

from pathlib import Path
import zlib


MAGIC = b'COCTRACE2\n'
SYNC_MARKER = b'\x00\x00\xff\xff'
READ_CHUNK = 65536


def is_compact(path):
    with Path(path).open('rb') as stream:
        return stream.read(len(MAGIC)) == MAGIC


class CompactTraceWriter:
    """One writer per new .ctr file; compressor state lives for that run."""

    def __init__(self, path, *, level=6):
        self.path = Path(path)
        self.compressor = zlib.compressobj(level, zlib.DEFLATED, -15)
        with self.path.open('xb') as stream:
            stream.write(MAGIC)

    def append(self, payload):
        data = (payload + '\n').encode('utf-8')
        chunk = self.compressor.compress(data) + self.compressor.flush(zlib.Z_SYNC_FLUSH)
        with self.path.open('ab') as stream:
            stream.write(chunk)


def iter_payloads(path):
    """Yield canonical JSON payload strings from compact or old JSONL traces."""
    path = Path(path)
    with path.open('rb') as stream:
        header = stream.read(len(MAGIC))
        if header != MAGIC:
            stream.seek(0)
            for number, raw in enumerate(stream, 1):
                if not raw.endswith(b'\n'):
                    raise ValueError(f'truncated JSONL record at line {number}')
                try:
                    yield raw[:-1].decode('utf-8')
                except UnicodeDecodeError as exc:
                    raise ValueError(f'invalid UTF-8 at line {number}') from exc
            return

        decoder = zlib.decompressobj(-15)
        pending = b''
        tail = b''
        number = 0
        while True:
            chunk = stream.read(READ_CHUNK)
            if not chunk:
                break
            tail = (tail + chunk)[-4:]
            try:
                decoded = decoder.decompress(chunk)
            except zlib.error as exc:
                raise ValueError(f'corrupt compact trace near record {number + 1}') from exc
            pending += decoded
            while b'\n' in pending:
                raw, pending = pending.split(b'\n', 1)
                number += 1
                try:
                    yield raw.decode('utf-8')
                except UnicodeDecodeError as exc:
                    raise ValueError(f'invalid UTF-8 at record {number}') from exc
        if pending or tail != SYNC_MARKER:
            raise ValueError(f'truncated compact trace after record {number}')


def decoded_size(path):
    """Byte length of the lossless JSONL export, for HTTP Content-Length."""
    return sum(len(payload.encode('utf-8')) + 1 for payload in iter_payloads(path))
