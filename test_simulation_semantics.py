"""Acceptance normalization must retain economic values, order and aliases."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from simulation_semantics import canonical_state


class SemanticStateTests(unittest.TestCase):
    def test_code_signature_retains_rules_without_marshal_identity(self):
        from python_code_signature import code_signature
        import types
        code=compile('def rule(x):\n return x + 10\n','first.py','exec').co_consts[0]
        same=compile('def rule(x):\n return x + 10\n','other.py','exec').co_consts[0]
        signature=code_signature(code)
        function=types.FunctionType(code,{})
        for i in range(100):function(i)
        self.assertEqual(signature,code_signature(code))
        self.assertEqual(signature,code_signature(same))
        changed=code.replace(co_consts=(None,11))
        self.assertNotEqual(signature,code_signature(changed))

    def state(self,tiles):
        with patch('simulation_checkpoint.capture_globals',return_value=({},{})):
            return canonical_state(tiles,[])['graph']

    def test_money_rules_and_shared_references_are_not_normalized_away(self):
        bank=SimpleNamespace(cash=100,liabilities=50)
        tile=SimpleNamespace(name='A',bank=bank,second_reference=bank,policy={'wage':1,'safety':2})
        opening=self.state([tile])
        bank.cash+=1
        self.assertNotEqual(opening,self.state([tile]))
        bank.cash-=1
        self.assertEqual(opening,self.state([tile]))
        tile.second_reference=SimpleNamespace(cash=100,liabilities=50)
        self.assertNotEqual(opening,self.state([tile]))
        tile.second_reference=bank
        tile.policy={'safety':2,'wage':1}
        self.assertNotEqual(opening,self.state([tile]))

    def test_only_native_uuid_fields_and_their_references_are_renamed(self):
        first=SimpleNamespace(name='A',construction_projects=[SimpleNamespace(project_id='proj_abcd1234',amount=100)],
                              intent_id='abcd1234',numeric_code='12345678',message='project proj_abcd1234')
        second=SimpleNamespace(name='A',construction_projects=[SimpleNamespace(project_id='proj_feed1234',amount=100)],
                               intent_id='feed1234',numeric_code='12345678',message='project proj_feed1234')
        self.assertEqual(self.state([first]),self.state([second]))
        second.numeric_code='87654321'
        self.assertNotEqual(self.state([first]),self.state([second]))

    def test_callback_closure_state_is_retained(self):
        def callback(amount):
            def apply():return amount
            return apply
        first=SimpleNamespace(callback=callback(5))
        second=SimpleNamespace(callback=callback(6))
        self.assertNotEqual(self.state([first]),self.state([second]))


if __name__=='__main__':unittest.main()
