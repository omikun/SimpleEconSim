"""Bounded packed causal storage. V3 remains readable and resumable.

V4 hashes encoded packets with their previous digest and logical count. Checked
unchanged coverage expands to stable historical observations and source IDs.
"""
from __future__ import annotations
from dataclasses import dataclass
from functools import cached_property
import hashlib
import json
from pathlib import Path
import struct
import threading
import weakref
import zlib
from trace_packing import canonical, freeze, pack, unpack, PreparedEvent, COVERAGE_RULE, BASELINE_RULE
from trace_state_coverage import (CoverageBuffer, CoverageGroup, CoverageSample, capture_cell,
                            validate_group, context_of, expand_cell, expanded_count)

MAGIC = b'COCTRACE5\n'
PACKED_MAGIC = b'COCTRACE4\n'
LEGACY_MAGIC = b'COCTRACE3\n'
SYNC_MARKER = b'\x00\x00\xff\xff'
HEADER = struct.Struct('>cII')
BLOCK_RECORDS = 256
MAX_FRAME = 64 * 1024 * 1024
PACK_ROWS = 128
PACK_BYTES = 512 * 1024
PACKED_DIGEST = 'packed-payload-chain-sha256.v1'
COVERAGE_DIGEST = 'state-coverage-packet-chain-sha256.v1'
LEGACY_DIGEST = 'canonical-json-chain-sha256.v1'
_OPEN_WRITERS = weakref.WeakValueDictionary()
_OPEN_WRITERS_LOCK = threading.RLock()

class TornTraceTail(ValueError): pass
class CorruptTrace(ValueError): pass

@dataclass(frozen=True)
class TraceRecord:
    raw_payload: str | None
    block_offset: int
    record_in_block: int
    end_offset: int
    row: dict | None = None
    digest_before: str | None = None
    digest_after: str | None = None
    count_before: int | None = None
    digest_scope: str = LEGACY_DIGEST

    @cached_property
    def payload(self):
        return self.raw_payload if self.raw_payload is not None else canonical(self.row)

    @cached_property
    def checksum(self):
        if self.digest_scope in (PACKED_DIGEST, COVERAGE_DIGEST):
            return hashlib.sha256((self.digest_after + ':' + str(self.record_in_block)).encode()).hexdigest()
        return hashlib.sha256(self.payload.encode()).hexdigest()

