"""Compile and execute HTTP's host-transport API under JavaScript/Wasm.
Only the small test C-runtime shim is provided here; it is not a production
Ocean JavaScript runtime or an asynchronous Fetch adapter.
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

compiler=Path(sys.argv[1]).resolve()
stdlib=Path(__file__).resolve().parents[3]
node=shutil.which('node')
assert node, 'Node is required to validate Wasm execution'
with tempfile.TemporaryDirectory(prefix='ocean-http-wasm-') as tmp:
    root=Path(tmp)
    source=root/'main.oc'
    source.write_text('''package main;
import "net/http";
import "time";
struct HostTransport {}
func (t HostTransport) RoundTrip(request http.Request) Result<http.Response> {
    if (request.Deadline <= time.Monotonic()) return Result<http.Response>.error("missing deadline");
    r: http.Response; r.StatusCode = 200; r.Status = "200 OK"; r.Body = "host transport";
    return Result<http.Response>.value(r);
}
func main() int {
    r := http.NewRequest("GET", "https://example.com", "");
    if (r.hasError()) return 1;
    c: http.Client; c.Timeout = time.Second; c.Transport = HostTransport{};
    result := c.Do(r.unwrap());
    if (result.hasError() || result.unwrap().Body != "host transport") return 2;
    cancel: http.Cancellation; cancel.Cancel();
    canceled := c.Do(r.unwrap().WithCancel(&cancel));
    if (!canceled.hasError() || canceled.error() != "http: request canceled") return 3;
    missing := http.Get("https://example.com");
    if (!missing.hasError() || missing.error() != "http: WebAssembly requires a host-supplied RoundTripper") return 4;
    return 0;
}
''')
    module=root/'http.wasm'
    env=dict(os.environ,OCOS='js',OCARCH='wasm',OCEAN_SRC=str(stdlib),OCEAN_BUILD_CACHE=str(root/'cache'))
    def build(*args):
        result=subprocess.run([str(compiler),*map(str,args)],env=env,capture_output=True,text=True,timeout=120)
        assert result.returncode==0,(args,result.stdout,result.stderr)
    for _ in range(2):
        build('build',source,'-o',module)
        assert module.read_bytes()[:4]==b'\0asm'
    build('check',source)
    build('build',stdlib/'net/http','-o',root/'http.o')
    env['OCEAN_BUILD_CACHE']='off'
    build('build',source,'-o',module)
    script=root/'run.cjs'
    script.write_text(r'''
const fs=require('fs');
const moduleBytes=fs.readFileSync(process.argv[2]);
const mod=new WebAssembly.Module(moduleBytes);
const imports=WebAssembly.Module.imports(mod);
if(imports.some(i=>/curl_|ocean_threads_/.test(i.name)))throw Error('native transport import leaked into Wasm');
let instance,next=8*1024*1024;
const env={
  malloc(n){n=Number(n);const pointer=next;next=Math.ceil((next+n)/8)*8;
    const memory=instance.exports.memory;
    if(next>memory.buffer.byteLength)memory.grow(Math.ceil((next-memory.buffer.byteLength)/65536));
    return pointer;},
  calloc(n,s){return env.malloc(Number(n)*Number(s));},
  free(){},
  memcmp(a,b,n){const bytes=new Uint8Array(instance.exports.memory.buffer);
    for(let i=0;i<Number(n);i++)if(bytes[a+i]!==bytes[b+i])return bytes[a+i]-bytes[b+i];return 0;},
  memcpy(d,s,n){new Uint8Array(instance.exports.memory.buffer).copyWithin(d,s,s+Number(n));return d;},
  memmove(d,s,n){return env.memcpy(d,s,n);},
  memset(d,v,n){new Uint8Array(instance.exports.memory.buffer).fill(v,d,d+Number(n));return d;},
  ocean_time_monotonic_ns(){return 1000000000n;},
  longjmp(){throw Error('unexpected longjmp');},
  dprintf(){throw Error('unexpected diagnostic');},
  exit(c){throw Error('unexpected exit '+c);},
  write(fd,p,n){return BigInt(n);},
  __cxa_atexit(){return 0;}
};
for(const item of imports)if(!(item.name in env))throw Error('unimplemented test runtime import '+item.name);
instance=new WebAssembly.Instance(mod,{env});
const status=instance.exports.main();
if(status!==0)throw Error('HTTP Wasm smoke returned '+status);
console.log('HTTP Wasm host transport, deadline, pre-cancel and missing-adapter behavior passed');
''')
    result=subprocess.run([node,str(script),str(module)],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,(result.stdout,result.stderr)
    print(result.stdout.strip())
