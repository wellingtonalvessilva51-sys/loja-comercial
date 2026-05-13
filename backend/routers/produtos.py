"""
Router de Produtos — proxy para a API do Bling.
O servidor faz a chamada ao Bling, resolvendo o problema de CORS do navegador.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from models.database import get_db, TokenBling
from services.auth import exigir_gerente
from services.bling import _get_headers
from models.database import Vendedora
import httpx
import re

router = APIRouter(prefix="/produtos", tags=["produtos"])

BLING_BASE = "https://api.bling.com.br/Api/v3"

# ── Tabela NCM por categoria ──────────────────────────────
NCM_MAP = {
    "blusa":     "6106.10.00",
    "camisa":    "6105.10.00",
    "camiseta":  "6109.10.00",
    "regata":    "6109.10.00",
    "cropped":   "6109.10.00",
    "top":       "6212.90.00",
    "body":      "6212.90.00",
    "cardigan":  "6110.20.00",
    "tricot":    "6110.20.00",
    "calca":     "6204.61.00",
    "shorts":    "6204.61.00",
    "bermuda":   "6203.42.00",
    "saia":      "6204.51.00",
    "vestido":   "6204.41.00",
    "macacao":   "6211.42.00",
    "conjunto":  "6204.19.00",
    "chamise":   "6204.19.00",
    "jaqueta":   "6202.13.00",
    "blazer":    "6204.31.00",
    "colete":    "6211.42.00",
    "parka":     "6202.13.00",
    "sobretudo": "6202.13.00",
    "lingerie":  "6212.10.00",
    "meia":      "6115.95.00",
    "calcado":   "6403.99.90",
    "acessorio": "6217.10.00",
}

CAT_ABBR = {
    "blusa":"BLS","camisa":"CMS","camiseta":"CMT","regata":"RGT","cropped":"CRP",
    "top":"TOP","body":"BDY","cardigan":"CDG","tricot":"TRC","calca":"CLC",
    "shorts":"SHT","bermuda":"BMD","saia":"SKT","vestido":"VSD","macacao":"MCC",
    "conjunto":"CNJ","chamise":"CHM","jaqueta":"JKT","blazer":"BLZ","colete":"CLT",
    "parka":"PRK","sobretudo":"SBT","lingerie":"LNG","meia":"MEA","calcado":"CAL",
    "acessorio":"ACS",
}

COR_ABBR = {
    "Preto":"PRT","Branco":"BRC","Cinza":"CNZ","Azul":"AZL","Azul Marinho":"AZM",
    "Vermelho":"VML","Rosa":"RSA","Pink":"PNK","Verde":"VRD","Amarelo":"AML",
    "Laranja":"LRJ","Roxo":"RXO","Caramelo":"CRM","Bege":"BGE","Nude":"NDE",
    "Off White":"OFW","Marrom":"MRM","Vinho":"VNH","Cobre":"CBR","Dourado":"DRD",
    "Prata":"PRT2","Estampado":"EST","Listrado":"LST","Floral":"FLR","Xadrez":"XDZ",
}


# ── Schemas ───────────────────────────────────────────────

class VariacaoInput(BaseModel):
    tamanho: str
    cor: str
    estoque: int = 0
    preco: Optional[float] = None

class ProdutoInput(BaseModel):
    nome: str
    categoria: str
    genero: str = "F"
    tecido: str = ""
    composicao: Optional[str] = None
    preco: float
    custo: Optional[float] = None
    marca: Optional[str] = None
    obs: Optional[str] = None
    peso: Optional[float] = None
    largura: Optional[float] = None
    comprimento: Optional[float] = None
    estoque_inicial: int = 0
    estoque_minimo: int = 2
    estoque_maximo: int = 50
    variacoes: Optional[List[VariacaoInput]] = None


# ── Helpers ───────────────────────────────────────────────

def gerar_sku_base(categoria: str, genero: str, nome: str) -> str:
    cat = CAT_ABBR.get(categoria, "PRD")
    gen = genero[:1].upper()
    # 4 chars do nome (sem espaços, maiúsculo)
    slug = re.sub(r'[^A-Za-z]', '', nome).upper()[:4].ljust(4,'X')
    return f"{cat}-{gen}{slug}"

def gerar_sku_variacao(sku_base: str, tamanho: str, cor: str) -> str:
    tam = tamanho.replace("/", "").upper()
    cor_abr = COR_ABBR.get(cor, cor[:3].upper())
    return f"{sku_base}-{tam}-{cor_abr}"

def ncm_limpo(categoria: str) -> str:
    ncm = NCM_MAP.get(categoria, "6109.10.00")
    return ncm.replace(".", "")   # Bling aceita sem pontos

def montar_payload_bling(produto: ProdutoInput) -> dict:
    sku_base = gerar_sku_base(produto.categoria, produto.genero, produto.nome)
    ncm = ncm_limpo(produto.categoria)

    descricao_partes = []
    if produto.composicao:
        descricao_partes.append(f"Composição: {produto.composicao}")
    if produto.tecido:
        descricao_partes.append(f"Tecido: {produto.tecido}")
    if produto.obs:
        descricao_partes.append(produto.obs)

    payload = {
        "nome": produto.nome,
        "codigo": sku_base,
        "preco": produto.preco,
        "tipo": "P",
        "situacao": "A",
        "formato": "V" if produto.variacoes else "S",
        "descricao": "\n".join(descricao_partes),
        "unidade": "UN",
        "ncm": ncm,
        "origem": 0,
    }

    if produto.custo:
        payload["precoCusto"] = produto.custo
    if produto.marca:
        payload["marca"] = produto.marca
    if produto.peso:
        payload["pesoLiquido"] = produto.peso
        payload["pesoBruto"] = produto.peso
    if produto.largura:
        payload["largura"] = produto.largura
    if produto.comprimento:
        payload["comprimento"] = produto.comprimento

    # Variações
    if produto.variacoes:
        variacoes_payload = []
        for i, v in enumerate(produto.variacoes):
            sku_var = gerar_sku_variacao(sku_base, v.tamanho, v.cor)
            variacoes_payload.append({
                "nome": f"{v.tamanho} / {v.cor}",
                "codigo": sku_var,
                "preco": v.preco or produto.preco,
                "variacao": {
                    "nome": f"{v.tamanho} / {v.cor}",
                    "ordem": i + 1,
                },
            })
        payload["variacoes"] = variacoes_payload

    return payload, sku_base


# ── Endpoints ─────────────────────────────────────────────

@router.post("/criar")
async def criar_produto(
    produto: ProdutoInput,
    db: Session = Depends(get_db),
    gerente: Vendedora = Depends(exigir_gerente),
):
    """Cria produto no Bling via servidor (sem CORS)."""
    try:
        headers = await _get_headers(db)
    except Exception as e:
        raise HTTPException(400, f"Bling não autenticado: {e}")

    payload, sku_base = montar_payload_bling(produto)

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{BLING_BASE}/produtos",
            headers=headers,
            json=payload,
        )

    if resp.status_code in (200, 201):
        data = resp.json()
        produto_id = data.get("data", {}).get("id")

        # Lança estoque inicial se informado
        if produto_id and produto.estoque_inicial > 0 and not produto.variacoes:
            await _lancar_estoque(produto_id, produto.estoque_inicial, headers)

        return {
            "sucesso": True,
            "id_bling": produto_id,
            "sku": sku_base,
            "ncm": NCM_MAP.get(produto.categoria, ""),
            "mensagem": f"Produto '{produto.nome}' criado com sucesso!",
            "variacoes_criadas": len(produto.variacoes) if produto.variacoes else 0,
        }
    else:
        erro = resp.json()
        msg = erro.get("error", {}).get("message") or str(erro)
        raise HTTPException(resp.status_code, f"Erro do Bling: {msg}")


@router.get("/ncm/{categoria}")
async def get_ncm(categoria: str, gerente: Vendedora = Depends(exigir_gerente)):
    """Retorna o NCM para uma categoria."""
    ncm = NCM_MAP.get(categoria)
    if not ncm:
        raise HTTPException(404, "Categoria não encontrada.")
    return {"categoria": categoria, "ncm": ncm}


@router.get("/sku-preview")
async def preview_sku(
    categoria: str,
    genero: str,
    nome: str,
    gerente: Vendedora = Depends(exigir_gerente),
):
    """Pré-visualiza o SKU base antes de criar."""
    sku = gerar_sku_base(categoria, genero, nome)
    return {"sku_base": sku}


@router.get("/listar")
async def listar_produtos(
    pagina: int = 1,
    db: Session = Depends(get_db),
    gerente: Vendedora = Depends(exigir_gerente),
):
    """Lista produtos cadastrados no Bling."""
    try:
        headers = await _get_headers(db)
    except Exception as e:
        raise HTTPException(400, f"Bling não autenticado: {e}")

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            f"{BLING_BASE}/produtos",
            headers=headers,
            params={"pagina": pagina, "limite": 20, "situacao": "A"},
        )

    if resp.ok:
        return resp.json()
    raise HTTPException(resp.status_code, "Erro ao listar produtos do Bling.")


async def _lancar_estoque(produto_id: int, quantidade: int, headers: dict):
    """Lança estoque inicial no Bling."""
    async with httpx.AsyncClient(timeout=15) as client:
        await client.post(
            f"{BLING_BASE}/estoques",
            headers=headers,
            json={
                "produto": {"id": produto_id},
                "deposito": {"id": 1},  # depósito Geral
                "quantidade": quantidade,
                "operacao": "B",        # Balanço (saldo inicial)
                "preco": 0,
                "observacoes": "Estoque inicial via Sistema Comercial",
            },
        )
