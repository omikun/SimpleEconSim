"""A retried economic command must not settle twice or drop its stock evidence."""
import unittest
from sim_server.sim_server import SimServer
from sim_server.protocol import CommandMessage, CommandType


class CommandTraceTests(unittest.TestCase):
    def test_exception_after_partial_write_is_not_repeated_on_retry(self):
        from trace_clock import trace_command_boundary
        from treasury_trace import begin_public_change,finish_public_change
        server=SimServer(seed=4242,terrain_seed=4242,nation_seed=4242)
        nation=server.nations[0];before=nation.government.agent.cash
        @trace_command_boundary
        def partial(server,command):
            context=begin_public_change(nation,nation.government.agent)
            nation.government.agent.cash-=5
            finish_public_change(context,'partial_test_action')
            raise ValueError('injected action failure')
        command=CommandMessage(CommandType.SOVEREIGN_BOND,command_id='partial-1')
        with self.assertRaisesRegex(ValueError,'action failure'):partial(server,command)
        response=partial(server,command)
        self.assertFalse(response['success'])
        self.assertTrue(response['partial_state_possible'])
        self.assertEqual(before-5,nation.government.agent.cash)

    def test_step_and_world_reload_retry_do_not_repeat(self):
        server=SimServer(seed=4242,terrain_seed=4242,nation_seed=4242)
        step=CommandMessage(CommandType.STEP,command_id='step-1')
        response=server.execute_command(step)
        self.assertEqual(response,server.execute_command(step))
        self.assertEqual(1,server.turn)
        reset=CommandMessage(CommandType.RELOAD_WORLD,command_id='reset-1')
        response=server.execute_command(reset)
        generation=server.world_generation
        self.assertEqual(response,server.execute_command(reset))
        self.assertEqual(generation,server.world_generation)
        from trace_audit import audit
        result=audit(server.run_trace.path)
        self.assertTrue(result['structural_and_supported_formula_checks_pass'],result['issues'])

    def test_retry_conflict_and_next_turn_account_closure(self):
        server=SimServer(seed=4242,terrain_seed=4242,nation_seed=4242)
        nation=server.nations[0]
        command=CommandMessage(CommandType.SOVEREIGN_BOND,
            {'action':'lobby_upgrade','nation':nation.name},command_id='lobby-1')
        before=nation.government.agent.cash
        result=server.execute_command(command)
        count=server.run_trace.count
        self.assertEqual(result,server.execute_command(CommandMessage.from_dict(command.to_dict())))
        self.assertEqual(count,server.run_trace.count)
        self.assertEqual(before-200,nation.government.agent.cash)
        conflict=server.execute_command(CommandMessage(CommandType.SOVEREIGN_BOND,
            {'action':'lobby_upgrade','nation':'different'},command_id='lobby-1'))
        self.assertFalse(conflict['success'])
        self.assertEqual(count,server.run_trace.count)
        rows=server.run_trace.query(kind='public_account_write',limit=1000)['events']
        self.assertTrue(rows)
        started=server.run_trace.query(kind='player_command_started')['events'][0]['event_id']
        self.assertTrue(any(started in row.get('cause_event_ids',[]) for row in rows))
        self.assertEqual(0,server.turn)
        server.step()
        closures=server.run_trace.query(kind='treasury_account_closure',limit=1000)['events']
        self.assertGreaterEqual(len(closures),len(server.nations)*2)
        self.assertTrue(all(row['record_class']=='calculation' for row in closures),
                        [(row['turn'],row['epoch'],row['inputs']) for row in closures if row['record_class']!='calculation'])
        self.assertEqual(1,server.turn)


if __name__=='__main__':unittest.main()
