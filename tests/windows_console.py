"""Native classic-console UI checks with fake audio/inference; never opens a mic."""
import ctypes as C
from ctypes import wintypes as W
import msvcrt
import os
from pathlib import Path
import subprocess
import sys
import time

kernel = C.WinDLL('kernel32', use_last_error=True)
kernel.CreateFileW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, C.c_void_p, W.DWORD, W.DWORD, W.HANDLE]
kernel.CreateFileW.restype = W.HANDLE
kernel.CreateConsoleScreenBuffer.argtypes = [W.DWORD, W.DWORD, C.c_void_p, W.DWORD, C.c_void_p]
kernel.CreateConsoleScreenBuffer.restype = W.HANDLE
kernel.ReadConsoleOutputCharacterW.argtypes = [W.HANDLE, W.LPWSTR, W.DWORD, W.DWORD, C.POINTER(W.DWORD)]
kernel.CloseHandle.argtypes = [W.HANDLE]

class Key(C.Structure):
    _fields_ = [('down', W.BOOL), ('repeat', W.WORD), ('vk', W.WORD), ('scan', W.WORD),
                ('char', W.WCHAR), ('control', W.DWORD)]
class Event(C.Union):
    _fields_ = [('key', Key), ('padding', C.c_byte * 16)]
class Record(C.Structure):
    _fields_ = [('kind', W.WORD), ('event', Event)]
kernel.WriteConsoleInputW.argtypes = [W.HANDLE, C.POINTER(Record), W.DWORD, C.POINTER(W.DWORD)]

kernel.FreeConsole()
if not kernel.AllocConsole():
    raise C.WinError(C.get_last_error())
input_handle = kernel.CreateFileW('CONIN$', 0xC0000000, 3, None, 3, 0, None)
if input_handle == W.HANDLE(-1).value:
    raise C.WinError(C.get_last_error())
try:
    for key, expected_code, expected_output in [('\r', 0, b'Test transcript.\r\n'), ('\x1b', 130, b'')]:
        handle = kernel.CreateConsoleScreenBuffer(0xC0000000, 3, None, 1, None)
        if handle == W.HANDLE(-1).value:
            raise C.WinError(C.get_last_error())
        descriptor = msvcrt.open_osfhandle(handle, os.O_WRONLY)
        with os.fdopen(descriptor, 'wb', buffering=0) as console:
            def screen():
                text = C.create_unicode_buffer(2001)
                count = W.DWORD()
                if not kernel.ReadConsoleOutputCharacterW(handle, text, 2000, 0, C.byref(count)):
                    raise C.WinError(C.get_last_error())
                return text[:count.value]
            process = subprocess.Popen([str(Path(sys.argv[1]).resolve())], stdout=subprocess.PIPE, stderr=console)
            try:
                deadline = time.monotonic() + 15
                while 'Listening 00:' not in screen():
                    if process.poll() is not None or time.monotonic() >= deadline:
                        raise AssertionError(f'No listening status: {screen()!r}')
                    time.sleep(0.02)
                assert 'Enter: finish | Esc: cancel' in screen(), screen()
                event = Record(1, Event(key=Key(True, 1, ord(key), 0, key, 0)))
                count = W.DWORD()
                if not kernel.WriteConsoleInputW(input_handle, C.byref(event), 1, C.byref(count)):
                    raise C.WinError(C.get_last_error())
                output, _ = process.communicate(timeout=15)
                assert (process.returncode, output) == (expected_code, expected_output)
                remaining = screen().strip('\x00 \r\n')
                assert remaining == ('' if expected_code == 0 else 'Cancelled.'), repr(remaining)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                process.stdout.close()
finally:
    kernel.CloseHandle(input_handle)
    kernel.FreeConsole()
print('PASS: native console Enter/Esc, transient status erasure, clean redirected transcript')
