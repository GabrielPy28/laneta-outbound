from fastapi import APIRouter

router = APIRouter(tags=["root"])


@router.get("/")
async def root() -> dict:
    """Indica que la API está operativa e informa sobre La Neta."""
    return {
        "status": "ok",
        "message": "La API está levantada correctamente.",
        "company": {
            "name": "La Neta",
            "website": "https://laneta.com",
            "ceo": "Jorge de los Santos",
            "emails": [
                "jorge@laneta.com",
                "daniel@laneta.com",
                "gabriel@parenas.com",
            ],
            "description": "For brands · Global · Digital · Creators",
            "tagline": "La Neta — Leaders of the digital ecosystem",
        },
    }
