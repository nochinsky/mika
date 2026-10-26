"""Offline segmentation experiment; explicit WAV/reference inputs, never a mic.

Runs the real C segmenter and the installed pinned CPU speech backend. Raw ASR
only: this does NOT validate live capture, a producer queue, cancellation, the
CLI output contract, punctuation or natural-dictation accuracy. A growing list
of transcript words remains in Python; recording storage stays bounded in C.
"""
import argparse
import array
import ctypes as C
import hashlib
import json
from pathlib import Path
import sys
import time
import wave
from native_backend import Backend, FLOATS, P, bind, ok, peak_rss_kib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from evaluate_spoken import word_errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('segmenter', 'app', 'model', 'audio', 'reference', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--kind', choices=('repeated-public', 'synthetic-boundary', 'public'), required=True)
    parser.add_argument('--max-seconds', type=int, default=60)
    parser.add_argument('--min-seconds', type=int, default=10)
    parser.add_argument('--pause-ms', type=int, default=800, help='0 disables pause cuts')
    parser.add_argument('--include-transcript', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.min_seconds <= args.max_seconds <= 300 or not 0 <= args.pause_ms <= 10000:
        parser.error('Use 1 <= min <= max <= 300 seconds and pause-ms between 0 and 10000')
    if args.output.exists():
        parser.error('Choose a new report path; existing reports are never overwritten')
    reference = args.reference.read_text(encoding='utf-8').strip()
    if not reference:
        parser.error('Reference must be predeclared and nonempty')
    started = time.perf_counter()
    lib = C.CDLL(str(args.segmenter.resolve()))
    create = bind(lib, 'mika_segmenter_open', [C.c_size_t] * 3, P)
    push = bind(lib, 'mika_segmenter_push', [P, FLOATS, C.c_size_t, C.c_int, C.POINTER(C.c_size_t)])
    peek = bind(lib, 'mika_segmenter_peek', [P, C.POINTER(FLOATS), C.POINTER(C.c_size_t),
                                           C.POINTER(C.c_uint64), C.POINTER(C.c_int)])
    consume = bind(lib, 'mika_segmenter_consume', [P], None)
    finish = bind(lib, 'mika_segmenter_finish', [P])
    total = bind(lib, 'mika_segmenter_total', [P], C.c_uint64)
    audio_bytes = bind(lib, 'mika_segmenter_audio_bytes', [P], C.c_size_t)
    close = bind(lib, 'mika_segmenter_close', [P], None)
    segmenter = create(args.max_seconds * 16000, args.min_seconds * 16000, args.pause_ms * 16)
    if not segmenter:
        raise MemoryError('Cannot allocate the bounded segment buffer')
    backend = None
    rows, transcripts = [], []
    source_hash, chunk_hash = hashlib.sha256(), hashlib.sha256()
    frames_read = frames_drained = 0
    try:
        backend = Backend(args.app, args.model)
        def drain():
            nonlocal frames_drained
            pcm, frames, start, reason = FLOATS(), C.c_size_t(), C.c_uint64(), C.c_int()
            if not peek(segmenter, C.byref(pcm), C.byref(frames), C.byref(start), C.byref(reason)):
                return False
            if start.value != frames_drained:
                raise RuntimeError('Discontinuous chunk frame offsets')
            chunk_hash.update(C.string_at(pcm, frames.value * C.sizeof(C.c_float)))
            inference_start = time.perf_counter()
            text, padding = backend.transcribe(pcm, frames.value)
            elapsed = time.perf_counter() - inference_start
            rows.append({'start_frame': start.value, 'frames': frames.value,
                         'reason': {1: 'forced', 2: 'pause', 3: 'end'}[reason.value],
                         'inference_seconds': round(elapsed, 4), 'characters': len(text),
                         'minimum_input_zero_pad_frames': padding})
            transcripts.append(text)
            frames_drained += frames.value
            consume(segmenter)
            if len(rows) % 10 == 0:
                print(f'Processed {frames_drained / 16000:.1f}s in {len(rows)} chunks', flush=True)
            return True
        with wave.open(str(args.audio), 'rb') as reader:
            if (reader.getnchannels(), reader.getsampwidth(), reader.getframerate(), reader.getcomptype()) != (1, 2, 16000, 'NONE'):
                raise ValueError('Expected explicit mono 16-bit 16 kHz uncompressed WAV')
            expected_frames = reader.getnframes()
            while data := reader.readframes(512):
                values = array.array('h', data)
                if sys.byteorder != 'little':
                    values.byteswap()
                block = (C.c_float * len(values))(*(v / 32768.0 for v in values))
                source_hash.update(bytes(block))
                speech = backend.speech(block, len(values)) if args.pause_ms else 1
                offset = 0
                while offset < len(values):
                    count = C.c_size_t()
                    pointer = C.cast(C.byref(block, offset * C.sizeof(C.c_float)), FLOATS)
                    ok(push(segmenter, pointer, len(values) - offset, speech, C.byref(count)))
                    offset += count.value
                    ready = drain()
                    if not ready and not count.value:
                        raise RuntimeError('Segmenter made no progress')
                frames_read += len(values)
        ok(finish(segmenter))
        drain()
        if not (frames_read == frames_drained == total(segmenter) == expected_frames):
            raise RuntimeError('Recording frames were lost or duplicated')
        if source_hash.digest() != chunk_hash.digest():
            raise RuntimeError('Chunked PCM differs from original PCM')
        seconds = frames_read / 16000
        hypothesis = ' '.join(text for text in transcripts if text)
        scores = word_errors(reference, hypothesis)
        report = {'scope': __doc__, 'kind': args.kind, 'audio_seconds': seconds,
                  'max_chunk_seconds': args.max_seconds, 'min_chunk_seconds': args.min_seconds,
                  'pause_ms': args.pause_ms, 'audio_buffer_bytes': audio_bytes(segmenter),
                  'all_pcm_preserved': True, 'pcm_sha256': source_hash.hexdigest(),
                  'reference_sha256': hashlib.sha256(args.reference.read_bytes()).hexdigest(),
                  'chunks': rows, 'word_errors': scores,
                  'total_seconds': round(time.perf_counter() - started, 4),
                  'peak_rss_kib': round(peak_rss_kib(), 1),
                  'inference_seconds': round(sum(row['inference_seconds'] for row in rows), 4),
                  'transcript_retained': args.include_transcript}
        if args.include_transcript:
            report['hypothesis'] = hypothesis
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, indent=2)
            stream.write('\n')
        print(json.dumps({key: value for key, value in report.items() if key not in ('chunks', 'hypothesis', 'scope')}, indent=2))
    finally:
        if backend:
            backend.close()
        close(segmenter)


if __name__ == '__main__':
    main()
