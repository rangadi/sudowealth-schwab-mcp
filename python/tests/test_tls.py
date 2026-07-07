from __future__ import annotations

import ipaddress

from cryptography import x509

from schwab_mcp.tls import ensure_cert


def test_cert_has_ip_san_and_is_cached(tmp_path):
    cert_path, key_path = ensure_cert(tmp_path, "127.0.0.1")
    assert cert_path.exists() and key_path.exists()

    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    ips = san.get_values_for_type(x509.IPAddress)
    assert ipaddress.ip_address("127.0.0.1") in ips

    # Second call reuses the same files (cached, not regenerated).
    before = cert_path.read_bytes()
    ensure_cert(tmp_path, "127.0.0.1")
    assert cert_path.read_bytes() == before
