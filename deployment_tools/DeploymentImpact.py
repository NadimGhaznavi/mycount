"""Determine deployment impact from the static artifact dependency graph."""

from collections.abc import Mapping


class DeploymentImpact:
    def __init__(self, targets: Mapping[str, tuple[str, ...]], dependencies: Mapping[str, tuple[str, ...]]) -> None:
        self.targets = targets
        self.dependencies = dependencies

    def is_impacted(self, target: str, artifact: str) -> bool:
        """Check a target's descendants for an exact repository-relative path.

        Unknown targets raise KeyError. Artifacts outside the mapped target
        dependencies have no declared impact. No filesystem access is needed.
        """
        pending = list(self.targets[target])
        visited = set()
        while pending:
            dependency = pending.pop()
            if dependency in visited:
                continue
            if dependency == artifact:
                return True
            visited.add(dependency)
            pending.extend(self.dependencies[dependency])
        return False

    def affected_targets(self, artifact: str) -> frozenset[str]:
        """Return every deployment target that depends on the artifact."""
        return frozenset(
            target for target in self.targets
            if self.is_impacted(target, artifact)
        )
