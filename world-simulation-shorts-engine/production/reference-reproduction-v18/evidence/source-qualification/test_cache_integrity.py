import unittest,tempfile,pathlib,json,hashlib
from unittest.mock import patch
import numpy as np
import bounded_cog as r
from cache_integrity import reusable_receipt
class CacheChecks(unittest.TestCase):
 def test_corrupt_cached_range_rejected_without_network(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(r,'ROOT',pathlib.Path(tmp)),patch.object(r.urllib.request,'urlopen',side_effect=AssertionError('network')):
   url='https://example.invalid/a';p=r.ROOT/hashlib.sha256(url.encode()).hexdigest();p.mkdir();(p/'header.json').write_text(json.dumps(dict(url=url,length=3,etag='v1')))
   (p/'00000000.bin').write_bytes(b'bad');(p/'00000000.json').write_text(json.dumps(dict(start=0,end=2,bytes=3,sha256=hashlib.sha256(b'yes').hexdigest())))
   with self.assertRaises(OSError):r.RangeFile(url).read(3)
 def test_missing_range_receipt_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp)/'00000000.bin';p.write_bytes(b'ok')
   with self.assertRaises(OSError):r.verified_block(p,0,1)
 def test_atomic_write_replaces_complete_file(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp)/'x';p.write_bytes(b'old');r.atomic_write(p,b'new');self.assertEqual(p.read_bytes(),b'new');self.assertEqual(len(list(p.parent.iterdir())),1)
 def test_concurrent_readers_publish_one_complete_block(self):
  from concurrent.futures import ThreadPoolExecutor
  from test_bounded_cog import Response
  with tempfile.TemporaryDirectory() as tmp,patch.object(r,'ROOT',pathlib.Path(tmp)):
   url='https://example.invalid/a';p=r.ROOT/hashlib.sha256(url.encode()).hexdigest();p.mkdir();(p/'header.json').write_text(json.dumps(dict(url=url,length=32,etag='source-v1')))
   with patch.object(r.urllib.request,'urlopen',side_effect=lambda *a,**k:Response(bytes(range(32)))) as req:
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(lambda _:r.RangeFile(url).read(32),range(4)))
    self.assertEqual(results,[bytes(range(32))]*4);self.assertEqual(req.call_count,1)
 def test_reuse_checks_all_bindings(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp)/'x.json';a=np.ones((2,2),dtype='float32');np.savez(p.with_suffix('.npz'),height=a)
   m=dict(status='ok',url='https://example.invalid/a',decodedShape=[2,2],sourceCRS='EPSG:4326',decodedTransform=[.5,0,126,0,-.5,38,0,0,1],npzSha256=hashlib.sha256(p.with_suffix('.npz').read_bytes()).hexdigest(),arraySha256=hashlib.sha256(a.tobytes()).hexdigest());p.write_text(json.dumps(m))
   kw=dict(status='ok',url=m['url'],shape=[2,2],keys=[('height','arraySha256',[2,2])],bounds=[126,37,127,38])
   self.assertTrue(reusable_receipt(p,**kw))
   for key,value in [('url','https://example.invalid/new'),('shape',[4,4]),('bounds',[125,37,126,38])]:
    wrong=dict(kw);wrong[key]=value;self.assertFalse(reusable_receipt(p,**wrong))
   for nonfinite in [float('nan'),float('inf'),float('-inf')]:
    bad=dict(m);bad['decodedTransform']=m['decodedTransform'].copy();bad['decodedTransform'][0]=nonfinite;p.write_text(json.dumps(bad));self.assertFalse(reusable_receipt(p,**kw))
   dsm=dict(m,status='DSM_DECODED_NOT_ADMITTED');p.write_text(json.dumps(dsm));dk=dict(kw,status='DSM_DECODED_NOT_ADMITTED');self.assertFalse(reusable_receipt(p,**dk))
   dsm.update(validityScope='DECODED_SAMPLE_VALIDITY_ONLY',nativeContributorCompletenessVerified=False);p.write_text(json.dumps(dsm));self.assertTrue(reusable_receipt(p,**dk))
   p.write_text(json.dumps(m))
   m['arraySha256']='0'*64;p.write_text(json.dumps(m));self.assertFalse(reusable_receipt(p,**kw))
   p.with_suffix('.npz').write_bytes(b'corrupt');self.assertFalse(reusable_receipt(p,**kw))
if __name__=='__main__':unittest.main(verbosity=2)