class CompactTraceWriter:
    def __init__(self, path, *, level=6, resume=False, block_records=BLOCK_RECORDS, version=5, sparse=True):
        self.path = Path(path)
        self.level, self.block_records = level, block_records
        self.compressor = None; self.in_block = 0
        self._pending = []; self._pending_size = 0; self._failure = None
        self.digest = '0' * 64; self.logical_count = 0
        self.accepted_count = 0; self.virtual_count = 0; self.coverage_groups = 0; self._coverage = None
        self.version = version; self.sparse = sparse
        self.stats = {'packed_frames': 0, 'raw_frames': 0, 'covered_snapshots': 0,
                      'explicit_snapshots': 0, 'logical_records': 0}
        self._lock = threading.RLock()
        if resume:
            with self.path.open('rb') as stream: magic = stream.read(len(MAGIC))
            self.version = {LEGACY_MAGIC:3, PACKED_MAGIC:4, MAGIC:5}.get(magic,0)
            if not self.version: raise ValueError('unsupported causal trace format')
            for record in iter_storage_records(self.path):
                self.digest = record.digest_after; self.logical_count += 1
                if record.row and record.row.get('kind') == 'state_coverage':
                    self.virtual_count += expanded_count(record.row); self.coverage_groups += 1
            self.accepted_count = self.logical_count
            self.end_offset = self.path.stat().st_size
        else:
            if version not in (3, 4, 5): raise ValueError('unsupported causal trace version')
            with self.path.open('xb') as stream: stream.write({3:LEGACY_MAGIC,4:PACKED_MAGIC,5:MAGIC}[version])
            self.end_offset = len(MAGIC)
        self.stats['logical_records'] = self.logical_count
        self._stream = self.path.open('ab', buffering=1024 * 1024)
        self._published_file_size = self.path.stat().st_size; self._published_offset = self.end_offset
        with _OPEN_WRITERS_LOCK: _OPEN_WRITERS[str(self.path.resolve())] = self

    @property
    def digest_scope(self):
        return COVERAGE_DIGEST if self.version == 5 else PACKED_DIGEST if self.version == 4 else LEGACY_DIGEST

    @property
    def event_count(self):
        return self.accepted_count + (self._coverage is not None)

    def append_coverage(self, context, rule, fields):
        with self._lock:
            self._check_open()
            if self.version != 5: raise ValueError('grouped coverage requires V5')
            cell, size = capture_cell(rule, fields)
            if self._coverage is not None and not self._coverage.accepts(context, cell[4], size):
                self.flush_coverage()
            if self._coverage is None: self._coverage = CoverageBuffer(context, cell[4])
            self._coverage.cells.append(cell); self._coverage.size += size; self.virtual_count += 1
            if len(self._coverage.cells) >= 512 or self._coverage.size >= PACK_BYTES: self.flush_coverage()
            return CoverageSample(context,cell)

    def flush_coverage(self):
        with self._lock:
            if self._coverage is None: return
            group = self._coverage.group(); self._coverage = None
            try: self.append(group)
            except (OSError,ValueError,TypeError) as error:
                self._failure = str(error); raise
            self.coverage_groups += 1

    def _check_open(self):
        if self._stream.closed: raise OSError('compact trace writer is closed')
        if self._failure: raise OSError(self._failure)

    def _publish_stream(self):
        self._stream.flush()
        self._published_file_size += self.end_offset - self._published_offset
        self._published_offset = self.end_offset

    def close(self):
        stream = getattr(self, '_stream', None)
        if stream is not None and not stream.closed:
            with self._lock:
                try:
                    if not self._failure: self.flush_pending()
                finally:
                    stream.flush(); stream.close()
        with _OPEN_WRITERS_LOCK:
            if _OPEN_WRITERS.get(str(self.path.resolve())) is self: _OPEN_WRITERS.pop(str(self.path.resolve()), None)

    def publish(self):
        with self._lock:
            self._check_open()
            if self.path.stat().st_size != self._published_file_size: raise OSError('compact trace changed outside its active writer')
            self.flush_pending(); self._publish_stream()
            return self.end_offset

    def __del__(self):
        try: self.close()
        except (OSError, ValueError, TypeError): pass

    def _write(self, frame):
        try:
            written = self._stream.write(frame)
            if written != len(frame): raise OSError('incomplete compact trace frame write')
        except OSError as error:
            self._failure = str(error); raise
        self.end_offset += written

    def append(self, payload):
        """Dicts take the packed path; strings retain the raw framing API."""
        with self._lock:
            self._check_open()
            self.flush_coverage()
            if isinstance(payload, PreparedEvent):
                if self.version < 4:
                    return self.append(canonical(payload.expand()))
                if self._pending_size + payload.size > PACK_BYTES: self.flush_pending()
                self._pending.append(payload); self._pending_size += payload.size
                self.accepted_count += 1
                if len(self._pending) >= PACK_ROWS or self._pending_size >= PACK_BYTES: self.flush_pending()
                return
            if isinstance(payload, dict):
                if self.version == 3: return self.append(canonical(payload))
                budget = [0]
                try:
                    row = payload if isinstance(payload,CoverageGroup) else freeze(payload, budget)
                    if isinstance(payload,CoverageGroup): budget[0] = payload.size
                except RecursionError as error: raise ValueError('Circular or excessively nested JSON data') from error
                boundary = row.get('kind') == 'turn_checkpoint' or row.get('record_class') == 'metadata'
                if boundary or self._pending_size + budget[0] > PACK_BYTES: self.flush_pending()
                self._pending.append(row); self._pending_size += budget[0]
                self.accepted_count += 1
                if boundary or len(self._pending) >= PACK_ROWS or self._pending_size >= PACK_BYTES: self.flush_pending()
                return
            if not isinstance(payload, str) or '\n' in payload: raise ValueError('trace payload must be one canonical JSON line')
            self.flush_pending()
            encoded = (payload + '\n').encode()
            if len(encoded) > MAX_FRAME: raise ValueError('decoded trace record exceeds configured size limit')
            start = self.compressor is None or self.in_block >= self.block_records
            if start:
                self.compressor = zlib.compressobj(self.level, zlib.DEFLATED, -15); self.in_block = 0
            chunk = self.compressor.compress(encoded) + self.compressor.flush(zlib.Z_SYNC_FLUSH)
            if len(chunk) > MAX_FRAME: raise ValueError('trace frame exceeds configured size limit')
            frame = HEADER.pack(b'D', len(chunk), zlib.crc32(chunk)) + chunk
            if start: frame = HEADER.pack(b'S', 0, 0) + frame
            self._write(frame)
            self.digest = hashlib.sha256((self.digest + payload).encode()).hexdigest()
            self.logical_count += 1; self.stats['logical_records'] += 1; self.stats['raw_frames'] += 1
            self.accepted_count += 1
            self.in_block += 1
            if self.in_block >= self.block_records: self._publish_stream()

    def _batch(self, rows):
        packet = pack(rows, sparse=self.sparse)
        payload = canonical({'previous_digest': self.digest, 'count_before': self.logical_count, 'packet': packet})
        encoded = (payload + '\n').encode()
        if len(encoded) > PACK_BYTES and len(rows) > 1:
            mid = len(rows) // 2; self._batch(rows[:mid]); self._batch(rows[mid:]); return
        if len(encoded) > MAX_FRAME: raise ValueError('decoded packed trace exceeds configured size limit')
        compressor = zlib.compressobj(self.level, zlib.DEFLATED, -15)
        chunk = compressor.compress(encoded) + compressor.flush(zlib.Z_SYNC_FLUSH)
        if len(chunk) > MAX_FRAME: raise ValueError('packed trace frame exceeds configured size limit')
        self._write(HEADER.pack(b'S', 0, 0) + HEADER.pack(b'P', len(chunk), zlib.crc32(chunk)) + chunk)
        self.digest = hashlib.sha256(payload.encode()).hexdigest(); self.logical_count += len(rows)
        self.stats['logical_records'] += len(rows); self.stats['packed_frames'] += 1
        covered = packet['covered_observations']; self.stats['covered_snapshots'] += covered
        self.stats['explicit_snapshots'] += sum(
            row.stored.get('@rule') == COVERAGE_RULE if isinstance(row, PreparedEvent)
            else row.get('kind') == 'metric_snapshot' for row in rows) - covered
        self.compressor = None; self.in_block = 0
        self._publish_stream()

    def flush_pending(self):
        with self._lock:
            self._check_open()
            self.flush_coverage()
            if not self._pending: return
            try: self._batch(self._pending)
            except (OSError, ValueError, TypeError) as error:
                self._failure = str(error); raise
            self._pending = []; self._pending_size = 0

