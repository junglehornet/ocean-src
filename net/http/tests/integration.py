"""Local fixture launcher for Ocean's integration_native_test.oc tests.
All behavior assertions are native Ocean unit tests; Python owns servers/certs.
Usage: python integration.py /path/to/ocean-c [--cache DIR]
Requires Python 3.10+, openssl, libcurl 7.68+ with TLS + async DNS, and Clang.
"""
import argparse
from pathlib import Path
import os
import socket
import ssl
import subprocess
import tempfile
import threading
import time

parser = argparse.ArgumentParser()
parser.add_argument('compiler', type=Path)
parser.add_argument('--cache', default='off')
parser.add_argument('--all', action='store_true', help='run all standard-library Ocean tests with these HTTP fixtures')
args = parser.parse_args()
compiler = args.compiler.resolve()
source_root = Path(__file__).resolve().parents[3]
env = dict(os.environ, OCEAN_SRC=str(source_root), OCEAN_BUILD_CACHE=args.cache)
scale = int(os.environ.get('OCEAN_HTTP_TIMING_SCALE', '1'))
assert 1 <= scale <= 20

def command(*argv):
    p = subprocess.run([str(a) for a in argv], capture_output=True, text=True, timeout=180 + 45 * scale, env=env)
    assert p.returncode == 0, (argv, p.returncode, p.stdout, p.stderr)
    return p

class Server:
    def __init__(self, context=None, mode='normal', count=1):
        self.sock = socket.socket()
        self.sock.bind(('127.0.0.1', 0))
        self.sock.listen(16)
        self.sock.settimeout(.1)
        self.stop = threading.Event()
        self.port = self.sock.getsockname()[1]
        self.context, self.mode, self.count = context, mode, count
        self.errors = []
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
    def run(self):
        try:
            for _ in range(self.count):
                while not self.stop.is_set():
                    try:
                        peer, _ = self.sock.accept()
                        break
                    except socket.timeout:
                        continue
                else:
                    return  # deadline/cancel may happen before the client connects
                peer.settimeout(10 * scale)
                try:
                    if self.mode == 'handshake-stall':
                        time.sleep(.7 * scale)
                        continue
                    if self.context:
                        try:
                            peer = self.context.wrap_socket(peer, server_side=True)
                        except (ssl.SSLError, OSError):
                            continue  # clients must reject untrusted/mismatched certificates
                    data = b''
                    while b'\r\n\r\n' not in data:
                        part = peer.recv(65536)
                        if not part:
                            break
                        data += part
                    if not data:
                        continue
                    headers, body = data.split(b'\r\n\r\n', 1)
                    if self.mode == 'upload-stall':
                        time.sleep(.7 * scale)
                        continue
                    length = 0
                    for line in headers.split(b'\r\n')[1:]:
                        key, val = line.split(b':', 1)
                        if key.lower() == b'content-length':
                            length = int(val)
                    while len(body) < length:
                        part = peer.recv(65536)
                        if not part:
                            break
                        body += part
                    if self.mode == 'header-stall':
                        time.sleep(.7 * scale)
                        continue
                    if self.mode == 'body-stall':
                        peer.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 100\r\n\r\na')
                        time.sleep(.7 * scale)
                        continue
                    if self.mode == 'echo':
                        content_type = b''
                        for line in headers.split(b'\r\n')[1:]:
                            key, value = line.split(b':', 1)
                            if key.lower() == b'content-type':
                                content_type = value.strip()
                        peer.sendall(b'HTTP/1.1 201 Created\r\nContent-Length: ' + str(len(body)).encode() +
                            b'\r\nX-Request-Line: ' + headers.split(b'\r\n')[0] +
                            b'\r\nX-Content-Type: ' + content_type + b'\r\n\r\n' + body)
                        peer.recv(1)
                    elif self.mode == 'chunked':
                        peer.sendall(b'HTTP/1.1 100 Continue\r\n\r\nHTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n')
                        for part in (b'2\r', b'\nhi\r\n', b'1;ext=x\r\n!\r\n0\r\n', b'X-End: yes\r\n', b'\r\n'):
                            peer.sendall(part)
                            time.sleep(.01)
                        peer.recv(1)  # wait for client close: it must use framing, not EOF
                    elif self.mode == 'head':
                        peer.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 99\r\n\r\n')
                        peer.recv(1)
                    elif self.mode == 'close':
                        peer.sendall(b'HTTP/1.0 404 Missing\r\n\r\nmissing')
                    elif self.mode == 'large':
                        peer.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 16384\r\n\r\n' + b'x' * 16384)
                    elif self.mode == 'truncated':
                        peer.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 99\r\n\r\nshort')
                    else:
                        peer.sendall(b'HTTP/1.1 201 Created\r\nContent-Length: 2\r\n\r\nOK')
                        if self.mode != 'fast':
                            peer.recv(1)
                except (BrokenPipeError, ConnectionResetError, ssl.SSLError):
                    pass  # intentional cancellation/size-limit shutdowns
                except Exception as exc:
                    self.errors.append(exc)
                finally:
                    peer.close()
        except Exception as exc:
            self.errors.append(exc)
        finally:
            self.sock.close()
    def finish(self):
        self.stop.set()
        self.thread.join(10 * scale)
        assert not self.thread.is_alive(), 'server did not finish'
        assert not self.errors, self.errors

