import asyncio
import os
import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://leadsim-beauty.vercel.app", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CampanhaRequest(BaseModel):
    tema: str
    formatos: list[str] = ["instagram", "email", "whatsapp"]
    clinica_id: Optional[str] = None
    clinica_nome: Optional[str] = None

def verificar_api_key(x_api_key: str = Header(None)):
    expected = os.getenv("LEADSIM_INTERNAL_KEY", "leadsim-dev-key")
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Chave inválida")

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.post("/campanha")
async def gerar_campanha(req: CampanhaRequest, x_api_key: str = Header(None)):
    verificar_api_key(x_api_key)
    formatos_validos = {"instagram", "email", "whatsapp", "stories"}
    formatos = [f for f in req.formatos if f in formatos_validos] or ["instagram", "email", "whatsapp"]
    try:
        from pipeline import executar_campanha as _exec
        resultado = await asyncio.wait_for(
            asyncio.to_thread(_exec, req.tema, formatos, False),
            timeout=90.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Pipeline timeout — tente novamente com menos formatos")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    campanha_id = str(uuid.uuid4())
    criado_em = datetime.now().isoformat()
    try:
        from supabase import create_client
        sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
        sb.table("campanhas_mkt").insert({"id": campanha_id, "tema": req.tema, "formatos": formatos, "briefing": resultado["briefing"], "conteudo_final": resultado["conteudo_final"], "score": resultado["meta"]["score_final"], "aprovado": resultado["meta"]["aprovado"], "notas_revisao": resultado["notas_revisao"], "tentativas": resultado["meta"]["tentativas"], "duracao_segundos": resultado["meta"]["duracao_segundos"], "clinica_id": req.clinica_id, "criado_em": criado_em}).execute()
    except:
        pass
    return {"id": campanha_id, "status": "concluida", "score": resultado["meta"]["score_final"], "aprovado": resultado["meta"]["aprovado"], "tema": req.tema, "formatos": formatos, "briefing": resultado["briefing"], "conteudo_final": resultado["conteudo_final"], "notas_revisao": resultado["notas_revisao"], "tentativas": resultado["meta"]["tentativas"], "duracao_segundos": resultado["meta"]["duracao_segundos"], "criado_em": criado_em, "clinica_id": req.clinica_id}

@app.get("/campanhas")
async def listar_campanhas(clinica_id: Optional[str] = None, limite: int = 20, x_api_key: str = Header(None)):
    verificar_api_key(x_api_key)
    try:
        from supabase import create_client
        sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
        query = sb.table("campanhas_mkt").select("*").order("criado_em", desc=True).limit(limite)
        if clinica_id:
            query = query.eq("clinica_id", clinica_id)
        result = query.execute()
        return {"campanhas": result.data, "total": len(result.data)}
    except Exception as e:
        return {"campanhas": [], "total": 0}

@app.get("/campanha/{campanha_id}")
async def buscar_campanha(campanha_id: str, x_api_key: str = Header(None)):
    verificar_api_key(x_api_key)
    try:
        from supabase import create_client
        sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
        result = sb.table("campanhas_mkt").select("*").eq("id", campanha_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Não encontrada")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
