#!/bin/bash
echo "=== Estado de servicios ===" && \
sudo systemctl status akkoma lighttpd mumble-server mumble-auth mumble-stunnel --no-pager | grep -E "Active|Loaded" && \
echo "" && \
echo "=== Usuarios registrados en Akkoma ===" && \
sudo -u akkoma psql -d akkoma -t -A -c "SELECT count(*) FROM users WHERE local = true AND is_active = true;" 2>/dev/null && \
echo "" && \
echo "=== Espacio en disco y memoria ===" && \
df -h / && free -h && \
echo "" && \
echo "=== Carga del sistema ===" && \
uptime && \
echo "" && \
echo "=== Últimos errores Akkoma ===" && \
sudo tail -5 /var/lib/akkoma/tmp/log/erlang.log.1 && \
echo "" && \
echo "=== Conectividad SMTP ===" && \
curl -s -o /dev/null -w "smtp.protonmail.ch:587 → %{http_code}\n" --connect-timeout 5 smtp.protonmail.ch:587 && \
echo "=== Listo ==="
