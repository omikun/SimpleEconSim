"""Exercise the actual Pygame laboratory controller and layouts without a GPU."""
import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
from pathlib import Path
import tempfile
import unittest
import pygame
from client.desktop.network_lab import Laboratory
from people_network.model import state_digest
from people_network.graph import Graph


class LaboratoryUITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app=Laboratory(save_path=Path(self.temp.name)/'save.json')
        self.addCleanup(pygame.quit)

    def test_controller_actions_rounds_history_and_load_errors(self):
        app=self.app;app.briefing=False
        app.perform('organize',dict(target='player',channel='player'))
        app.end_round();app.end_round()
        self.assertEqual(app.session.state['round'],2)
        app.persist()
        expected=state_digest(app.session.state)
        app.scrub(-1);app.end_round()
        self.assertEqual(state_digest(app.session.state),expected)
        app.history_index=None;app.end_round();app.persist(True)
        self.assertEqual(state_digest(app.session.state),expected)
        app.save_path.write_text('{broken')
        app.persist(True)
        self.assertEqual(state_digest(app.session.state),expected)
        self.assertIn('Invalid',app.message)

    def test_all_panels_fit_supported_windows_and_modal_blocks_background(self):
        app=self.app
        for size in [(1100,800),(1440,960)]:
            app.screen=pygame.display.set_mode(size)
            app.briefing=False
            for mode in ('Person','Council','Promises','Why?'):
                app.sidebar_mode=mode;app.draw()
                for rect,_,_,_ in app.buttons:
                    self.assertGreaterEqual(rect.left,0)
                    self.assertGreaterEqual(rect.top,0)
                    self.assertLessEqual(rect.right,size[0])
                    self.assertLessEqual(rect.bottom,size[1])
                self.assertEqual(len(app.markers),len(app.state['people'])+(min(8,len(Graph(app.state).contacts(app.selected))) if mode=='Person' else 0))
            app.briefing=True;app.draw()
            self.assertEqual(len(app.buttons),1,'Modal must block all background actions')


if __name__=='__main__':unittest.main()
