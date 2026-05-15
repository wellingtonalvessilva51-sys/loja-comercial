"""
Sistema Comercial - Loja de Roupas
Integração Bling + Dashboard de Vendedoras
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager
from models.database import criar_tabelas, SessionLocal, Vendedora
from services.auth import hash_senha
from services.bling import sincronizar_pedidos
from routers import auth, metricas, produtos
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

async def job_sincronizar():
    db = SessionLocal()
    try:
        logger.info("Sincronização automática iniciando...")
        resultado = await sincronizar_pedidos(db, dias=35)
        logger.info(f"Sincronização automática: {resultado}")
    except Exception as e:
        logger.error(f"Erro na sincronização automática: {e}")
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    criar_tabelas()
    _criar_gerente_padrao()
    scheduler.add_job(job_sincronizar, "interval", hours=1, id="sync_bling")
    scheduler.start()
    logger.info("Sistema iniciado. Sincronização automática ativa.")
    yield
    scheduler.shutdown()

def _criar_gerente_padrao():
    db = SessionLocal()
    try:
        gerente = db.query(Vendedora).filter(Vendedora.is_gerente == True).first()
        if not gerente:
            senha_padrao = os.getenv("SENHA_GERENTE", "loja@2024")
            email_padrao = os.getenv("EMAIL_GERENTE", "gerente@loja.com")
            gerente = Vendedora(
                nome="Gerente",
                email=email_padrao,
                senha_hash=hash_senha(senha_padrao),
                bling_vendedor_nome="",
                is_gerente=True,
                ativa=True,
            )
            db.add(gerente)
            db.commit()
            logger.info(f"Conta gerente criada: {email_padrao}")
    finally:
        db.close()

app = FastAPI(
    title="Sistema Comercial - Loja",
    description="Dashboard de vendas integrado ao Bling",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(metricas.router)
app.include_router(produtos.router)

# Serve os arquivos estáticos do frontend
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if not os.path.exists(frontend_path):
    frontend_path = "/app/frontend"
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=os.path.join(frontend_path, "static")), name="static")

    @app.get("/")
    async def serve_login():
        return FileResponse(os.path.join(frontend_path, "login.html"))

    @app.get("/gerente")
    async def serve_gerente():
        return FileResponse(os.path.join(frontend_path, "gerente", "index.html"))

    @app.get("/produtos/cadastrar")
    async def serve_cadastro_produtos():
        return FileResponse(os.path.join(frontend_path, "gerente", "cadastro-produtos.html"))

    @app.get("/vendedora")
    async def serve_vendedora():
        return FileResponse(os.path.join(frontend_path, "vendedora", "index.html"))
@app.get("/diagnostico")
async def diagnostico():
    import os
    versao = "v3"
    raiz = os.listdir("/")
    app_path = "/app"
    arquivos_app = os.listdir(app_path) if os.path.exists(app_path) else "nao existe"
    return {
        "versao": versao,
        "file": __file__,
        "raiz": raiz,
        "app": arquivos_app,
    }
@app.get("/health")
async def health():
    return {"status": "ok", "sistema": "Loja Comercial"}

@app.get("/api")
async def api_info():
    return {
        "endpoints": {
            "login": "POST /auth/login",
            "conectar_bling": "GET /auth/bling",
            "dashboard_gerente": "GET /gerente/dashboard",
            "dashboard_vendedora": "GET /vendedora/dashboard",
            "sincronizar": "POST /gerente/sincronizar",
        }
    }
