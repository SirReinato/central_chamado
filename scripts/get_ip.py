import socket

def get_network_ip():
    """Identifica o endereço IP real da máquina na rede local corporativa."""
    # Tenta resolver o IP através da rota para a rede externa ou gateway local
    for target in [("8.8.8.8", 80), ("1.1.1.1", 80), ("172.16.0.254", 80)]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(target)
            ip = s.getsockname()[0]
            s.close()
            if ip and not ip.startswith("127."):
                return ip
        except Exception:
            pass

    # Fallback procurando ips não virtuais
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127.") and not ip.startswith("169.254.") and not ip.startswith("172.17."):
                return ip
    except Exception:
        pass

    return "127.0.0.1"

if __name__ == '__main__':
    print(get_network_ip())
