"""Project-supplied deployment settings; no project-specific defaults."""
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class DeploymentConfig:
    targets: Mapping[str, tuple[str, ...]]
    dependencies: Mapping[str, tuple[str, ...]]
    manifest: str
    version_marker: str
    version_file: str
    version_pattern: bytes
    scan_roots: tuple[str, ...]
    package_roots: tuple[str, ...]
    setup_files: tuple[str, ...]
    full_setup_target: str
