"""CI-only: explicitly fetch the fixed test model using Mika's real downloader."""
from pathlib import Path
import re
import subprocess
import sys

header = (Path(__file__).resolve().parents[1] / 'src/model.h').read_text()
def value(name):
    return re.search(r'#define ' + name + r' "([^"]+)"', header).group(1)

filename = value('MIKA_MODEL_FILE')
revision = value('MIKA_MODEL_REVISION')
sha256 = value('MIKA_MODEL_SHA256')
size = re.search(r'MIKA_MODEL_BYTES UINT64_C\((\d+)\)', header).group(1)
url = f'https://huggingface.co/handy-computer/granite-speech-5.0-470m-turboctc-gguf/resolve/{revision}/{filename}'
subprocess.run([sys.argv[1], url, sys.argv[2], size, sha256], check=True)
