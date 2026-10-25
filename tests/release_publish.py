"""Execute the real publication shell with fake gh/preflight; no network/writes to GitHub."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which('bash') if os.name != 'nt' else str(
    Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Git/bin/bash.exe')
if not BASH or not Path(BASH).is_file():
    BASH = None


@unittest.skipUnless(BASH, 'requires Bash (Git Bash on Windows)')
class Publication(unittest.TestCase):
    def publish(self, **changes):
        temporary = tempfile.TemporaryDirectory(prefix='mika-release-policy-')
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        (base / 'fake-bin').mkdir()
        (base / 'dist').mkdir()
        (base / 'dist/asset').write_text('fixture')
        version = changes.pop('SOURCE_VERSION', '0.3.2')
        (base / 'CMakeLists.txt').write_text(f'project(mika VERSION {version} LANGUAGES C CXX)\n')
        workflow = (ROOT / '.github/workflows/build.yml').read_text(encoding='utf-8')
        step = workflow.split('      - name: Publish checked assets\n', 1)[1].split('        run: |\n', 1)[1]
        script = '\n'.join(line[10:] if line.startswith('          ') else line for line in step.splitlines())
        for name, body in {
            'python3': '#!/usr/bin/env bash\nexit "${FAIL_PREFLIGHT:-0}"\n',
            'gh': '''#!/usr/bin/env bash
printf '%s\\n' "$*" >> calls.log
if [[ "$1 $2" == 'api repos/fixture/mika/git/ref/tags/v0.3.2' ]]; then
  if [[ -z "${EXISTING_TAG:-}" ]]; then
    printf '%s\\n' '{"message":"Not Found","status":"404"}'
    exit 1
  fi
  printf '%s\\n' "$EXISTING_TAG"
elif [[ "$1 $2 $3" == 'api --method POST' ]]; then
  exit "${FAIL_TAG_CREATE:-0}"
elif [[ "$1 $2" == 'release view' ]]; then
  printf '%s\\n' "${UPLOADED_ASSETS:-6}"
fi
''',
        }.items():
            path = base / 'fake-bin' / name
            path.write_text(body, encoding='utf-8', newline='\n')
            path.chmod(0o755)
        env = {**os.environ, 'GITHUB_EVENT_NAME': 'workflow_dispatch',
               'GITHUB_REF': 'refs/heads/main', 'GITHUB_REF_NAME': 'main',
               'GITHUB_REPOSITORY': 'fixture/mika', 'GITHUB_SHA': 'a' * 40,
               'GH_TOKEN': 'unused-test-token', 'EXISTING_TAG': '',
               'FAIL_PREFLIGHT': '0', 'FAIL_TAG_CREATE': '0', 'UPLOADED_ASSETS': '6', **changes}
        result = subprocess.run([BASH, '--noprofile', '--norc', '-e', '-o', 'pipefail',
                                 '-c', 'export PATH="$PWD/fake-bin:$PATH"\n' + script],
                                cwd=base, env=env, capture_output=True, text=True, timeout=20)
        calls = (base / 'calls.log').read_text() if (base / 'calls.log').exists() else ''
        return result, calls

    def test_manual_main_creates_exact_tested_tag_then_publishes(self):
        result, calls = self.publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('ref=refs/tags/v0.3.2 -f sha=' + 'a' * 40, calls)
        self.assertIn('--verify-tag --draft', calls)
        self.assertIn('release edit v0.3.2 --draft=false --latest', calls)

    def test_existing_matching_tag_is_never_recreated(self):
        result, calls = self.publish(EXISTING_TAG='a' * 40)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('--method POST', calls)

    def test_tag_creation_failure_prevents_release_writes(self):
        result, calls = self.publish(FAIL_TAG_CREATE='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('--method POST', calls)
        self.assertNotIn('release create', calls)

    def test_conflicting_tag_stops_before_release(self):
        result, calls = self.publish(EXISTING_TAG='b' * 40)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('--method POST', calls)
        self.assertNotIn('release create', calls)

    def test_manual_non_main_and_bad_version_cannot_write(self):
        for values in ({'GITHUB_REF': 'refs/heads/feature'}, {'SOURCE_VERSION': 'invalid'}):
            with self.subTest(values=values):
                result, calls = self.publish(**values)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(calls, '')

    def test_preflight_failure_prevents_tag_and_release_writes(self):
        result, calls = self.publish(FAIL_PREFLIGHT='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, '')

    def test_incomplete_upload_cannot_publish(self):
        result, calls = self.publish(UPLOADED_ASSETS='5')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('release create', calls)
        self.assertNotIn('release edit', calls)

    def test_matching_tag_push_preserves_original_route(self):
        result, calls = self.publish(GITHUB_EVENT_NAME='push', GITHUB_REF='refs/tags/v0.3.2',
                                     GITHUB_REF_NAME='v0.3.2')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('api ', calls)
        self.assertIn('release edit', calls)

    def test_mismatched_tag_push_cannot_write(self):
        result, calls = self.publish(GITHUB_EVENT_NAME='push', GITHUB_REF_NAME='v0.3.1')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, '')


if __name__ == '__main__':
    unittest.main(verbosity=2)
