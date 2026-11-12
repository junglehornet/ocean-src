# testing

## Unit tests

Run `ocean test [location]` to compile and execute a package's tests. A location
is a directory or an Ocean file selecting its containing package; it defaults to
`.`. Test source filenames must end in `_test.oc`. Normal `build`, `run`, and
`check` commands always ignore these files, including those in dependencies.
Test sources are never linked into a normal executable or library object.

Tests are top-level functions whose names start with `Test`, with exactly one
`*testing.T` parameter and no results, type parameters, or variadic parameters:

```ocean
// arithmetic_test.oc
package arithmetic;
import "testing";

func TestAnswer(t *testing.T) {
    if (privateAnswer() != 42) t.Fatal("wrong answer");
    t.Run("positive", func(t *testing.T) {
        if (Add(2, 3) != 5) t.Errorf("Add(2, 3): wanted {}, got {}", 5, Add(2, 3));
    });
}
```

Same-package test files share private declarations with the package. Files
with `package arithmetic_test;` form a separate external test package in the
same directory. They must import the package under test and can access only its
exported declarations. Both kinds run in one temporary test executable. A
production `main` function is preserved for normal builds and replaced by the
generated test entry point only in test builds. Imported packages' tests do not
run as part of the target package's suite.

`testing.T` supports `Run(name, callback) bool`, `Parallel(name, callback)`,
`Error`, `Errorf`, `Fatal`,
`Fatalf`, `Fail`, `FailNow`, `Failed`, `Log`, `Logf`, `Skip`, `Skipf`, `SkipNow`,
`Skipped`, `Name`, `Cleanup`, and `Helper`. Format methods use Ocean's `{}`
format placeholders. `Error` marks failure and continues; `Fatal` stops the
current test, runs its defers and cleanup callbacks, and lets other tests run.
`Run` waits for its subtest and cleanups, returns false on failure, and propagates
failure to the parent. `Cleanup` callbacks run in reverse order, including after fatal errors
and panics. A panic fails the current test; subsequent tests continue. `Helper`
is accepted but does not currently alter source-location reporting. There is no
benchmark API yet. Do not call fatal/skip methods from a thread
created by the test; they terminate their calling thread.

Top-level `Test*` functions run through one shared work queue with up to 16
managed OS worker threads by default (or fewer when there are fewer tests).
Each worker pulls another function when it finishes. Use `-t N` to choose a
positive worker count or `--single-threaded` for one top-level worker. Workers
are reused across tests; workers stopped by Fatal, skips, or threads.Return
are joined and replaced when pending work remains.

`t.Run(name, callback) bool` starts a synchronous subtest and waits for its
completion and cleanup. `t.Parallel(name, callback)` starts an asynchronous
subtest on an additional OS thread and returns immediately, with no result.
The pool limit does not cap subtest threads: Parallel may start more than 16
children, including with `-t 1` or `--single-threaded`. This is an async version
of Run, rather than Go’s no-argument Parallel scheduling marker.

After a parent body returns or stops, the runner joins all of its async children
before running the parent’s Cleanup callbacks and reporting its final status.
This applies recursively to nested subtests. Child failures propagate to the
parent. Ordinary defers run when the body exits; use `t.Cleanup` for resources
that async children still need. Subtests cannot be started from cleanup.
`testing.T` synchronizes its failure/skip flags, cleanup registrations, and
subtest bookkeeping, and serializes log events. Protect shared test fixtures
with synchronization or use `--single-threaded` for sequential top-level tests.

```ocean
func TestConcurrent(t *testing.T) {
    t.Parallel("first", func(t *testing.T) { /* first check */ });
    t.Parallel("second", func(t *testing.T) { /* second check */ });
    // Both subtests can run before this body returns.
}
```

Interactive terminals show a live [tang](https://github.com/ansel1/tang)-style
TUI implemented in Ocean with `term/tui`. It updates running and completed tests,
nested subtests, live output, status counts (▶ / ⏸ / ✓ / ✗ / ∅ / ∑), and elapsed
time. The frontend handles terminal resizing; use ↑/↓ or Page Up/Page Down to
scroll, `f` or End to follow recent tests, and `q` or Ctrl+C to stop the suite.
After execution, the live view is cleared and the final report is printed.

The TUI requires terminal stdin/stdout and a TERM other than `dumb`.
`--notty` (also `-notty` or `--no-tui`) disables it. `--json` and redirected
output always use their noninteractive formats. `NO_COLOR` and `--no-color`
disable colors while retaining live progress and terminal redraw controls.
The frontend is shipped in `testing/internal/display` and uses `term/tui` from
the selected standard library. It is compiled and cached separately from the
test executable. If the frontend is unavailable, the final report still works.
While the TUI owns keyboard input, tests receive EOF on stdin; use `--notty`
for tests that need stdin. Test stdout/stderr remain captured in all modes.

The final report follows [tang](https://github.com/ansel1/tang)'s static
Messages/Summary format: nested failure and skip details, aligned package and
suite counts under ✓ / ✗ / ∅ / ∑ / ⏱ headers, and elapsed durations. Passing
details are hidden unless requested. `NO_COLOR` (including an empty value) or
`--no-color` disables automatic terminal color. Redirected output and report
files are plain text. The report counts both tests and subtests, as tang does.

```sh
ocean test .
ocean test . -v                         # include passed tests in the final report
ocean test . --notty                    # disable the live TUI
ocean test . -t 4                       # up to four top-level workers
ocean test . --single-threaded          # one top-level worker
ocean test . --json                     # JSON events on stdout
ocean test . --outfile results.txt      # save the plain report too
ocean test . --jsonfile results.jsonl    # save JSON events too
ocean test . --json --outfile results.txt --jsonfile results.jsonl
ocean test . --timeout 30s               # default 10m; 0 disables timeout
NO_COLOR=1 ocean test .
```

`-o` aliases `--outfile`; `-json`, `-outfile`, and `-jsonfile` spellings also
work. `--hide-skipped` omits skipped-test details while retaining their counts.
Timeout durations accept `ms`, `s`, `m`, or a number of seconds. A timed-out or
abnormally terminated test process fails the suite. The command exits zero for
success (including an empty suite), nonzero for a failed test, compilation,
report writing, timeout, or abnormal process exit. Runtime execution preserves
the caller's working directory and captures stdout/stderr. The private test
executable is removed when the command finishes.

JSON output consists of one event per line with `Time`, `Action`, `Package`,
`Elapsed` (seconds), and optional `Test` and `Output` fields. Actions include
`start`, `run`, `output`, `pass`, `fail`, and `skip`; slash-separated test names
identify nested subtests. Package completion reflects the actual process exit.
Arbitrary stdout/stderr becomes package-level `output` events, so it cannot
corrupt the JSON stream. `t.Log`/error messages are associated with their test.
The event shape can also be consumed by tang. Tests currently require a native
host target and the matching `testing`, `threads`, and `sync` library sources.
Test binaries are compiled separately without using normal package object cache
entries. This command accepts one package location per invocation.
