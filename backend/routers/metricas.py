from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from models.database import Vendedora, Meta, get_db
from services.auth import get_vendedora_atual, exigir_gerente, hash_senha
from services import metricas as metricas_svc
from services import bling as bling_svc

router = APIRouter(tags=["metricas"])


def periodo_atual():
    hoje = datetime.now()
    return hoje.month, hoje.year


# ── GERENTE ──────────────────────────────────────────────

@router.get("/gerente/dashboard")
async def dashboard_gerente(
    mes: Optional[int] = None,
    ano: Optional[int] = None,
    db: Session = Depends(get_db),
    gerente: Vendedora = Depends(exigir_gerente),
):
    m, a = periodo_atual()
    return metricas_svc.get_metricas_gerente(db, mes or m, ano or a)


@router.post("/gerente/sincronizar")
async def sincronizar(
    dias: int = 30,
    db: Session = Depends(get_db),
    gerente: Vendedora = Depends(exigir_gerente),
):
    resultado = await bling_svc.sincronizar_pedidos(db, dias)
    return {"mensagem": "Sincronização concluída.", **resultado}


@router.get("/gerente/vendedoras")
async def listar_vendedoras(
    db: Session = Depends(get_db),
    gerente: Vendedora = Depends(exigir_gerente),
):
    vendedoras = db.query(Vendedora).filter(Vendedora.is_gerente == False).all()
    return [
        {
            "id": v.id,
            "nome": v.nome,
            "email": v.email,
            "bling_vendedor_nome": v.bling_vendedor_nome,
            "meta_mensal": v.meta_mensal,
            "percentual_comissao": v.percentual_comissao,
            "ativa": v.ativa,
        }
        for v in vendedoras
    ]


class NovaVendedoraRequest(BaseModel):
    nome: str
    email: str
    senha: str
    bling_vendedor_nome: str
    meta_mensal: float = 12000.0
    percentual_comissao: float = 5.0


@router.post("/gerente/vendedoras")
async def criar_vendedora(
    body: NovaVendedoraRequest,
    db: Session = Depends(get_db),
    gerente: Vendedora = Depends(exigir_gerente),
):
    existente = db.query(Vendedora).filter(Vendedora.email == body.email.lower()).first()
    if existente:
        raise HTTPException(400, "E-mail já cadastrado.")

    nova = Vendedora(
        nome=body.nome,
        email=body.email.lower().strip(),
        senha_hash=hash_senha(body.senha),
        bling_vendedor_nome=body.bling_vendedor_nome,
        meta_mensal=body.meta_mensal,
        percentual_comissao=body.percentual_comissao,
        is_gerente=False,
    )
    db.add(nova)
    db.commit()
    db.refresh(nova)
    return {"mensagem": "Vendedora criada.", "id": nova.id}


class AtualizarMetaRequest(BaseModel):
    vendedora_id: int
    mes: int
    ano: int
    valor_meta: float


@router.put("/gerente/meta")
async def atualizar_meta(
    body: AtualizarMetaRequest,
    db: Session = Depends(get_db),
    gerente: Vendedora = Depends(exigir_gerente),
):
    meta = db.query(Meta).filter(
        Meta.vendedora_id == body.vendedora_id,
        Meta.mes == body.mes,
        Meta.ano == body.ano,
    ).first()

    if meta:
        meta.valor_meta = body.valor_meta
    else:
        meta = Meta(
            vendedora_id=body.vendedora_id,
            mes=body.mes,
            ano=body.ano,
            valor_meta=body.valor_meta,
        )
        db.add(meta)
    db.commit()
    return {"mensagem": "Meta atualizada."}


# ── VENDEDORA ─────────────────────────────────────────────

@router.get("/vendedora/dashboard")
async def dashboard_vendedora(
    mes: Optional[int] = None,
    ano: Optional[int] = None,
    db: Session = Depends(get_db),
    vendedora: Vendedora = Depends(get_vendedora_atual),
):
    if vendedora.is_gerente:
        raise HTTPException(403, "Use o endpoint de gerente.")
    m, a = periodo_atual()
    return metricas_svc.get_metricas_vendedora(db, vendedora, mes or m, ano or a)


@router.get("/vendedora/perfil")
async def perfil(vendedora: Vendedora = Depends(get_vendedora_atual)):
    return {
        "nome": vendedora.nome,
        "email": vendedora.email,
        "meta_mensal": vendedora.meta_mensal,
        "percentual_comissao": vendedora.percentual_comissao,
    }
