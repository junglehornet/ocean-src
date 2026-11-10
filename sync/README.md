# Synchronization

`import "sync";` provides zero-value mutexes and wait groups for native threads.
Keep these values at stable addresses and do not copy them after first use.
Methods have pointer receivers. Shared state becomes visible to a thread after
it acquires a mutex or returns from the corresponding wait.

| Type | Methods |
| --- | --- |
| `Mutex` | `Lock()`, `Unlock()`, `TryLock() bool` |
| `WaitGroup` | `Add(delta int)`, `Done()`, `Wait()` |

Mutexes are nonrecursive. Lock blocks until it can acquire ownership; TryLock
reports success without waiting for ownership. Unlocking an unlocked mutex
panics. Like Go, a mutex may be unlocked by a different thread. Register a
deferred Unlock immediately after successfully locking when cancellation or
Return can occur.

Add work before spawning it. Done subtracts one; Wait blocks until the count
reaches zero. Multiple waiters are supported. Negative counts, overflow, and
starting a new group while previous Wait calls are returning panic. Reuse only
after every preceding Wait has returned. Register deferred Done for each task
so thread termination does not leave unfinished work.

Native state is lazily initialized and retained until process shutdown. Linux
and macOS use pthreads; Windows uses Win32 synchronization. Wasm compilation
fails. Mutex and wait-group waits can be interrupted by threads.Kill, which
runs deferred cleanup before terminating the caller.
