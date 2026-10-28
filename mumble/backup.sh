#!/bin/bash
set -e
BACKUP_DIR="/home/nombre/bckups"
DATE=$(date +%Y-%m-%d)
KEEP_DAYS=7
cd "$BACKUP_DIR"

sudo cp /etc/mumble-auth.conf "mumble-auth-conf-${DATE}.conf"
sudo cp /etc/mumble-server.ini "mumble-server-ini-${DATE}.ini"
sudo cp /var/lib/mumble-server/mumble-server.sqlite "mumble-server-db-${DATE}.sqlite"
sudo chown nombre:nombre mumble-auth-conf-${DATE}.conf mumble-server-ini-${DATE}.ini mumble-server-db-${DATE}.sqlite

find "$BACKUP_DIR" -name "mumble-*" -mtime +${KEEP_DAYS} -delete

git add -A
git commit -m "backup mumble ${DATE}" --allow-empty
git push origin main

echo "Backup de Mumble completado: ${DATE}"
