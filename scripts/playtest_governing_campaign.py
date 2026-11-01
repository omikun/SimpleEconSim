"""Play grain-policy routes through the primary renderer and real button targets."""

import argparse
import json
from pathlib import Path
import random

import numpy as np
import pygame

from client.desktop.app import render_frame
from client.desktop.engine import build_world_view
from client.desktop.panels.scenario_ui import guided_ui_hit
from governing_actions import project_actions
from governing_network import project
from world_config import get_map_topology, set_map_topology
from scripts.governing_campaign_driver import resolve_notices


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--route', choices=('buy', 'requisition', 'market'), default='buy')
    parser.add_argument('--steps', type=int, default=7)
    parser.add_argument('--output-dir', type=Path, default=Path('outputs/governing_network/governing-ui'))
    args = parser.parse_args()
    output = args.output_dir / args.route
    output.mkdir(parents=True, exist_ok=True)
    pygame.init()
    screen = pygame.display.set_mode((1400, 900))
    previous = get_map_topology()
    try:
        set_map_topology('voronoi')
        world = build_world_view(scenario_id='egypt_1877', governing_network_mode='governing')
        from random_cache import rand
        random.seed(1877)
        np.random.seed(1877)
        rand._idx = rand._capacity
        world.update(ui_mode='guided', use_gpu_pipeline=False)
        commands, snapshots, notices = [], [], []

        def draw(filename=None):
            pygame.event.pump()
            render_frame(screen, world)
            if filename:
                pygame.image.save(screen, str(output / filename))

        def click(action):
            draw()
            target = next((t for t in world['_ui_targets'] if t.scope == 'guided' and t.action == action), None)
            if target is None or not guided_ui_hit(target.rect.center, world):
                raise AssertionError(f'Unavailable real control: {action}')

        def snapshot():
            info = project(world)
            return dict(turn=world['turn'], treasury=project_actions(world)['treasury'],
                        public_maize=project_actions(world)['public_maize'],
                        private_maize=project_actions(world)['private_maize'],
                        organized=info['organized_people'], walkouts=info['network_strikers'],
                        planned=sum(row['planned_strikers'] for row in info['locations']),
                        underfed=info['communities'][0]['underfed'],
                        explanation=info['recent_explanation'],
                        debt=world['scenario_state']['payment_status'],
                        ending=world['scenario_state']['ending'])

        draw('opening.png')
        snapshots.append(snapshot())
        click('governing_all_policies')
        draw('all-policies.png')
        click('governing_back')
        route_action = dict(buy='buy_private_grain', requisition='requisition_private_grain',
                            market='open_private_grain_market')[args.route]
        for _ in range(args.steps):
            notices.extend(resolve_notices(world, draw))
            state, turn = world['scenario_state'], int(world['turn'])
            if state['ending']:
                break
            choices = project_actions(world)
            action = ('release_maize' if turn == 1 else route_action if turn == 2 else
                      'release_maize' if turn == 3 and args.route != 'market' else None)
            rationale = ('Feed people from existing public stocks.' if turn == 1 else
                         'Compare treasury payment, property seizure and cash-dependent private sales.' if turn == 2 else
                         'Acquired public grain still needs distribution.' if turn == 3 else '')
            if choices['debt']:
                affordable = next((a for a in choices['debt'] if a['enabled']), None)
                action = affordable['id'] if affordable else None
                rationale = 'Debt is due; use an available existing fiscal response.'
            available = choices['food'] + choices['debt'] + list(choices['responses'].values())
            option = next((a for a in available if a['id'] == action and a['enabled']), None)
            if option:
                click(('governing_action', option['id'], option['tile']))
                commands.append(dict(turn=turn, action=option['id'], rationale=rationale,
                                     ui_label=option['label'], ui_cost=option['detail'],
                                     result=world['scenario_feedback']))
                if state['last_action_turn'] != turn:
                    raise AssertionError('The policy did not consume the existing decision.')
            click('step_next')
            notices.extend(resolve_notices(world, draw))
            snapshots.append(snapshot())
            if world['turn'] in (2, 4, 6, 8):
                draw(f'turn-{world["turn"]}.png')
        draw('final.png')
        report = dict(passed=True, route=args.route, commands=commands, snapshots=snapshots, notices=notices,
                      political_upkeep_actions=0,
                      note='Actual policy buttons and economic turns; no forced actors, resources or victory.')
        (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(dict(route=args.route, commands=len(commands), final=snapshots[-1])))
    finally:
        set_map_topology(previous)
        pygame.quit()


if __name__ == '__main__':
    main()
