"""
Dominios que el job programado de Postmaster consulta en cada corrida.

Mantener esta lista sincronizada con los dominios y subdominios actuales de la empresa, cuando el equipo
registre un dominio nuevo, añadir aquí el nuevo nombre en minúsculas.
"""

POSTMASTER_BEAT_DOMAIN_NAMES: tuple[str, ...] = (
    "app.elevnhub.me",
    "brands.lanetahub.com",
    "brands.lanetapro.com",
    "creators.elevn.me",
    "creators.elevngo.me",
    "creators.elevnhub.me",
    "creators.elevnpro.me",
    "creators.laneta.com",
    "creators.lanetahub.com",
    "elevn.me",
    "elevngo.me",
    "elevnhub.me",
    "elevnpro.me",
    "go.lanetapro.com",
    "hello.elevngo.me",
    "hello.elevnhub.me",
    "hello.elevnpro.me",
    "laneta.com",
    "lanetahub.com",
    "lanetapro.com",
    "we.elevnhub.me",
    "we.elevnpro.me",
)
