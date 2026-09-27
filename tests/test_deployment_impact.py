"""Verify target impact for direct, nested, shared, and unrelated artifacts."""

import unittest

from mycount.activity.DeploymentImpact import DeploymentImpact
from mycount.constants.DDeployment import DDeployment


class DeploymentImpactTests(unittest.TestCase):
    def setUp(self):
        self.impact = DeploymentImpact()

    def test_direct_service_unit_dependency(self):
        self.assertTrue(self.impact.is_impacted(
            DDeployment.REPORT_SERVER, "systemd/mycount-control.service"))
        self.assertFalse(self.impact.is_impacted(
            DDeployment.LISTENER, "systemd/mycount-control.service"))

    def test_nested_template_affects_only_report_server(self):
        self.assertEqual(self.impact.affected_targets(
            "mycount/server/templates/styles.html"), {DDeployment.REPORT_SERVER})

    def test_collection_module_affects_only_listener(self):
        self.assertEqual(self.impact.affected_targets(
            "mycount/interface/CollectorHttp.py"), {DDeployment.LISTENER})

    def test_shared_visit_interface_affects_both_servers(self):
        self.assertEqual(self.impact.affected_targets(
            "mycount/interface/VisitDb.py"),
            {DDeployment.REPORT_SERVER, DDeployment.LISTENER})

    def test_shared_database_and_requirements_affect_all_targets(self):
        for artifact in ("mycount/interface/DbMgr.py", "requirements.txt"):
            with self.subTest(artifact=artifact):
                self.assertEqual(self.impact.affected_targets(artifact), set(DDeployment.TARGETS))

    def test_schema_and_deployment_activity_affect_filesystem(self):
        for artifact in ("mycount/activity/VisitorSchema.py", "mycount/activity/DeploymentImpact.py"):
            with self.subTest(artifact=artifact):
                self.assertEqual(self.impact.affected_targets(artifact), {DDeployment.FILESYSTEM})

    def test_unmapped_artifacts_have_no_declared_impact(self):
        for artifact in ("README.md", "mycount/interface/Unmapped.py"):
            with self.subTest(artifact=artifact):
                self.assertEqual(self.impact.affected_targets(artifact), frozenset())

    def test_unknown_target_surfaces_caller_error(self):
        with self.assertRaises(KeyError):
            self.impact.is_impacted("unknown", "requirements.txt")
