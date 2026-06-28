# asamblea.social Infrastructure

Configuración del servidor de asamblea.social

## Servicios
- **Akkoma** - Instancia fediverso en asamblea.social
- **Mumble** - Servidor de voz con autenticación Akkoma
- **mumble-web** - Cliente web en mumble.asamblea.social
- **lighttpd** - Proxy reverso
- **stunnel** - Túnel TLS para Mumble

## Notas
- Las contraseñas están omitidas, usar variables de entorno o /etc/mumble-auth.conf
- Certificados Let's Encrypt en /etc/letsencrypt/
- murmurd 1.5 compilado desde fuente en /usr/sbin/murmurd

## Puertos
- 80/443 - HTTP/HTTPS (lighttpd)
- 2024 - SSH
- 6777 - Mumble TCP/UDP
- 9000 - WebSocket Mumble (legacy, puede eliminarse)
