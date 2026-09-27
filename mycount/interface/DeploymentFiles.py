"""Configure the portable DeploymentFiles interface for MyCount."""
from pathlib import Path
from deployment_tools.DeploymentFiles import DeploymentFiles as PortableDeploymentFiles
from mycount.interface.DeploymentConfiguration import DeploymentConfiguration


class DeploymentFiles(PortableDeploymentFiles):
    def __init__(self, checkout: Path, installation: Path) -> None:
        super().__init__(checkout, installation, DeploymentConfiguration.resolve())
