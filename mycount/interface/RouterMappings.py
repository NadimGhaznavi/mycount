"""Manage the collector's TCP mappings on the discovered UPnP router."""

from ipaddress import IPv4Address
import re
import subprocess

from mycount.constants.DRouterMappings import DRouterMappings


class RouterMappings:
    def clear(self, ports: tuple[int, ...]) -> None:
        listing = self._listing()
        existing = self._mappings(listing)
        udp = self._mappings(listing, 'UDP')
        selected = []
        for port in ports:
            if port in existing:
                selected.append((port, 'TCP'))
                if udp.get(port) == existing[port]:
                    selected.append((port, 'UDP'))
        for port, protocol in selected:
            subprocess.run(['upnpc', '-d', str(port), protocol], check=True, timeout=DRouterMappings.COMMAND_TIMEOUT)
        listing = self._listing()
        current = {protocol: self._mappings(listing, protocol) for protocol in ('TCP', 'UDP')}
        for port, protocol in selected:
            if port in current[protocol]:
                raise RuntimeError(f"UPnP {protocol} port {port} mapping remains after deletion.")

    def forward(self, ports: tuple[int, ...]) -> tuple[int, ...]:
        """Restore incorrect mappings and return the ports that were repaired."""
        listing = self._listing()
        local = re.search(r"^Local LAN ip address\s*:\s*(\S+)\s*$", listing, re.MULTILINE)
        if local is None:
            raise RuntimeError("UPnP discovery did not report the host's LAN address.")
        address = IPv4Address(local[1])
        if address.is_loopback or address.is_unspecified or address.is_multicast:
            raise ValueError("UPnP reported an invalid LAN address.")
        existing = self._mappings(listing)
        changed = tuple(port for port in ports if existing.get(port) != (str(address), port))
        if not changed:
            return ()
        for port in changed:
            if port in existing:
                subprocess.run(['upnpc', '-d', str(port), 'TCP'], check=True, timeout=DRouterMappings.COMMAND_TIMEOUT)
            subprocess.run(['upnpc', '-a', str(address), str(port), str(port), 'TCP'], check=True, timeout=DRouterMappings.COMMAND_TIMEOUT)
        current = self._mappings(self._listing())
        for port in ports:
            if current.get(port) != (str(address), port):
                raise RuntimeError(f"UPnP did not forward TCP port {port} to {address}:{port}.")

        return changed

    @staticmethod
    def _listing() -> str:
        return subprocess.run(['upnpc', '-l'], check=True, capture_output=True, text=True, timeout=DRouterMappings.COMMAND_TIMEOUT).stdout

    @staticmethod
    def _mappings(listing: str, protocol: str = 'TCP') -> dict[int, tuple[str, int]]:
        return {int(port): (address, int(internal)) for port, address, internal in re.findall(
            rf"^\s*\d+\s+{protocol}\s+(\d+)->([\d.]+):(\d+)\s", listing, re.MULTILINE)}
