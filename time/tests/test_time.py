#!/usr/bin/env python3
"""Native timing and Linux signal-interruption tests; set OCEAN to the compiler."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]


def run(*args, env=None):
    result = subprocess.run(args, env=env, capture_output=True, timeout=30)
    assert result.returncode == 0, (args, result.returncode, result.stdout, result.stderr)
    return result


def main():
    compiler = os.environ.get("OCEAN", shutil.which("ocean"))
    assert compiler, "set OCEAN to the matching compiler"
    with tempfile.TemporaryDirectory(prefix="ocean-time-") as directory:
        root = Path(directory)
        fixture = str(Path(__file__).parent)
        executable = str(root / "sleep")
        env = dict(os.environ, OCEAN_SRC=str(ROOT), OCEAN_BUILD_CACHE=str(root / "cache"))
        run(compiler, "check", fixture, env=env)
        for cache in (str(root / "cache"), str(root / "cache"), "off"):
            env["OCEAN_BUILD_CACHE"] = cache
            run(compiler, "build", fixture, "-o", executable, env=env)
            for duration in ("0", "-1", "-9223372036854775808", "1", "1000", "1000000"):
                run(executable, duration)
            start = time.monotonic()
            run(executable, "125000000")
            assert time.monotonic() - start >= 0.125, "sleep returned early"
        if sys.platform.startswith("linux"):
            symbols = run("nm", "-u", executable).stdout
            assert b"pthread_" not in symbols and b"ocean_threads_" not in symbols
            # Interrupt nanosleep repeatedly with a real handled signal. No
            # Ocean callback is passed across the native function-value ABI.
            shim = root / "signals.c"
            shim.write_text('''#include <signal.h>
#include <stdio.h>
#include <sys/time.h>
static volatile sig_atomic_t seen;
static void tick(int signal) { (void)signal; seen++; }
__attribute__((constructor)) static void setup(void) {
    struct sigaction action = {0};
    action.sa_handler = tick;
    sigaction(SIGALRM, &action, 0);
    struct itimerval timer = {{0, 10000}, {0, 10000}};
    setitimer(ITIMER_REAL, &timer, 0);
}
__attribute__((destructor)) static void finish(void) {
    fprintf(stderr, "SIGNALS:%d\\n", (int)seen);
}
''')
            library = str(root / "signals.so")
            run("clang", "-shared", "-fPIC", str(shim), "-o", library)
            start = time.monotonic()
            result = run(executable, "150000000", env=dict(os.environ, LD_PRELOAD=library))
            assert time.monotonic() - start >= 0.150, "interrupted sleep returned early"
            assert int(result.stderr.split(b"SIGNALS:")[1]) >= 5, result.stderr
    print("time units, native sleep, cache modes, and interruption tests passed")


if __name__ == "__main__":
    main()
