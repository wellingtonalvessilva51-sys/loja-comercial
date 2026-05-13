"""
Serviço de integração com o Bling API v3.
Documentação: https://developer.bling.com.br/
"""
import httpx
import os
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models.database import Venda, TokenBling
import logging

logger = logging.getLogger(__name__)

BLING_BASE_URL = "https://api.bling.com.br/Api/v3"
BLING_AUTH_URL = "https://www.bling.com.br/Api/v3/oauth/token"


# ─────────────────────────────────────────
# AUTENTICAÇÃO OAuth2
# ─────────────────────────────────────────

def gerar_url_autorizacao() -> str:
    client_id = os.getenv("BLING_CLIENT_ID")
    redirect_uri = os.getenv("BLING_REDIRECT_URI")
    return (
        f"https://www.bling.com.br/Api/v3/oauth/authorize"
        f"?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}"
    )


async def trocar_codigo_por_token(code: str, db: Session) -> bool:
    """Troca o código de autorização pelo access_token + refresh_token."""
    import base64
    client_id = os.getenv("BLING_CLIENT_ID")
    client_secret = os.getenv("BLING_CLIENT_SECRET")
    redirect_uri = os.getenv("BLING_REDIRECT_URI")

    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            BLING_AUTH_URL,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )

    if resp.status_code != 200:
        logger.error(f"Erro ao trocar código: {resp.text}")
        return False

    data = resp.json()
    _salvar_token(data, db)
    return True


async def renovar_token(db: Session) -> bool:
    """Renova o access_token usando o refresh_token."""
    import base64
    token_db = db.query(TokenBling).first()
    if not token_db:
        return False

    client_id = os.getenv("BLING_CLIENT_ID")
    client_secret = os.getenv("BLING_CLIENT_SECRET")
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            BLING_AUTH_URL,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": token_db.refresh_token,
            },
        )

    if resp.status_code != 200:
        logger.error(f"Erro ao renovar token: {resp.text}")
        return False

    _salvar_token(resp.json(), db)
    return True


def _salvar_token(data: dict, db: Session):
    expires_at = datetime.utcnow() + timedelta(seconds=data.get("expires_in", 21600))
    token_db = db.query(TokenBling).first()
    if token_db:
        token_db.access_token = data["access_token"]
        token_db.refresh_token = data["refresh_token"]
        token_db.expires_at = expires_at
        token_db.atualizado_em = datetime.utcnow()
    else:
        token_db = TokenBling(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=expires_at,
        )
        db.add(token_db)
    db.commit()


async def _get_headers(db: Session) -> dict:
    """Retorna headers com token válido, renovando se necessário."""
    token_db = db.query(TokenBling).first()
    if not token_db:
        raise Exception("Bling não autenticado. Acesse /auth/bling para conectar.")

    # Renova se expira em menos de 5 min
    if token_db.expires_at < datetime.utcnow() + timedelta(minutes=5):
        await renovar_token(db)
        token_db = db.query(TokenBling).first()

    return {
        "Authorization": f"Bearer {token_db.access_token}",
        "Accept": "application/json",
    }


# ─────────────────────────────────────────
# SINCRONIZAÇÃO DE PEDIDOS
# ─────────────────────────────────────────

async def sincronizar_pedidos(db: Session, dias: int = 30) -> dict:
    """
    Busca pedidos dos últimos N dias no Bling e salva no banco local.
    Só importa pedidos com situação 'Atendido' ou 'Em aberto'.
    """
    headers = await _get_headers(db)
    data_inicio = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d")

    novos = 0
    atualizados = 0
    pagina = 1

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            resp = await client.get(
                f"{BLING_BASE_URL}/pedidos/vendas",
                headers=headers,
                params={
                    "pagina": pagina,
                    "limite": 100,
                    "dataInicial": data_inicio,
                },
            )

            if resp.status_code != 200:
                logger.error(f"Erro ao buscar pedidos página {pagina}: {resp.text}")
                break

            data = resp.json()
            pedidos = data.get("data", [])
            if not pedidos:
                break

            for pedido in pedidos:
                resultado = _processar_pedido(pedido, db)
                if resultado == "novo":
                    novos += 1
                elif resultado == "atualizado":
                    atualizados += 1

            # Próxima página
            total_paginas = data.get("meta", {}).get("totalPages", 1)
            if pagina >= total_paginas:
                break
            pagina += 1

    db.commit()
    logger.info(f"Sincronização concluída: {novos} novos, {atualizados} atualizados")
    return {"novos": novos, "atualizados": atualizados, "paginas": pagina}


def _processar_pedido(pedido: dict, db: Session) -> str:
    """Salva ou atualiza um pedido no banco local."""
    bling_id = str(pedido.get("id", ""))
    if not bling_id:
        return "ignorado"

    # Vendedor — vem dentro de "vendedor" → "nome"
    vendedor = pedido.get("vendedor") or {}
    vendedora_nome = vendedor.get("nome", "").strip() or "Sem vendedor"

    # Data
    data_str = pedido.get("data", "")
    try:
        data_venda = datetime.strptime(data_str, "%Y-%m-%d")
    except Exception:
        data_venda = datetime.utcnow()

    # Cliente
    contato = pedido.get("contato") or {}
    cliente_nome = contato.get("nome", "")
    cliente_id = str(contato.get("id", ""))

    # Valores
    valor_total = float(pedido.get("totalVenda", 0) or 0)
    num_itens = sum(
        int(item.get("quantidade", 0))
        for item in (pedido.get("itens") or [])
    )
    situacao_obj = pedido.get("situacao") or {}
    situacao = situacao_obj.get("nome", "") if isinstance(situacao_obj, dict) else str(situacao_obj)

    venda_db = db.query(Venda).filter(Venda.bling_pedido_id == bling_id).first()
    if venda_db:
        venda_db.valor_total = valor_total
        venda_db.situacao = situacao
        venda_db.sincronizado_em = datetime.utcnow()
        return "atualizado"
    else:
        nova = Venda(
            bling_pedido_id=bling_id,
            vendedora_nome=vendedora_nome,
            cliente_nome=cliente_nome,
            cliente_id_bling=cliente_id,
            valor_total=valor_total,
            num_itens=num_itens,
            data_venda=data_venda,
            situacao=situacao,
        )
        db.add(nova)
        return "novo"
