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

    def test_network_names_everyone_and_advice_can_act_without_person_inspection(self):
        app=self.app;app.briefing=False
        for size in [(1100,800),(1440,960)]:
            app.screen=pygame.display.set_mode(size)
            for view in ('Terrain','Network'):
                app.map_mode=view;app.sidebar_mode='Overview';app.draw()
                if view=='Network':self.assertEqual(app.visible_labels,set(app.state['people']))
                self.assertTrue(app.insights['recommendations'])
                self.assertEqual([r['number'] for r in app.insights['recommendations']],list(range(1,len(app.insights['recommendations'])+1)))
                for rect,_,_,_ in app.buttons:self.assertLessEqual(rect.bottom,size[1])
        suggestion=next(r for r in app.insights['recommendations'] if r['kind']=='organize')
        app.perform(suggestion['kind'],suggestion['params'])
        self.assertIn(suggestion['person'],app.session.state['organizers'])
        self.assertEqual(app.sidebar_mode,'Overview')
        self.assertEqual(app.session.state['ap']['player'],1)

    def test_groups_actions_and_goal_cycle_are_reachable(self):
        app=self.app;app.briefing=False;app.sidebar_mode='Groups';app.draw()
        self.assertIn('growers',app.insights['groups'])
        app.perform('fund',dict(group='growers',donor='trade'))
        self.assertEqual(app.session.state['government']['allocations']['growers'],2)
        app.perform('agreement',dict(group='growers'))
        self.assertEqual(app.session.state['agreements'][0]['group'],'growers')
        agreement_event=next(e for e in app.session.events if e['kind']=='agreement_offered')
        self.assertIn("Cultivators",app.event_label(agreement_event))
        for _ in range(6):app.cycle_channel()
        self.assertEqual(app.channel,'player')

    def test_all_panels_fit_supported_windows_and_modal_blocks_background(self):
        app=self.app
        for size in [(1100,800),(1440,960)]:
            app.screen=pygame.display.set_mode(size)
            app.briefing=False
            for mode in ('Overview','Person','Groups','Council','Promises','Why?'):
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
