from fastapi import APIRouter, HTTPException, status
from supabase import AuthError, AuthInvalidCredentialsError

from app.api.auth.schemas import LoginRequest, LoginResponse, LoginUser
from app.core.jwt_utils import create_access_token
from app.core.supabase_client import get_supabase_client

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_from_auth_and_table(supabase_client, auth_user) -> LoginUser:
    """
    Construye LoginUser: id y email desde Supabase Auth;
    first_name, last_name y avatar_url desde la tabla `users` de Supabase.
    """
    user_id = str(auth_user.id)
    email = auth_user.email or ""

    first_name = ""
    last_name = ""
    avatar_url = ""

    try:
        r = (
            supabase_client.table("users")
            .select("first_name, last_name, avatar_url")
            .eq("auth_user_id", user_id)
            .execute()
        )
        if r.data and len(r.data) > 0:
            row = r.data[0]
            first_name = (row.get("first_name") or "").strip()
            last_name = (row.get("last_name") or "").strip()
            avatar_url = (row.get("avatar_url") or "").strip()
    except Exception:
        pass

    name = f"{first_name} {last_name}".strip() or email

    return LoginUser(
        id=user_id,
        email=email,
        name=name,
        avatar_url=avatar_url,
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    """Verifica email y contraseña contra Supabase Auth; devuelve JWT y datos del usuario."""
    try:
        supabase = get_supabase_client()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        ) from e

    try:
        response = supabase.auth.sign_in_with_password(
            {
                "email": payload.email,
                "password": payload.password,
            }
        )
    except AuthInvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    except AuthError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    user = response.user
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    try:
        login_user = _user_from_auth_and_table(supabase, user)
        access_token = create_access_token(
            sub=str(user.id),
            email=user.email or str(payload.email),
            name=login_user.name,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        ) from e

    return LoginResponse(access_token=access_token, user=login_user)
