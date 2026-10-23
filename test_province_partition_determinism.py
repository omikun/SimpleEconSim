"""Geographic tie breaks must not depend on object allocation addresses."""
import random
import unittest
from province import partition_contiguous_graph


class Node:
    def __init__(self,name,hash_value):self.name=name;self.hash_value=hash_value
    def __hash__(self):return self.hash_value


class ProvincePartitionDeterminismTests(unittest.TestCase):
    def test_equal_distance_candidates_keep_native_input_order_across_hash_layouts(self):
        outcomes=[]
        for hashes in ([0,1,2,3,4,5],[901,3,100,32,9000,2],[71,92,30,401,0,7]):
            nodes=[Node(str(index),value) for index,value in enumerate(hashes)]
            def neighbors(node):return nodes[1:] if node is nodes[0] else [nodes[0]]
            parts=partition_contiguous_graph(nodes,neighbors,2,rng=random.Random(42))
            outcomes.append([[node.name for node in part] for part in parts])
            self.assertEqual(set(nodes),{node for part in parts for node in part})
            self.assertLessEqual(abs(len(parts[0])-len(parts[1])),1)
        self.assertEqual(outcomes[0],outcomes[1])
        self.assertEqual(outcomes[0],outcomes[2])


if __name__=='__main__':unittest.main()
