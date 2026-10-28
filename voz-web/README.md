# voz.asamblea.social — cliente web (mumble-web modificado)

- Base: https://github.com/johni0702/mumble-web, commit 4ef594c8a097d180700d22d91e9a7fea3bab08ac
- Modificaciones: voz-build.patch (git diff --binary HEAD de /opt/voz-build, generado el 2026-10-28_0247).
- config.local.js: configuración del cliente. No contiene secretos (se entrega al navegador).
  Toda la lógica nueva depende de config.voz en ese archivo.

## Reconstrucción

    git clone https://github.com/johni0702/mumble-web voz-build
    cd voz-build
    git checkout 4ef594c8a097d180700d22d91e9a7fea3bab08ac
    git apply ../voz-web/voz-build.patch
    cp ../voz-web/config.local.js .
    npm ci
    NODE_OPTIONS=--openssl-legacy-provider npm run build    # unos 50 segundos
    # publicar dist/ en /opt/voz-asamblea/dist

Probado con node v18.20.4 y npm 9.2.0.

## Piezas relacionadas

- Puente OAuth y boletos: ../mumble-auth/voz_bridge.py, ../mumble-auth/ticket_auth.py
- Autenticador de murmur con boletos: ../mumble-auth/authenticator.py
- Unidad: ../systemd/voz-bridge.service (gunicorn, 127.0.0.1:8091)
- Sitio en lighttpd: ../lighttpd/conf-available/41-voz-asamblea.conf
- Los secretos viven en /etc/voz-bridge.conf, que NO está en este repo
  (se respalda cifrado por acceso en el repo privado bckups).
