"""Read release inputs and persist deployment metadata for the SDLC scripts."""

import ast
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re

from deployment_tools.DeploymentConfig import DeploymentConfig


class ReleaseFiles:
    def __init__(self, checkout: Path, config: DeploymentConfig) -> None:
        self.checkout = checkout
        self.config = config

    def snapshot(self) -> dict[str, str]:
        """Hash deployment inputs, excluding the automatic version-number edit."""
        artifacts = set(self.config.dependencies)
        for folder in self.config.scan_roots:
            for path in (self.checkout / folder).rglob("*"):
                if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                    name = path.relative_to(self.checkout).as_posix()
                    if name not in artifacts:
                        raise ValueError(f"Add deployment artifact to the dependency map: {name}")
        return {
            name: self.digest(name, (self.checkout / name).read_bytes())
            for name in sorted(artifacts)
        }

    def digest(self, name: str, content: bytes) -> str:
        if name == self.config.version_file:
            content = re.sub(self.config.version_pattern, rb'\1"<release>"', content)
        return sha256(content).hexdigest()

    def read(self) -> dict:
        data = json.loads((self.checkout / self.config.manifest).read_text())
        if not isinstance(data, dict) or set(data) != {"releases", "artifacts"}:
            raise ValueError("Invalid release deployment metadata")
        if not isinstance(data["releases"], list) or not data["releases"]:
            raise ValueError("Release history must not be empty")
        versions = set()
        for release in data["releases"]:
            if (not isinstance(release, dict) or set(release) != {"version", "targets"}
                    or not isinstance(release["version"], str) or not release["version"]
                    or release["version"] in versions):
                raise ValueError("Invalid or duplicate release version")
            self._validate_targets(release["targets"])
            versions.add(release["version"])
        if not isinstance(data["artifacts"], dict):
            raise ValueError("Invalid artifact baseline")
        for name, artifact in data["artifacts"].items():
            if (not isinstance(name, str) or not isinstance(artifact, dict)
                    or set(artifact) != {"digest", "targets"}):
                raise ValueError("Invalid artifact baseline entry")
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or path.as_posix() != name or name == ".":
                raise ValueError(f"Invalid artifact path: {name}")
            if artifact["digest"] is not None and (
                    not isinstance(artifact["digest"], str)
                    or re.fullmatch(r"[0-9a-f]{64}", artifact["digest"]) is None):
                raise ValueError(f"Invalid artifact digest: {name}")
            self._validate_targets(artifact["targets"])
        return data

    def _validate_targets(self, targets: object) -> None:
        if (not isinstance(targets, list)
                or any(not isinstance(target, str) or target not in self.config.targets for target in targets)):
            raise ValueError("Invalid deployment targets")

    def write(self, data: dict) -> None:
        path = self.checkout / self.config.manifest
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        temporary.replace(path)

    def installed_version(self, installation: Path) -> str:
        marker = installation / self.config.version_marker
        if marker.exists():
            return marker.read_text().strip()
        content = (installation / self.config.version_file).read_bytes()
        matches = list(re.finditer(self.config.version_pattern, content))
        if len(matches) != 1:
            raise ValueError("Installed version assignment is missing or ambiguous")
        assignment = matches[0].group().decode().split("=", 1)[1].strip()
        return ast.literal_eval(assignment)
