#!/usr/bin/env python3
"""
Generación one-time de token.json para Calendar API + Gmail Postmaster Tools.

Uso (desde la carpeta `backend/`, con el venv activado):

    python scripts/generate_google_token.py

Por defecto lee `./credentials.json` y escribe `./token.json`.
Requiere un cliente OAuth en Google Cloud con tipo recomendado **Desktop**;
si usas cliente **Web**, añade en la consola un redirect URI local, p. ej.
`http://localhost` o el que use `run_local_server`.

Antes: en Google Cloud habilita **Gmail Postmaster Tools API** para el proyecto.

Los scopes son `GOOGLE_OAUTH_SCOPES` en
`app.integrations.google_postmaster.client` (Calendar + `postmaster.readonly` +
`postmaster.traffic.readonly`).
Tras autorizar en el navegador, puedes copiar `refresh_token` del JSON a
`GOOGLE_OAUTH_REFRESH_TOKEN` si despliegas sin montar token.json.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> int:
    root = _backend_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from google_auth_oauthlib.flow import InstalledAppFlow

    from app.integrations.google_postmaster.client import GOOGLE_OAUTH_SCOPES

    parser = argparse.ArgumentParser(description="OAuth interactivo: credentials.json → token.json")
    parser.add_argument(
        "--credentials",
        type=Path,
        default=Path.cwd() / "credentials.json",
        help="Ruta al JSON de cliente OAuth (default: ./credentials.json respecto al cwd)",
    )
    parser.add_argument(
        "--token-out",
        type=Path,
        default=Path.cwd() / "token.json",
        help="Ruta donde guardar token.json (default: ./token.json respecto al cwd)",
    )
    args = parser.parse_args()

    cred_path: Path = args.credentials
    if not cred_path.is_file():
        print(f"No existe el archivo de credenciales: {cred_path.resolve()}", file=sys.stderr)
        return 1

    flow = InstalledAppFlow.from_client_secrets_file(
        str(cred_path),
        list(GOOGLE_OAUTH_SCOPES),
    )
    print("Abriendo el navegador para autorizar (Calendar + Postmaster)...")
    creds = flow.run_local_server(port=0, prompt="consent")

    out: Path = args.token_out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(creds.to_json(), encoding="utf-8")
    print(f"Guardado: {out.resolve()}")
    if creds.refresh_token:
        print("refresh_token presente. Opcional: copialo a GOOGLE_OAUTH_REFRESH_TOKEN en .env")
    else:
        print(
            "Advertencia: no hay refresh_token en la respuesta. "
            "Prueba revocar el acceso de la app en tu cuenta Google o usa prompt=consent.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
