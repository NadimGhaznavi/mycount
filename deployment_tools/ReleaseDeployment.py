"""Prepare release impact flags and combine them for a version upgrade."""

from deployment_tools.DeploymentImpact import DeploymentImpact
from deployment_tools.ReleaseFiles import ReleaseFiles


class ReleaseDeployment:
    def __init__(self, files: ReleaseFiles) -> None:
        self._files = files

    def prepare(self, previous_version: str, version: str) -> frozenset[str]:
        data = self._files.read()
        if data["releases"][-1]["version"] != previous_version:
            raise ValueError("Release baseline does not match the current version")
        if any(release["version"] == version for release in data["releases"]):
            raise ValueError("Deployment metadata already contains this version")
        snapshot = self._files.snapshot()
        impact = DeploymentImpact(self._files.config.targets, self._files.config.dependencies)
        artifacts = {
            name: {"digest": digest, "targets": sorted(impact.affected_targets(name))}
            for name, digest in snapshot.items()
        }
        affected = set()
        for name in data["artifacts"].keys() | artifacts.keys():
            old = data["artifacts"].get(name)
            new = artifacts.get(name)
            if old is not None and new is not None and old["digest"] == new["digest"]:
                affected.update(set(old["targets"]) ^ set(new["targets"]))
            else:
                if old is not None:
                    affected.update(old["targets"])
                if new is not None:
                    affected.update(new["targets"])
        data["releases"].append({"version": version, "targets": sorted(affected)})
        data["artifacts"] = artifacts
        self._files.write(data)
        return frozenset(affected)

    def upgrade_targets(self, installed_version: str, version: str) -> frozenset[str]:
        data = self._files.read()
        versions = [release["version"] for release in data["releases"]]
        if version != versions[-1]:
            raise ValueError(
                f"No complete deployment history for this upgrade: checkout version {version}, "
                f"latest prepared release {versions[-1]}. "
                "The release must include prepared deployment metadata."
            )
        if installed_version not in versions:
            raise ValueError(
                f"No complete deployment history for this upgrade: installed version "
                f"{installed_version} is absent from the prepared release history."
            )
        # Verify release inputs, without recalculating their dependency impact.
        expected = {name: entry["digest"] for name, entry in data["artifacts"].items()}
        if self._files.snapshot() != expected:
            raise ValueError("Deployment files differ from the prepared release; prepare a release first")
        affected = set()
        for release in data["releases"][versions.index(installed_version) + 1:]:
            affected.update(release["targets"])
        # Setup changes can alter dependencies or schemas shared by running processes.
        if self._files.config.full_setup_target in affected:
            affected.update(self._files.config.targets)
        return frozenset(affected)
