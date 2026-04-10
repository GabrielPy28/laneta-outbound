from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class LoginUser(BaseModel):
    id: str
    email: str
    name: str
    avatar_url: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: LoginUser
