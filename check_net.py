import socket

domains = ["google.com", "dns.google", "leetcode.com"]

for d in domains:
    try:
        ip = socket.gethostbyname(d)
        print(f"✓ {d} -> {ip}")
    except socket.gaierror as e:
        print(f"✗ {d} FAILED: {e}")