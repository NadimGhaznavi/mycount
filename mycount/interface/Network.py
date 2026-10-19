"""Resolve application listeners from the CMDB network inventory."""

from mycount.constants.DMyCount import DMyCount


class Network:
    @staticmethod
    def binding(use: str) -> tuple[str, int]:
        return {name: (interface, port) for name, interface, port in DMyCount.CMDB_NETWORK}[use]
