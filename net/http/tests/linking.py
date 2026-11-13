"""Verify libcurl link requirements survive check, library builds and cache hits."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

compiler = Path(sys.argv[1]).resolve()
stdlib = Path(__file__).resolve().parents[3]
with tempfile.TemporaryDirectory(prefix='ocean-http-link-') as directory:
    root = Path(directory)
    source = root/'main.oc'
    source.write_text('''package main;
import "net/http";
func main() int {
    client: http.Client;
    result := client.Get("http://localhost:0");
    if (!result.hasError()) return 1;
    return 0;
}
''')
    binary = root/('program.exe' if os.name == 'nt' else 'program')
    env = dict(os.environ, OCEAN_SRC=str(stdlib), OCEAN_BUILD_CACHE=str(root/'cache'))
    def run(*args):
        p = subprocess.run([str(a) for a in args], env=env, capture_output=True, text=True, timeout=120)
        assert p.returncode == 0, (args,p.stdout,p.stderr)
    for _ in range(2):
        run(compiler, 'build', source, '-o', binary)
        run(binary)
    run(compiler, 'check', source)
    run(compiler, 'build', stdlib/'net/http', '-o', root/'http.o')
    env['OCEAN_BUILD_CACHE']='off'
    run(compiler, 'build', source, '-o', binary)
    run(binary)
    # Link metadata must opt in to curl, not make it a universal dependency.
    def metadata(cache):
        result=[]
        for path in (cache/'v1/data').glob('*/*'):
            data=path.read_bytes()
            if len(data)==3 and all(byte in b'01' for byte in data): result.append(data)
        return result
    assert any(flags[-1:]==b'1' for flags in metadata(root/'cache'))
    source.write_text('package main; func main() int { return 0; }')
    env['OCEAN_BUILD_CACHE']=str(root/'plain-cache')
    run(compiler, 'build', source, '-o', binary)
    run(binary)
    run(compiler, 'build', source, '-o', binary)
    plain=metadata(root/'plain-cache')
    assert plain and all(flags[-1:]==b'0' for flags in plain)
print('HTTP cold/hot/uncached linking and no-curl metadata for unrelated programs passed')
