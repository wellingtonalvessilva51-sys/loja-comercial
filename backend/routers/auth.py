from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from models.database import Vendedora, get_db
from services.auth import verificar_senha, criar_token, hash_senha
from services import bling as bling_svc

router = APIRouter(prefix="/auth", tags=["auth"])

class LoginRequest(BaseModel):
    email: str
    senha: str

@router.post("/login")
async def login(body: LoginRequest, db: Session = Depends(get_db)):
    vendedora = db.query(Vendedora).filter(
        Vendedora.email == body.email.lower().strip(),
        Vendedora.ativa == True
    ).first()
    if not vendedora or not verificar_senha(body.senha, vendedora.senha_hash):
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")
    token = criar_token(vendedora.id, vendedora.is_gerente)
    return {
        "token": token,
        "nome": vendedora.nome,
        "is_gerente": vendedora.is_gerente,
    }

# ── Bling OAuth ─────────────────────────────────────────
@router.get("/bling")
async def iniciar_bling():
    """Redireciona para a página de autorização do Bling."""
    url = bling_svc.gerar_url_autorizacao()
    return RedirectResponse(url)

@router.get("/