def _frames(path, *, start_offset=None, end_offset=None):
    path = Path(path)
    with _OPEN_WRITERS_LOCK: writer = _OPEN_WRITERS.get(str(path.resolve()))
    if writer is not None and not writer._stream.closed:
        try: writer.publish()
        except OSError as error:
            if writer._failure:
                # Inspection/recovery must still read a complete prefix after
                # a failed append, and distinguish its damaged tail from it.
                writer._stream.flush()
            elif 'changed outside its active writer' not in str(error): raise
    with path.open('rb') as stream:
        magic = stream.read(len(MAGIC)); version = {LEGACY_MAGIC:3,PACKED_MAGIC:4,MAGIC:5}.get(magic,0)
        if not version: raise ValueError('unsupported causal trace format; expected compact .ctr blocks')
        size = path.stat().st_size if end_offset is None else end_offset
        if size > path.stat().st_size or size < len(MAGIC): raise TornTraceTail('truncated compact trace boundary')
        if start_offset is not None:
            if start_offset < len(MAGIC) or start_offset > size: raise ValueError('invalid trace block offset')
            stream.seek(start_offset)
        decoder = None; block_offset = None; number = 0; last = None
        while stream.tell() < size:
            offset = stream.tell(); raw = stream.read(min(HEADER.size, size - offset))
            if len(raw) != HEADER.size: raise TornTraceTail(f'truncated compact trace frame header at {offset}')
            kind, length, checksum = HEADER.unpack(raw)
            if kind == b'S':
                if length or checksum: raise CorruptTrace(f'corrupt compact trace block header at {offset}')
                decoder = zlib.decompressobj(-15); block_offset = offset; number = 0; last = kind; continue
            if kind not in ((b'D', b'P') if version >= 4 else (b'D',)) or decoder is None or length > MAX_FRAME:
                raise CorruptTrace(f'corrupt compact trace frame at {offset}')
            if stream.tell() + length > size: raise TornTraceTail(f'truncated compact trace payload at {offset}')
            chunk = stream.read(length)
            if zlib.crc32(chunk) != checksum: raise CorruptTrace(f'corrupt compact trace checksum at {offset}')
            try:
                decoded = decoder.decompress(chunk, MAX_FRAME + 1)
                if len(decoded) > MAX_FRAME or decoder.unconsumed_tail: raise CorruptTrace(f'oversized compact trace record at {offset}')
                if not chunk.endswith(SYNC_MARKER) or not decoded.endswith(b'\n') or decoded.count(b'\n') != 1:
                    raise CorruptTrace(f'incomplete compact trace record at {offset}')
                payload = decoded[:-1].decode('utf-8')
            except (zlib.error, UnicodeDecodeError) as error:
                raise CorruptTrace(f'corrupt compact trace record at {offset}') from error
            if kind == b'P' and number: raise CorruptTrace('packed batch must start a seek block')
            last = kind
            yield version, kind, payload, block_offset, number, stream.tell()
            number += 1
        if last not in (b'D', b'P'): raise TornTraceTail('truncated compact trace after block header')

