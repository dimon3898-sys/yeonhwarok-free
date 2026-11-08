import io,json,hashlib,tempfile,pathlib,unittest
from unittest.mock import patch
import bounded_cog as m
class Response(io.BytesIO):
 def __init__(self,data,content_range='bytes 0-31/32',etag='source-v1',status=206):super().__init__(data);self.status=status;self.headers={'Content-Range':content_range,'ETag':etag}
class TestRanges(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();m.ROOT=pathlib.Path(self.tmp.name);m.TOTAL=0;m.LIMIT=1024**3;self.url='https://example.invalid/source.tif';p=m.ROOT/hashlib.sha256(self.url.encode()).hexdigest();p.mkdir();(p/'header.json').write_text(json.dumps({'url':self.url,'length':32,'etag':'source-v1'}))
 def tearDown(self):self.tmp.cleanup()
 def test_valid_range_and_cache(self):
  with patch.object(m.urllib.request,'urlopen',return_value=Response(bytes(range(32)))) as request:
   f=m.RangeFile(self.url);self.assertEqual(f.read(8),bytes(range(8)));f.seek(0);self.assertEqual(f.read(32),bytes(range(32)));self.assertEqual(request.call_count,1)
 def test_wrong_range_rejected(self):
  with patch.object(m.urllib.request,'urlopen',return_value=Response(bytes(32),content_range='bytes 1-32/32')):
   with self.assertRaises(OSError):m.RangeFile(self.url).read(1)
 def test_source_changed_rejected(self):
  with patch.object(m.urllib.request,'urlopen',return_value=Response(bytes(32),etag='changed')):
   with self.assertRaises(OSError):m.RangeFile(self.url).read(1)
 def test_full_response_rejected(self):
  with patch.object(m.urllib.request,'urlopen',return_value=Response(bytes(32),status=200)):
   with self.assertRaises(OSError):m.RangeFile(self.url).read(1)
 def test_budget_stops_before_network(self):
  m.LIMIT=1
  with patch.object(m.urllib.request,'urlopen') as request:
   with self.assertRaises(OSError):m.RangeFile(self.url).read(1)
   request.assert_not_called()
 def test_truncated_range_rejected(self):
  with patch.object(m.urllib.request,'urlopen',return_value=Response(bytes(31))):
   with self.assertRaises(OSError):m.RangeFile(self.url).read(1)
if __name__=='__main__':unittest.main()
