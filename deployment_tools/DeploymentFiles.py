"""Copy release artifacts for the deployment targets selected by an upgrade."""

from pathlib import Path
import shutil

from deployment_tools.DeploymentConfig import DeploymentConfig
from deployment_tools.ReleaseFiles import ReleaseFiles


class DeploymentFiles:
    def __init__(self, checkout: Path, installation: Path, config: DeploymentConfig) -> None:
        self.config = config
        self._checkout = checkout
        self._installation = installation

    def copy_application(self, targets: frozenset[str]) -> None:
        artifacts = ReleaseFiles(self._checkout, self.config).read()["artifacts"]
        full_setup = self.config.full_setup_target in targets
        for name, artifact in artifacts.items():
            if any(name.startswith(folder + "/") for folder in self.config.package_roots) and (full_setup or targets.intersection(artifact["targets"])):
                self._copy(name)

        previous_manifest = self._installation / self.config.manifest
        if previous_manifest.exists():
            previous = ReleaseFiles(self._installation, self.config).read()["artifacts"]
            obsolete = (
                name for name, artifact in previous.items()
                if any(name.startswith(folder + "/") for folder in self.config.package_roots) and name not in artifacts
                and (full_setup or targets.intersection(artifact["targets"]))
            )
        elif full_setup:
            # The first managed upgrade has no previous artifact manifest.
            obsolete = (
                path.relative_to(self._installation).as_posix()
                for folder in self.config.package_roots
                for path in (self._installation / folder).rglob("*")
                if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
                and path.relative_to(self._installation).as_posix() not in artifacts
            )
        else:
            obsolete = ()
        for name in obsolete:
            (self._installation / name).unlink(missing_ok=True)

    def copy_setup(self) -> None:
        for name in self.config.setup_files:
            self._copy(name)

    def complete(self, version: str) -> None:
        """Publish release bookkeeping after the selected deployment work succeeds."""
        self._copy(self.config.version_file)
        self._copy(self.config.manifest)
        marker = self._installation / self.config.version_marker
        temporary = marker.with_suffix(".tmp")
        temporary.write_text(version + "\n")
        temporary.replace(marker)

    def _copy(self, name: str) -> None:
        source = self._checkout / name
        destination = self._installation / name
        if destination.exists() and destination.read_bytes() == source.read_bytes():
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        shutil.copy2(source, temporary)
        temporary.replace(destination)
