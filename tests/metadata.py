"""Offline consistency checks for fixed assets and release metadata; no network."""
import importlib.util
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
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
        self.assertIn('needs: [uninstallers, model-free, package, macos-cpu, release-assets]', publish)
        preflight = workflow.split('  release-assets:', 1)[1].split('  release:', 1)[0]
        for required in ('needs: [package, macos-cpu]', 'pattern: mika-*',
                         'merge-multiple: true', 'scripts/check_release_assets.py --directory dist'):
            self.assertIn(required, preflight)
        self.assertNotIn('gh release', preflight)
        self.assertNotIn('contents: write', preflight)
        self.assertIn('pattern: mika-*', publish)
        self.assertIn('scripts/check_release_assets.py --directory dist', publish)
        self.assertIn('--verify-tag --draft', publish)
        self.assertIn('--draft=false --latest', publish)
        dispatch = workflow.split('  workflow_dispatch:', 1)[1].split('\npermissions:', 1)[0]
        for required in ('publish_release:', 'type: boolean', 'default: false'):
            self.assertIn(required, dispatch)
        for required in ("github.event_name == 'workflow_dispatch'",
                         "github.ref == 'refs/heads/main' && inputs.publish_release",
                         'group: mika-release', 'cancel-in-progress: false'):
            self.assertIn(required, publish)
        version = json.loads((ROOT / 'vcpkg.json').read_text(encoding='utf-8'))['version-string']
        self.assertIn('Mika v' + version, (ROOT / '.github/release-notes.md').read_text(encoding='utf-8'))

    def test_ci_actions_remain_pinned_without_persisted_checkout_credentials(self):
        workflow = (ROOT / '.github/workflows/build.yml').read_text(encoding='utf-8')
        actions = re.findall(r'^\s+- uses: (\S+)', workflow, re.M)
        self.assertTrue(actions)
        for action in actions:
            self.assertRegex(action, r'^actions/[a-z/-]+@[0-9a-f]{40}$')
        checkouts = [action for action in actions if action.startswith('actions/checkout@')]
        ephemeral = re.findall(r'- uses: actions/checkout@[^\n]+\n\s+with:\n\s+persist-credentials: false', workflow)
        self.assertEqual(len(ephemeral), len(checkouts))

    def test_model_free_ci_keeps_sanitizer_coverage(self):
        workflow = (ROOT / '.github/workflows/build.yml').read_text(encoding='utf-8')
        core = workflow.split('  model-free:', 1)[1].split('  package:', 1)[0]
        for required in ('-DMIKA_SANITIZERS=ON', 'ASAN_OPTIONS: detect_leaks=1',
                         'UBSAN_OPTIONS: halt_on_error=1', 'ctest --test-dir build-sanitizers'):
            self.assertIn(required, core)

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
