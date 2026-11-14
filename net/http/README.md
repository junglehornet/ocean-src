# net/http

Go-inspired HTTP/1.1 and HTTPS clients with verified TLS, deadlines, and
cancellation. Bodies are owned strings; errors use Ocean `Result<T>`.

```ocean
import "net/http";
import "time";

client: http.Client;
client.Timeout = 5 * time.Second;
response := client.Get("https://example.com/status").unwrap();

cancel: http.Cancellation;
request := http.NewRequestWithCancel(&cancel, "POST", "https://example.com/items", "hello").unwrap();
request.Header.Set("Content-Type", "text/plain");
response = client.Do(request).unwrap();
// Another native thread can call cancel.Cancel() while Do is running.
```

## API

- `Get(url string)` and `Post(url, contentType, body string)` use a zero-value
  client and return `Result<Response>`.
- `NewRequest(method, url, body string) Result<Request>` accepts HTTP/HTTPS URLs.
  An empty method means GET. Request fields are Method, URL, Header, Body,
  Cancel, Deadline, and ResponseLimit. The latter two are populated by Do for
  transports: absolute monotonic nanoseconds (0 means none), and a byte budget.
  A positive preexisting request Deadline is combined with the client deadline
  by choosing the earlier one.
- `NewRequestWithCancel(cancel *Cancellation, method, url, body string)` and
  `request.WithCancel(cancel)` attach a borrowed cancellation token.
- `Cancellation` has `Cancel()` and `Canceled()`. Its zero value works.
  Native tokens synchronize access across threads. Keep tokens at stable
  addresses, do not copy them after use, and keep them alive until every request
  and canceling thread finishes. Cancellation is permanent and idempotent; a
  token can cancel multiple requests. It is independent of threads.Kill.
- Response has Status (such as `200 OK`), StatusCode, Header, and Body fields.
  Non-2xx statuses are normal responses. Body.Close is not needed.
- Client has MaxResponseBytes, Timeout, TLSClientConfig, and Transport fields.
  Its Do/Get/Post methods return `Result<Response>`.
- Header's zero value supports Set, Add, Get, Values, and Del. Names are case
  insensitive. Get returns the first value or an empty string. Values returns
  an independent array; missing names return an empty array.

## TLS, timeouts, and limits

The built-in native transport verifies both the certificate chain and hostname,
uses the libcurl backend's default trust store, and requires TLS 1.2 or newer.
`client.TLSClientConfig.RootCAFile` optionally selects a PEM trust bundle for a
private CA. Windows uses the OS trust store with libcurl 7.71+ when no private CA file is selected, so relocated executables do not depend on a build-machine PEM path. There is no option to disable certificate verification. TLS settings
apply to the built-in native transport; custom transports configure their own.

Timeout is a nonnegative nanosecond budget; use `time.Second` and
`time.Millisecond`. Zero means no deadline. It spans request preparation, DNS,
TCP connect, TLS handshake, upload, and response reading. Polling checks deadlines
and cancellation at intervals of at most 10 ms. Upload retries borrow chunks
of at most 64 KiB from the existing body buffer without copying the unsent body.
Timing remains subject to OS scheduling, clock
resolution, and libcurl operations. There are no detached per-request worker
threads. Handles are removed and cleaned up on every return path. Cancellation
and timeout errors are `http: request canceled` and `http: timeout exceeded`.

MaxResponseBytes limits the complete received HTTP wire response, including
headers and chunk framing; nonpositive values select the default 16 MiB budget.
Headers and trailers have 64 KiB limits. Framed responses finish once their body
is complete, without waiting for connection close. Close-delimited bodies still
need EOF. Invalid framing, duplicate transfer encodings, conflicting lengths,
truncated bodies, and oversized responses return errors.

Supports DNS/IPv4 hosts, explicit ports, GET/POST/custom methods, binary request
and response strings, chunked responses/trailers, HEAD, no-body statuses, and up
to 16 informational responses. Host, Connection, Content-Length, and
Transfer-Encoding request headers are client-controlled; overrides are errors.
Paths must already be percent escaped; URL fragments are removed. Proxies from
ambient environment variables are explicitly disabled. Redirects, IPv6 URL
literals, cookies, compression, connection pooling, and server APIs are not
implemented.

