"""Exercise actual offer controls, layouts, replay and normal-play visibility."""
import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
import pygame
from client.desktop.network_patronage import PatronageLaboratory
from client.desktop.network_lab import Laboratory
from people_network.engine import command,step
from people_network.model import state_digest
from people_network.persistence import save
from scripts.playtest_people_network_patronage import click_label,ui_command,run_route


class PatronageUITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.app=PatronageLaboratory(save_path=Path(self.temp.name)/'save.json')
        self.addCleanup(pygame.quit)

    def test_offer_controls_and_map_selection_are_real_actions(self):
        app=self.app;app.draw()
        self.assertEqual(len(app.buttons),1)
        click_label(app,'Play Patronage')
        for kind,params in [('award_contract',dict(route='merchant')),('hiring_office',dict(holder='p16'))]:
            ui_command(app,dict(kind=kind,params=params))
        click_label(app,'End round')
        self.assertEqual(app.state['project']['streak'],1)
        self.assertEqual(app.state['ap']['player'],2)
        ui_command(app,dict(kind='completion_bonus',params={}))
        self.assertEqual(app.state['patronage']['contract']['bonus'],2)

    def test_all_deal_pages_panels_and_modal_fit_supported_windows(self):
        app=self.app;app.briefing=False
        command(app.session,'player','award_contract',route='merchant')
        command(app.session,'player','hiring_office',holder='p16')
        step(app.session)
        for size in ((1100,800),(1440,960)):
            app.screen=pygame.display.set_mode(size)
            for panel in ('Overview','Offers','Jobs','Power','Council','Groups','Person','Why?'):
                for page in ('Repair','Access','Records') if panel=='Offers' else ('Repair',):
                    app.sidebar_mode=panel;app.deal_page=page;app.draw()
                    for rect,_,_,_ in app.buttons:
                        self.assertGreaterEqual(rect.left,0,(panel,page))
                        self.assertGreaterEqual(rect.top,0,(panel,page))
                        self.assertLessEqual(rect.right,size[0],(panel,page))
                        self.assertLessEqual(rect.bottom,size[1],(panel,page))
            app.briefing=True;app.draw();self.assertEqual(len(app.buttons),1)
            app.briefing=False

    def test_private_rival_action_and_terms_do_not_leak_into_normal_views(self):
        app=self.app
        app.session=__import__('people_network.scenario',fromlist=['new_session']).new_session('displaced',ruleset='patronage')
        command(app.session,'rival','award_contract',route='merchant')
        command(app.session,'rival','grant_access',target='p24')
        step(app.session,rival=False)
        command(app.session,'rival','exempt',target='p08')
        action=next(e for e in reversed(app.session.events) if e['kind']=='action')
        fact=next(e for e in reversed(app.session.events) if e['kind']=='exemption')
        self.assertFalse(app.event_visible(action))
        self.assertFalse(app.event_visible(fact))
        painted=[]
        original=app.text
        def capture(words,*args,**kwargs):painted.append(str(words));return original(words,*args,**kwargs)
        app.text=capture;app.briefing=False
        for panel in ('Offers','Why?','Power','Council','Person'):
            app.sidebar_mode=panel;app.deal_page='Access';app.show_trace=True;app.draw()
        self.assertFalse(any('Known personal exemptions: Inez' in text for text in painted))
        self.assertFalse(any('Inez received a private personal exemption' in text for text in painted))
        self.assertFalse(any('contribution' in text and 'forecast' in text for text in painted))

    def test_cross_ruleset_load_does_not_replace_live_session(self):
        app=self.app
        from people_network.scenario import new_session
        save(new_session(),app.save_path)
        before=state_digest(app.state)
        app.persist(True)
        self.assertEqual(before,state_digest(app.state))
        self.assertIn('different ruleset',app.message)

    def test_private_relationship_changes_do_not_leak_as_map_weights(self):
        app=self.app;raw=app.session.state
        old=deepcopy(raw['edges']['p08>p09']['trust'])
        raw['edges']['p08>p09']['trust']['governing']=.02
        app.session.emit('structural_change','p08>p09',old,raw['edges']['p08>p09']['trust'],
                         audience=['p08','p09'],reason='private evidence')
        self.assertEqual(app.state['edges']['p08>p09']['trust'],old)
        edge=dict(source='p24',target='p02',trust=dict(governing=.3,organizing=.4),capacity=.3,available=1.)
        self.assertNotIn('p24>p02',app.state['edges'])
        raw['edges']['p24>p02']=edge
        app.session.emit('dependence','p24>p02',0,.24,audience=['p24','p02'])
        self.assertNotIn('p24>p02',app.state['edges'])

    def test_both_complete_winning_routes_can_be_clicked_and_replayed(self):
        for name in ('public','brokers'):
            report=run_route(name,Path(self.temp.name),ui=True)
            self.assertTrue(report['outcome']['won'])
            self.assertEqual(report['replay'],'passed')
            self.assertEqual(report['played_through'],'Pygame mouse hit testing')


if __name__=='__main__':unittest.main()
