#!/usr/bin/env python3
"""Native thread regression tests; set OCEAN to the matching compiler."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
MODES = ["basic", "return", "kill", "kill-goto", "yield", "kill-yield", "yield-main",
         "kill-lock", "kill-group", "kill-await", "awaiters", "closures", "invalid",
         "main-return", "main-kill", "worker-kill-main", "return-defer", "shutdown"]


def run(command, env, **kwargs):
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=30, **kwargs)
    return result


def main():
    compiler = os.environ.get("OCEAN", shutil.which("ocean") or "ocean")
    with tempfile.TemporaryDirectory(prefix="ocean-thread-tests-") as directory:
        temp = Path(directory)
        env = dict(os.environ, OCEAN_SRC=str(ROOT), OCEAN_BUILD_CACHE=str(temp / "cache"))
        executable = temp / "threads"
        checked = run([compiler, "check", str(Path(__file__).parent)], env)
        assert checked.returncode == 0, checked.stderr
        for cache_mode in (str(temp / "cache"), "off"):
            env["OCEAN_BUILD_CACHE"] = cache_mode
            built = run([compiler, "build", str(Path(__file__).parent), "-o", str(executable)], env)
            assert built.returncode == 0, built.stderr
            for mode in MODES:
                result = run([str(executable), mode], env)
                assert (result.returncode, result.stdout, result.stderr) == (0, "OK\n", ""), (cache_mode, mode, result)
            for mode, status in (("exit", 23), ("worker-exit", 24), ("worker-panic", 1), ("main-panic", 1)):
                result = run([str(executable), mode], env)
                assert result.returncode == status, (mode, result)
                if "panic" in mode:
                    assert f"Panic: {mode.split('-')[0]} failed" in result.stderr, result
                else:
                    assert result.stdout == "" and result.stderr == "", result
        # Stress concurrency and closure registration beyond a single schedule.
        for attempt in range(10):
            for mode in ("basic", "awaiters", "closures", "kill", "return"):
                result = run([str(executable), mode], env)
                assert (result.returncode, result.stdout, result.stderr) == (0, "OK\n", ""), (attempt, mode, result)
        # Exercise the Windows implementation on POSIX through a test-only API
        # shim. This covers its branches, not the real Windows SDK/kernel ABI.
        compiler_source = Path(os.environ.get("OCEAN_COMPILER_SOURCE", Path(compiler).resolve().parent))
        runtime = compiler_source / "runtime_threads.c"
        shim = compiler_source / "tests" / "win32_shim"
        if os.name != "nt" and runtime.exists() and shim.exists():
            ir, native = temp / "threads.ll", temp / "windows-runtime.o"
            emitted = run([compiler, "build", "--emit-llvm", str(Path(__file__).parent), "-o", str(ir)], env)
            assert emitted.returncode == 0, emitted.stderr
            built = run(["clang", "-std=c11", "-D_POSIX_C_SOURCE=200809L", "-D_WIN32", "-I", str(shim), "-c", str(runtime), "-o", str(native)], env)
            assert built.returncode == 0, built.stderr
            built = run(["clang", "-Wno-override-module", "-O2", str(ir), str(native), "-pthread", "-lffi", "-o", str(executable)], env)
            assert built.returncode == 0, built.stderr
            for mode in MODES:
                result = run([str(executable), mode], env)
                assert (result.returncode, result.stdout, result.stderr) == (0, "OK\n", ""), ("Windows shim", mode, result)
            for mode, status in (("exit", 23), ("worker-exit", 24), ("worker-panic", 1), ("main-panic", 1)):
                result = run([str(executable), mode], env)
                assert result.returncode == status, ("Windows shim", mode, result)
                if "panic" in mode:
                    assert f"Panic: {mode.split('-')[0]} failed" in result.stderr, result
        # WebAssembly cannot use native OS threads; reject both packages even
        # when imported without executing a Spawn call.
        source = temp / "main.oc"
        wasm = dict(env, OCOS="js", OCARCH="wasm")
        for package in ("threads", "sync"):
            source.write_text(f'package main; import "{package}"; func main() {{}}\n')
            result = run([compiler, "check", str(source)], wasm)
            assert result.returncode != 0 and "unavailable on WebAssembly" in result.stderr, result
        # Restrict compiler bridges to the actual standard library.
        source.write_text('package main; func main() { compilerThreadSpawn(func() {}); }\n')
        result = run([compiler, "check", str(source)], env)
        assert result.returncode != 0 and "restricted" in result.stderr, result
        # Trace clang arguments to verify conditional pthread linking, native
        # runtime caching, and checkpoint mode when a dependency is reused.
        if os.name != "nt":
            clang = shutil.which("clang")
            tools = temp / "tools"
            tools.mkdir()
            log = temp / "clang.jsonl"
            wrapper = tools / "clang"
            wrapper.write_text('#!/usr/bin/env python3\nimport json,os,sys\n'
                               f'with open({str(log)!r},"a") as f: f.write(json.dumps(sys.argv[1:])+"\\n")\n'
                               f'os.execv({clang!r},[{clang!r}]+sys.argv[1:])\n')
            wrapper.chmod(0o755)
            env.update(PATH=str(tools) + os.pathsep + os.environ["PATH"], OCEAN_BUILD_CACHE=str(temp / "trace-cache"))
            (temp / "ocean.mod").write_text("module example.com/thread-tests\n")
            helper = temp / "helper"
            helper.mkdir()
            (helper / "helper.oc").write_text('package helper; func Busy() { for (;;) {} }\n')
            for threaded in (False, True, True, False):
                if log.exists():
                    log.unlink()
                if threaded:
                    source.write_text('package main; import "helper"; import "threads"; func main() { id:=threads.Spawn(helper.Busy); threads.Kill(id); threads.Await(id); }\n')
                else:
                    source.write_text('package main; import "helper"; func main() {}\n')
                built = run([compiler, "build", str(source), "-o", str(temp / "trace")], env)
                assert built.returncode == 0, built.stderr
                calls = [json.loads(line) for line in log.read_text().splitlines()]
                links = [args for args in calls if "-o" in args and "-c" not in args and "-r" not in args]
                assert links, calls
                assert any("-pthread" in args for args in links) == threaded, calls
                if threaded:
                    result = run([str(temp / "trace")], env)
                    assert result.returncode == 0, result
            # Explicit hot build: only one native linker invocation, no C/IR
            # compilation. This also checks persisted threading link metadata.
            source.write_text('package main; import "threads"; func main() { id:=threads.Spawn(func(){}); threads.Await(id); }\n')
            for attempt in range(2):
                if log.exists(): log.unlink()
                result = run([compiler, "build", str(source), "-o", str(temp / "hot")], env)
                assert result.returncode == 0, result.stderr
                if attempt:
                    calls = [json.loads(line) for line in log.read_text().splitlines()]
                    assert len(calls) == 1 and "-pthread" in calls[0], calls
    print("thread and synchronization tests passed")


if __name__ == "__main__":
    main()
