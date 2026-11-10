#!/usr/bin/env python3
"""Native async tests and POSIX PTY integration; set OCEAN to the matching compiler."""
import fcntl
import os
from pathlib import Path
import pty
import select
import shutil
import struct
import subprocess
import tempfile
import termios
import time

ROOT = Path(__file__).resolve().parents[3]
COMPILER = os.environ.get("OCEAN", shutil.which("ocean"))


def run(*args, env=None):
    result = subprocess.run(args, env=env, capture_output=True, timeout=45)
    assert result.returncode == 0, (args, result.returncode, result.stdout, result.stderr)
    return result


def terminal(executable, mode):
    master, slave = pty.openpty()
    original = termios.tcgetattr(slave)
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
    process = subprocess.Popen([executable, mode], stdin=slave, stdout=slave, stderr=subprocess.PIPE)
    received = b""

    def expect(text):
        nonlocal received
        deadline = time.monotonic() + 8
        while text not in received:
            assert time.monotonic() < deadline, (text, received, process.poll())
            if select.select([master], [], [], 0.1)[0]:
                received += os.read(master, 65536)
        received = b""

    try:
        expect(b"VIEW:80\r\nready")
        assert not termios.tcgetattr(slave)[3] & (termios.ECHO | termios.ICANON)
        if mode == "panic":
            os.write(master, b"x")
            assert process.wait(timeout=8) == 1
            assert b"update failed" in process.stderr.read()
        else:
            os.write(master, b"\x1b[")
            time.sleep(0.01)
            os.write(master, b"A")
            expect(b"VIEW:81")
            # Split UTF-8 must produce one message; mixed-width input stays whole.
            os.write(master, b"\xc3")
            time.sleep(0.04)
            os.write(master, b"\xa9")
            expect(b"VIEW:91")
            os.write(master, b"\x1b")
            expect(b"VIEW:191")
            os.write(master, b"\x1bx")
            expect(b"VIEW:1201")
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 100, 0, 0))
            expect(b"VIEW:100")
            os.write(master, b"q")
            assert process.wait(timeout=8) == 0, process.stderr.read()
        assert termios.tcgetattr(slave) == original, "terminal was not restored"
        # Drain cleanup bytes after process completion.
        while select.select([master], [], [], 0)[0]:
            received += os.read(master, 65536)
        assert b"\x1b[?25h" in received, received
        if mode != "inline":
            assert b"\x1b[?1049l" in received, received
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        os.close(master)
        os.close(slave)


def main():
    assert COMPILER, "set OCEAN to the matching compiler"
    with tempfile.TemporaryDirectory(prefix="ocean-tui-") as directory:
        root = Path(directory)
        executable = str(root / "tui")
        env = dict(os.environ, OCEAN_SRC=str(ROOT), OCEAN_BUILD_CACHE=str(root / "cache"))
        fixture = str(Path(__file__).parent)
        run(COMPILER, "check", fixture, env=env)
        for cache in (str(root / "cache"), str(root / "cache"), "off"):
            env["OCEAN_BUILD_CACHE"] = cache
            run(COMPILER, "build", fixture, "-o", executable, env=env)
            for mode in ("async", "pointer", "send", "quit", "order", "cancel", "cancel-tree", "command-panic", "stress"):
                run(executable, mode)
            source, destination = root / "input", root / "output"
            source.write_text("asynchronous I/O\n")
            run(executable, "io", str(source), str(destination))
            assert destination.read_bytes() == source.read_bytes()
        for _ in range(10):
            run(executable, "async")
            run(executable, "cancel")
        for mode in ("terminal", "inline", "panic"):
            terminal(executable, mode)
        failed = subprocess.run([executable, "terminal"], stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
        assert failed.returncode == 1 and b"tui output must be a terminal" in failed.stderr
        run(COMPILER, "check", str(ROOT / "term/tui/examples/counter"), env=env)
    print("tui command, model interface, I/O, cancellation, and PTY tests passed")


if __name__ == "__main__":
    main()
