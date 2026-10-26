import random
import unittest
from sim_server.sim_server import SimServer
from sim_server.protocol import CommandMessage,CommandType


class ServerBondLobbyTests(unittest.TestCase):
    def test_server_uses_native_rating_api_and_debits_fee_once(self):
        server=SimServer(seed=4242,terrain_seed=4242,nation_seed=4242)
        nation=server.nations[0]
        before=nation.government.agent.cash
        rng=random.getstate()
        try:
            random.seed(77)
            result=server.execute_command(CommandMessage(CommandType.SOVEREIGN_BOND,
                {'action':'lobby_upgrade','nation':nation.name}))
        finally:random.setstate(rng)
        self.assertIn('scandal',result)
        self.assertEqual(before-200,nation.government.agent.cash)
        self.assertEqual(0,server.turn)


if __name__=='__main__':unittest.main()
