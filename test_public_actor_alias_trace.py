"""Public wallets can reach nominally private contractor and payroll paths."""
from pathlib import Path
import tempfile
import unittest
from agent import Agent,initialize_agent
from buildings import BUILDING_RECIPES,ConstructionProject
from goods import Goods
from nation import Nation
from region import Region
from run_trace import RunTrace
from trace_audit import audit


class PublicActorAliasTraceTests(unittest.TestCase):
    def test_authored_project_reserves_survive_market_ticks_and_retry(self):
        from sim_server.sim_server import SimServer
        from sim_server.protocol import CommandMessage, CommandType
        from trace_coverage import coverage
        server=SimServer(seed=612,scenario_id='labor_frontier_rivalry')
        command=CommandMessage(CommandType.SCENARIO_ACTION,
                               {'action_id':'cofund_machinery'},command_id='reserved-input-project')
        first=server.execute_command(command)
        self.assertTrue(first['success'],first)
        self.assertEqual(first,server.execute_command(command))
        self.assertEqual(1,len(server.scenario_state['machinery_projects']))
        for _ in range(2):server.step()
        project=server.scenario_state['machinery_projects'][0]
        self.assertEqual('complete',project['status'])
        self.assertEqual({'iron':0,'coal':0},project['reserved_materials'])
        rows=server.run_trace.query(metric_id='construction.material_stock',limit=100)['events']
        self.assertEqual(4,len(rows))
        self.assertTrue(all(row['formula_replay']['matches'] for row in rows))
        self.assertEqual(0,sum(row['delta'] for row in rows))
        from causal_contracts import validate
        consumed=next(row for row in rows if row['kind']=='scenario_machinery_material_consumed')
        consumed['cause_event_ids']=[]
        self.assertFalse(validate(consumed,lambda ident: server.run_trace.query(event_id=ident)['events'][0])['matches'])
        self.assertTrue(audit(server.run_trace.path)['structural_and_supported_formula_checks_pass'])
        self.assertEqual(0,coverage(server.run_trace.path)['_treasury_account_closure']['gaps'])

    def test_government_contractor_materials_and_navvy_wages_close(self):
        with tempfile.TemporaryDirectory() as directory:
            nation=Nation('Public contractor','C',register=False)
            tile=Region('Works',0,number_of_agents=0);nation.add_tile(tile)
            contractor=tile.gov.agent;contractor.is_corporation=True;contractor.cash=100
            tile.agents=[contractor]
            for _ in range(3):
                worker=Agent(0);initialize_agent(worker,Goods.food,0,0,0)
                tile.agents.append(worker)
            trace=RunTrace(Path(directory)/'contractor.ctr','contractor')
            clock={'turn':0,'phase':'setup','next':1}
            for source in (tile,nation):source._run_trace=trace;source._collective_trace_clock=clock
            trace.treasury_book.register_nations([nation],clock)
            before={('finance.treasury',nation.name):(None,'C',nation.treasury()['total'])}
            project=ConstructionProject('public-project',nation.name,tile,BUILDING_RECIPES['turnpike_road'],contractor,0)
            clock['turn']=1
            project.step(1)
            self.assertLess(contractor.cash,100)
            self.assertEqual(4.5,sum(person.cash for person in tile.agents if person is not contractor))
            trace.treasury_book.close([nation],clock,before)
            closing=trace.query(kind='treasury_account_closure')['events'][0]
            self.assertTrue(closing['formula_replay']['matches'])
            writes=trace.query(kind='public_account_write')['events']
            self.assertTrue(any(row['inputs'].get('source_writer','').startswith('buildings.py:ConstructionProject.step:') for row in writes))
            self.assertTrue(audit(trace.path)['structural_and_supported_formula_checks_pass'])


if __name__=='__main__':unittest.main()
