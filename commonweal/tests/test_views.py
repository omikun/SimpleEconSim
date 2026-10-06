import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sim.world import World
from sim.config import Params


class ViewTests(unittest.TestCase):
    def test_state_and_person_json(self):
        w = World(Params(seed=2))
        for _ in range(240):
            w.step()
        st = json.loads(json.dumps(w.state()))
        self.assertEqual(len(st["people"]), len(w.alive()))
        self.assertIn("med_health", st["series"])
        pid = st["people"][0][0]
        person = json.loads(json.dumps(w.person(pid)))
        self.assertIn("trail", person)
        self.assertIsNone(w.person(99999))

    def test_server_module_imports(self):
        import server  # noqa: F401  (handler class + dial validation compile)


if __name__ == "__main__":
    unittest.main()
