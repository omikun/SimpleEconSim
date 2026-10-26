from pathlib import Path
import tempfile
import unittest
from trace_codec import CompactTraceWriter, CorruptTrace, TornTraceTail, iter_records, iter_payloads


class TraceBlockTests(unittest.TestCase):
    def test_independent_seek_and_resume(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'blocks.ctr';writer=CompactTraceWriter(path,block_records=2)
            for value in ('a','b','c','d','e'):writer.append(value)
            rows=list(iter_records(path));self.assertEqual(['a','b','c','d','e'],[r.payload for r in rows])
            start=rows[2].block_offset
            self.assertEqual(['c','d','e'],[r.payload for r in iter_records(path,start_offset=start)])
            CompactTraceWriter(path,resume=True).append('f')
            self.assertEqual(['a','b','c','d','e','f'],list(iter_payloads(path)))

    def test_torn_tail_and_checksum_corruption_are_different(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'blocks.ctr';writer=CompactTraceWriter(path);writer.append('a');writer.append('b')
            writer.publish()
            original=path.read_bytes();path.write_bytes(original[:-1])
            with self.assertRaises(TornTraceTail):list(iter_payloads(path))
            changed=bytearray(original);changed[-6]^=1;path.write_bytes(changed)
            with self.assertRaises(CorruptTrace):list(iter_payloads(path))


if __name__=='__main__':unittest.main()
