"""List / selectively extract members of a remote zip via HTTP range requests.
Usage: python -I remote_zip.py URL list
       python -I remote_zip.py URL extract OUTDIR PREFIX [PREFIX...]
"""
import sys, io, os, zipfile, urllib.request, shutil

class HttpFile(io.RawIOBase):
    def __init__(self, url):
        self.url = url; self.pos = 0
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req) as r:
            self.size = int(r.headers["Content-Length"])
    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos
    def seek(self, off, whence=0):
        self.pos = {0: off, 1: self.pos + off, 2: self.size + off}[whence]; return self.pos
    def read(self, n=-1):
        if n is None or n < 0: n = self.size - self.pos
        if n == 0 or self.pos >= self.size: return b""
        end = min(self.pos + n, self.size) - 1
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={self.pos}-{end}"})
        for attempt in range(5):
            try:
                with urllib.request.urlopen(req, timeout=120) as r: data = r.read()
                break
            except Exception as e:
                if attempt == 4: raise
        self.pos += len(data); return data
    def readinto(self, b):
        d = self.read(len(b)); b[:len(d)] = d; return len(d)

def main():
    url, cmd = sys.argv[1], sys.argv[2]
    f = io.BufferedReader(HttpFile(url), buffer_size=8 << 20)
    z = zipfile.ZipFile(f)
    if cmd == "list":
        import collections
        agg = collections.defaultdict(lambda: [0, 0, 0])
        for i in z.infolist():
            parts = i.filename.split("/")
            key = "/".join(parts[:3]) if len(parts) > 3 else "/".join(parts[:-1]) or parts[0]
            ext = os.path.splitext(i.filename)[1].lower()
            a = agg[(key, ext)]; a[0] += 1; a[1] += i.compress_size; a[2] += i.file_size
        for (k, e), (n, c, s) in sorted(agg.items()):
            print(f"{k}\t{e}\t{n}\t{c/1e6:.0f}MB\t{s/1e6:.0f}MB")
    elif cmd == "extract":
        out = os.path.abspath(sys.argv[3]); prefixes = tuple(sys.argv[4:])
        exts = tuple(os.environ.get("EXTS", "").split(",")) if os.environ.get("EXTS") else None
        members = [i for i in z.infolist() if i.filename.startswith(prefixes) and not i.is_dir()
                   and (exts is None or i.filename.lower().endswith(exts) or i.filename.endswith("LICENSE.md"))]
        print(f"{len(members)} members, {sum(m.file_size for m in members)/1e9:.2f} GB", flush=True)
        for k, m in enumerate(members):
            dest = os.path.abspath(os.path.join(out, m.filename))
            if not dest.startswith(out + os.sep): continue  # path traversal guard
            if os.path.exists(dest) and os.path.getsize(dest) == m.file_size: continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with z.open(m) as src, open(dest + ".part", "wb") as dst: shutil.copyfileobj(src, dst, 4 << 20)
            os.replace(dest + ".part", dest)
            if k % 200 == 0: print(k, m.filename, flush=True)
        print("done")
main()