def iter_storage_records(path, *, start_offset=None, end_offset=None):
    digest = '0' * 64 if start_offset in (None, len(MAGIC)) else None
    count = 0 if digest is not None else None
    last_sequence = None
    for version, kind, payload, block, position, end in _frames(path, start_offset=start_offset, end_offset=end_offset):
        if kind == b'D':
            # A seek into a legacy/raw block has no preceding chain digest.
            # Keep it unknown until a packed envelope supplies its prefix.
            after = hashlib.sha256((digest + payload).encode()).hexdigest() if digest is not None else None
            yield TraceRecord(payload, block, position, end, digest_before=digest, digest_after=after, count_before=count)
            digest = after
            if count is not None: count += 1
            continue
        try:
            envelope = json.loads(payload); previous = envelope['previous_digest']; prior_count = envelope['count_before']
            if (type(previous) is not str or len(previous) != 64 or any(c not in '0123456789abcdef' for c in previous)
                    or type(prior_count) is not int or prior_count < 0): raise ValueError('invalid packed prefix')
            if digest is not None and digest != previous: raise ValueError('packed digest chain mismatch')
            if count is not None and count != prior_count: raise ValueError('packed logical count mismatch')
            after = hashlib.sha256(payload.encode()).hexdigest(); rows = list(unpack(envelope['packet']))
            for row in rows:
                if row.get('kind') == 'state_coverage':
                    if version != 5: raise ValueError('state coverage requires V5')
                    validate_group(row)
                if version == 5 and row.get('sequence') is not None:
                    first = row['inputs']['sequence_min'] if row.get('kind') == 'state_coverage' else row['sequence']
                    if type(first) is not int or (last_sequence is not None and first <= last_sequence):
                        raise ValueError('non-increasing V5 event sequence')
                    last_sequence = row['sequence']
            if any(row.get('kind') == 'turn_checkpoint' for row in rows) and len(rows) != 1:
                raise ValueError('checkpoint must have its own packed frame')
        except (KeyError, TypeError, ValueError, IndexError, OverflowError) as error:
            raise CorruptTrace(f'corrupt packed trace batch at {block}: {error}') from error
        for i, row in enumerate(rows):
            yield TraceRecord(None, block, i, end, row, previous, after, prior_count + i,
                              COVERAGE_DIGEST if version == 5 else PACKED_DIGEST)
        digest = after; count = prior_count + len(rows)


