from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from models.database import Vendedora, get_db
import os

SECRET_KEY = os.getenv("SECRET_KEY", "chave-insegura-troque-em-producao")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 12

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


def hash_senha(senha: str) -> str:
    return pwd_context.hash(senha)


def verificar_senha(senha: str, hash: str) -> bool:
    return pwd_context.verify(senha, hash)


def criar_token(vendedora_id: int, is_gerente: bool) -> str:
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": str(vendedora_id),
        "is_gerente": is_gerente,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_vendedora_atual(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Vendedora:
    erro = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não autenticado. Faça login novamente.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not credentials:
        raise erro
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        vendedora_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        raise erro

    vendedora = db.query(Vendedora).filter(Vendedora.id == vendedora_id, Vendedora.ativa == True).first()
    if not vendedora:
        raise erro
    return vendedora


def exigir_gerente(vendedora: Vendedora = Depends(get_vendedora_atual)) -> Vendedora:
    if not vendedora.is_gerente:
        raise HTTPException(status_code=403, detail="Acesso restrito à gerente.")
    return vendedora
