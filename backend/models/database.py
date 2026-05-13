from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./loja.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Vendedora(Base):
    __tablename__ = "vendedoras"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    senha_hash = Column(String(255), nullable=False)
    bling_vendedor_nome = Column(String(100))   # nome exato como aparece no Bling
    meta_mensal = Column(Float, default=12000.0)
    percentual_comissao = Column(Float, default=5.0)
    ativa = Column(Boolean, default=True)
    criada_em = Column(DateTime, default=datetime.utcnow)
    is_gerente = Column(Boolean, default=False)


class Venda(Base):
    __tablename__ = "vendas"

    id = Column(Integer, primary_key=True, index=True)
    bling_pedido_id = Column(String(50), unique=True, index=True)
    vendedora_nome = Column(String(100), index=True)   # vem do campo vendedor do Bling
    cliente_nome = Column(String(200))
    cliente_id_bling = Column(String(50))
    valor_total = Column(Float, default=0.0)
    num_itens = Column(Integer, default=0)
    data_venda = Column(DateTime, index=True)
    situacao = Column(String(50))                      # status do pedido no Bling
    sincronizado_em = Column(DateTime, default=datetime.utcnow)


class Meta(Base):
    __tablename__ = "metas"

    id = Column(Integer, primary_key=True, index=True)
    vendedora_id = Column(Integer, index=True)
    mes = Column(Integer)   # 1-12
    ano = Column(Integer)
    valor_meta = Column(Float)
    criada_em = Column(DateTime, default=datetime.utcnow)


class TokenBling(Base):
    __tablename__ = "tokens_bling"

    id = Column(Integer, primary_key=True, index=True)
    access_token = Column(Text)
    refresh_token = Column(Text)
    expires_at = Column(DateTime)
    atualizado_em = Column(DateTime, default=datetime.utcnow)


def criar_tabelas():
    Base.metadata.create_all(bind=engine)
