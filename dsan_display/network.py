"""Listen configuration and local-network URL discovery."""
import ipaddress
import socket
from urllib.parse import urlsplit


def listen_address(value):
    try:
        return str(ipaddress.ip_address(value))
    except ValueError as exc:
        raise ValueError('Use an IP address, such as 0.0.0.0 or 127.0.0.1') from exc


def canonical_ip(value):
    address = ipaddress.ip_address(value.split('%', 1)[0])
    return str(getattr(address, 'ipv4_mapped', None) or address)


def local_hostnames():
    names = {'localhost', socket.gethostname().lower()}
    names.add(socket.gethostname().split('.')[0].lower() + '.local')
    return names


def network_addresses():
    addresses = set()
    try:
        addresses.update(item[4][0] for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET))
    except OSError:
        pass
    try:
        # Consult routing only; no datagram is sent to this documentation address.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(('192.0.2.1', 9))
            addresses.add(sock.getsockname()[0])
    except OSError:
        pass
    return sorted(address for address in addresses
                  if not ipaddress.IPv4Address(address).is_loopback
                  and not ipaddress.IPv4Address(address).is_unspecified)


def host_allowed(header, port, local_address, names):
    """Accept the addressed interface or known local names, not arbitrary Host values."""
    try:
        parsed = urlsplit('//' + header)
        if parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            return False
        if (parsed.port or 80) != port:
            return False
        hostname = (parsed.hostname or '').lower().rstrip('.')
        if hostname in names:
            return True
        return canonical_ip(hostname) == canonical_ip(local_address)
    except (ValueError, TypeError):
        return False
