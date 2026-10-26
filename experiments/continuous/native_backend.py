"""Developer-only driver for the pinned native Windows/Linux speech libraries.

No microphone, model download, Python ML runtime, or formatter. Data identities
and admission settings match Mika 0.3.2. The app itself does not import this file.
"""
import ctypes as C
import hashlib
import os
from pathlib import Path


class Load(C.Structure):
    _fields_ = [('size', C.c_uint64), ('backend', C.c_int), ('device', C.c_void_p)]


class Run(C.Structure):
    _fields_ = [('size', C.c_uint64), ('task', C.c_int), ('timestamps', C.c_int),
                ('pnc', C.c_int), ('itn', C.c_int), ('diarize', C.c_int),
                ('language', C.c_char_p), ('target_language', C.c_char_p),
                ('keep_special_tags', C.c_bool), ('family', C.c_void_p),
                ('spec_k_drafts', C.c_int32), ('vocabulary', C.c_void_p),
                ('n_vocabulary', C.c_int32), ('prompt', C.c_char_p), ('prefix', C.c_char_p)]


class VadSession(C.Structure):
    _fields_ = [('size', C.c_uint64), ('n_threads', C.c_int32)]


class VadParams(C.Structure):
    _fields_ = [('size', C.c_uint64), ('threshold', C.c_double), ('neg_threshold', C.c_double),
                ('min_speech_ms', C.c_int32), ('min_silence_ms', C.c_int32),
                ('speech_pad_ms', C.c_int32), ('max_speech_ms', C.c_int32)]


class VadResult(C.Structure):
    _fields_ = [('size', C.c_uint64), ('n_probs', C.c_int32),
                ('first_frame', C.c_int64), ('n_segments', C.c_int32)]


P = C.c_void_p
FLOATS = C.POINTER(C.c_float)


def bind(lib, name, args, result=C.c_int):
    function = getattr(lib, name)
    function.argtypes, function.restype = args, result
    return function


def ok(code):
    if code:
        raise RuntimeError(f'Native speech operation failed: {code}')


def verified(path, expected):
    with path.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if actual != expected:
        raise ValueError(f'Pinned asset checksum mismatch: {path.name}')
    return str(path).encode('utf-8')


