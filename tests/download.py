"""Exercise the real downloader against a private local HTTPS server, offline."""
import hashlib
import http.server
import os
from pathlib import Path
import shutil
import signal
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest

DRIVER = str(Path(sys.argv[1]).resolve())
sys.argv = sys.argv[:1]
if os.name == 'posix':
    from terminal import TerminalProcess


@unittest.skipUnless(shutil.which("openssl"), "openssl executable needed for local test certificates")
class Downloads(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.directory.name)
        cls.cert, cls.key = cls.root / "cert.pem", cls.root / "key.pem"
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
            "-subj", "/CN=localhost", "-addext", "subjectAltName=IP:127.0.0.1",
            "-keyout", str(cls.key), "-out", str(cls.cert),
        ], check=True, capture_output=True, timeout=20)
        cls.slow_started = threading.Event()

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def handle(self):
                try:
                    super().handle()
                except (BrokenPipeError, ConnectionResetError, ssl.SSLError):
                    pass  # Expected when the downloader rejects or cancels a connection.

            def do_GET(self):
                if self.path in ("/loop", "/redirect-ok", "/redirect-http"):
                    self.send_response(302)
                    self.send_header("Location", {
                        "/loop": "/loop", "/redirect-ok": "/ok",
                        "/redirect-http": "http://127.0.0.1:1/forbidden",
                    }[self.path])
                    self.end_headers()
                    return
                if self.path == "/error":
                    self.send_error(404)
                    return
                content = {"/ok": b"abc", "/wrong": b"abd", "/truncated": b"ab",
                           "/oversized": b"x" * 100, "/no-length-oversized": b"x" * 100,
                           "/empty": b"", "/slow": b"abc"}[self.path]
                self.send_response(200)
                if self.path != "/no-length-oversized":
                    self.send_header("Content-Length", "3" if self.path == "/truncated" else str(len(content)))
                self.end_headers()
                if self.path == "/slow":
                    cls.slow_started.set()
                    time.sleep(3)
                try:
                    self.wfile.write(content)
                except (BrokenPipeError, ConnectionResetError, ssl.SSLError):
                    pass

        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cls.cert, cls.key)
        cls.server.socket = context.wrap_socket(cls.server.socket, server_side=True)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"https://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.directory.cleanup()

    def setUp(self):
        self.target = self.root / "model.gguf"
        self.target.write_bytes(b"previous model")
        self.env = {**os.environ, "CURL_CA_BUNDLE": str(self.cert), "NO_PROXY": "127.0.0.1,localhost"}

    def command(self, route, payload=b"abc"):
        return [DRIVER, self.base + route, str(self.target), str(len(payload)), hashlib.sha256(payload).hexdigest()]

    def check_no_partial(self):
        self.assertEqual(list(self.root.glob("*.part.*")), [])

    def test_verified_success_and_https_redirect(self):
        for route in ("/ok", "/redirect-ok"):
            result = subprocess.run(self.command(route), env=self.env, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, b"")
            self.assertEqual(self.target.read_bytes(), b"abc")
            self.check_no_partial()

    def test_failed_transfers_never_replace_destination(self):
        for route in ("/wrong", "/truncated", "/oversized", "/no-length-oversized", "/error", "/loop", "/redirect-http"):
            with self.subTest(route=route):
                result = subprocess.run(self.command(route), env=self.env, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(result.stdout, b"")
                self.assertEqual(self.target.read_bytes(), b"previous model")
                self.check_no_partial()

    def test_untrusted_certificate_is_rejected(self):
        env = self.env.copy()
        env.pop("CURL_CA_BUNDLE")
        result = subprocess.run(self.command("/ok"), env=env, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.target.read_bytes(), b"previous model")
        self.check_no_partial()

    def test_empty_payload_hash(self):
        result = subprocess.run(self.command("/empty", b""), env=self.env, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_bytes(), b"")
        self.check_no_partial()

    @unittest.skipUnless(os.name == 'posix', 'requires a POSIX controlling terminal')
    def test_lost_terminal_discards_download(self):
        self.slow_started.clear()
        process = TerminalProcess(binary='/bin/bash', redirect_stderr=True, env=self.env,
            args=('-c', 'trap "" HUP; exec "$@"', 'download-test', *self.command('/slow'), '--terminal'))
        self.addCleanup(process.close)
        self.assertTrue(self.slow_started.wait(timeout=5))
        process.hangup()
        self.assertEqual(process.finish(), (1, b''))
        self.assertIn(b'lost the controlling terminal', process.diagnostics)
        self.assertEqual(self.target.read_bytes(), b'previous model')
        self.check_no_partial()

    @unittest.skipUnless(os.name == 'posix', 'requires a POSIX controlling terminal')
    def test_escape_behind_ordinary_keys_discards_download(self):
        self.slow_started.clear()
        process = TerminalProcess(binary=DRIVER, args=(*self.command('/slow')[1:], '--terminal'),
                                  redirect_stderr=True, env=self.env)
        self.addCleanup(process.close)
        self.assertTrue(self.slow_started.wait(timeout=5))
        process.send(b'ordinary keys\x1b')
        self.assertEqual(process.finish(), (130, b''))
        self.assertEqual(self.target.read_bytes(), b'previous model')
        self.check_no_partial()

    @unittest.skipUnless(os.name == "posix", "Windows requires a console Ctrl+C event")
    def test_interrupt_discards_partial_download(self):
        self.slow_started.clear()
        process = subprocess.Popen(self.command("/slow"), env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            self.assertTrue(self.slow_started.wait(timeout=5))
            process.send_signal(signal.SIGINT)
            out, err = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 130, err)
            self.assertEqual(out, b"")
            self.assertEqual(self.target.read_bytes(), b"previous model")
            self.check_no_partial()
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()
            process.stderr.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
