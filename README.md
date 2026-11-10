# Ocean-src

The standard library for the [Ocean programming language](https://ocean-lang.dev).
Use this source tree with the matching `ocean-c` compiler (`OCEAN_SRC` selects it).
It is loaded as Ocean source; do not precompile it.

`io` has no `extern` declarations. Its public printing and formatting functions
keep their existing signatures. Stdout is implemented with platform assembly:

| Platform | Architectures | Interface |
| --- | --- | --- |
| Linux | `x86_64`, `aarch64`, `riscv64` | `write` system call |
| macOS | `x86_64`, `aarch64` | Darwin `write` system call |
| Windows | `x86_64`, `aarch64` | `GetStdHandle` and `WriteFile` called from assembly |

Partial writes are completed and interrupted Unix writes are retried. Other
write failures return error Results. Unimplemented architecture/platform combinations report
unsupported stdout rather than silently dropping nonempty output. Windows uses
the stable Win32 API instead of version-dependent raw syscall numbers; link
`kernel32` when manually linking emitted LLVM (`-lkernel32`). The compiler adds
this library to native Windows executable links.

Float formatting is implemented in Ocean, with exact IEEE binary64 conversion
and round-to-nearest, ties-to-even decimal rounding. It handles subnormals,
signed zero, infinities and NaNs independently of the C locale. Default printed
floats use two decimal places. The internal `sprintFloat(x, -1)` formatter uses
17 significant digits for round trips. This removes `snprintf` from the library;
the compiler runtime and boxed values still use native libraries/libffi.

This library requires compiler support for `${name}` read/write scalar memory
operands in `asm architecture/platform { ... }`, aligned asm entry stacks, and
red-zone protection around native calls. See `skills/ocean/SKILL.md` in the
compiler checkout for operand rules and reserved registers.

The OS interfaces follow the [Linux syscall ABI](https://man7.org/linux/man-pages/man2/syscall.2.html),
[Darwin syscall definitions](https://github.com/apple-oss-distributions/xnu/blob/main/libsyscall/custom/SYS.h),
and Microsoft's [GetStdHandle](https://learn.microsoft.com/en-us/windows/console/getstdhandle)
and [WriteFile](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-writefile)
contracts.

## Input scanning and files

Recoverable standard-library I/O failures return `Result<T>`. Use `.unwrap()` to
panic on an error, or inspect the error variant to recover. `Close()` and
`Setpos()` return no value and panic on failure; neither returns `Result<unit>`.

`os.Stdin()`, `os.Stdout()`, and `os.Stderr()` return `Result<os.File>`.
Stdin is readable; stdout and stderr are writable and cannot be scanned.
`os.Open(path string, mode os.FileMode)` also returns `Result<os.File>`.
Modes are `Read`, `Write` (create/truncate), `ReadWrite` (create without
truncating), `Append`, and `ReadAppend`. Binary counterparts are `Binary`
(read-only), `BinaryWrite`, `BinaryReadWrite`, `BinaryAppend`, and
`BinaryReadAppend`. `io.NewScanner(file)` panics for binary, closed, or
nonreadable files. Copies share native cursor, close state and EOF state.

```oc
package main;
import "io";
import "os";

func main() {
    file := os.Open("input.txt", os.FileMode.Read).unwrap();
    scanner := io.NewScanner(file);
    line := scanner.Scanln().unwrap();
    io.Println(line).unwrap();
    file.Close();
}
```

`io.Scan()` and `io.Scanln()` return `Result<string>` using a shared stdin
scanner. Scanner `Scan()`, `Scanln()`, and `Scanc(delimiter i8)` likewise return
`Result<string>`. They consume the delimiter and return an empty string when it
is immediately encountered. Scan stops at ASCII whitespace; Scanln stops at
newline or EOF; a preceding CR is retained. Scanc stops at the requested
byte or EOF. EOF is a successful result, including an empty string.

`scanner.Scann(n)` returns `Result<io.ScanResult>`, with `Bytes i8[]` and
`End bool` fields. It reads up to n bytes; End is true when EOF prevents filling
the request. Unlike File.Readn, the scanner buffer contains only bytes read.
Zero reads succeed without consuming input; negative sizes panic.
`HasNext()`, `HasNextln()`, and `HasNextc(delimiter)` return `Result<bool>`.
They inspect buffered input and check OS readiness without waiting for more
input, returning true for a complete delimited segment or remaining EOF data.
Readiness errors return errors rather than false. Readiness is a snapshot;
another reader can consume data before a subsequent scan.

## Byte reads, binary files, and file positions

| File method | Return value and behavior |
| --- | --- |
| `Read()` | `Result<int>`: unsigned byte 0–255, or -1 at EOF |
| `Readn(n)` | `Result<os.ReadResult>`: `Bytes array<i8>` of length n, `End bool` for early EOF; unused bytes are zero-filled |
| `Readend()` | `Result<array<i8>>`: current position through EOF, advances cursor |
| `Readall()` | `Result<array<i8>>`: entire file, preserves cursor and previous EOF state |
| `Readchunk(n)` | `Result<i8[]>`: up to n bytes; successful empty buffer at EOF |
| `Size()` | `Result<int>`: size in bytes, requires a seekable file |
| `PollRead()` | `Result<int>`: OS readiness information without blocking |
| `Write(text)` | `Result<int>`: number of bytes written |
| `Close()` | Closes the shared file; repeated close succeeds; native failure panics |
| `Setpos(position)` | Sets next byte offset from 0 through size inclusive; bounds and native failures panic |

```oc
file := os.Open("data.bin", os.FileMode.Binary).unwrap();
read := file.Readn(16).unwrap();
bytes := read.Bytes;
shortRead := read.End;
file.Setpos(0);
wholeFile := file.Readall().unwrap();
file.Close();
```

Read, Readn and Readend advance the shared position. Readall attempts to restore
the cursor even after a read failure; restoration failure returns an error and
invalidates buffered scanner state. Setpos also invalidates scanner buffers.
Another Read after EOF has already been reported panics. Negative sizes panic.
Ordinary access errors, closed files and native I/O errors return error Results,
not EOF. Failed operations can have consumed bytes or written part of the output.
Close failures are not retried because the OS may already have released the handle.

`File.IsOpen()`, `CanRead()`, `CanWrite()`, and `IsBinary()` return bool.
`os.FromDescriptor(fd, readable, writable)` adopts a native descriptor as a text
stream; negative descriptors panic. `File.NativeHandle()` returns the native
handle and panics when closed. Keep one scanner per stream and avoid mixing its
buffered reads with direct reads or writes.

`io.Print`, `Println`, `Printf`, and `Printfln` return `Result<int>` containing
the emitted byte count, including a newline where applicable. `io.Sprintf`
returns `Result<string>` and reports argument-count mismatches as errors.
`io.Sprint` remains a plain string conversion. Unix writes retry interruptions;
other native output failures return errors.

## Built-in Result and number parsing

`Result<T>` is available without imports or standard-library files. It is the
compiler-owned equivalent of:

```ocean
enum Result<T> { value(T), error(string) }
```

Construct values with explicit type arguments, for example
`Result<int>.value(42)` or `Result<float>.error("invalid number")`. Use normal
variant comparisons, extraction, and `match` to inspect either case. Its
lowercase variants and methods are public language built-ins, independent of
package capitalization rules; ordinary package members retain those rules.
A user-declared Result may shadow the built-in name and remains a distinct type.

| Method | value case | error case |
| --- | --- | --- |
| `unwrap() T` | Returns the payload | Returns a panic containing the stored error string, attributed to the caller |
| `unwrapOrElse(fallback T) T` | Returns the payload | Returns the provided fallback value |
| `unwrapOrZero() T` | Returns the payload | Returns `zero(T)` |

`unwrapOrElse` accepts a value, not a callback; its argument is evaluated with
normal function-call rules even when the Result holds a value. Payloads and
fallbacks retain ordinary value-copy and ownership behavior. `zero(T)` follows
Ocean's existing zero semantics, including a zero-address pointer distinct from
explicit `null`.

```ocean
package main;
import "io";

func main() {
    count := io.ParseInt("42").unwrap();
    ratio := io.ParseFloat("1.25e-2").unwrapOrElse(0.0);
    result := io.ParseInt("not a number");
    match(result) {
        Result<int>.value(value) => io.Println(value);
        Result<int>.error(message) => io.Println(message);
    }
    io.Println(count, " ", ratio);
}
```

`io.ParseInt(text string) Result<int>` parses the entire string as a signed
base-10, 64-bit integer. It accepts an optional leading `+` or `-` and one or more
ASCII decimal digits, including leading zeros. Both -9223372036854775808 and
9223372036854775807 are supported. Empty input, a sign alone, whitespace, digit
separators, base prefixes, fractions, trailing characters, and overflow produce
an error Result instead of panicking.

`io.ParseFloat(text string) Result<float>` parses a binary64 value from an
optional sign, decimal digits with an optional point, and an optional signed
`e`/`E` exponent. At least one digit is required; `.5`, `1.`, and `-1.25e2` are
valid. It also accepts case-insensitive `nan`, `inf`, and `infinity`, with an
optional sign. Whitespace, separators, hexadecimal forms, malformed exponents,
and trailing characters are rejected.

Finite decimal values round to the nearest representable float, with ties to
even. Subnormals are supported; sufficiently small magnitudes underflow to
signed zero. Finite overflow returns an error rather than infinity; explicit
`inf` is a successful value. Parsing is implemented in Ocean, independent of
libc parsing and locale. Current error messages distinguish invalid input from
out-of-range input. Only calling unwrap on an error turns that error into a
panic; unwrapOrElse and unwrapOrZero provide non-panicking fallbacks.

Use the matching updated compiler and io sources together. Result is embedded
in the compiler; ParseInt and ParseFloat are provided by the standard-library io
package. Existing compiler build/install and native library requirements remain
unchanged.

`io.Sprint` and the print/format functions support unsigned `uint`/`u64`,
`u32`, `u16`, and `u8` values as decimal strings across their full ranges,
including 18446744073709551615 for `uint`/`u64`.

## Native threads and synchronization

`threads` provides native function spawning, completion queries, joins, explicit
parking/waking, and cooperative termination. Main has ID 0. `sync` supplies
zero-value mutexes and wait groups. `os.Exit(code)` immediately terminates the
whole process and all threads, without running deferred calls.

Use these packages with the matching updated compiler. Linux/macOS use pthreads
and Windows uses Win32 APIs; Wasm rejects native threading and synchronization.
Only programs requiring the native runtime receive it and POSIX `-pthread`
linking. See [threads](threads/README.md) and [sync](sync/README.md) for API,
cancellation, ownership, and shutdown behavior.
