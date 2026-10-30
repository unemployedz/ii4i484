"""Password-only private sign-in for the single-owner hosted workspace."""

from __future__ import annotations

import hashlib
import hmac
import os
import time

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.types import ASGIApp, Receive, Scope, Send

router = APIRouter()
COOKIE_NAME = "ii4i484_session"
SESSION_TTL = 60 * 60 * 24 * 7


def _secret(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"{name} is not configured")
    return value


def _signature(timestamp: str) -> str:
    return hmac.new(
        _secret("APP_SESSION_SECRET").encode(),
        f"ii4i484:{timestamp}".encode(),
        hashlib.sha256,
    ).hexdigest()


def _valid_session(value: str) -> bool:
    try:
        timestamp, signature = value.split(".", 1)
        issued = int(timestamp)
        if issued > int(time.time()) + 60 or int(time.time()) - issued > SESSION_TTL:
            return False
        return hmac.compare_digest(signature, _signature(timestamp))
    except (ValueError, RuntimeError):
        return False


@router.get("/login", include_in_schema=False)
async def login_page() -> HTMLResponse:
    return HTMLResponse(LOGIN_HTML)


@router.post("/auth/session", include_in_schema=False)
async def create_session(request: Request, response: Response):
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Enter the password") from exc
    supplied = body.get("password", "") if isinstance(body, dict) else ""
    expected = _secret("APP_ACCESS_PASSWORD")
    if not isinstance(supplied, str) or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Nope. Try again.")
    timestamp = str(int(time.time()))
    response.set_cookie(
        COOKIE_NAME,
        f"{timestamp}.{_signature(timestamp)}",
        max_age=SESSION_TTL,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )
    return {"authenticated": True}


@router.post("/auth/logout", include_in_schema=False)
async def delete_session(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/", secure=True, httponly=True, samesite="strict")
    return {"authenticated": False}


@router.get("/auth/logout", include_in_schema=False)
async def logout_redirect():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(COOKIE_NAME, path="/", secure=True, httponly=True, samesite="strict")
    return response


class HostedAuthMiddleware:
    """Require a signed password session for all hosted browser/admin routes."""

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
            or path in {"/auth/session", "/auth/logout"}
            or path.startswith("/v1/")
        ):
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        cookie_header = headers.get(b"cookie", b"").decode("latin-1")
        session = None
        for item in cookie_header.split(";"):
            name, separator, value = item.strip().partition("=")
            if separator and name == COOKIE_NAME:
                session = value
                break

        if session and _valid_session(session):
            scope.setdefault("state", {})["hosted_authenticated"] = True
            await self.app(scope, receive, send)
            return

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
.panel{width:min(390px,calc(100% - 32px));padding:30px;border:1px solid #252525;border-radius:18px;background:#0b0b0b}
h1{font-size:22px;margin:0 0 8px;letter-spacing:-.5px}p{color:#92929b;font-size:14px;line-height:1.5;margin:0 0 24px}
label{display:block;font-size:12px;color:#b7b7c0;margin:16px 0 7px}
input{width:100%;height:48px;border:1px solid #303038;border-radius:9px;background:#111;color:#fff;padding:0 12px;font-size:15px;outline:none}
input:focus{border-color:#777}button{width:100%;height:46px;margin-top:20px;border:0;border-radius:9px;background:#f4f4f5;color:#080808;font-weight:650;font-size:14px}
#message{min-height:20px;margin-top:14px;color:#fca5a5;font-size:13px}
</style></head><body><main class="panel">
<h1>Funny business.</h1><p>Private workspace. One password. No email, no account.</p>
<form id="form"><label for="password">Password</label><input id="password" type="password" placeholder="Enter the secret word" autocomplete="current-password" required autofocus>
<button id="submit" type="submit">Unlock workspace</button><div id="message" role="status"></div></form>
</main><script>
const form=document.getElementById("form"),input=document.getElementById("password"),message=document.getElementById("message"),button=document.getElementById("submit");
form.addEventListener("submit",async event=>{event.preventDefault();button.disabled=true;message.textContent="Checking…";
try{const response=await fetch("/auth/session",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({password:input.value})});const data=await response.json();if(!response.ok)throw new Error(data.detail||"Access denied");location.replace("/admin");}
catch(error){message.textContent=error.message||"Try again";input.select();}finally{button.disabled=false;}});
</script></body></html>"""
