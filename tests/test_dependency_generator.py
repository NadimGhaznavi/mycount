"""Test dependency generation and portability without Git or host services."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from deployment_tools.DependencyGenerator import DependencyGenerator

ROOT = Path(__file__).resolve().parents[1]


class DependencyGeneratorTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.rules = {
            'output': 'acme/Generated.py', 'template': 'map.py.in',
            'python_roots': ['acme'], 'template_roots': ['views'],
            'scan': ['acme/**/*.py', 'views/**/*.html'], 'exclude': [],
            'targets': {'web': ['acme/web.py', 'views/sub/page.html'],
                        'setup': ['acme/Generated.py', 'project.json']},
            'extra': {'project.json': ['map.py.in']},
        }
        self.write('acme/__init__.py', '')
        self.write('acme/web.py', 'from . import shared\n')
        self.write('acme/shared.py', 'VALUE = 1\n')
        self.write('views/sub/page.html', '{% extends "base.html" %}')
        self.write('views/base.html', '{# {% include "not-real.html" %} #}')
        self.write('map.py.in', '# Generated\nTARGETS = {{TARGETS}}\nDEPENDENCIES = {{DEPENDENCIES}}\n')
        self.save_rules()

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def save_rules(self):
        self.write('project.json', json.dumps(self.rules))

    def generator(self):
        return DependencyGenerator(self.root, 'project.json')

    def test_relative_imports_initializers_and_template_loader_root(self):
        graph = self.generator().build()
        self.assertEqual(graph['acme/web.py'], ('acme/__init__.py', 'acme/shared.py'))
        self.assertEqual(graph['views/sub/page.html'], ('views/base.html',))

    def test_deterministic_generation_and_nonmutating_check(self):
        generator = self.generator()
        self.assertFalse(generator.update(check=True))
        self.assertFalse((self.root / 'acme/Generated.py').exists())
        generator.update()
        before = (self.root / 'acme/Generated.py').stat().st_mtime_ns
        generator.update()
        self.assertEqual((self.root / 'acme/Generated.py').stat().st_mtime_ns, before)
        self.write('acme/other.py', '')
        self.write('acme/web.py', 'from . import other\nfrom . import shared\n')
        self.assertFalse(generator.update(check=True))
        self.assertEqual((self.root / 'acme/Generated.py').stat().st_mtime_ns, before)
        generator.update()
        self.assertTrue(generator.update(check=True))

    def test_unreachable_module_requires_explicit_ownership(self):
        self.write('acme/unused.py', '')
        with self.assertRaisesRegex(ValueError, 'unreachable'):
            self.generator().build()
        self.rules['extra']['acme/web.py'] = ['acme/unused.py']
        self.save_rules()
        self.assertIn('acme/unused.py', self.generator().build()['acme/web.py'])

    def test_missing_import_and_cycle_fail(self):
        self.write('acme/web.py', 'from acme.missing import value\n')
        with self.assertRaisesRegex(ValueError, 'unresolved local import'):
            self.generator().build()
        self.write('acme/web.py', 'from . import shared\n')
        self.write('acme/shared.py', 'from . import web\n')
        with self.assertRaisesRegex(ValueError, 'cycle'):
            self.generator().build()

    def test_dynamic_templates_require_rules(self):
        self.write('views/sub/page.html', '{% include chosen %}')
        with self.assertRaisesRegex(ValueError, 'dynamic template'):
            self.generator().build()
        self.rules['extra']['views/sub/page.html'] = ['views/base.html']
        self.save_rules()
        self.assertIn('views/base.html', self.generator().build()['views/sub/page.html'])

    def test_conditional_literal_is_not_mistaken_for_complete_dependency(self):
        self.write('views/sub/page.html', '{% include "base.html" if test else "other.html" %}')
        with self.assertRaisesRegex(ValueError, 'dynamic template'):
            self.generator().build()

    def test_python_heredocs_are_scanned_without_execution(self):
        self.write('install.sh', "python3 - <<'PYCODE'\nfrom acme import shared\nraise RuntimeError('never execute')\nPYCODE\n")
        self.rules['targets']['setup'].append('install.sh')
        self.save_rules()
        self.assertIn('acme/shared.py', self.generator().build()['install.sh'])

    def test_copied_tool_runs_in_another_project_with_only_its_rules(self):
        shutil.copytree(ROOT / 'deployment_tools', self.root / 'deployment_tools',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        for args, status in ((['--check'], 1), ([], 0), (['--check'], 0)):
            result = subprocess.run([sys.executable, '-B', '-m', 'deployment_tools',
                                     '--rules', 'project.json', *args], cwd=self.root,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, status, result.stderr)
        # Exercise release metadata and installation using the copied package too.
        self.write('exercise.py', '''from pathlib import Path
from deployment_tools.DeploymentConfig import DeploymentConfig
from deployment_tools.DeploymentImpact import DeploymentImpact
from deployment_tools.ReleaseFiles import ReleaseFiles
from deployment_tools.ReleaseDeployment import ReleaseDeployment
from deployment_tools.DeploymentFiles import DeploymentFiles
import sys
assert not any(name == 'mycount' or name.startswith('mycount.') for name in sys.modules)
root = Path.cwd()
(root / 'acme/version.py').write_text('VERSION = "1"\\n')
config = DeploymentConfig(
    targets={'web': ('acme/web.py',), 'setup': ('acme/version.py',)},
    dependencies={'acme/web.py': (), 'acme/version.py': ()},
    manifest='history.json', version_marker='.version', version_file='acme/version.py',
    version_pattern=rb'(VERSION = )"[^"\\n]+"', scan_roots=(),
    package_roots=('acme',), setup_files=(), full_setup_target='setup')
files = ReleaseFiles(root, config)
impact = DeploymentImpact(config.targets, config.dependencies)
files.write({'releases': [{'version': '1', 'targets': []}], 'artifacts': {
    name: {'digest': digest, 'targets': sorted(impact.affected_targets(name))}
    for name, digest in files.snapshot().items()}})
(root / 'acme/web.py').write_text('# second release\\n')
releases = ReleaseDeployment(files)
assert releases.prepare('1', '2') == {'web'}
assert releases.upgrade_targets('1', '2') == {'web'}
installed = root / 'installed'
installed.mkdir()
deployment = DeploymentFiles(root, installed, config)
deployment.copy_application(frozenset({'web'}))
deployment.complete('2')
assert files.installed_version(installed) == '2'
assert (installed / 'acme/web.py').read_text() == '# second release\\n'
''')
        result = subprocess.run([sys.executable, '-B', 'exercise.py'], cwd=self.root,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_binary_assets_can_be_declared_without_text_decoding(self):
        (self.root / 'image.bin').write_bytes(bytes([255, 0, 128]))
        self.rules['extra']['acme/web.py'] = ['image.bin']
        self.save_rules()
        self.assertIn('image.bin', self.generator().build()['acme/web.py'])

    def test_dynamic_import_requires_declared_dependencies(self):
        self.write('acme/web.py', 'from importlib import import_module\nimport_module(selected)\n')
        with self.assertRaisesRegex(ValueError, 'dynamic import'):
            self.generator().build()
        self.rules['extra']['acme/web.py'] = ['acme/shared.py']
        self.save_rules()
        self.assertIn('acme/shared.py', self.generator().build()['acme/web.py'])

    def test_rules_reject_invalid_structure_and_paths(self):
        self.rules['extra'] = []
        self.save_rules()
        with self.assertRaisesRegex(ValueError, 'extra'):
            self.generator()
        self.rules['extra'] = {}
        self.rules['output'] = '../escape.py'
        self.save_rules()
        with self.assertRaisesRegex(ValueError, 'repository-relative'):
            self.generator()

    def test_project_generated_map_is_current(self):
        self.assertTrue(DependencyGenerator(ROOT, 'deployment/rules.json').update(check=True))


if __name__ == '__main__':
    unittest.main()
