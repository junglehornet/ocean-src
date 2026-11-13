# net/http

A small blocking HTTP/1.1 client for 64-bit Linux. API names follow Go's
`net/http`; errors use Ocean `Result<T>` and bodies are owned strings.

```ocean
import "net/http";

response := http.Get("http://localhost:8080/status").unwrap();
body := response.Body;
request := http.NewRequest("POST", "http://localhost:8080/items", "hello").unwrap();
request.Header.Set("Content-Type", "text/plain");
client: http.Client;
response = client.Do(request).unwrap();
```

- `Get(url string) Result<Response>` and `Post(url, contentType, body string)
  Result<Response>` use a zero-value client.
- `NewRequest(method, url, body string) Result<Request>` validates the method and
  URL. An empty method means GET.
- `Request` has `Method`, `URL`, `Header`, and `Body` fields.
- `Response` has `Status` (for example `200 OK`), `StatusCode`, `Header`, and `Body`.
- `Client { MaxResponseBytes int }` has `Do(request Request)`, `Get(url string)`,
  and `Post(url, contentType, body string)` methods returning `Result<Response>`.
  A positive limit bounds the complete wire response, including headers and chunk
  framing. The default is 16 MiB. Response headers have a 64 KiB limit.
- Zero-value `Header` supports `Set`, `Add`, `Get`, `Values`, and `Del`.
  Names are case insensitive; Get returns the first value or an empty string.
  Values returns an independent array; missing names return an empty array.

Supports DNS names, IPv4 hosts, explicit ports, GET/POST/custom methods, request
bodies, content-length, connection-close bodies, chunked responses and trailers,
HEAD, no-body status codes, and up to 16 informational responses. Non-2xx status
codes are successful responses. Sockets and resolver allocations are released
on success and failure. There is no response Body.Close requirement.

Host, Connection, Content-Length, and Transfer-Encoding request headers are
managed by the client; overriding them is an error. Methods, URLs, and headers
are checked for request injection. URL paths must already be percent escaped;
fragments are removed. Invalid framing and truncated bodies return errors.

This initial client supports plain `http://` only. HTTPS/TLS, IPv6 URL literals,
proxies, redirects, compression, cookies, connection reuse, servers, cancellation,
and timeouts are not implemented. Calls can block on DNS, connect, or response
I/O; the byte limit is not a time limit. Other operating systems are untested.

Run `ocean test net/http`; integration tests use local loopback sockets and no
external network service. The matching compiler must support fields named after
their types (`Header Header`) and enum payload tuple boxing.
