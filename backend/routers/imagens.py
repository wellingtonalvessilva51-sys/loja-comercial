"""
Geração de imagens de modelo vestindo o produto via OpenAI gpt-image-1 + Cloudinary.
"""
import os
import base64
import hashlib
import httpx
from fastapi import APIRouter, Request
from models.database import SessionLocal

router = APIRouter()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
CLOUDINARY_CLOUD = os.getenv("CLOUDINARY_CLOUD_NAME", "dlbkwkhce")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "523222474788819")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "rB8C45bY26CSwNWgkYKV6qFI9wA")
N8N_API_KEY_INTERNO = "modexa-n8n-2026"


def _cloudinary_signature(params: dict, secret: str) -> str:
    sorted_params = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    return hashlib.sha1(f"{sorted_params}{secret}".encode()).hexdigest()


async def _upload_cloudinary(img_bytes: bytes, public_id: str) -> str:
    import time
    timestamp = int(time.time())
    folder = "modexa/modelos"
    params = {"folder": folder, "public_id": public_id, "timestamp": timestamp}
    signature = _cloudinary_signature(params, CLOUDINARY_API_SECRET)

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD}/image/upload",
            data={
                "api_key": CLOUDINARY_API_KEY,
                "timestamp": timestamp,
                "folder": folder,
                "public_id": public_id,
                "signature": signature,
            },
            files={"file": ("image.png", img_bytes, "image/png")},
        )
    result = resp.json()
    if "secure_url" in result:
        return result["secure_url"]
    raise Exception(f"Cloudinary error: {result.get('error', result)}")


@router.post("/api/gerar-imagens-modelo")
async def gerar_imagens_modelo(request: Request):
    api_key = request.headers.get("X-API-Key", "")
    if api_key != N8N_API_KEY_INTERNO:
        return {"ok": False, "error": "Unauthorized"}

    data = await request.json()
    produto_id = data.get("produto_id", 0)
    bling_produto_id = data.get("bling_produto_id", "")
    modelos = data.get("modelos", [])

    if not modelos or modelos == "":
        return {"ok": True, "resultados": ""}

    resultados = []

    async with httpx.AsyncClient(timeout=120) as client:
        for modelo in modelos:
            tamanho = modelo.get("tamanho", "M")
            tipo = modelo.get("tipo", "")
            prompt = modelo.get("prompt", "")

            try:
                resp = await client.post(
                    "https://api.openai.com/v1/images/generations",
                    headers={
                        "Authorization": f"Bearer {OPENAI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "gpt-image-1",
                        "prompt": prompt,
                        "n": 1,
                        "size": "1024x1024",
                        "quality": "standard",
                    },
                )
                img_data = resp.json()

                if "data" not in img_data:
                    error_msg = img_data.get("error", {})
                    if isinstance(error_msg, dict):
                        error_msg = error_msg.get("message", str(img_data))
                    raise Exception(f"OpenAI: {error_msg}")

                b64_str = img_data["data"][0].get("b64_json")
                if not b64_str:
                    raise Exception("OpenAI não retornou b64_json")

                img_bytes = base64.b64decode(b64_str)
                public_id = f"produto_{bling_produto_id}_{tamanho}_{tipo}"
                url = await _upload_cloudinary(img_bytes, public_id)

                resultados.append({
                    "tamanho": tamanho,
                    "tipo": tipo,
                    "ok": True,
                    "url": url,
                })

            except Exception as e:
                resultados.append({
                    "tamanho": tamanho,
                    "tipo": tipo,
                    "ok": False,
                    "error": str(e),
                })

    return {"ok": True, "resultados": resultados}