with tempfile.TemporaryDirectory(prefix='ocean-http-tls-') as tmp:
    root = Path(tmp)
    # A dedicated CA and a localhost-only certificate make hostname and trust
    # failures independent. Certificates are test-only and generated per run.
    command('openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', root/'ca.key', '-out', root/'ca.pem', '-subj', '/CN=Ocean Test CA', '-days', '1')
    command('openssl', 'req', '-newkey', 'rsa:2048', '-nodes', '-keyout', root/'server.key', '-out', root/'server.csr', '-subj', '/CN=localhost')
    (root/'extensions').write_text('subjectAltName=DNS:localhost\nextendedKeyUsage=serverAuth\n')
    command('openssl', 'x509', '-req', '-in', root/'server.csr', '-CA', root/'ca.pem', '-CAkey', root/'ca.key', '-CAcreateserial', '-out', root/'server.pem', '-days', '1', '-extfile', root/'extensions')
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.minimum_version = ssl.TLSVersion.TLSv1_2
    tls.load_cert_chain(root/'server.pem', root/'server.key')
    servers = []
    def register(name, context=None, mode='normal', count=1, https=False, host='127.0.0.1'):
        server = Server(context, mode, count)
        servers.append(server)
        env['OCEAN_HTTP_FIXTURE_' + name] = f'{"https" if https else "http"}://{host}:{server.port}/items?x=1'
    env['OCEAN_HTTP_FIXTURE_CA'] = str(root/'ca.pem')
    register('TRUSTED', tls, mode='echo', https=True, host='localhost')
    register('UNTRUSTED', tls, https=True, host='localhost')
    register('WRONG_HOST', tls, https=True)
    for suffix in ('TIMEOUT', 'CANCEL'):
        register('HANDSHAKE_' + suffix, mode='handshake-stall', https=True)
        register('HEADER_' + suffix, mode='header-stall')
        register('BODY_' + suffix, mode='body-stall')
        register('UPLOAD_' + suffix, mode='upload-stall')
    for name, mode in [('CHUNKED','chunked'),('HEAD','head'),('CLOSE','close'),('LARGE','large'),('TRUNCATED','truncated')]:
        register(name, mode=mode)
    register('CONCURRENT', mode='fast', count=4)
    # Reserve a non-listening port for the refusal test, avoiding reuse races.
    refused = socket.socket()
    refused.bind(('127.0.0.1', 0))
    env['OCEAN_HTTP_FIXTURE_REFUSED'] = f'http://127.0.0.1:{refused.getsockname()[1]}/'
    try:
        location = str(source_root) + '/...' if args.all else str(source_root/'net/http')
        result = command(compiler, 'test', location, '--notty', '--timeout', str(45 * scale) + 's')
        print(result.stdout, end='')
        for server in servers:
            server.finish()
    finally:
        refused.close()
