"""Real CPU VAD admission regressions; synthetic/public audio only, never a mic.

Attenuated positives test admission retention, NOT transcript accuracy. A speech
classifier cannot guarantee intended speaker, intelligibility or semantic safety.
"""
import array
import math
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys
import tempfile
import wave

PROBE, MODEL, SAMPLE = [Path(arg).resolve() for arg in sys.argv[1:]]
RATE = 16000


def write_wav(path, values):
    pcm = array.array('h', values)
    if sys.byteorder != 'little':
        pcm.byteswap()
    with wave.open(str(path), 'wb') as output:
        output.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
        output.writeframes(pcm.tobytes())


rng = random.Random(7301)
# These first four reproduce the previously observed false-success inputs.
negatives = {'digital-silence': [0] * 80000,
             'white-low': [int(rng.uniform(-100, 100)) for _ in range(80000)],
             'white-louder': [int(rng.uniform(-2000, 2000)) for _ in range(80000)],
             'tone-100': [int(700 * math.sin(2 * math.pi * 100 * i / RATE)) for i in range(80000)]}
for seed in (12, 984):
    noise = random.Random(seed)
    negatives[f'white-seed-{seed}'] = [int(noise.uniform(-1000, 1000)) for _ in range(48000)]
for frequency in (50, 300, 1000):
    negatives[f'tone-{frequency}'] = [int(2000 * math.sin(2 * math.pi * frequency * i / RATE)) for i in range(48000)]
with wave.open(str(SAMPLE), 'rb') as source:
    assert (source.getnchannels(), source.getsampwidth(), source.getframerate()) == (1, 2, RATE)
    speech = array.array('h', source.readframes(source.getnframes()))
    if sys.byteorder != 'little':
        speech.byteswap()
positives = {f'public-speech-gain-{gain}': [int(value * gain) for value in speech]
             for gain in (1, .25, .1, .01)}
positives['brief-speech-with-pauses'] = [0] * RATE + list(speech[:RATE]) + [0] * (3 * RATE)

with tempfile.TemporaryDirectory(prefix='Mika speech admission ü ') as directory:
    for expected, cases in ((3, negatives), (0, positives)):
        for name, samples in cases.items():
            path = Path(directory) / (name + '.wav')
            write_wav(path, samples)
            result = subprocess.run([str(PROBE), str(MODEL), str(path), '--raw'],
                                    capture_output=True, text=True, timeout=60)
            fields = dict(re.findall(r'(\w+)=([\d.]+)', result.stderr))
            assert result.returncode == expected, (name, result.returncode, result.stdout, result.stderr)
            assert fields.get('speech_admitted') == ('1' if expected == 0 else '0'), (name, result.stderr)
            if expected == 3:
                assert result.stdout == '' and fields.get('asr_ms') == '0.000', (name, result.stdout, result.stderr)
            else:
                assert result.stdout.strip(), (name, result.stderr)
            print('PASS:', name, 'no-speech' if expected == 3 else 'speech admitted')
    # Exercise actual required-asset verification on a private relocated probe;
    # original build and installed model are read-only throughout.
    clone = Path(directory) / 'relocated probe'
    clone.mkdir()
    shutil.copy2(PROBE, clone / PROBE.name)
    for library in PROBE.parent.iterdir():
        if library.is_file() and (library.suffix in ('.dll', '.dylib') or '.so' in library.name):
            shutil.copy2(library, clone / library.name)
    libraries = PROBE.parent.parent / 'lib'
    if libraries.is_dir():
        shutil.copytree(libraries, clone.parent / 'lib')
    shutil.copytree(PROBE.parent / 'speech', clone / 'speech')
    asset = clone / 'speech/silero-vad-v6.2-F32.gguf'
    original = asset.read_bytes()
    healthy = subprocess.run([str(clone / PROBE.name), str(MODEL), str(SAMPLE), '--raw'],
                             capture_output=True, text=True, timeout=60)
    assert healthy.returncode == 0, healthy.stderr
    for damage in ('missing', 'truncated', 'wrong-hash'):
        if damage == 'missing':
            asset.unlink()
        elif damage == 'truncated':
            asset.write_bytes(original[:100])
        else:
            asset.write_bytes(bytes([original[0] ^ 1]) + original[1:])
        for mode in ([], ['--raw']):
            result = subprocess.run([str(clone / PROBE.name), str(MODEL), str(SAMPLE), *mode],
                                    capture_output=True, text=True, timeout=60)
            assert result.returncode == 1 and result.stdout == '', (damage, mode, result.stdout, result.stderr)
            assert 'speech-detection data is missing or damaged' in result.stderr, result.stderr
        asset.write_bytes(original)
        print('PASS: required speech asset fails closed:', damage)
print(f'PASS: {len(negatives)} non-speech rejects, {len(positives)} public speech admissions and required-asset failures; not natural-dictation accuracy evidence')
