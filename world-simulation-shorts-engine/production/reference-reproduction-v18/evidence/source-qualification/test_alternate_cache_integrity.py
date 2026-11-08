import unittest,tempfile,pathlib,json,copy,numpy as np
from alternate_cache_integrity import reusable,sha
class Cache(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.p=pathlib.Path(self.tmp.name);data=np.array([[[100]],[[200]],[[300]],[[400]]],dtype='uint16');mask=np.zeros((1,1),dtype=bool);self.f=self.p/'N35E128_1_2.npz';np.savez_compressed(self.f,data=data,invalid=mask)
  self.b={'schema':'ALTERNATE_SOURCE_BINDING_V1','tile':'N35E128','url':'https://example.test/source','samplesPerDegree':12000,'coordinates':[[1,2]],'parentFileSha256':{'parent':'abc'},'algorithmSha256':'code','cacheVerifierSha256':'verifier'}
  self.d={'status':'ACTUAL_ALTERNATE_INSPECTED','url':self.b['url'],'sourceBinding':self.b,'entries':[{'overviewPixel':[1,2],'file':self.f.name,'npzSha256':sha(self.f.read_bytes()),'arraySha256':sha(data.tobytes()),'maskSha256':sha(mask.tobytes()),'nativeWindow':[1,2,1,1],'completeValidTargetCell':True,'areaWeightedFourBandValue':[100,200,300,400]}],'completeValidCells':1,'totalCells':1};self.j=self.p/'N35E128.json';self.write()
 def tearDown(self):self.tmp.cleanup()
 def write(self):self.j.write_text(json.dumps(self.d))
 def test_valid_and_legacy_rejected(self):
  self.assertTrue(reusable(self.j,self.b));del self.d['sourceBinding'];self.write();self.assertFalse(reusable(self.j,self.b))
 def test_parent_coordinate_and_algorithm_change(self):
  for key,value in [('coordinates',[[2,2]]),('parentFileSha256',{'parent':'changed'}),('algorithmSha256','changed')]:
   b=copy.deepcopy(self.b);b[key]=value;self.assertFalse(reusable(self.j,b))
 def test_corrupt_bytes_rejected(self):
  self.f.write_bytes(b'broken');self.assertFalse(reusable(self.j,self.b))
 def test_numeric_result_recomputed(self):
  self.d['entries'][0]['areaWeightedFourBandValue'][0]=999;self.write();self.assertFalse(reusable(self.j,self.b))
 def test_coordinate_and_path_rejected(self):
  self.d['entries'][0]['file']='../outside.npz';self.write();self.assertFalse(reusable(self.j,self.b))
if __name__=='__main__':unittest.main()
