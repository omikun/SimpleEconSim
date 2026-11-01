"""Render Egypt and use its real buttons to check the community observation UI."""

import argparse
import json
from pathlib import Path
import random

import pygame
import numpy as np

from client.desktop.app import render_frame
from client.desktop.engine import build_world_view
from client.desktop.panels.scenario_ui import guided_ui_hit
from governing_network import KEY, project
from world_config import get_map_topology, set_map_topology


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=Path('outputs/governing_network/ui'))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    pygame.init()
    screen = pygame.display.set_mode((1400, 900))
    previous_topology = get_map_topology()
    try:
        set_map_topology('voronoi')
        world = build_world_view(scenario_id='egypt_1877', trace_enabled=False,
                                governing_network_mode='observe')
        from random_cache import rand
        random.seed(1877)
        np.random.seed(1877)
        rand._idx = rand._capacity
        world['ui_mode'] = 'guided'
        world['use_gpu_pipeline'] = False
        commands = []

        def draw(name=None):
            render_frame(screen, world)
            if name:
                pygame.image.save(screen, str(args.output_dir / name))

        def click(action):
            draw()
            target = next((t for t in world['_ui_targets']
                           if t.scope == 'guided' and t.action == action), None)
            if target is None:
                raise AssertionError(f'Button unavailable: {action}')
            if not guided_ui_hit(target.rect.center, world):
                raise AssertionError(f'Button was not handled: {action}')
            commands.append(dict(action=action, turn=world['turn'],
                                 observation_turn=project(world)['turn']))

        draw('opening.png')
        opening = project(world)
        click(('scenario_action', 'release_maize'))
        if world['scenario_state']['last_action_turn'] != 1:
            raise AssertionError('The real relief decision was not recorded.')
        click('step_next')
        after_relief = project(world)
        if after_relief['turn'] != 2:
            raise AssertionError('The observation did not follow the economic turn.')
        draw('after-relief.png')
        click('toggle_society_observation')
        click('step_next')
        if project(world)['turn'] != 3 or not world['_ui_society_observation_hidden']:
            raise AssertionError('Hiding the panel stopped observations or changed its mode.')
        draw('hidden.png')
        click('toggle_society_observation')
        draw('reopened.png')
        state = world['scenario_state'][KEY]
        for info in (opening, after_relief):
            for group in info['communities']:
                group.pop('member_ids')
        report = dict(passed=True, commands=commands, opening=opening,
                      after_relief=after_relief, last_turn=world['turn'],
                      active_nodes=state['diagnostics']['active_nodes'],
                      contacts=state['diagnostics']['contacts'],
                      note='One real relief decision; two normal turns; hide/reopen changes UI only.')
        (args.output_dir / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print('Native UI observation playtest passed: ' + str(args.output_dir))
    finally:
        set_map_topology(previous_topology)
        pygame.quit()


if __name__ == '__main__':
    main()
