"""Framed compact trace with independently decodable compressed blocks.

Every record is synchronously flushed and checksummed. A new block resets the
DEFLATE dictionary, providing safe seek/resume boundaries without pickling a
compressor. JSONL is a decoded export; legacy trace input is not supported.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import struct
import zlib

MAGIC = b'COCTRACE3\n'
SYNC_MARKER = b'\x00\x00\xff\xff'
HEADER = struct.Struct('>cII')
BLOCK_RECORDS = 256
MAX_FRAME = 64 * 1024 * 1024


class TornTraceTail(ValueError):
    pass


class CorruptTrace(ValueError):
    pass


@dataclass(frozen=True)
class TraceRecord:
    payload: str
    block_offset: int
    record_in_block: int
    end_offset: int


class CompactTraceWriter:
    def __init__(self, path, *, level=6, resume=False, block_records=BLOCK_RECORDS):
        self.path = Path(path)
        self.level, self.block_records = level, block_records
        self.compressor = None
        self.in_block = 0
        self.end_offset = None
        if resume:
            # Verify complete framing first. RunTrace separately checks decoded
            # checkpoint/identity invariants before reopening for append.
            for _ in iter_records(self.path):
                pass
            self.end_offset = self.path.stat().st_size
        else:
            with self.path.open('xb') as stream:
                stream.write(MAGIC)
            self.end_offset = len(MAGIC)
        # One writer owns this append-only file. Unbuffered writes publish each
        # complete frame to readers without opening/stat-ing the path per row.
        self._stream=self.path.open('ab',buffering=0)

    def close(self):
        stream=getattr(self,'_stream',None)
        if stream is not None:stream.close()

    def __del__(self):
        self.close()

    def append(self, payload):
        if '\n' in payload:
            raise ValueError('trace payload must be one canonical JSON line')
        encoded = (payload+'\n').encode()
        if len(encoded) > MAX_FRAME:
            raise ValueError('decoded trace record exceeds configured size limit')
        start = self.compressor is None or self.in_block >= self.block_records
        if start:
            self.compressor = zlib.compressobj(self.level, zlib.DEFLATED, -15)
            self.in_block = 0
        chunk = self.compressor.compress(encoded) + self.compressor.flush(zlib.Z_SYNC_FLUSH)
        if len(chunk) > MAX_FRAME:
            raise ValueError('trace frame exceeds configured size limit')
        frame = HEADER.pack(b'D', len(chunk), zlib.crc32(chunk)) + chunk
        if start:frame=HEADER.pack(b'S',0,0)+frame
        if self._stream.closed:raise OSError('compact trace writer is closed')
        written=self._stream.write(frame)
        if written!=len(frame):raise OSError('incomplete compact trace frame write')
        self.end_offset += written
        self.in_block += 1


def iter_records(path, *, start_offset=None, end_offset=None):
    """Yield payload and rebuildable block coordinates within a fixed boundary."""
    path = Path(path)
    with path.open('rb') as stream:
        if stream.read(len(MAGIC)) != MAGIC:
            raise ValueError('unsupported causal trace format; expected current compact .ctr blocks')
        size = path.stat().st_size if end_offset is None else end_offset
        if size > path.stat().st_size or size < len(MAGIC):
            raise TornTraceTail('truncated compact trace boundary')
        if start_offset is not None:
            if start_offset < len(MAGIC) or start_offset > size:
                raise ValueError('invalid trace block offset')
            stream.seek(start_offset)
        decoder = None
        block_offset, number, last = None, 0, None
        while stream.tell() < size:
            offset = stream.tell()
            raw = stream.read(min(HEADER.size, size-offset))
            if len(raw) != HEADER.size:
                raise TornTraceTail(f'truncated compact trace frame header at {offset}')
            kind, length, checksum = HEADER.unpack(raw)
            if kind == b'S':
                if length or checksum:
                    raise CorruptTrace(f'corrupt compact trace block header at {offset}')
                decoder = zlib.decompressobj(-15)
                block_offset, number, last = offset, 0, kind
                continue
            if kind != b'D' or decoder is None or length > MAX_FRAME:
                raise CorruptTrace(f'corrupt compact trace frame at {offset}')
            if stream.tell()+length > size:
                raise TornTraceTail(f'truncated compact trace payload at {offset}')
            chunk = stream.read(length)
            if zlib.crc32(chunk) != checksum:
                raise CorruptTrace(f'corrupt compact trace checksum at {offset}')
            try:
                decoded = decoder.decompress(chunk, MAX_FRAME+1)
                if len(decoded)>MAX_FRAME or decoder.unconsumed_tail:
                    raise CorruptTrace(f'oversized compact trace record at {offset}')
                if not chunk.endswith(SYNC_MARKER) or not decoded.endswith(b'\n') or decoded.count(b'\n') != 1:
                    raise CorruptTrace(f'incomplete compact trace record at {offset}')
                payload = decoded[:-1].decode('utf-8')
            except (zlib.error, UnicodeDecodeError) as error:
                raise CorruptTrace(f'corrupt compact trace record at {offset}') from error
            last = kind
            yield TraceRecord(payload, block_offset, number, stream.tell())
            number += 1
        if last != b'D':
            raise TornTraceTail('truncated compact trace after block header')


def iter_payloads(path, *, end_offset=None):
    for record in iter_records(path, end_offset=end_offset):
        yield record.payload


def decoded_size(path, *, end_offset=None):
    return sum(len(payload.encode())+1 for payload in iter_payloads(path,end_offset=end_offset))
