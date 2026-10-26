import unittest
import os
import json
import shutil
import tempfile
from mapgen_web import (
    SLOTS_DIR,
    CURRENT_SLOT_SCHEMA_VERSION,
    migrate_slot_data,
    save_slot_to_file,
    get_all_saved_slots,
    clear_slot_file,
    set_active_slot,
)


class TestSaveSlotsSystem(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.orig_slots_dir = SLOTS_DIR
        import mapgen_web
        mapgen_web.SLOTS_DIR = self.test_dir

    def tearDown(self):
        import mapgen_web
        mapgen_web.SLOTS_DIR = self.orig_slots_dir
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_empty_slots(self):
        res = get_all_saved_slots()
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["active_slot"], 1)
        self.assertIn("1", res["slots"])
        self.assertIsNone(res["slots"]["1"])

    def test_save_and_reload_slot(self):
        sample_data = {
            "slot": 2,
            "date": "2026-09-24 15:30",
            "summary": "Test Radial Preset",
            "state": {
                "seed": 999,
                "shape": "radial",
                "polys": 32000,
            },
        }
        ok = save_slot_to_file(2, sample_data)
        self.assertTrue(ok)

        # Check file exists on disk
        slot_file = os.path.join(self.test_dir, "slot_2.json")
        self.assertTrue(os.path.exists(slot_file))

        with open(slot_file, "r", encoding="utf-8") as f:
            content = json.load(f)
        self.assertEqual(content["schema_version"], CURRENT_SLOT_SCHEMA_VERSION)
        self.assertEqual(content["state"]["seed"], 999)

        # Reload through get_all_saved_slots
        res = get_all_saved_slots()
        self.assertEqual(res["active_slot"], 2)
        self.assertIsNotNone(res["slots"]["2"])
        self.assertEqual(res["slots"]["2"]["summary"], "Test Radial Preset")

    def test_schema_migration_backwards_compatibility(self):
        # Emulate older schema version missing schema_version or with version 0
        old_data = {
            "date": "Legacy Date",
            "state": {"seed": 42},
        }
        migrated = migrate_slot_data(old_data)
        self.assertEqual(migrated["schema_version"], CURRENT_SLOT_SCHEMA_VERSION)
        self.assertEqual(migrated["state"]["seed"], 42)

    def test_clear_slot(self):
        sample_data = {
            "slot": 1,
            "state": {"seed": 123},
        }
        save_slot_to_file(1, sample_data)
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "slot_1.json")))

        ok = clear_slot_file(1)
        self.assertTrue(ok)
        self.assertFalse(os.path.exists(os.path.join(self.test_dir, "slot_1.json")))

    def test_set_active_slot(self):
        set_active_slot(3)
        res = get_all_saved_slots()
        self.assertEqual(res["active_slot"], 3)


if __name__ == "__main__":
    unittest.main()
