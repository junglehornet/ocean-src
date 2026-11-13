"""Build a native process fixture and run Ocean's exec tests with diagnostics."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

compiler = Path(sys.argv[1]).resolve()
stdlib = Path(__file__).resolve().parents[3]
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
with tempfile.TemporaryDirectory(prefix='ocean exec fixture ') as directory:
    root = Path(directory)
    fixture = root / ('fixture.exe' if os.name == 'nt' else 'fixture')
    command = ['clang', '-std=c11', str(Path(__file__).with_name('fixture.c')), '-o', str(fixture)]
    if os.name == 'nt':
        command.append('-municode')
    subprocess.run(command, check=True, timeout=60)
    env = dict(os.environ, OCEAN_SRC=str(stdlib), OCEAN_EXEC_FIXTURE=str(fixture),
               OCEAN_EXEC_FIXTURE_DIR=str(root), OCEAN_BUILD_CACHE='off')
    command = [str(compiler), 'test', str(stdlib/'os/exec'), '--notty', '--timeout', '120s']
    print('exec fixture test:', command, flush=True)
    try:
        result = subprocess.run(command, env=env, encoding='utf-8', capture_output=True, timeout=240)
    except subprocess.TimeoutExpired as error:
        print('TIMED OUT exec fixture:', command, 'stdout=', error.stdout,
              'stderr=', error.stderr, flush=True)
        raise
    print(result.stdout, end='', flush=True)
    print(result.stderr, end='', file=sys.stderr, flush=True)
    assert result.returncode == 0, result.returncode
