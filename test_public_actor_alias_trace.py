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
