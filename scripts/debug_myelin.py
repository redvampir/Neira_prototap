import sys
sys.path.insert(0, 'f:/Нейронки/prototype')
from myelination_system import MyelinationSystem, PathwayType
import tempfile, shutil

test_dir = tempfile.mkdtemp()
system = MyelinationSystem(data_dir=test_dir)

pathway = system.create_pathway(
    name='test',
    nodes=['a', 'b', 'c'],
    pathway_type=PathwayType.RESPONSE
)

print(f'Start: myelin={pathway.myelin_level}, stage={pathway.stage}')

for i in range(50):
    old, new = system.activate_pathway(pathway.id, success=True, intensity=1.0)
    pathway = system.get_pathway(pathway.id)
    if (i+1) % 10 == 0:
        print(f'After {i+1}: myelin={pathway.myelin_level:.3f}, stage={pathway.stage}')

shutil.rmtree(test_dir)
