"""Private hosted-app sign-in backed by Neon Managed Auth."""

from __future__ import annotations

import os
import time
from functools import lru_cache
from typing import Any

import jwt
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from jwt import PyJWKClient
from starlette.types import ASGIApp, Receive, Scope, Send

router = APIRouter()
COOKIE_NAME = "ii4i484_session"
COOKIE_MAX_AGE = 900


def _auth_base_url() -> str:
    value = os.environ.get("NEON_AUTH_BASE_URL", "").strip().rstrip("/")
    if not value:
        raise RuntimeError("NEON_AUTH_BASE_URL is not configured")
    return value


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    url = os.environ.get("NEON_AUTH_JWKS_URL", "").strip()
    if not url:
        raise RuntimeError("NEON_AUTH_JWKS_URL is not configured")
    return PyJWKClient(url, cache_keys=True)


def verify_neon_token(token: str) -> dict[str, Any]:
    try:
        key = _jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            key.key,
            algorithms=["EdDSA"],
            issuer=_auth_base_url(),
            options={"verify_aud": False},
        )
        if not isinstance(claims.get("exp"), (int, float)) or claims["exp"] <= time.time():
            raise jwt.InvalidTokenError("Expired token")
        return claims
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired sign-in session") from exc


@router.get("/login", include_in_schema=False)
async def login_page() -> HTMLResponse:
    return HTMLResponse(LOGIN_HTML)


@router.post("/auth/session", include_in_schema=False)
async def create_session(request: Request, response: Response):
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.casefold() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Sign in is required")
    claims = verify_neon_token(token.strip())
    max_age = min(COOKIE_MAX_AGE, max(1, int(claims["exp"] - time.time())))
    response.set_cookie(
        COOKIE_NAME,
        token.strip(),
        max_age=max_age,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    return {"authenticated": True}


@router.post("/auth/logout", include_in_schema=False)
async def delete_session(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/", secure=True, httponly=True, samesite="lax")
    return {"authenticated": False}


@router.get("/auth/logout", include_in_schema=False)
async def logout_redirect():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(COOKIE_NAME, path="/", secure=True, httponly=True, samesite="lax")
    return response


class HostedAuthMiddleware:
    """Require a verified Neon session for browser/admin routes.

    The OpenAI-compatible /v1 API keeps its separate proxy bearer-token auth.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "/")
        if (
            path == "/health"
            or path == "/login"
            or path.startswith("/auth/")
            or path == "/favicon.ico"
            or path.startswith("/v1/")
            or path == "/muse-code/models"
        ):
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        cookie_header = headers.get(b"cookie", b"").decode("latin-1")
        token = None
        for item in cookie_header.split(";"):
            name, separator, value = item.strip().partition("=")
            if separator and name == COOKIE_NAME:
                token = value
                break

        if token:
            try:
                verify_neon_token(token)
                scope.setdefault("state", {})["hosted_authenticated"] = True
                await self.app(scope, receive, send)
                return
            except HTTPException:
                pass

        if scope.get("method") in {"GET", "HEAD"}:
            response = RedirectResponse("/login", status_code=303)
        else:
            from starlette.responses import JSONResponse
            response = JSONResponse({"detail": "Sign in required"}, status_code=401)
        await response(scope, receive, send)


LOGIN_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ii4i484 · Sign in</title>
<style>
:root{color-scheme:dark;font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;background:#050505;color:#f4f4f5}
.panel{width:min(420px,calc(100% - 32px));padding:30px;border:1px solid #252525;border-radius:18px;background:#0b0b0b}
h1{font-size:22px;margin:0 0 8px;letter-spacing:-.5px}p{color:#92929b;font-size:14px;line-height:1.5;margin:0 0 24px}
label{display:block;font-size:12px;color:#b7b7c0;margin:16px 0 7px}
input{width:100%;height:46px;border:1px solid #303038;border-radius:9px;background:#111;color:#fff;padding:0 12px;font-size:15px;outline:none}
input:focus{border-color:#777}button{width:100%;height:46px;margin-top:20px;border:0;border-radius:9px;background:#f4f4f5;color:#080808;font-weight:650;font-size:14px}
button.secondary{margin-top:10px;background:#17171b;color:#eee;border:1px solid #303038}
#message{min-height:20px;margin-top:14px;color:#fca5a5;font-size:13px;white-space:pre-wrap}
</style></head><body><main class="panel">
<h1>Sign in to ii4i484</h1><p>Private workspace · Authentication powered by Neon</p>
<form id="form"><label for="email">Email</label><input id="email" type="email" autocomplete="email" required>
<label for="password">Password</label><input id="password" type="password" autocomplete="current-password" minlength="8" required>
<label id="nameLabel" hidden for="name">Name</label><input id="name" hidden autocomplete="name">
<button id="submit" type="submit">Sign in</button><button class="secondary" id="toggle" type="button">Create account</button>
<div id="message" role="status"></div></form></main>
<script type="module">
import { createAuthClient } from "https://esm.sh/@neondatabase/auth";
const auth = createAuthClient("https://ep-aged-frog-b4o7qjuo.neonauth.c-6.us-east-2.aws.neon.tech/neondb/auth");
const form=document.getElementById("form"),message=document.getElementById("message"),submit=document.getElementById("submit"),toggle=document.getElementById("toggle"),nameInput=document.getElementById("name"),nameLabel=document.getElementById("nameLabel");
let signup=false;
toggle.addEventListener("click",()=>{signup=!signup;nameInput.hidden=!signup;nameLabel.hidden=!signup;nameInput.required=signup;submit.textContent=signup?"Create account":"Sign in";toggle.textContent=signup?"Back to sign in":"Create account";message.textContent="";});
form.addEventListener("submit",async event=>{event.preventDefault();submit.disabled=true;message.textContent="Please wait…";
try{
 const email=document.getElementById("email").value.trim(),password=document.getElementById("password").value;
 const result=signup?await auth.signUp.email({email,password,name:nameInput.value.trim()||email.split("@")[0]}):await auth.signIn.email({email,password});
 if(result.error)throw new Error(result.error.message||"Authentication failed");
 const tokenResult=await auth.token();
 if(tokenResult.error||!tokenResult.data?.token)throw new Error(tokenResult.error?.message||"Could not create a secure session");
 const exchange=await fetch("/auth/session",{method:"POST",headers:{Authorization:"Bearer "+tokenResult.data.token}});
 if(!exchange.ok)throw new Error((await exchange.json()).detail||"Could not establish a secure session");
 location.replace("/admin");
}catch(error){message.textContent=error?.message||"Sign-in failed";}finally{submit.disabled=false;}
});
</script></body></html>"""
