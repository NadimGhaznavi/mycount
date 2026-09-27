"""Bind deployment impact analysis to MyCount's generated dependency map."""
from deployment_tools.DeploymentImpact import DeploymentImpact as PortableDeploymentImpact
from mycount.constants.DDeployment import DDeployment


class DeploymentImpact(PortableDeploymentImpact):
    def __init__(self) -> None:
        super().__init__(DDeployment.TARGETS, DDeployment.DEPENDENCIES)
