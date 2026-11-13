import unittest
from pathlib import Path, PureWindowsPath
from simulation_semantics import canonical_state, state_digest


class SemanticPathTests(unittest.TestCase):
    def digest(self, path, **extra):
        return state_digest(canonical_state([], [], extra={'path': path, **extra}))

    def test_lazy_caches_do_not_change_semantic_path(self):
        cold, warm = Path('/tmp/same/file'), Path('/tmp/same/file')
        hash(warm); str(warm); warm.parts; warm.parent; warm.name
        self.assertEqual(self.digest(cold), self.digest(warm))
        self.assertNotEqual(self.digest(cold), self.digest(Path('/tmp/other/file')))
        self.assertNotEqual(self.digest(cold, cursor=1), self.digest(cold, cursor=2))
        self.assertNotEqual(self.digest(Path('same')), self.digest(PureWindowsPath('same')))
