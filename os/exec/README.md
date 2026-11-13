# os/exec

Go-inspired process execution on Linux (x86-64, AArch64, RISC-V), macOS
(x86-64, AArch64), and Windows (x86-64, AArch64). Arguments go
directly to the executable; no shell is inserted. Functions return `Result<T>`.

```ocean
import "os/exec";

command := exec.Command("printf", "%s", "hello world");
output := command.Output().unwrap();
command = exec.Command("/bin/sh", "-c", "printf '%s' \"$GREETING\"");
command.Env = string[]{"GREETING=hello"};
command.Dir = "/tmp";
output = command.CombinedOutput().unwrap();
```

- `Command(name string, args ...string) Cmd` constructs a command.
- `LookPath(name string) Result<string>` finds an executable using PATH, or checks
  an explicit path. Implicit relative PATH results are rejected.
- `Cmd` has `Path`, `Args` (arguments excluding argv[0]), `Dir`, `Env`, and
  `ExitCode` fields. Empty Dir inherits the working directory. Empty Env inherits
  the environment; a nonempty Env replaces it with `KEY=value` strings.
- `Run() Result<int>` inherits standard streams and returns the zero exit code on
  success. `Output() Result<string>` captures stdout and inherits stderr.
  `CombinedOutput() Result<string>` captures stdout and stderr in one file,
  preserving their write order.

A command may be executed once. Missing executables, invalid NUL-containing
arguments/paths/environment entries, spawn failures, wait failures, and nonzero
or signal exits return errors. ExitCode is -1 before completion or on a signal,
otherwise the process's exit code. Output methods return an error on a nonzero
exit and do not return partial output alongside that error.

Output capture uses temporary files rather than pipes, so a child producing
more than a pipe buffer of output does not deadlock. Temporary files and spawn
actions are released, and interrupted waits are retried. Output is returned
as an owned string, including embedded NUL bytes.

The initial implementation has no Start/Wait, pipes, configurable standard
streams, context cancellation, timeout, or Wasm backend. Empty Env
cannot request an empty child environment. Child output capture requires a
writable system temporary directory and has no output-size bound.

Run `ocean test os/exec`; tests use local Unix tools or Windows PowerShell and do not require network
access. Use the matching compiler and this standard-library source tree.

The matching compiler supplies the native process bridge: POSIX spawn on Unix
and Unicode CreateProcess on Windows. Windows argument quoting preserves spaces,
quotes and backslashes without invoking a shell.
