"""Self-signed certificate for the loopback HTTPS callback listener.

Only the browser ever sees this cert, during OAuth login. It is generated once
and cached in the config dir so it stays stable across restarts.
"""

from __future__ import annotations

import datetime as dt
import ipaddress
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def ensure_cert(config_dir: Path, host: str = "127.0.0.1") -> tuple[Path, Path]:
    """Return (cert_path, key_path), generating a self-signed pair if absent."""
    config_dir.mkdir(parents=True, exist_ok=True)
    cert_path = config_dir / "callback-cert.pem"
    key_path = config_dir / "callback-key.pem"
    if cert_path.exists() and key_path.exists():
        return cert_path, key_path

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)])
    # Use a fixed validity window; the clock is not needed for a loopback cert.
    not_before = dt.datetime(2020, 1, 1, tzinfo=dt.UTC)
    not_after = dt.datetime(2100, 1, 1, tzinfo=dt.UTC)
    san = _san_for(host)

    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .add_extension(san, critical=False)
        .sign(key, hashes.SHA256())
    )

    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    key_path.chmod(0o600)
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return cert_path, key_path


def _san_for(host: str) -> x509.SubjectAlternativeName:
    try:
        return x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(host))])
    except ValueError:
        return x509.SubjectAlternativeName([x509.DNSName(host)])
