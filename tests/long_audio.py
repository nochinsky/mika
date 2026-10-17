"""Opt-in 5-minute inference regression using only repeated public JFK audio.

This checks duration handling and speech near the end, not dictation accuracy.
No microphone, network request, or private recording is used.
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import wave

probe, model, sample = [str(Path(value).resolve()) for value in sys.argv[1:]]
with wave.open(sample, 'rb') as reader:
    assert (reader.getnchannels(), reader.getsampwidth(), reader.getframerate()) == (1, 2, 16000)
    speech = reader.readframes(reader.getnframes())
slot_bytes = 12 * 16000 * 2
assert 0 < len(speech) <= slot_bytes
slot = speech + bytes(slot_bytes - len(speech))
with tempfile.TemporaryDirectory(prefix='mika public long-audio test ') as directory:
    audio = Path(directory) / 'five-minutes.wav'
    with wave.open(str(audio), 'wb') as writer:
        writer.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        for _ in range(25):
            writer.writeframesraw(slot)
    with wave.open(str(audio), 'rb') as reader:
        assert reader.getnframes() == 300 * 16000
    result = subprocess.run([probe, model, str(audio)], capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=480)
    assert result.returncode == 0, result.stderr
    text = re.sub(r'\s+', ' ', result.stdout.lower()).strip()
    # Introductory words vary with local-attention boundaries; these stable core
    # phrases check all 25 slots, rather than accepting a truncated first minute.
    for phrase in ['your country can do for you', 'what you can do for your country']:
        assert text.count(phrase) == 25, (phrase, text.count(phrase), text)
    assert text.endswith('what you can do for your country'), text[-200:]
    print(result.stderr.strip())
    print('PASS: 300-second input, all 25 public-speech segments represented, final phrase intact')
