"""
Serviço de métricas: ranking, metas, comissões e histórico de clientes.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from models.database import Venda, Vendedora, Meta
from datetime import datetime, date
from typing import Optional


def get_metricas_gerente(db: Session, mes: int, ano: int) -> dict:
    """Dashboard completo para a gerente."""
    vendedoras = db.query(Vendedora).filter(Vendedora.ativa == True, Vendedora.is_gerente == False).all()

    # Vendas do período (mês/ano)
    vendas_periodo = (
        db.query(Venda)
        .filter(
            extract("month", Venda.data_venda) == mes,
            extract("year", Venda.data_venda) == ano,
            Venda.situacao.notin_(["Cancelado", "Cancelada"]),
        )
        .all()
    )

    # Totais gerais
    faturamento_total = sum(v.valor_total for v in vendas_periodo)
    pecas_total = sum(v.num_itens for v in vendas_periodo)
    ticket_medio = faturamento_total / len(vendas_periodo) if vendas_periodo else 0

    # Ranking por vendedora
    ranking = []
    for v in vendedoras:
        dados = _metricas_vendedora(v, vendas_periodo, db, mes, ano)
        ranking.append(dados)

    ranking.sort(key=lambda x: x["faturamento"], reverse=True)
    for i, r in enumerate(ranking):
        r["posicao"] = i + 1

    # Vendas por dia (últimos 7 dias para o gráfico)
    from datetime import timedelta
    hoje = date.today()
    vendas_semana = []
    for i in range(6, -1, -1):
        dia = hoje - timedelta(days=i)
        total_dia = sum(
            v.valor_total for v in vendas_periodo
            if v.data_venda and v.data_venda.date() == dia
        )
        vendas_semana.append({"data": dia.strftime("%d/%m"), "valor": total_dia})

    return {
        "periodo": {"mes": mes, "ano": ano},
        "totais": {
            "faturamento": round(faturamento_total, 2),
            "pecas": pecas_total,
            "ticket_medio": round(ticket_medio, 2),
            "comissoes": round(sum(r["comissao"] for r in ranking), 2),
            "num_pedidos": len(vendas_periodo),
        },
        "ranking": ranking,
        "vendas_semana": vendas_semana,
    }


def get_metricas_vendedora(db: Session, vendedora: Vendedora, mes: int, ano: int) -> dict:
    """Dashboard individual para a vendedora."""
    vendas_periodo = (
        db.query(Venda)
        .filter(
            extract("month", Venda.data_venda) == mes,
            extract("year", Venda.data_venda) == ano,
            Venda.situacao.notin_(["Cancelado", "Cancelada"]),
        )
        .all()
    )

    meus_dados = _metricas_vendedora(vendedora, vendas_periodo, db, mes, ano)

    # Ranking completo (posição)
    todas_vendedoras = db.query(Vendedora).filter(
        Vendedora.ativa == True, Vendedora.is_gerente == False
    ).all()
    ranking = []
    for v in todas_vendedoras:
        d = _metricas_vendedora(v, vendas_periodo, db, mes, ano)
        ranking.append({"nome": v.nome, "faturamento": d["faturamento"]})
    ranking.sort(key=lambda x: x["faturamento"], reverse=True)
    for i, r in enumerate(ranking):
        r["posicao"] = i + 1
        if r["nome"] == vendedora.nome:
            meus_dados["posicao"] = i + 1

    # Vendas do dia (hoje)
    hoje = date.today()
    minhas_vendas_hoje = [
        v for v in vendas_periodo
        if v.vendedora_nome == vendedora.bling_vendedor_nome
        and v.data_venda and v.data_venda.date() == hoje
    ]
    faturamento_hoje = sum(v.valor_total for v in minhas_vendas_hoje)
    pecas_hoje = sum(v.num_itens for v in minhas_vendas_hoje)

    # Histórico de clientes (últimos 10 clientes únicos)
    minhas_vendas = [
        v for v in vendas_periodo
        if v.vendedora_nome == vendedora.bling_vendedor_nome
    ]
    clientes_vistos = {}
    for v in sorted(minhas_vendas, key=lambda x: x.data_venda or datetime.min, reverse=True):
        if v.cliente_nome and v.cliente_nome not in clientes_vistos:
            clientes_vistos[v.cliente_nome] = {
                "nome": v.cliente_nome,
                "ultima_compra": v.data_venda.strftime("%d/%m/%Y") if v.data_venda else "-",
                "valor": round(v.valor_total, 2),
            }

    return {
        **meus_dados,
        "hoje": {
            "faturamento": round(faturamento_hoje, 2),
            "pecas": pecas_hoje,
            "comissao": round(faturamento_hoje * vendedora.percentual_comissao / 100, 2),
        },
        "ranking": ranking,
        "clientes_recentes": list(clientes_vistos.values())[:10],
    }


def _metricas_vendedora(vendedora: Vendedora, vendas_periodo: list, db: Session, mes: int, ano: int) -> dict:
    minhas_vendas = [
        v for v in vendas_periodo
        if v.vendedora_nome == vendedora.bling_vendedor_nome
    ]
    faturamento = sum(v.valor_total for v in minhas_vendas)
    pecas = sum(v.num_itens for v in minhas_vendas)
    num_pedidos = len(minhas_vendas)
    ticket_medio = faturamento / num_pedidos if num_pedidos else 0
    comissao = faturamento * vendedora.percentual_comissao / 100

    # Meta do mês
    meta_db = (
        db.query(Meta)
        .filter(Meta.vendedora_id == vendedora.id, Meta.mes == mes, Meta.ano == ano)
        .first()
    )
    meta_valor = meta_db.valor_meta if meta_db else vendedora.meta_mensal
    percentual_meta = (faturamento / meta_valor * 100) if meta_valor else 0

    return {
        "id": vendedora.id,
        "nome": vendedora.nome,
        "faturamento": round(faturamento, 2),
        "pecas": pecas,
        "num_pedidos": num_pedidos,
        "ticket_medio": round(ticket_medio, 2),
        "comissao": round(comissao, 2),
        "meta_valor": meta_valor,
        "meta_percentual": round(percentual_meta, 1),
        "percentual_comissao": vendedora.percentual_comissao,
    }
