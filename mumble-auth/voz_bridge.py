"""
Puente OAuth (v2): traduce una sesión de Akkoma en un boleto temporal que
mumble-auth valida, para que voz.asamblea.social permita entrar sin volver a
escribir usuario y contraseña.

Rutas (lighttpd manda /auth-bridge/ aquí):
  /auth-bridge/login     -> crea 'state' (cookie firmada) y redirige a Akkoma
  /auth-bridge/callback  -> comprueba 'state', canjea el code, pregunta quién es,
                            REVOCA el token, genera el boleto y redirige a
                            voz.asamblea.social/#u=<usuario>&t=<boleto>
Nunca registra codes, tokens ni boletos.
"""
import configparser
import hashlib
import hmac
import logging
import secrets
import sys
from urllib.parse import urlencode

import requests
from flask import Flask, redirect, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

sys.path.insert(0, "/opt/mumble-auth")
from ticket_auth import generate_ticket  # noqa: E402

CONF_PATH = "/etc/voz-bridge.conf"
LOG_FILE = "/var/log/voz-bridge.log"
STATE_COOKIE = "voz_state"
STATE_MAX_AGE = 600   # segundos para completar el paso por Akkoma
HTTP_TIMEOUT = 10

logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("voz_bridge")
logging.getLogger("werkzeug").setLevel(logging.WARNING)

app = Flask(__name__)


def load_config():
    cfg = configparser.ConfigParser()
    with open(CONF_PATH) as f:
        cfg.read_string("[creds]\n" + f.read())
    return cfg["creds"]


def _serializer(cfg):
    # Clave derivada del SHARED_SECRET: si se rota, también cambia esta.
    clave = hmac.new(cfg["shared_secret"].encode(), b"voz-bridge/state-cookie",
                     hashlib.sha256).hexdigest()
    return URLSafeTimedSerializer(clave, salt="voz-state")


def _sin_cache(resp):
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


@app.route("/auth-bridge/login")
def login():
    cfg = load_config()
    state = secrets.token_urlsafe(32)
    url = cfg["akkoma_base_url"] + "/oauth/authorize?" + urlencode({
        "client_id": cfg["oauth_client_id"],
        "redirect_uri": cfg["oauth_redirect_uri"],
        "response_type": "code",
        "scope": "read",
        "state": state,
    })
    resp = _sin_cache(redirect(url))
    resp.set_cookie(STATE_COOKIE, _serializer(cfg).dumps(state), max_age=STATE_MAX_AGE,
                    secure=True, httponly=True, samesite="Lax", path="/auth-bridge/")
    log.info("login: redirigiendo a Akkoma.")
    return resp


@app.route("/auth-bridge/callback")
def callback():
    cfg = load_config()

    def fin(**fragmento):
        resp = _sin_cache(redirect(cfg["voz_base_url"] + "/#" + urlencode(fragmento)))
        resp.delete_cookie(STATE_COOKIE, path="/auth-bridge/", secure=True,
                           httponly=True, samesite="Lax")
        return resp

    # 1. state: debe coincidir con el de la cookie firmada (protección CSRF)
    try:
        esperado = _serializer(cfg).loads(request.cookies.get(STATE_COOKIE, ""),
                                          max_age=STATE_MAX_AGE)
    except SignatureExpired:
        log.warning("callback: cookie de state caducada.")
        return fin(error="caducado")
    except BadSignature:
        log.warning("callback: cookie de state ausente o inválida.")
        return fin(error="state")
    if not hmac.compare_digest(request.args.get("state", ""), esperado):
        log.warning("callback: el state no coincide.")
        return fin(error="state")

    if request.args.get("error"):
        log.info("callback: Akkoma devolvió error (p. ej. la persona canceló).")
        return fin(error="cancelado")

    code = request.args.get("code")
    if not code:
        log.warning("callback: sin code.")
        return fin(error="sin_code")

    # 2. canjear el code por un token
    try:
        r = requests.post(cfg["akkoma_base_url"] + "/oauth/token", data={
            "grant_type": "authorization_code", "code": code,
            "client_id": cfg["oauth_client_id"],
            "client_secret": cfg["oauth_client_secret"],
            "redirect_uri": cfg["oauth_redirect_uri"],
        }, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        token = r.json()["access_token"]
    except Exception as e:
        log.error("callback: fallo al canjear el code (%s).", type(e).__name__)
        return fin(error="token")

    # 3. quién es; 4. revocar el token SIEMPRE (finally)
    try:
        try:
            w = requests.get(cfg["akkoma_base_url"] + "/api/v1/accounts/verify_credentials",
                             headers={"Authorization": "Bearer " + token},
                             timeout=HTTP_TIMEOUT)
            w.raise_for_status()
            datos = w.json()
            usuario = datos["username"]
            if "@" in datos.get("acct", usuario):
                raise ValueError("cuenta no local")
        finally:
            try:
                requests.post(cfg["akkoma_base_url"] + "/oauth/revoke", data={
                    "token": token,
                    "client_id": cfg["oauth_client_id"],
                    "client_secret": cfg["oauth_client_secret"],
                }, timeout=HTTP_TIMEOUT).raise_for_status()
            except Exception as e:
                log.warning("callback: no se pudo revocar el token (%s).", type(e).__name__)
    except Exception as e:
        log.error("callback: fallo al verificar la cuenta (%s).", type(e).__name__)
        return fin(error="cuenta")

    # 5. boleto (firmado, 60 s) y vuelta a voz con el boleto en el FRAGMENTO
    boleto = generate_ticket(usuario, secret=cfg["shared_secret"])
    log.info("callback: boleto generado para '%s'.", usuario)
    return fin(u=usuario, t=boleto)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8091)
