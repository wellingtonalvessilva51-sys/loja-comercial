from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from models.database import Vendedora, get_db
from services.auth import verificar_senha, criar_token
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
    return {"token": token, "nome": vendedora.nome, "is_gerente": vendedora.is_gerente}

@router.get("/bling")
async def iniciar_bling():
    url = bling_svc.gerar_url_autorizacao()
    return RedirectResponse(url)

@router.get("/bling/callback")
async def callback_bling(code: str = None, state: str = None, error: str = None, db: Session = Depends(get_db)):
    if error:
        raise HTTPException(400, f"Erro na autorização do Bling: {error}")
    if not code:
        raise HTTPException(400, "Código de autorização não recebido.")
    ok = await bling_svc.trocar_codigo_por_token(code, db)
    if not ok:
        raise HTTPException(500, "Erro ao conectar com o Bling. Tente novamente.")
    return {"mensagem": "Bling conectado com sucesso! Pode fechar esta janela."}
