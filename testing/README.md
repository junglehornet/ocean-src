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

`testing.T` supports `Run(name, callback) bool`, `Error`, `Errorf`, `Fatal`,
`Fatalf`, `Fail`, `FailNow`, `Failed`, `Log`, `Logf`, `Skip`, `Skipf`, `SkipNow`,
`Skipped`, `Name`, `Cleanup`, and `Helper`. Format methods use Ocean's `{}`
format placeholders. `Error` marks failure and continues; `Fatal` stops the
current test, runs its defers and cleanup callbacks, and lets other tests run.
`Run` waits for its subtest and cleanups, returns false on failure, and propagates
failure to the parent. Tests and subtests run sequentially on managed native
threads. `Cleanup` callbacks run in reverse order, including after fatal errors
and panics. A panic fails the current test; subsequent tests continue. `Helper`
is accepted but does not currently alter source-location reporting. There is no
parallel-test or benchmark API yet. Do not call fatal/skip methods from a thread
created by the test; they terminate their calling thread.

The default report follows [tang](https://github.com/ansel1/tang)'s static
Messages/Summary format: nested failure and skip details, aligned package and
suite counts under ✓ / ✗ / ∅ / ∑ / ⏱ headers, and elapsed durations. Passing
details are hidden unless requested. `NO_COLOR` (including an empty value) or
`--no-color` disables automatic terminal color. Redirected output and report
files are plain text. The report counts both tests and subtests, as tang does.

```sh
ocean test .
ocean test . -v                         # include passed tests and logs
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
