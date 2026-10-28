#!/bin/bash
# akkoma-backup.sh — respaldo nocturno de asamblea.social al repo PRIVADO bckups
# Versión r6b (2026-10-28): pipefail, secretos de servicios, Etherpad antes del push,
# sin modificar /root/.gitconfig en cada ejecución.
set -euo pipefail

BACKUP_DIR="/home/nombre/bckups"
DATE=$(date +%Y-%m-%d)
KEEP_DAYS=7
SECRETOS=(/etc/voz-bridge.conf /etc/meilisearch.env
          /srv/etherpad-lite/settings.json /srv/etherpad-lite/APIKEY.txt /srv/etherpad-lite/SESSIONKEY.txt
          /root/.my.cnf /root/.pgpass)

cd "$BACKUP_DIR"

# 1. PostgreSQL (Akkoma)
pg_dump -U akkoma -h localhost akkoma | gzip > "akkoma-db-${DATE}.sql.gz"

# 2. MariaDB (Etherpad)
mysqldump --single-transaction -u ether pad | gzip > "etherpad-db-${DATE}.sql.gz"

# 3. Configuración de Akkoma (/etc/akkoma: config.exs, akkoma.env)
tar -czf "akkoma-etc-${DATE}.tar.gz" -C / etc/akkoma

# 4. Secretos de otros servicios (voz, Meilisearch, Etherpad, clientes de BD)
EXISTEN=()
for f in "${SECRETOS[@]}"; do [ -f "$f" ] && EXISTEN+=("${f#/}"); done
tar -czf "servicios-etc-${DATE}.tar.gz" -C / "${EXISTEN[@]}"

# 5. Uploads y static de Akkoma
tar -czf "akkoma-uploads-${DATE}.tar.gz" -C / var/lib/akkoma/uploads var/lib/akkoma/static

chown nombre:nombre "akkoma-db-${DATE}.sql.gz" "etherpad-db-${DATE}.sql.gz" "akkoma-etc-${DATE}.tar.gz" \
                    "servicios-etc-${DATE}.tar.gz" "akkoma-uploads-${DATE}.tar.gz"
chmod 600 "akkoma-etc-${DATE}.tar.gz" "servicios-etc-${DATE}.tar.gz"

# 6. Rotación: conservar KEEP_DAYS días
find "$BACKUP_DIR" -maxdepth 1 -name "*.gz" -mtime +${KEEP_DAYS} -delete

# 7. Git (repo privado)
git -C "$BACKUP_DIR" add -A
git -C "$BACKUP_DIR" commit -q -m "backup ${DATE}" --allow-empty
git -C "$BACKUP_DIR" push -q origin main

echo "Backup completado: ${DATE} $(date -u +%T) UTC"
