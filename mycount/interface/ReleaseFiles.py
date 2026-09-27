"""Configure the portable ReleaseFiles interface for MyCount."""
from pathlib import Path
from deployment_tools.ReleaseFiles import ReleaseFiles as PortableReleaseFiles
from mycount.interface.DeploymentConfiguration import DeploymentConfiguration


class ReleaseFiles(PortableReleaseFiles):
    def __init__(self, checkout: Path) -> None:
        super().__init__(checkout, DeploymentConfiguration.resolve())
