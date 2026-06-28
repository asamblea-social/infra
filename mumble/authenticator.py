#!/opt/mumble-auth/bin/python3
import sys
import Ice
import logging
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


class AkkomaAuthenticator(Murmur.ServerAuthenticator):

    def __init__(self):
        self.ph = PasswordHasher()
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
                "WHERE nickname = %s AND local = true AND is_active = true "
                "LIMIT 1",
                (name,),
            )
            row = cur.fetchone()
        except Exception as e:
            log.error("Error BD para '%s': %s", name, e)
            return (-1, None, None)
        if row is None or not row[0]:
            return (-2, None, None)
        try:
            self.ph.verify(row[0], pw)
            log.info("Login exitoso: '%s'", name)
            uid = abs(hash(name)) % 100000 + 1000
            return (uid, name, [])
        except VerifyMismatchError:
            log.info("Contrasena incorrecta para '%s'", name)
            return (-2, None, None)
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
