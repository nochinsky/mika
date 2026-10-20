"""Prepare the one bundled CPU Silero VAD; build-time only, no ASR downloads."""
import argparse
from pathlib import Path
import shutil
from asset_io import fetch, payload_transaction, run_bounded

REVISION = 'a9b2d61c20ae4ddf3644edb34969e8185a485448'
MODEL_FILE = 'silero-vad-v6.2-F32.gguf'
MODEL_BYTES = 1241056
MODEL_SHA256 = '0d871a800c420fdd5d1b17a3aea4296d1c39608f0ff4a9295eb76457eb1c88e6'
MODEL_URL = ('https://huggingface.co/handy-computer/silero-vad-v6.2-gguf/resolve/'
             + REVISION + '/' + MODEL_FILE)
LICENSE = Path(__file__).resolve().parents[1] / 'licenses/silero-vad-LICENSE.txt'
PREPARE_TIMEOUT = 120


def prepare(stage):
    stage.mkdir(parents=True, exist_ok=True)
    model = fetch(stage / 'downloads', MODEL_FILE, (MODEL_URL, MODEL_BYTES, MODEL_SHA256))
    # Only the fixed, verified VAD and its combined license/notice ship.
    with payload_transaction(stage) as payload:
        shutil.copyfile(model, payload / MODEL_FILE)
        shutil.copyfile(LICENSE, payload / 'LICENSE.txt')
    return stage / 'payload'


def prepare_bounded(stage, timeout=PREPARE_TIMEOUT):
    run_bounded(__file__, stage, timeout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', required=True, type=Path)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        print('Pinned Silero VAD ready:', prepare(args.stage), flush=True)
    else:
        prepare_bounded(args.stage)


if __name__ == '__main__':
    main()
