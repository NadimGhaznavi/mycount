"""Supply MyCount policy to the portable deployment tools."""
from deployment_tools.DeploymentConfig import DeploymentConfig
from mycount.constants.DDeployment import DDeployment


class DeploymentConfiguration:
    @staticmethod
    def resolve() -> DeploymentConfig:
        return DeploymentConfig(
            targets=DDeployment.TARGETS, dependencies=DDeployment.DEPENDENCIES,
            manifest=DDeployment.RELEASE_MANIFEST, version_marker=DDeployment.VERSION_MARKER,
            version_file="mycount/constants/DMyCount.py",
            version_pattern=rb'(    VERSION: Final\[str\] = )"[^"\n]+"',
            scan_roots=("mycount", "deployment_tools", "systemd", "caddy"),
            package_roots=("mycount", "deployment_tools"),
            setup_files=("requirements.txt", "scripts/update-geoip.sh", "scripts/uninstall.sh"),
            full_setup_target=DDeployment.FILESYSTEM,
        )
