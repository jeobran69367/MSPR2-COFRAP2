import os

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="COFRAP — Portail d'authentification")
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

OPENFAAS_URL = os.environ.get("OPENFAAS_URL", "http://localhost:31112")


async def call_function(name: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{OPENFAAS_URL}/function/{name}", json=payload)
        return r.json()


# ── Routes ────────────────────────────────────────────────────
# Note : Starlette 1.x a changé la signature de TemplateResponse.
# Nouvelle forme : TemplateResponse(request, "template.html", {contexte})
# (l'ancienne forme TemplateResponse("template.html", {"request": ...})
# a été retirée, cf. migration lors de la mise à jour de sécurité de
# fastapi/starlette — voir CVE-2024-47874, CVE-2026-48818, CVE-2026-54283).

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {})


@app.get("/create", response_class=HTMLResponse)
async def create_get(request: Request):
    return templates.TemplateResponse(request, "create.html", {})


@app.post("/create", response_class=HTMLResponse)
async def create_post(request: Request, username: str = Form(...)):
    pwd_resp = await call_function("generate-password", {"username": username})
    if pwd_resp.get("statusCode", 200) not in (200, None) or "error" in pwd_resp:
        return templates.TemplateResponse(request, "create.html", {
            "error": pwd_resp.get("error", "Erreur generate-password")
        })
    mfa_resp = await call_function("generate-2fa", {"username": username})
    if "error" in mfa_resp:
        return templates.TemplateResponse(request, "create.html", {
            "error": mfa_resp.get("error", "Erreur generate-2fa")
        })
    return templates.TemplateResponse(request, "qrcodes.html", {
        "username": username,
        "qr_password": pwd_resp.get("qr_code"),
        "qr_2fa": mfa_resp.get("qr_code"),
    })


@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    return templates.TemplateResponse(request, "login.html", {})


@app.post("/login", response_class=HTMLResponse)
async def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    totp_code: str = Form(...),
):
    resp = await call_function("authenticate", {
        "username": username, "password": password, "totp_code": totp_code
    })
    if resp.get("expired"):
        return RedirectResponse(url=f"/renew?username={username}", status_code=303)
    if resp.get("authenticated"):
        return templates.TemplateResponse(request, "success.html", {"username": username})
    return templates.TemplateResponse(request, "login.html", {
        "error": resp.get("error", "Authentification échouée.")
    })


@app.get("/renew", response_class=HTMLResponse)
async def renew_get(request: Request, username: str = ""):
    return templates.TemplateResponse(request, "renew.html", {"username": username})


@app.post("/renew", response_class=HTMLResponse)
async def renew_post(request: Request, username: str = Form(...)):
    pwd_resp = await call_function("generate-password", {"username": username})
    if "error" in pwd_resp:
        return templates.TemplateResponse(request, "renew.html", {
            "username": username,
            "error": pwd_resp.get("error", "Erreur renouvellement mot de passe")
        })
    mfa_resp = await call_function("generate-2fa", {"username": username})
    if "error" in mfa_resp:
        return templates.TemplateResponse(request, "renew.html", {
            "username": username,
            "error": mfa_resp.get("error", "Erreur renouvellement 2FA")
        })
    return templates.TemplateResponse(request, "qrcodes.html", {
        "username": username,
        "qr_password": pwd_resp.get("qr_code"),
        "qr_2fa": mfa_resp.get("qr_code"),
        "renewed": True,
    })
