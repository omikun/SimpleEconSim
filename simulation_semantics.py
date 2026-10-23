"""Identity-normalized metric evidence for deterministic continuation checks.

This compares every sampled metric. It is not a digest of every internal model
field; release acceptance must also compare actions, RNG and pending state.
"""
from trace_snapshots import sample


def normalized_metrics(server):
    # Projects created after a checkpoint use UUID4, independently of gameplay
    # RNG. Match by tile and native creation-list position while preserving each
    # identity's references and every measured quantity.
    identities={}
    for tile in server.tiles:
        for index,project in enumerate(getattr(tile,'construction_projects',())):
            identities[project.project_id]=f'project:{tile.name}:{index}'
    def normalize(value):
        if isinstance(value,str):return identities.get(value,value)
        if isinstance(value,tuple):return tuple(normalize(item) for item in value)
        if isinstance(value,list):return [normalize(item) for item in value]
        if isinstance(value,dict):return {normalize(key):normalize(item) for key,item in value.items()}
        return value
    return {normalize(key):normalize(value) for key,value in sample(server.tiles,server.nations).items()}
