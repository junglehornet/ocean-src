"""Verify libcurl link requirements survive check, library builds and cache hits."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import time

compiler = Path(sys.argv[1]).resolve()
stdlib = Path(__file__).resolve().parents[3]
build_timeout = int(os.environ.get('OCEAN_HTTP_BUILD_TIMEOUT', '120'))
assert 1 <= build_timeout <= 3600
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
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
        timeout = build_timeout if Path(args[0]) == compiler else 30
        print('START linking:', *map(str, args), 'timeout=', timeout, flush=True)
        started = time.monotonic()
        try:
            p = subprocess.run([str(a) for a in args], env=env, capture_output=True, text=True,encoding="utf-8", timeout=timeout)
        except subprocess.TimeoutExpired as error:
            print('TIMED OUT linking:', args, 'stdout=', error.stdout, 'stderr=', error.stderr, flush=True)
            raise
        print('DONE linking:', args[0], 'exit=', p.returncode, 'elapsed=', round(time.monotonic()-started, 2), flush=True)
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
            if len(data)==4 and all(byte in b'01' for byte in data): result.append(data)
        return result
    assert any(flags[2:3]==b'1' for flags in metadata(root/'cache'))
    source.write_text('package main; func main() int { return 0; }')
    env['OCEAN_BUILD_CACHE']=str(root/'plain-cache')
    run(compiler, 'build', source, '-o', binary)
    run(binary)
    run(compiler, 'build', source, '-o', binary)
    plain=metadata(root/'plain-cache')
    assert plain and all(flags[2:3]==b'0' for flags in plain)
print('HTTP cold/hot/uncached linking and no-curl metadata for unrelated programs passed')
