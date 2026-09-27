"""Verify selected deployment copies against isolated source/install trees."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from mycount.constants.DDeployment import DDeployment
from mycount.interface.DeploymentFiles import DeploymentFiles
from mycount.interface.ReleaseFiles import ReleaseFiles


class DeploymentFilesTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source"
        self.installed = self.root / "installed"
        self.installed.mkdir()
        self.paths = {
            "mycount/report.py": [DDeployment.REPORT_SERVER],
            "mycount/listener.py": [DDeployment.LISTENER],
            "mycount/shared.py": [DDeployment.REPORT_SERVER, DDeployment.LISTENER],
            "mycount/setup.py": [DDeployment.FILESYSTEM],
            "mycount/constants/DMyCount.py": list(DDeployment.TARGETS),
        }
        for name in (*self.paths, "requirements.txt", "scripts/update-geoip.sh", "scripts/uninstall.sh"):
            for root, content in ((self.source, "new"), (self.installed, "old")):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
        self.metadata = {
            "releases": [{"version": "1.0.1", "targets": [DDeployment.REPORT_SERVER]}],
            "artifacts": {name: {"digest": "a" * 64, "targets": targets}
                          for name, targets in self.paths.items()},
        }
        ReleaseFiles(self.source).write(self.metadata)
        ReleaseFiles(self.installed).write({**self.metadata, "releases": [{"version": "1.0.0", "targets": []}]})
        (self.installed / DDeployment.VERSION_MARKER).write_text("1.0.0\n")
        self.files = DeploymentFiles(self.source, self.installed)

    def test_report_copy_leaves_listener_setup_and_bookkeeping_untouched(self):
        previous = (self.installed / DDeployment.RELEASE_MANIFEST).read_bytes()
        self.files.copy_application(frozenset({DDeployment.REPORT_SERVER}))
        for name in ("mycount/report.py", "mycount/shared.py"):
            self.assertEqual((self.installed / name).read_text(), "new")
        for name in ("mycount/listener.py", "mycount/setup.py", "requirements.txt", "scripts/uninstall.sh"):
            self.assertEqual((self.installed / name).read_text(), "old")
        self.assertEqual((self.installed / DDeployment.RELEASE_MANIFEST).read_bytes(), previous)
        self.assertEqual((self.installed / DDeployment.VERSION_MARKER).read_text(), "1.0.0\n")

    def test_unchanged_shared_module_is_not_replaced(self):
        path = self.installed / "mycount/shared.py"
        path.write_text("new")
        inode = path.stat().st_ino
        self.files.copy_application(frozenset({DDeployment.REPORT_SERVER}))
        self.assertEqual(path.stat().st_ino, inode)

    def test_removed_artifacts_are_limited_to_selected_targets(self):
        previous = ReleaseFiles(self.installed).read()
        for name, target in (("mycount/old_report.py", DDeployment.REPORT_SERVER),
                             ("mycount/old_listener.py", DDeployment.LISTENER)):
            previous["artifacts"][name] = {"digest": "b" * 64, "targets": [target]}
            (self.installed / name).write_text("old")
        ReleaseFiles(self.installed).write(previous)
        self.files.copy_application(frozenset({DDeployment.REPORT_SERVER}))
        self.assertFalse((self.installed / "mycount/old_report.py").exists())
        self.assertTrue((self.installed / "mycount/old_listener.py").exists())

    def test_full_setup_copies_package_and_setup_files(self):
        self.files.copy_application(frozenset(DDeployment.TARGETS))
        self.files.copy_setup()
        for name in (*self.paths, "requirements.txt", "scripts/update-geoip.sh", "scripts/uninstall.sh"):
            self.assertEqual((self.installed / name).read_text(), "new")

    def test_completion_without_impact_only_updates_release_bookkeeping(self):
        self.files.complete("1.0.1")
        self.assertEqual((self.installed / DDeployment.VERSION_MARKER).read_text(), "1.0.1\n")
        self.assertEqual((self.installed / DDeployment.RELEASE_MANIFEST).read_bytes(),
                         (self.source / DDeployment.RELEASE_MANIFEST).read_bytes())
        self.assertEqual((self.installed / "mycount/constants/DMyCount.py").read_text(), "new")
        self.assertEqual((self.installed / "mycount/report.py").read_text(), "old")

    def test_manifest_paths_cannot_escape_installation(self):
        self.metadata["artifacts"]["mycount/../../outside.py"] = {"digest": "a" * 64, "targets": []}
        ReleaseFiles(self.installed).write(self.metadata)
        with self.assertRaisesRegex(ValueError, "artifact path"):
            ReleaseFiles(self.installed).read()
