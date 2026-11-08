"""Verified-TLS bounded range reader with persistent block cache and byte receipts."""
import io,urllib.request,pathlib,json,hashlib,threading,time
ROOT=pathlib.Path(__file__).parent/'range_cache';ROOT.mkdir(exist_ok=True)
LOCK=threading.Lock();TOTAL=sum(p.stat().st_size for p in ROOT.glob('*/*.bin'));LIMIT=1024**3
class RangeFile(io.RawIOBase):
 def __init__(self,url):
  self.url=url;self.pos=0;self.root=ROOT/hashlib.sha256(url.encode()).hexdigest();self.root.mkdir(exist_ok=True)
  h=self.root/'header.json'
  if h.exists():self.meta=json.loads(h.read_text())
  else:
   with urllib.request.urlopen(urllib.request.Request(url,method='HEAD'),timeout=30) as r:self.meta={'url':url,'length':int(r.headers['Content-Length']),'etag':r.headers.get('ETag'),'lastModified':r.headers.get('Last-Modified')}
   h.write_text(json.dumps(self.meta))
  self.length=self.meta['length']
 def readable(self):return True
 def seekable(self):return True
 def tell(self):return self.pos
 def seek(self,offset,whence=0):
  self.pos=offset if whence==0 else self.pos+offset if whence==1 else self.length+offset
  if self.pos<0:raise OSError('Negative seek')
  return self.pos
 def read(self,size=-1):
  global TOTAL
  if size<0:size=self.length-self.pos
  size=max(0,min(size,self.length-self.pos))
  if size>32*1024**2:raise OSError('Single read exceeds 32MiB bound')
  out=bytearray();block=256*1024
  while len(out)<size:
   n=self.pos//block;start=n*block;end=min(start+block,self.length)-1;dest=self.root/f'{n:08d}.bin'
   if dest.exists():b=dest.read_bytes()
   else:
    with LOCK:
     if TOTAL+block>LIMIT:raise OSError('Global 1GiB network budget reached')
     if sum(p.stat().st_size for p in self.root.glob('*.bin'))+block>80*1024**2:raise OSError('Per-source 80MiB bound reached')
     TOTAL+=block
    req=urllib.request.Request(self.url,headers={'Range':f'bytes={start}-{end}'})
    with urllib.request.urlopen(req,timeout=45) as r:
     expected=f'bytes {start}-{end}/{self.length}'
     if r.status!=206 or r.headers.get('Content-Range')!=expected:raise OSError('Unverified HTTP range response')
     if self.meta.get('etag') and r.headers.get('ETag')!=self.meta['etag']:raise OSError('Source ETag changed')
     b=r.read(block+1)
     if len(b)!=end-start+1:raise OSError('Incorrect range length')
    dest.write_bytes(b)
    (self.root/f'{n:08d}.json').write_text(json.dumps({'start':start,'end':end,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'contentRange':expected}))
   piece=b[self.pos-start:self.pos-start+size-len(out)]
   if not piece:break
   out.extend(piece);self.pos+=len(piece)
  return bytes(out)
 def readinto(self,b):
  d=self.read(len(b));b[:len(d)]=d;return len(d)
