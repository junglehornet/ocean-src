# time

Import `"time"`. `Sleep(nanoseconds int)` blocks the calling thread for the
requested duration, subject to the operating system's timer resolution and
scheduling delays. Zero and negative durations return immediately.

```ocean
package main;
import "time";

func main() {
    time.Sleep(10 * time.Millisecond);
    time.Sleep(500 * time.Microsecond);
}
```

| Unit | Nanoseconds (`int`) |
| --- | ---: |
| `Nanosecond` | 1 |
| `Microsecond` | 1,000 |
| `Millisecond` | 1,000,000 |
| `Second` | 1,000,000,000 |

Ocean currently has no constant declaration. These are exported integer bindings
used as constants by convention; do not assign to them. Duration arithmetic is
ordinary signed 64-bit integer arithmetic; ensure products fit in `int`.

Linux x86-64/AArch64/RISC-V64 use native nanosleep system calls. macOS
x86-64/AArch64 use nanosleep and retry EINTR with the remaining duration.
Linux likewise resumes interrupted sleeps. Windows x86-64/AArch64 use a relative
waitable timer, rounding nanoseconds upward to 100ns timer units; actual timer
resolution depends on the host. No busy waiting or timer-resolution changes are
used. Native failures panic. Unsupported platforms, including Wasm, panic for
positive durations; nonpositive durations still return immediately.

Long waits are split into at most 50ms native waits, allowing cooperative thread
cancellation at compiler checkpoints between waits when threading is enabled.
The package does not import threads or sync and does not require pthread
linking by itself. Scheduling delays and interruption handling can lengthen a
sleep; nanosecond input does not promise nanosecond precision. Real Windows and
macOS execution still requires host validation.

Run `OCEAN=/path/to/ocean python3 time/tests/test_time.py` to check unit values,
cached/uncached builds, nonpositive/tiny/multichunk sleeps, no threading runtime
dependency, and repeated signal interruption on Linux.
