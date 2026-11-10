# Terminal utilities

All functions accept an open `os.File`, for example `os.Stdin().unwrap()`.
Native descriptors can be adopted with `os.FromDescriptor`. The package does
not close the supplied file.

| Function | Result |
| --- | --- |
| `GetSize(file os.File)` | `Result<Size>`; `Width` and `Height` are `int` columns and rows |
| `IsTerminal(file os.File)` | `Result<bool>`; valid files and pipes return `false`, invalid or closed descriptors return errors |
| `ReadPassword(file os.File)` | `Result<string>`; reads a line without echo, consumes its newline, and restores the prior settings |
| `MakeRaw(file os.File)` | `Result<bool>`; saves the current settings and enables raw input/output |
| `Restore(file os.File)` | `Result<bool>`; restores settings saved by `MakeRaw` |

Successful mode changes return `true`. Repeated `MakeRaw` calls preserve the
first saved state; one `Restore` restores it. Restoring without a saved state
returns an error. Restore before closing the file. Copies of a file share its
native terminal and saved settings. Calls that change the same terminal must
be coordinated by the caller.

```oc
package main;
import "io";
import "os";
import "term";

func restore(input os.File) { term.Restore(input).unwrap(); }

func main() {
    input := os.Stdin().unwrap();
    size := term.GetSize(input).unwrap();
    io.Println(size.Width, " columns, ", size.Height, " rows").unwrap();
    io.Print("Password: ").unwrap();
    password := term.ReadPassword(input).unwrap();
    io.Println().unwrap();

    term.MakeRaw(input).unwrap();
    defer restore(input);
    key := input.Readchunk(1).unwrap();
}
```

`ReadPassword` uses canonical line input, preserving terminal erase processing.
It prints neither a prompt nor a newline. EOF returns the bytes read so far,
including an empty string. Read errors and restoration errors return error
Results; restoration is attempted after read errors and during ordinary panic
unwinding. It restores an existing raw mode without changing the state saved
for `Restore`. Avoid mixing password input with buffered scanners. Password
strings use ordinary Ocean string storage; they are not securely erased.

Settings cannot be restored after forced process termination. Callers that
handle termination signals should arrange their own cleanup.

Native bindings use Linux ioctls on x86-64, AArch64 and RISC-V64, Darwin ioctls
on x86-64 and AArch64, and Win32 console APIs on x86-64 and AArch64. Windows
size is the visible console window size. Other targets return unsupported
errors. Runtime integration tests currently cover Linux; run
`python3 term/tests/test_term.py` (set `OCEAN` to select a compiler).