## Platforms and dependencies

The same libcurl transport supports the seven native Ocean targets: Linux
x86-64/AArch64/RISC-V64, macOS x86-64/AArch64, and Windows x86-64/AArch64. It uses
libcurl's socket/TLS implementation instead of platform-specific sockaddr layouts
or Unix file descriptors. C long options account for Windows's 32-bit long;
size_t and pointers are 64-bit on all seven native targets.

Native applications need libcurl 7.68+ built with TLS and asynchronous DNS, an
appropriate CA trust store, and the matching libcurl development/import library.
The accompanying compiler automatically links `-lcurl` and preserves that
requirement on full object-cache hits. libffi and the native threading runtime
are also required by the existing Ocean ABI and synchronization implementation.
For example, install libcurl4-openssl-dev on Debian/Ubuntu, curl on Homebrew, or
the target-matching curl package in MSYS2 CLANG64/CLANGARM64. Ensure Clang can find
the library and the OS loader can find its shared library/DLL and dependencies.
Static builds additionally need libcurl's static transitive libraries; automatic
static dependency discovery is not implemented. No curl executable is invoked.

Requires compiler support for `_native.oc`/`_wasm.oc` source variants (and their
`_native_test.oc`/`_wasm_test.oc` counterparts), selected before import resolution.
Use the compiler from the same change; old compilers load both implementations.

## JavaScript/WebAssembly

The HTTP API also compiles with `OCOS=js OCARCH=wasm`. Native libcurl and sync
implementations are excluded. There is no built-in synchronous browser Fetch
implementation: JavaScript Fetch is asynchronous, and Ocean's Do is synchronous.

Supply `Client.Transport` with an implementation of:

```ocean
interface RoundTripper {
    func RoundTrip(request Request) Result<Response>;
}
```

The host transport owns network I/O and TLS verification. It must honor the
request Deadline, cancellation token, and ResponseLimit. Do checks cancellation
and deadlines before and after delegation and enforces the returned body limit;
it cannot interrupt a custom transport that blocks without cooperating. Browser
CORS, forbidden headers, trust policy, Fetch/worker/suspension integration, and
AbortController wiring belong to the host adapter. Wasm Cancellation is a
single-threaded flag; in-flight cancellation requires an appropriate host
execution model. Without a transport, requests return the explicit error
`http: WebAssembly requires a host-supplied RoundTripper`.

The Wasm host must also provide Ocean's usual C-runtime imports and
`env.ocean_time_monotonic_ns() -> i64` (a JavaScript BigInt). Programs using
Client.Do generally import this clock even when Timeout is zero, because the
deadline machinery references it. Use a monotonic clock, not wall-clock time. A browser
host may derive nanoseconds from performance.now().

## Validation

```sh
ocean test net/http time --notty
python3 net/http/tests/integration.py /path/to/ocean-c
python3 net/http/tests/linking.py /path/to/ocean-c
python3 net/http/tests/wasm.py /path/to/ocean-c
python3 net/http/tests/assembly.py /path/to/asm_backend_probe /path/to/clang
```

All library behavior assertions are native Ocean tests in *_native_test.oc,
including the TLS, timeout, cancellation, upload, and concurrency tests.
Without fixtures, those network tests are reported as skipped. The Python
launcher only creates OpenSSL certificates and local loopback server fixtures,
sets fixture addresses in the environment, and invokes ocean test net/http.
It never calls an external service or generates replacement Ocean test programs. The Wasm test compiles
cold/hot/uncached modules and runs a custom host-transport smoke test in Node;
its minimal allocator shim is test-only, not a production runtime/Fetch adapter.
The assembly test checks all seven clock variants at -O0/-O2. The CI workflow
covers each native target plus Wasm; foreign execution requires those CI runners.

CI uses Clang/LLD 23 for native x86-64/AArch64 and JavaScript/Wasm. RISC-V uses
the Ubuntu 26.04 native Clang 21 toolchain. The linking harness accepts
`OCEAN_HTTP_BUILD_TIMEOUT` in seconds (default 120, CI uses 900 under QEMU);
this compile budget does not change HTTP request deadlines. Subprocess output
is decoded as UTF-8 on every host.
