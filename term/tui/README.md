# tui

Import `"term/tui"`. A terminal application follows the model/update/view pattern
of [Bubble Tea](https://github.com/charmbracelet/bubbletea). Native commands use
`threads`; terminal setup and sizing use `term`.

```ocean
interface Model {
    Init() Cmd;
    Update(message Msg) (Model, Cmd);
    View() string;
}
type Msg = any;
type Cmd = func() Msg;
```

`Init` returns the first effect. `Update` handles one message and returns the next
model and effect. `View` describes the current display. These methods run
serially on the thread calling `Run`. A value model returns a modified copy from
Update; a pointer model mutates its state and returns the same pointer. Models
satisfy the interface structurally; no callback adapters are needed.

Commands run on native workers and return messages to Update. Keep model
mutation in Update. Capture command inputs as snapshots rather than accessing
mutable model state from a command. Messages own copies of strings and other
value collections; pointers in messages still borrow their pointees.

## Example

```ocean
package main;
import "term/tui";
import "io";
import "time";

struct counter { count int; }
struct tickMsg {}
func (model counter) Init() tui.Cmd { return tui.Tick(time.Second, tickMsg{}); }
func (model counter) Update(message tui.Msg) (tui.Model, tui.Cmd) {
    switch (event := message.(type)) {
        case tui.KeyMsg:
            if (event.Key == "ctrl+c" || event.Text == "q") return model, tui.Quit;
            if (event.Key == "up") model.count++;
        case tickMsg:
            model.count++;
            return model, tui.Tick(time.Second, tickMsg{});
    }
    return model, tui.NoCmd;
}
func (model counter) View() string {
    return "Count: " + io.Sprint(model.count) + "\n↑ to increment, q to quit";
}
func main() {
    program := tui.NewProgram(counter{}, tui.Options{AltScreen: true});
    final := program.Run().unwrap();
    // final is a Model interface; final.(counter) retrieves the final value.
}
```

Run the complete [counter example](examples/counter/main.oc) with
`ocean run term/tui/examples/counter` from the library checkout.

## Program

| API | Behavior |
| --- | --- |
| `NewProgram(model Model, options ...Options) Program` | Construct a single-use program; accepts zero or one Options value. |
| `(*Program).Run() Result<Model>` | Run until Quit and return the final model; terminal/I/O failures and command panics return errors. |
| `(*Program).Send(message Msg) bool` | Thread-safe FIFO enqueue; works before Run, returns false after shutdown. |
| `(*Program).Quit() bool` | Thread-safe enqueue of QuitMsg. |

Keep a Program at a stable address and do not copy it after first use: it contains
a mutex. Keep it alive until all external Send callers have finished. The queue
is unbounded. FIFO order is enqueue order; concurrent effects may finish in any
order. QuitMsg is processed in that order and pending messages may be discarded.

`Options{}` uses stdin/stdout in raw mode, hides the cursor, and redraws from the
current line. `AltScreen: true` uses the alternate screen and restores the
previous screen on exit. `Headless: true` disables terminal input, size messages,
raw mode, View calls, and rendering, allowing command-only applications and tests
without a terminal. Headless takes precedence over AltScreen.

Only one terminal program may own a terminal at a time. Do not read stdin or
write stdout elsewhere while Run owns them. Use View for terminal output.
Terminal settings, cursor visibility (restored visible), the alternate screen,
and Windows output mode are restored on normal return, returned errors, and
ordinary Ocean panic unwinding from model methods. Model panics propagate.
SIGKILL, default OS signal termination, os.Exit, and native crashes bypass defers.
Command panics are recovered by the command runner and returned as Run errors.

Shutdown requests cancellation of outstanding commands, including nested Batch
children, and joins them before Run returns. Command defers run. Cancellation is
cooperative: arbitrary blocking native I/O may delay joins until the native call
returns. Terminal restoration happens before those joins. Commands should use
bounded I/O or application-specific cancellation; Run cannot forcibly interrupt
a blocking native read. Do not call threads.Return or Kill on the Run thread.

## Commands and async I/O

| API | Behavior |
| --- | --- |
| `NoCmd` or `zero(tui.Cmd)` | No effect. Return the function value, without calling it. |
| `Quit` | Command returning QuitMsg. |
| `Batch(commands ...Cmd) Cmd` | Execute child commands concurrently; deliver results as each finishes. |
| `Sequence(commands ...Cmd) Cmd` | Execute commands in order; a nested Batch finishes before the next command starts. |
| `Tick(nanoseconds int, message Msg) Cmd` | One-shot approximate timer using time units; negative durations panic. Schedule another in Update to repeat. |
| `Read(file os.File, count int) Cmd` | Read up to count bytes, returning ReadMsg or ErrorMsg; count must be positive. |
| `Write(file os.File, text string) Cmd` | Write all text, returning WriteMsg or ErrorMsg. |

Sequence enqueues results in order; it does not wait for Update to process a
result before starting the next effect. Empty composites are valid. NoCmd,
NoneMsg, and composite command control messages are never sent to Update.
The event loop polls approximately every 5ms; Tick uses time.Sleep and is
subject to native timer resolution and scheduling delays. Each ordinary effect uses a native thread. Batch is
unbounded; choose a bounded amount of work rather than creating thousands of
simultaneous threads.

Custom commands can perform I/O and return any application-defined message:

```ocean
func load(file os.File) tui.Cmd {
    return func() tui.Msg {
        result := file.Readchunk(4096);
        if (result == Result<i8[]>.error) return tui.ErrorMsg{result.(Result<i8[]>.error)};
        return tui.ReadMsg{Bytes: result.unwrap()};
    };
}
```

Open streams before Run and close them after Run returns. Give each stream one
reader/writer at a time, and do not use these helpers on the terminal's own
stdin/stdout. The existing os file registry and term saved-state registry do not
provide internal synchronization: concurrent opening/closing/registering streams
while Run uses the terminal is unsupported. Preopened, independent streams avoid
registry mutation. User-created threads and resources remain the caller's
responsibility. Normal I/O failures become ErrorMsg, not automatic termination.

## Messages and input

| Message | Fields and meaning |
| --- | --- |
| `KeyMsg` | `Key string`, `Text string`, `Alt bool`. Text contains one UTF-8 scalar for printable input; other keys have empty Text. |
| `WindowSizeMsg` | `Width int`, `Height int` in terminal cells; initially queued before Init results, then when dimensions change. |
| `ReadMsg` | `Bytes i8[]`, `End bool`; empty successful read reports End. A short nonempty read does not imply EOF. |
| `WriteMsg` | `Bytes int` successfully written. |
| `ErrorMsg` | `Error string` from an I/O command. |
| `EOFMsg` | Terminal input ended; input polling stops. Update decides whether to quit. |
| `QuitMsg` | Stops Run; not delivered to Update. |
| `NoneMsg` | Ignored. |

Key names are `rune`, `space`, `enter`, `tab`, `backspace`, `esc`, `up`, `down`,
`left`, `right`, `home`, `end`, `insert`, `delete`, `pgup`, `pgdown`, `shift+tab`,
`f1`–`f12`, and `ctrl+a`–`ctrl+z` (with enter/tab/backspace taking precedence).
NUL is `ctrl+space`; remaining control bytes use their numeric value, such as
`ctrl+28`. Alt prefixes set Alt. Split UTF-8 and common CSI/SS3 key sequences are
buffered; a lone Escape waits about 30ms. Invalid UTF-8 yields replacement
characters. Unrecognized escape sequences produce `Key: "unknown"`.
Ctrl+C is a KeyMsg in raw mode; handle it explicitly to quit.

Sizing is polled approximately every 100ms, without installing signal handlers.
Views redraw when changed or resized, clear stale content, translate newlines
to CRLF, and accept SGR color/style escapes. Other control characters are
filtered. The viewport clips excess lines and columns, reserving the last
column to avoid autowrap. Common combining and East Asian widths are estimated;
full grapheme/emoji layout, mouse input, bracketed paste, focus events, and
extended keyboard protocols are not implemented.

## Platforms and tests

Uses the existing native term/threads platforms: Linux x86-64/AArch64/RISC-V64,
macOS x86-64/AArch64, and Windows x86-64/AArch64 with a VT-capable console.
Windows output VT mode is enabled and restored. Native threading makes Wasm
compilation fail. Linux PTY behavior is tested; real Windows/macOS execution
requires validation on those hosts.

Use the matching compiler with interface method dispatch and native threads:

```sh
OCEAN=/path/to/ocean python3 term/tui/tests/test_tui.py
```

The harness checks cached, warm-cache, and uncached builds; value/pointer model
dispatch; concurrent owned messages; batching/sequencing; async file I/O;
cancellation; command panics; and POSIX PTY input, resize, and terminal cleanup.
