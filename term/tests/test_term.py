#!/usr/bin/env python3
"""Linux PTY integration tests. Run: python3 term/tests/test_term.py"""
import fcntl
import os
from pathlib import Path
import pty
import select
import shutil
import struct
import subprocess
import tempfile
import time
import termios

ROOT = Path(__file__).resolve().parents[2]


def line(process, expected):
    assert select.select([process.stdout], [], [], 10)[0], f"timeout waiting for {expected}"
    actual = process.stdout.readline().decode().strip()
    assert actual == expected, (expected, actual)


def drain(master):
    data = b""
    while select.select([master], [], [], 0)[0]:
        data += os.read(master, 4096)
    return data


def terminal_test(executable, mode):
    master, slave = pty.openpty()
    original = termios.tcgetattr(slave)
    # Exercise preservation of settings that differ from the usual defaults.
    original[6][termios.VMIN] = 3
    original[6][termios.VTIME] = 2
    termios.tcsetattr(slave, termios.TCSANOW, original)
    original = termios.tcgetattr(slave)
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 37, 101, 0, 0))
    process = subprocess.Popen([executable, mode], stdin=slave, stdout=subprocess.PIPE, bufsize=0)
    try:
        line(process, "RAW")
        raw = termios.tcgetattr(slave)
        assert not raw[3] & (termios.ICANON | termios.ECHO | termios.ISIG | termios.IEXTEN)
        assert not raw[1] & termios.OPOST
        assert raw[6][termios.VMIN] == 1 and raw[6][termios.VTIME] == 0
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
        os.write(master, b"x")
        line(process, "RESTORED")
        assert termios.tcgetattr(slave) == original, (termios.tcgetattr(slave), original)
        os.write(master, b"\n")
        line(process, "PASSWORD")
        # ReadPassword switches echo off after printing PASSWORD; wait for it.
        deadline = time.monotonic() + 10
        while termios.tcgetattr(slave)[3] & termios.ECHO:
            assert time.monotonic() < deadline, "password echo was not disabled"
            time.sleep(0.001)
        drain(master)
        os.write(master, b"secrex\x7ft\n")  # canonical erase still works
        line(process, "READ")
        assert drain(master) == b"", "password was echoed"
        assert termios.tcgetattr(slave) == (raw if mode == "password-raw" else original)
        os.write(master, b"\n")
        line(process, "OK")
        assert process.wait(timeout=10) == 0
        assert termios.tcgetattr(slave) == original, (termios.tcgetattr(slave), original)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        os.close(master)
        os.close(slave)


def password_edge_test(executable, mode):
    master, slave = pty.openpty()
    original = termios.tcgetattr(slave)
    if (mode == "password-error"):
        fcntl.fcntl(slave, fcntl.F_SETFL, os.O_NONBLOCK)
    process = subprocess.Popen([executable, mode], stdin=slave, stdout=subprocess.PIPE, bufsize=0)
    try:
        if mode == "password-eof":
            deadline = time.monotonic() + 10
            while termios.tcgetattr(slave)[3] & termios.ECHO:
                assert time.monotonic() < deadline
                time.sleep(0.001)
            os.write(master, b"\x04")
        line(process, "OK")
        assert process.wait(timeout=10) == 0
        assert termios.tcgetattr(slave) == original
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        os.close(master)
        os.close(slave)


def main():
    with tempfile.TemporaryDirectory(prefix="ocean-term-") as directory:
        executable = str(Path(directory) / "test-term")
        env = dict(os.environ, OCEAN_SRC=str(ROOT), OCEAN_BUILD_CACHE=str(Path(directory) / "cache"))
        compiler = os.environ.get("OCEAN", shutil.which("ocean") or "ocean")
        subprocess.run([compiler, "check", str(ROOT / "term")], env=env, check=True)
        subprocess.run([compiler, "build", str(Path(__file__).parent), "-o", executable], env=env, check=True)
        for mode in ("pipe", "invalid"):
            result = subprocess.run([executable, mode], input=b"", capture_output=True, timeout=10)
            assert result.returncode == 0 and result.stdout == b"OK\n", result
        with open(__file__, "rb") as file:
            result = subprocess.run([executable, "pipe"], stdin=file, capture_output=True, timeout=10)
            assert result.returncode == 0 and result.stdout == b"OK\n", result
        for mode in ("password", "password-raw"):
            terminal_test(executable, mode)
        for mode in ("password-error", "password-eof"):
            password_edge_test(executable, mode)
    print("terminal tests passed")


if __name__ == "__main__":
    main()
