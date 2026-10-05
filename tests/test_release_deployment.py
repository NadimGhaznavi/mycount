"""Exercise release metadata without Git, release scripts, or host services."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from mycount.activity.DeploymentImpact import DeploymentImpact
from mycount.activity.ReleaseDeployment import ReleaseDeployment
from mycount.constants.DDeployment import DDeployment
from mycount.interface.ReleaseFiles import ReleaseFiles


class ReleaseDeploymentTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.report = "mycount/report.py"
        self.listener = "mycount/listener.py"
        self.shared = "mycount/constants/DMyCount.py"
        self.graph = {self.report: (self.shared,), self.listener: (self.shared,), self.shared: ()}
        self.targets = {DDeployment.REPORT_SERVER: (self.report,),
                        DDeployment.LISTENER: (self.listener,), DDeployment.FILESYSTEM: ()}
        for name, value in (("DEPENDENCIES", self.graph), ("TARGETS", self.targets)):
            patcher = patch.object(DDeployment, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        for name in self.graph:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# initial\n")
        (self.root / self.shared).write_text('class DMyCount:\n    VERSION: Final[str] = "1.0.0"\n')
        self.files = ReleaseFiles(self.root)
        self.releases = ReleaseDeployment(self.files)
        impact = DeploymentImpact()
        self.files.write({
            "releases": [{"version": "1.0.0", "targets": []}],
            "artifacts": {name: {"digest": digest, "targets": sorted(impact.affected_targets(name))}
                          for name, digest in self.files.snapshot().items()},
        })

    def test_display_only_release(self):
        (self.root / self.report).write_text("# new report\n")
        self.assertEqual(self.releases.prepare("1.0.0", "1.0.1"), {DDeployment.REPORT_SERVER})
        self.assertEqual(self.releases.upgrade_targets("1.0.0", "1.0.1"), {DDeployment.REPORT_SERVER})

    def test_skipped_releases_union_flags(self):
        (self.root / self.report).write_text("# report\n")
        self.releases.prepare("1.0.0", "1.0.1")
        (self.root / self.listener).write_text("# listener\n")
        self.releases.prepare("1.0.1", "1.0.2")
        self.assertEqual(self.releases.upgrade_targets("1.0.0", "1.0.2"),
                         {DDeployment.REPORT_SERVER, DDeployment.LISTENER})
        self.assertEqual(self.releases.upgrade_targets("1.0.1", "1.0.2"), {DDeployment.LISTENER})
        self.assertEqual(self.releases.upgrade_targets("1.0.2", "1.0.2"), frozenset())

    def test_only_automatic_version_edit_is_ignored(self):
        path = self.root / self.shared
        path.write_text(path.read_text().replace('"1.0.0"', '"1.0.1"'))
        self.assertEqual(self.releases.prepare("1.0.0", "1.0.1"), frozenset())
        path.write_text(path.read_text() + '    PORT = 1234\n')
        self.assertEqual(self.releases.prepare("1.0.1", "1.0.2"),
                         {DDeployment.REPORT_SERVER, DDeployment.LISTENER})

    def test_release_script_records_updated_constants_and_stages_metadata(self):
        # Exercise only embedded metadata preparation, without invoking the
        # release script, Git, or any host deployment operations.
        script = (Path(__file__).resolve().parents[1] / 'scripts/new-release.sh').read_text()
        preparation = script.split("<<'PYRELEASE'\n", 1)[1].split('\nPYRELEASE', 1)[0]
        self.assertIn('git add -- "${version_file}" "${changelog_file}" "${deployment_manifest}"', script)
        path = self.root / self.shared
        path.write_text('class DMyCount:\n    VERSION: Final[str] = "1.0.1"\n'
                        '    CMDB_CODENAME: Final[str] = "New release"\n')
        with patch('sys.argv', ['-', '1.0.0', '1.0.1']), \
                patch('mycount.interface.ReleaseFiles.ReleaseFiles', return_value=self.files), \
                patch('builtins.print'):
            exec(compile(preparation, 'release metadata preparation', 'exec'), {})
        data = self.files.read()
        self.assertEqual(data['releases'][-1], {
            'version': '1.0.1',
            'targets': sorted((DDeployment.REPORT_SERVER, DDeployment.LISTENER)),
        })
        self.assertEqual(self.releases.upgrade_targets('1.0.0', '1.0.1'),
                         {DDeployment.REPORT_SERVER, DDeployment.LISTENER})

    def test_deleted_artifact_retains_previous_owners(self):
        (self.root / self.report).unlink()
        del self.graph[self.report]
        self.targets[DDeployment.REPORT_SERVER] = ()
        self.assertEqual(self.releases.prepare("1.0.0", "1.0.1"), {DDeployment.REPORT_SERVER})

    def test_filesystem_flags_require_full_workflow(self):
        self.targets[DDeployment.FILESYSTEM] = (self.shared,)
        self.releases.prepare("1.0.0", "1.0.1")
        self.assertEqual(self.releases.upgrade_targets("1.0.0", "1.0.1"), set(self.targets))

    def test_unprepared_or_unknown_versions_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "installed version 0.0.1 is absent"):
            self.releases.upgrade_targets("0.0.1", "1.0.0")
        with self.assertRaisesRegex(ValueError, "checkout version 1.0.1, latest prepared release 1.0.0"):
            self.releases.upgrade_targets("1.0.0", "1.0.1")
        (self.root / self.report).write_text("# uncommitted change\n")
        with self.assertRaisesRegex(ValueError, "differ"):
            self.releases.upgrade_targets("1.0.0", "1.0.0")

    def test_new_unmapped_module_is_rejected(self):
        (self.root / 'mycount/new.py').write_text("# new\n")
        with self.assertRaisesRegex(ValueError, "dependency map"):
            self.releases.prepare("1.0.0", "1.0.1")

    def test_missing_installed_baseline_artifact_is_not_assumed_unchanged(self):
        data = self.files.read()
        data['artifacts'][self.report]['digest'] = None
        self.files.write(data)
        self.assertEqual(self.releases.prepare("1.0.0", "1.0.1"), {DDeployment.REPORT_SERVER})

    def test_malformed_metadata_is_rejected(self):
        data = self.files.read()
        data['releases'][0]['targets'] = ['typo']
        self.files.write(data)
        with self.assertRaisesRegex(ValueError, "targets"):
            self.files.read()

    def test_success_marker_takes_precedence_over_replaced_version_file(self):
        self.assertEqual(self.files.installed_version(self.root), "1.0.0")
        (self.root / DDeployment.VERSION_MARKER).write_text("0.9.0\n")
        self.assertEqual(self.files.installed_version(self.root), "0.9.0")