def iter_records(path, *, start_offset=None, end_offset=None):
    """Expanded compatibility view. Storage/index work uses iter_storage_records."""
    block = None; position = 0
    for record in iter_storage_records(path,start_offset=start_offset,end_offset=end_offset):
        if block != record.block_offset: block = record.block_offset; position = 0
        row = record.row
        if row is not None and row.get('kind') == 'state_coverage':
            context = context_of(row)
            for cell in row['inputs']['cells']:
                yield TraceRecord(None,block,position,record.end_offset,expand_cell(context,cell),
                                  record.digest_before,record.digest_after,record.count_before,record.digest_scope)
                position += 1
        else:
            yield TraceRecord(record.raw_payload,block,position,record.end_offset,row,
                              record.digest_before,record.digest_after,record.count_before,record.digest_scope)
            position += 1

def iter_payloads(path, *, end_offset=None):
    for record in iter_records(path, end_offset=end_offset): yield record.payload

def decoded_size(path, *, end_offset=None):
    return sum(len(payload.encode()) + 1 for payload in iter_payloads(path, end_offset=end_offset))

def storage_stats(path):
    stats = {'packed_frames': 0, 'raw_frames': 0, 'covered_snapshots': 0, 'explicit_snapshots': 0,
             'logical_records': 0, 'stored_bytes': Path(path).stat().st_size}
    groups = virtual = initial = 0
    for version, kind, payload, *_ in _frames(path):
        stats['version'] = version
        if kind == b'P':
            packet = json.loads(payload)['packet']; expanded = list(unpack(packet)); covered = packet['covered_observations']
            stats['packed_frames'] += 1; stats['logical_records'] += len(expanded); stats['covered_snapshots'] += covered
            stats['explicit_snapshots'] += sum(row.get('kind') == 'metric_snapshot' for row in expanded) - covered
            for row in expanded:
                if row.get('kind') == 'state_coverage':
                    cells = validate_group(row);groups += 1;virtual += len(cells)
                    stats['covered_snapshots'] += sum(cell[1] == COVERAGE_RULE for cell in cells)
                    initial += sum(cell[1] == BASELINE_RULE for cell in cells)
        else:
            stats['raw_frames'] += 1; stats['logical_records'] += 1
            try: row = json.loads(payload)
            except json.JSONDecodeError: row = None
            if isinstance(row, dict) and row.get('kind') == 'metric_snapshot': stats['explicit_snapshots'] += 1
    stats['physical_frames'] = stats['packed_frames'] + stats['raw_frames']
    stats['stored_bytes'] = Path(path).stat().st_size
    stats['event_records'] = stats['logical_records']
    stats['coverage_groups'] = groups;stats['virtual_samples'] = virtual
    stats['initial_samples'] = initial
    stats['expanded_records'] = stats['event_records']-groups+virtual
    stats['logical_records'] = stats['expanded_records']  # Legacy expanded-view alias.
    return stats
