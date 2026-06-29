#!/bin/bash
set -e

BACKUP_DIR="/home/nombre/bckups"
DATE=$(date +%Y-%m-%d)
KEEP_DAYS=7

cd "$BACKUP_DIR"

# 1. Backup PostgreSQL
pg_dump -U akkoma -h localhost akkoma | gzip > "akkoma-db-${DATE}.sql.gz"

# 2. Backup uploads y static
tar -czf "akkoma-uploads-${DATE}.tar.gz" /var/lib/akkoma/uploads /var/lib/akkoma/static

# 3. Eliminar backups de más de 7 días
find "$BACKUP_DIR" -name "*.gz" -mtime +${KEEP_DAYS} -delete

# 4. Git push
git add -A
git commit -m "backup ${DATE}" --allow-empty
git push origin main

echo "Backup completado: ${DATE}"

# 5. Backup MariaDB (Etherpad)
mysqldump --single-transaction -u ether pad | gzip > "${BACKUP_DIR}/etherpad-db-${DATE}.sql.gz"
