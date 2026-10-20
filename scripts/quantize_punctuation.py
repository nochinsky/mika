"""Developer-only, reproducible conversion of the pinned English FullStop model."""
import importlib.metadata
from pathlib import Path
import sys


def convert(source, destination):
    # Run in the preparation worker so its hard timeout covers conversion too,
    # without a detached converter continuing to write after the worker is killed.
    for name, version in [('onnxruntime', '1.28.0'), ('onnx', '1.23.2'),
                          ('numpy', '2.5.4'), ('protobuf', '7.36.2')]:
        try:
            actual = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            actual = 'missing'
        if actual != version:
            raise SystemExit(name + ' must be ' + version + ' (found ' + actual + ').\n'
                             'Install scripts/requirements-punctuation.txt into a Python 3.12+ development venv.\n'
                             'Mika itself does not require Python.')
    from onnxruntime.quantization import QuantType, quantize_dynamic
    quantize_dynamic(str(Path(source)), str(Path(destination)),
                     weight_type=QuantType.QInt8, per_channel=True,
                     op_types_to_quantize=['MatMul', 'Gather'],
                     extra_options={'MatMulConstBOnly': True})


def main():
    if len(sys.argv) != 3:
        raise SystemExit('usage: quantize_punctuation.py SOURCE.onnx OUTPUT.onnx')
    convert(sys.argv[1], sys.argv[2])


if __name__ == '__main__':
    main()
