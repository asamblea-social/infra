#!/opt/mumble-auth/bin/python3
import sys
import Ice
import logging
import hashlib
import threading
import time
import psycopg2
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

MURMUR_ICE_HOST = "127.0.0.1"
MURMUR_ICE_PORT = 6502
AUTH_HOST       = "127.0.0.1"
AUTH_PORT       = 6503
MURMUR_SECRET   = ""
SERVER_ID       = 1
# Credenciales desde archivo protegido
import configparser as _cp
_cfg = _cp.ConfigParser()
_cfg.read_dict({'DEFAULT': {}})
with open('/etc/mumble-auth.conf') as _f:
    _cfg.read_string('[creds]\n' + _f.read())
DB_HOST = _cfg['creds'].get('db_host', 'localhost')
DB_NAME = _cfg['creds'].get('db_name', 'akkoma')
DB_USER = _cfg['creds'].get('db_user', 'akkoma')
DB_PASS = _cfg['creds'].get('db_pass', '')
LOG_FILE        = "/var/log/mumble-auth.log"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

Ice.loadSlice("", ["-I/usr/share/ice/slice", "-I/usr/share/slice", "/usr/share/slice/MumbleServer.ice"])
import MumbleServer as Murmur

# Boletos SSO de voz.asamblea.social (aditivo: si esto falla, todo sigue como antes)
try:
    from ticket_auth import is_ticket, validate_ticket
    SSO_DISPONIBLE = True
except Exception as _e:
    SSO_DISPONIBLE = False
    log.error("Boletos SSO desactivados: no se pudo importar ticket_auth (%s)", _e)


class AkkomaAuthenticator(Murmur.ServerAuthenticator):

    def __init__(self):
        self.ph = PasswordHasher()
        self._usados = {}            # firma del boleto -> hasta cuándo recordarla
        self._lock = threading.Lock()
        self._db_connect()

    def _db_connect(self):
        try:
            self.conn = psycopg2.connect(
                host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASS
            )
            self.conn.autocommit = True
            log.info("Conexion a PostgreSQL establecida.")
        except Exception as e:
            log.error("Error conectando a PostgreSQL: %s", e)
            self.conn = None

    def _ensure_connection(self):
        try:
            if self.conn is None or self.conn.closed:
                self._db_connect()
            else:
                self.conn.cursor().execute("SELECT 1")
        except Exception:
            self._db_connect()

    def _boleto_valido(self, name, pw):
        """True solo si 'pw' es un boleto SSO válido para 'name' y no se ha usado antes.
        Nunca registra el boleto."""
        if not SSO_DISPONIBLE or not is_ticket(pw):
            return False
        try:
            if not validate_ticket(pw, name):
                log.info("Boleto no valido para '%s'", name)
                return False
        except Exception as e:
            log.warning("Error validando boleto para '%s': %s", name, type(e).__name__)
            return False
        firma = pw.rsplit(":", 1)[-1]
        ahora = time.time()
        with self._lock:
            for k in [k for k, v in self._usados.items() if v < ahora]:
                del self._usados[k]
            if firma in self._usados:
                log.info("Boleto ya usado para '%s'", name)
                return False
            self._usados[firma] = ahora + 120
        return True

    def authenticate(self, name, pw, certificates, certhash, certstrong, current=None):
        log.info("Intento de login: '%s'", name)
        if name == "SuperUser":
            return (-1, None, None)
        self._ensure_connection()
        if self.conn is None:
            return (-1, None, None)
        try:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT password_hash FROM users "
                "WHERE nickname = %s AND local = true AND is_active = true AND is_confirmed = true AND is_approved = true "
                "LIMIT 1",
                (name,),
            )
            row = cur.fetchone()
        except Exception as e:
            log.error("Error BD para '%s': %s", name, e)
            return (-1, None, None)
        if row is None or not row[0]:
            return (-1, None, None)
        if self._boleto_valido(name, pw):
            log.info("Login exitoso (boleto): '%s'", name)
            return (int(hashlib.sha256(name.encode("utf-8")).hexdigest(), 16) % 2000000000 + 1000, name, [])
        try:
            self.ph.verify(row[0], pw)
            log.info("Login exitoso: '%s'", name)
            uid = int(hashlib.sha256(name.encode("utf-8")).hexdigest(), 16) % 2000000000 + 1000
            return (uid, name, [])
        except VerifyMismatchError:
            log.info("Contrasena incorrecta para '%s'", name)
            return (-1, None, None)
        except (VerificationError, InvalidHashError) as e:
            log.warning("Error de hash para '%s': %s", name, e)
            return (-1, None, None)

    def getInfo(self, id, current=None):
        return (False, {})

    def nameToId(self, name, current=None):
        return -2

    def idToName(self, id, current=None):
        return ""

    def idToTexture(self, id, current=None):
        return []


def main():
    props = Ice.createProperties(sys.argv)
    props.setProperty("Ice.ImplicitContext", "Shared")
    props.setProperty("Ice.Default.EncodingVersion", "1.0")
    init_data = Ice.InitializationData()
    init_data.properties = props

    with Ice.initialize(init_data) as communicator:
        if MURMUR_SECRET:
            communicator.getImplicitContext().put("secret", MURMUR_SECRET)

        adapter = communicator.createObjectAdapterWithEndpoints(
            "AkkomaAuthAdapter",
            "tcp -h {} -p {}".format(AUTH_HOST, AUTH_PORT),
        )
        auth_obj = AkkomaAuthenticator()
        auth_proxy = adapter.addWithUUID(auth_obj)
        adapter.activate()
        log.info("Adapter activo en %s:%s", AUTH_HOST, AUTH_PORT)
        print("[mumble-auth] Adapter en {}:{}".format(AUTH_HOST, AUTH_PORT))

        try:
            base = communicator.stringToProxy(
                "Meta:tcp -h {} -p {}".format(MURMUR_ICE_HOST, MURMUR_ICE_PORT)
            )
            meta = Murmur.MetaPrx.checkedCast(base)
            if not meta:
                raise RuntimeError("MetaPrx cast fallido")
            server = meta.getServer(SERVER_ID)
            server.setAuthenticator(
                Murmur.ServerAuthenticatorPrx.uncheckedCast(auth_proxy)
            )
            log.info("Authenticator registrado en servidor virtual %d.", SERVER_ID)
            print("[mumble-auth] Registrado en servidor {}. Esperando logins...".format(SERVER_ID))
        except Exception as e:
            log.error("Error registrando authenticator: %s", e)
            print("ERROR: {}".format(e), file=sys.stderr)
            sys.exit(1)

        communicator.waitForShutdown()


if __name__ == "__main__":
    main()
