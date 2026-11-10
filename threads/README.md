# Native threads

`import "threads";` starts native OS threads from first-class Ocean functions.
This package requires the matching updated compiler and supports POSIX threads
on Linux/macOS and Win32 threads on Windows. Compilation for Wasm fails.

| Function | Behavior |
| --- | --- |
| `Spawn(job func()) int` | Start a function or closure and return its positive ID. Panics on failure or an uninitialized function. |
| `CurrentID() int` | Return the caller's ID. Main is always 0. |
| `Await(id int)` | Block until completion and join the worker. Multiple and repeated awaits work. Awaiting yourself panics. |
| `IsDone(id int) bool` | Report whether the thread's function and deferred calls have finished. |
| `Yield()` | Park the caller until woken while parked. |
| `Wake(id int)` | Resume a yielded thread. Wakes of running/completed threads are discarded. Unknown IDs panic. |
| `Return()` | Run defers and exit just the caller, from any call depth. |
| `Kill(id int)` | Request cancellation of a thread. Call Await afterward to wait for termination. Completed threads are unaffected. |

IDs are monotonically allocated and never reused. Completed IDs remain valid.
All identifier-taking functions panic for unknown IDs, including negative IDs.

`Kill` is cooperative: compiler checkpoints cover function entries, loop
iterations, and goto jumps. Yield, Await, mutex waits, and wait-group waits also
check cancellation. Arbitrary blocking native calls and long inline assembly
cannot be interrupted until execution reaches a checkpoint. Deferred cleanup
is not interrupted. Return and cancellation cannot be stopped by recover;
recover returns null during their cleanup. Use deferred Unlock and Done calls.
An unrecovered panic terminates the whole program after reporting the error.

Normal main return marks ID 0 done and waits for workers before process cleanup.
Wake yielded workers before returning from main. Return or Kill of ID 0 stops
main while letting workers continue. `os.Exit(code)` immediately exits the whole
process and all threads without defers or cleanup.

Closures share captured variables. Protect shared mutation with `sync` and
await workers before borrowed pointers go out of scope. Other standard-library
registries such as `os.File` state also require caller synchronization.

The native runtime is compiled into the program support object and cached.
Only programs using native threading/synchronization receive it and, on POSIX,
the `-pthread` link option. Windows uses Win32 APIs and does not link pthread.

Run `OCEAN=/path/to/matching/ocean python3 threads/tests/test_threads.py`.
Tests cover native Linux behavior and, when compiler sources are available,
Windows runtime control flow through a POSIX test shim. Real Windows and macOS
hosts are still needed to validate those OS ABIs.
