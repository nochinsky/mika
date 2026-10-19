"""Offline consistency checks for fixed assets and release metadata; no network."""
import importlib.util
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('assets', ROOT / 'scripts/fetch_punctuation.py')
assets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assets)


class Metadata(unittest.TestCase):
    def test_release_versions_match(self):
        version = re.search(r'project\(mika VERSION ([^ ]+)', (ROOT / 'CMakeLists.txt').read_text())[1]
        self.assertEqual(json.loads((ROOT / 'vcpkg.json').read_text())['version-string'], version)
        self.assertIn('"@PROJECT_VERSION@"', (ROOT / 'src/mika_version.h.in').read_text())
        self.assertIn('"mika/" MIKA_VERSION', (ROOT / 'src/model.c').read_text())

    def test_release_waits_for_and_publishes_all_platforms(self):
        workflow = (ROOT / '.github/workflows/build.yml').read_text(encoding='utf-8')
        mac = workflow.split('  macos-cpu:', 1)[1].split('  uninstallers:', 1)[0]
        self.assertIn('name: mika-macos-arm64', mac)
        publish = workflow.split('  release:', 1)[1]
        self.assertIn('needs: [uninstallers, model-free, package, macos-cpu]', publish)
        self.assertIn('pattern: mika-*', publish)
        self.assertIn('scripts/check_release_assets.py --directory dist', publish)
        self.assertIn('--verify-tag --draft', publish)
        self.assertIn('--draft=false --latest', publish)
        version = json.loads((ROOT / 'vcpkg.json').read_text(encoding='utf-8'))['version-string']
        self.assertIn('Mika v' + version, (ROOT / '.github/release-notes.md').read_text(encoding='utf-8'))

    def test_native_asset_identities_match_fetcher(self):
        source = (ROOT / 'src/punctuation_backend.cpp').read_text()
        for name, expected in [('model', assets.QUANTIZED), ('vocab', assets.ARTIFACTS['sp.model'][1:])]:
            match = re.search(r'mika_model_verify\(' + name + r'\.c_str\(\),\s*(\d+),\s*"([a-f0-9]{64})"', source)
            self.assertIsNotNone(match)
            self.assertEqual((int(match[1]), match[2]), expected)
        size = assets.ARTIFACTS['sp.model'][1]
        self.assertIn(f'serialized({size},', (ROOT / 'src/fullstop.cpp').read_text())


if __name__ == '__main__':
    unittest.main(verbosity=2)
