"""Verified-TLS bounded range reader with persistent block cache and byte receipts."""
import io,urllib.request,pathlib,json,hashlib,threading,time,os,tempfile,fcntl
from contextlib import contextmanager
ROOT=pathlib.Path(__file__).parent/'range_cache';ROOT.mkdir(exist_ok=True)
LOCK=threading.Lock();TOTAL=sum(p.stat().st_size for p in ROOT.glob('*/*.bin'));LIMIT=1024**3
def atomic_write(path,data):
 fd,name=tempfile.mkstemp(prefix='.'+path.name+'.',dir=path.parent)
 try:
  with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
  os.replace(name,path)
 finally:
  if os.path.exists(name):os.unlink(name)
@contextmanager
def cache_lock(path):
 with open(path,'a+b') as f:
  fcntl.flock(f,fcntl.LOCK_EX)
  try:yield
  finally:fcntl.flock(f,fcntl.LOCK_UN)
def verified_block(dest,start,end):
 b=dest.read_bytes();r=json.loads(dest.with_suffix('.json').read_text())
 if len(b)!=end-start+1 or r.get('start')!=start or r.get('end')!=end or r.get('bytes')!=len(b) or r.get('sha256')!=hashlib.sha256(b).hexdigest():raise OSError('Cached range integrity mismatch')
 return b
class RangeFile(io.RawIOBase):
 def __init__(self,url):
  self.url=url;self.pos=0;self.root=ROOT/hashlib.sha256(url.encode()).hexdigest();self.root.mkdir(exist_ok=True)
  h=self.root/'header.json'
  if h.exists():self.meta=json.loads(h.read_text())
  else:
   with urllib.request.urlopen(urllib.request.Request(url,method='HEAD'),timeout=30) as r:self.meta={'url':url,'length':int(r.headers['Content-Length']),'etag':r.headers.get('ETag'),'lastModified':r.headers.get('Last-Modified')}
   atomic_write(h,json.dumps(self.meta).encode())
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
   # Cross-process lock serializes cache writers and budget decisions. Existing
   # legacy processes do not honor it; cache mismatch fails closed, never repairs.
   with cache_lock(ROOT/'.cache-write.lock'):
    if dest.exists():b=verified_block(dest,start,end)
    else:
     actual=sum(p.stat().st_size for p in ROOT.glob('*/*.bin'))
     if actual+end-start+1>LIMIT:raise OSError('Global 1GiB network budget reached')
     if sum(p.stat().st_size for p in self.root.glob('*.bin'))+end-start+1>80*1024**2:raise OSError('Per-source 80MiB bound reached')
     req=urllib.request.Request(self.url,headers={'Range':f'bytes={start}-{end}'})
     with urllib.request.urlopen(req,timeout=45) as r:
      expected=f'bytes {start}-{end}/{self.length}'
      if r.status!=206 or r.headers.get('Content-Range')!=expected:raise OSError('Unverified HTTP range response')
      if self.meta.get('etag') and r.headers.get('ETag')!=self.meta['etag']:raise OSError('Source ETag changed')
      b=r.read(block+1)
      if len(b)!=end-start+1:raise OSError('Incorrect range length')
     atomic_write(dest.with_suffix('.json'),json.dumps({'start':start,'end':end,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'contentRange':expected}).encode())
     atomic_write(dest,b)
   piece=b[self.pos-start:self.pos-start+size-len(out)]
   if not piece:break
   out.extend(piece);self.pos+=len(piece)
  return bytes(out)
 def readinto(self,b):
  d=self.read(len(b));b[:len(d)]=d;return len(d)
