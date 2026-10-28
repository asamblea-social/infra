"""
Validación de boletos temporales de un solo uso para el login SSO
de voz.asamblea.social (Akkoma -> Mumble vía OAuth).

Formato del boleto: "SSO:<usuario>:<timestamp_unix>:<firma_hex>"
firma = HMAC-SHA256(SHARED_SECRET, "<usuario>:<timestamp_unix>")

Este módulo NO tiene estado ni hace red: es puro cálculo/verificación,
para poder usarse igual desde el puente Flask (para generar) y desde
authenticator.py (para validar), sin duplicar la lógica de firma.
"""
import hmac
import hashlib
import time
import configparser

TICKET_PREFIX = "SSO:"


def _load_shared_secret(conf_path="/etc/voz-bridge.conf"):
    cfg = configparser.ConfigParser()
    with open(conf_path) as f:
        cfg.read_string("[creds]\n" + f.read())
    return cfg["creds"].get("shared_secret", "")


def _load_validity_seconds(conf_path="/etc/voz-bridge.conf"):
    cfg = configparser.ConfigParser()
    with open(conf_path) as f:
        cfg.read_string("[creds]\n" + f.read())
    return int(cfg["creds"].get("ticket_validity_seconds", "60"))


def is_ticket(value):
    """True si 'value' tiene la forma de un boleto SSO (no una contraseña real)."""
    return isinstance(value, str) and value.startswith(TICKET_PREFIX)


def generate_ticket(username, secret=None):
    """Genera un boleto firmado para 'username', válido a partir de ahora."""
    if secret is None:
        secret = _load_shared_secret()
    timestamp = str(int(time.time()))
    payload = "{}:{}".format(username, timestamp)
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return "{}{}:{}:{}".format(TICKET_PREFIX, username, timestamp, signature)


def validate_ticket(ticket, expected_username, secret=None, validity_seconds=None):
    """
    Verifica que 'ticket' sea válido para 'expected_username':
    firma correcta, no expirado, y el usuario coincide.
    Devuelve True/False. Nunca lanza excepción por un boleto malformado.
    """
    if secret is None:
        secret = _load_shared_secret()
    if validity_seconds is None:
        validity_seconds = _load_validity_seconds()

    if not is_ticket(ticket):
        return False
    try:
        body = ticket[len(TICKET_PREFIX):]
        username, timestamp_str, signature = body.rsplit(":", 2)
    except ValueError:
        return False

    if username != expected_username:
        return False

    payload = "{}:{}".format(username, timestamp_str)
    expected_signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return False

    try:
        ticket_age = time.time() - int(timestamp_str)
    except ValueError:
        return False

    return 0 <= ticket_age <= validity_seconds