class Backend:
    def __init__(self, app, model):
        self.session, self.vad_weight = P(), P()
        self.online, self.admission = P(), P()
        self.directories = []
        app = Path(app).resolve()
        if os.name == 'nt':
            library = app / 'bin/transcribe.dll'
            self.directories.append(os.add_dll_directory(str(app / 'bin')))
        else:
            library = app / 'lib/libtranscribe.so'
        model_path = verified(Path(model), '3f30525381d72246b7f99e49b6cb66b249cf1b990c6c3d0e031a7765735f513e')
        vad_path = verified(app / 'bin/speech/silero-vad-v6.2-F32.gguf',
                            '0d871a800c420fdd5d1b17a3aea4296d1c39608f0ff4a9295eb76457eb1c88e6')
        self.lib = C.CDLL(str(library))
        lib = self.lib
        try:
            ok(bind(lib, 'transcribe_init_backends', [C.c_char_p])(str(library.parent).encode()))
            load = Load()
            bind(lib, 'transcribe_model_load_params_init', [C.POINTER(Load)], None)(C.byref(load))
            load.backend = 1  # Strict CPU, as in the application.
            ok(bind(lib, 'transcribe_model_load_file', [C.c_char_p, C.POINTER(Load), C.POINTER(P)])(
                vad_path, C.byref(load), C.byref(self.vad_weight)))
            params = VadSession()
            bind(lib, 'transcribe_vad_session_params_init', [C.POINTER(VadSession)], None)(C.byref(params))
            params.n_threads = 1
            create_vad = bind(lib, 'transcribe_vad_session_init', [P, C.POINTER(VadSession), C.POINTER(P)])
            for session in (self.online, self.admission):
                ok(create_vad(self.vad_weight, C.byref(params), C.byref(session)))
            ok(bind(lib, 'transcribe_open', [C.c_char_p, C.POINTER(Load), P, C.POINTER(P)])(
                model_path, C.byref(load), None, C.byref(self.session)))
            self.feed = bind(lib, 'transcribe_vad_stream_feed', [P, FLOATS, C.c_int])
            self.get_vad = bind(lib, 'transcribe_vad_get_result', [P, C.POINTER(VadResult)])
            self.probs = bind(lib, 'transcribe_vad_probs', [P], FLOATS)
            self.gate = bind(lib, 'transcribe_vad_run', [P, FLOATS, C.c_int, C.POINTER(VadParams)])
            self.run = bind(lib, 'transcribe_run', [P, FLOATS, C.c_int, C.POINTER(Run)])
            self.text = bind(lib, 'transcribe_full_text', [P], C.c_char_p)
            self.params = Run()
            bind(lib, 'transcribe_run_params_init', [C.POINTER(Run)], None)(C.byref(self.params))
            self.params.language = b'en'
            self.gate_params = VadParams()
            bind(lib, 'transcribe_vad_params_init', [C.POINTER(VadParams)], None)(C.byref(self.gate_params))
            self.gate_params.min_speech_ms = 0
        except BaseException:
            self.close()
            raise

    def result(self, session):
        value = VadResult()
        bind(self.lib, 'transcribe_vad_result_init', [C.POINTER(VadResult)], None)(C.byref(value))
        ok(self.get_vad(session, C.byref(value)))
        return value

    def speech(self, pcm, frames):
        # The evaluator feeds 512 samples/32 ms. Only the final partial block
        # gets zero padding for VAD; the native segmenter retains original PCM.
        if frames < 512:
            padded = (C.c_float * 512)()
            C.memmove(padded, pcm, frames * C.sizeof(C.c_float))
            pcm = padded
        ok(self.feed(self.online, pcm, 512))
        result = self.result(self.online)
        if result.n_probs <= 0:
            raise RuntimeError('Streaming VAD returned no frame probability')
        values = self.probs(self.online)
        return any(values[i] >= 0.5 for i in range(result.n_probs))

    def transcribe(self, pcm, frames):
        padding = max(0, 1600 - frames)
        if padding:
            padded = (C.c_float * 1600)()
            C.memmove(padded, pcm, frames * C.sizeof(C.c_float))
            pcm, frames = padded, 1600
        ok(self.gate(self.admission, pcm, frames, C.byref(self.gate_params)))
        result = self.result(self.admission)
        if result.n_segments < 0 or result.n_probs <= 0 or result.n_segments > result.n_probs:
            raise RuntimeError('Invalid speech admission result')
        if not result.n_segments:
            return '', padding
        ok(self.run(self.session, pcm, frames, C.byref(self.params)))
        text = self.text(self.session)
        return text.decode('utf-8') if text else '', padding

    def close(self):
        lib = self.lib
        bind(lib, 'transcribe_session_free', [P], None)(self.session)
        self.session = P()
        for name in ('online', 'admission'):
            bind(lib, 'transcribe_vad_session_free', [P], None)(getattr(self, name))
            setattr(self, name, P())
        bind(lib, 'transcribe_model_free', [P], None)(self.vad_weight)
        self.vad_weight = P()


def peak_rss_kib():
    if os.name != 'nt':
        import resource
        import sys
        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return value / 1024 if sys.platform == 'darwin' else value
    from ctypes import wintypes as W
    class Counters(C.Structure):
        _fields_ = [('cb', W.DWORD), ('faults', W.DWORD)] + [
            (name, C.c_size_t) for name in ('peak_working', 'working', 'peak_pool', 'pool',
                                          'peak_nonpaged', 'nonpaged', 'pagefile', 'peak_pagefile')]
    kernel = C.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = P
    info = Counters()
    info.cb = C.sizeof(info)
    function = C.WinDLL('psapi', use_last_error=True).GetProcessMemoryInfo
    function.argtypes = [P, C.POINTER(Counters), W.DWORD]
    if not function(kernel.GetCurrentProcess(), C.byref(info), info.cb):
        raise C.WinError(C.get_last_error())
    return info.peak_working / 1024
