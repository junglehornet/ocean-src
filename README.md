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
write failures panic. Unimplemented architecture/platform combinations report
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
