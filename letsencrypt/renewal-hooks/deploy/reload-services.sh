#!/bin/bash
# Reaplica los permisos ACL necesarios tras cada renovación de certificado,
# porque Certbot crea un archivo nuevo (privkeyN.pem) sin las ACL del anterior.
# Referencia: asamblea-social/infra — arreglo de agosto 2026.
set -e

for domain_dir in /etc/letsencrypt/live/*/; do
  domain=$(basename "$domain_dir")
  privkey="$domain_dir/privkey.pem"
  [ -e "$privkey" ] || continue
  real=$(readlink -f "$privkey")

  setfacl -m u:mumble-server:r-- "$real" 2>/dev/null || true
  setfacl -m u:www-data:r--      "$real" 2>/dev/null || true
done

# Los directorios intermedios también necesitan paso para ambos usuarios.
setfacl -m u:mumble-server:r-x /etc/letsencrypt/live/ /etc/letsencrypt/archive/
setfacl -m u:www-data:r-x      /etc/letsencrypt/live/ /etc/letsencrypt/archive/

systemctl reload lighttpd
systemctl restart mumble-stunnel
systemctl restart mumble-server
systemctl restart mumble-auth
