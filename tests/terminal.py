"""Shared POSIX PTY harness; no argument parsing, test collection or microphone I/O."""
import errno
import fcntl
import os
import pty
import select
import signal
import struct
import subprocess
import sys
import termios
import time


class TerminalProcess:
    def __init__(self, binary, env=None, columns=80, redirect_stderr=False,
                 args=('--raw',), pass_fds=()):
        self.master, self.slave = pty.openpty()
        fcntl.ioctl(self.slave, termios.TIOCSWINSZ, struct.pack('HHHH', 24, columns, 0, 0))
        self.diagnostics = b''
        self.before = termios.tcgetattr(self.slave)
        self.messages = b''

        # Acquire the PTY in a fresh interpreter, not preexec_fn: download tests
        # also run an HTTPS server thread, where Python preexec hooks can deadlock.
        self.process = subprocess.Popen(
            [sys.executable, __file__, binary, *args], stdin=self.slave, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE if redirect_stderr else self.slave,
            env={**os.environ, **(env or {})}, start_new_session=True, pass_fds=pass_fds,
        )
        # Only the child owns the slave. Keeping an extra BSD slave open can
        # block session revocation/process exit. Query modes through the master.
        os.close(self.slave)
        self.slave = None

    def wait_for(self, marker, timeout=10):
        deadline = time.monotonic() + timeout
        while marker not in self.messages:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AssertionError(f'timeout waiting for {marker!r}: {self.messages!r}')
            ready, _, _ = select.select([self.master], [], [], min(remaining, 0.1))
            if ready:
                self.messages += os.read(self.master, 4096)
            elif self.process.poll() is not None:
                raise AssertionError(f'process exited before {marker!r}: {self.messages!r}')

    def send(self, keys):
        os.write(self.master, keys)

    def hangup(self):
        """Deliberately revoke the controlling terminal without killing the child."""
        if self.master is not None:
            os.close(self.master)
            self.master = None

    def finish(self):
        try:
            # BSD can wait for PTY output drain during session exit. Drain the
            # terminal and redirected streams concurrently, never wait first.
            streams = {} if self.master is None else {self.master: 'terminal'}
            for name in ('stdout', 'stderr'):
                stream = getattr(self.process, name)
                if stream is not None and not stream.closed:
                    streams[stream.fileno()] = name
            captured = {'stdout': b'', 'stderr': b''}
            deadline = time.monotonic() + 10
            while streams:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AssertionError(f'PTY process did not finish: {self.messages!r}')
                ready, _, _ = select.select(list(streams), [], [], min(remaining, .1))
                for fd in ready:
                    try:
                        chunk = os.read(fd, 65536)
                    except OSError as error:
                        if fd != self.master or error.errno != errno.EIO:
                            raise
                        chunk = b''  # Linux master EOF.
                    if not chunk:
                        del streams[fd]
                    elif streams[fd] == 'terminal':
                        self.messages += chunk
                    else:
                        captured[streams[fd]] += chunk
            self.process.wait(timeout=max(.01, deadline - time.monotonic()))
            self.diagnostics = captured['stderr']
            self.assert_restored()
            return self.process.returncode, captured['stdout']
        finally:
            self.close()

    def assert_restored(self):
        if self.master is None:
            return  # Deliberate hangup: the terminal no longer exists to inspect.
        try:
            after = termios.tcgetattr(self.master)
        except termios.error as error:
            # Darwin revokes the PTY when its session leader exits. A surviving
            # parent-shell test checks restoration before that revoke instead.
            if sys.platform == 'darwin' and error.args[0] in (errno.EIO, errno.ENXIO):
                return
            raise
        if after != self.before:
            raise AssertionError('terminal modes were not restored')

    def close(self):
        # Close the PTY before waiting for a killed BSD session leader: revoke
        # can otherwise wait on our still-open terminal handles.
        for name in ('master', 'slave'):
            fd = getattr(self, name, None)
            if fd is not None:
                os.close(fd)
                setattr(self, name, None)
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=5)
        if self.process.stdout:
            self.process.stdout.close()
        if self.process.stderr:
            self.process.stderr.close()


if __name__ == '__main__':
    # stdin is the slave PTY. BSD needs an explicit foreground process group.
    signal.signal(signal.SIGTTOU, signal.SIG_IGN)
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)
    os.tcsetpgrp(0, os.getpgrp())
    signal.signal(signal.SIGTTOU, signal.SIG_DFL)
    # Match Popen(restore_signals=True); Python ignores these on interpreter start.
    for name in ('SIGPIPE', 'SIGXFZ', 'SIGXFSZ'):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), signal.SIG_DFL)
    os.execvpe(sys.argv[1], sys.argv[1:], os.environ)
