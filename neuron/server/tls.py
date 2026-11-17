"""Optional HTTPS for the phone page: a certificate made on this computer (no outside service involved).

Phones do not know this certificate, so the first visit shows a warning; the owner checks that the
fingerprint the browser shows matches the one NEURON prints, then continues. After that the traffic
between phone and computer is encrypted, so others on the same Wi-Fi cannot read it."""
import hashlib
import shutil
import ssl
import subprocess
from pathlib import Path

from . import sysinfo


def ensure_cert(home, addresses=None):
    """Create <home>/tls/cert.pem and key.pem once (10 years). Returns (cert, key)."""
    d = Path(home) / "tls"
    cert, key = d / "cert.pem", d / "key.pem"
    if cert.exists() and key.exists():
        return cert, key
    if not shutil.which("openssl"):
        raise RuntimeError("HTTPS needs the openssl program (sudo apt install openssl)")
    d.mkdir(parents=True, exist_ok=True)
    names = ["DNS:localhost", "IP:127.0.0.1"] + [f"IP:{ip}" for ip in (addresses if addresses is not None else sysinfo.lan_addresses())]
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "3650", "-subj", "/CN=NEURON",
                    "-keyout", str(key), "-out", str(cert), "-addext", "subjectAltName=" + ",".join(names)],
                   check=True, capture_output=True)
    key.chmod(0o600)
    return cert, key


def fingerprint(cert):
    der = ssl.PEM_cert_to_DER_cert(Path(cert).read_text())
    h = hashlib.sha256(der).hexdigest().upper()
    return ":".join(h[i:i + 2] for i in range(0, len(h), 2))


def context(cert, key):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(str(cert), str(key))
    return ctx
