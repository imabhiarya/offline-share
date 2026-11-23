"""Internal certificate authority for HTTPS on the LAN.

Creates (once) an organisation root CA, then a server certificate signed by it with the
server IP and host name in the Subject Alternative Name. Client PCs import ``OfflineShare-RootCA.crt``
into "Trusted Root Certification Authorities" (see docs/NETWORK_GUIDE.md) so Chrome/Edge trust the site.
"""
from __future__ import annotations

import datetime as dt
import ipaddress
import socket
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def _write_key(key, path: Path) -> None:  # noqa: ANN001
    path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                       serialization.NoEncryption()))


def make_certs(cert_dir: Path, server_ip: str, org: str = "Office", extra_names: list[str] | None = None) -> dict:
    cert_dir.mkdir(parents=True, exist_ok=True)
    ca_key_p, ca_crt_p = cert_dir / "rootCA.key", cert_dir / "OfflineShare-RootCA.crt"
    now = dt.datetime.now(dt.timezone.utc)
    if ca_key_p.exists() and ca_crt_p.exists():
        ca_key = serialization.load_pem_private_key(ca_key_p.read_bytes(), None)
        ca_crt = x509.load_pem_x509_certificate(ca_crt_p.read_bytes())
    else:
        ca_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "OFFLINE SHARE Internal Root CA"),
                          x509.NameAttribute(NameOID.ORGANIZATION_NAME, org)])
        ca_crt = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(ca_key.public_key())
                  .serial_number(x509.random_serial_number()).not_valid_before(now - dt.timedelta(days=1))
                  .not_valid_after(now + dt.timedelta(days=3650))
                  .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
                  .add_extension(x509.KeyUsage(digital_signature=True, key_cert_sign=True, crl_sign=True,
                                               content_commitment=False, key_encipherment=False,
                                               data_encipherment=False, key_agreement=False, encipher_only=False,
                                               decipher_only=False), critical=True)
                  .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
                  .sign(ca_key, hashes.SHA256()))
        _write_key(ca_key, ca_key_p)
        ca_crt_p.write_bytes(ca_crt.public_bytes(serialization.Encoding.PEM))

    host = socket.gethostname()
    sans: list[x509.GeneralName] = [x509.IPAddress(ipaddress.ip_address(server_ip)),
                                    x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                                    x509.DNSName("localhost"), x509.DNSName(host)]
    for n in extra_names or []:
        try:
            sans.append(x509.IPAddress(ipaddress.ip_address(n)))
        except ValueError:
            sans.append(x509.DNSName(n))
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    crt = (x509.CertificateBuilder()
           .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, server_ip),
                                    x509.NameAttribute(NameOID.ORGANIZATION_NAME, org)]))
           .issuer_name(ca_crt.subject).public_key(key.public_key()).serial_number(x509.random_serial_number())
           .not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=825))
           .add_extension(x509.SubjectAlternativeName(sans), critical=False)
           .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
           .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
           .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
           .sign(ca_key, hashes.SHA256()))
    key_p, crt_p = cert_dir / "server.key", cert_dir / "server.crt"
    _write_key(key, key_p)
    crt_p.write_bytes(crt.public_bytes(serialization.Encoding.PEM) + ca_crt.public_bytes(serialization.Encoding.PEM))
    # DER copy of the root CA for easy double-click install on Windows clients
    (cert_dir / "OfflineShare-RootCA.cer").write_bytes(ca_crt.public_bytes(serialization.Encoding.DER))
    return {"ca": str(ca_crt_p), "ca_der": str(cert_dir / "OfflineShare-RootCA.cer"), "cert": str(crt_p),
            "key": str(key_p)}
