import unittest,tempfile,pathlib,numpy as np
from source_snapshot import Snapshot,check_grid,paired_masks,verify_pair
class Checks(unittest.TestCase):
 def test_file_mutation_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   p=pathlib.Path(t)/'a';p.write_bytes(b'a');s=Snapshot();s.read(p);p.write_bytes(b'b')
   with self.assertRaisesRegex(ValueError,'INPUT_CHANGED'):s.verify()
 def test_inventory_mutation_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   s=Snapshot();s.inventory(t,'*.json');(pathlib.Path(t)/'new.json').write_text('{}')
   with self.assertRaisesRegex(ValueError,'INVENTORY'):s.verify()
 def test_grid_shear_and_shift_rejected(self):
  m=dict(tile='N37E126',sourceCRS='EPSG:4326',sourceBounds=[126,37,127,38],decodedShape=[4,2,2],decodedTransform=[.5,0,126,0,-.5,38,0,0,1]);check_grid(m,(2,2))
  for i in [1,2,3,5]:
   bad={**m,'decodedTransform':m['decodedTransform'].copy()};bad['decodedTransform'][i]+=.1
   with self.assertRaisesRegex(ValueError,'GRID'):check_grid(bad,(2,2))
 def test_pair_exact_and_tamper_rejected(self):
  o=dict(tile='N37E126',sourceCRS='EPSG:4326',sourceBounds=[126,37,127,38],decodedShape=[4,2,2],decodedTransform=[.5,0,126,0,-.5,38,0,0,1]);c=dict(tile='N36E126',sourceCRS='EPSG:4326',sourceBounds=[126,36,129,39],sourceShape=[36000,36000],decodedShape=[12,12],decodedTransform=[.25,0,126,0,-.25,39,0,0,1]);a=np.full((12,12),80);a[5,1]=10;a[5,3]=90;a[7,1]=0
  m=paired_masks(o,c,a);self.assertEqual(m['classes'].tolist(),[[10,90],[0,80]]);verify_pair(m,m)
  bad={k:v.copy() for k,v in m.items()};bad['knownLand'][0,0]=False
  with self.assertRaisesRegex(ValueError,'PARENT_MISMATCH'):verify_pair(bad,m)
if __name__=='__main__':unittest.main(verbosity=2)
