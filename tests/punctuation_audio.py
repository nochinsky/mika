"""Actual public-speech ASR -> native formatting regression, never a microphone."""
from pathlib import Path
import re
import subprocess
import sys

probe, model, sample = [str(Path(value).resolve()) for value in sys.argv[1:]]
raw = subprocess.run([probe, model, sample], capture_output=True, encoding='utf-8', timeout=90)
formatted = subprocess.run([probe, model, sample, '--punctuate'], capture_output=True, encoding='utf-8', timeout=90)
assert raw.returncode == formatted.returncode == 0, raw.stderr + formatted.stderr
assert 'formatting=0 ' in formatted.stderr, formatted.stderr
assert re.sub(r'[,?.]', '', formatted.stdout).lower().split() == raw.stdout.lower().split()
assert 'ask not what your country can do for you' in raw.stdout.lower(), raw.stdout
assert 'Americans' in formatted.stdout, formatted.stdout
assert '.' in formatted.stdout, formatted.stdout
print(raw.stdout.strip())
print(formatted.stdout.strip())
print(formatted.stderr.strip())
print('PASS: actual public JFK speech, unchanged word sequence, native punctuation/casing')
