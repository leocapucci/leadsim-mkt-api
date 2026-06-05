import asyncio
import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

from api.routes.aprovacao import router as aprovacao_router
app.include_router(aprovacao_router)


@app.on_event("startup")
def startup_scheduler():
    from cron.scheduler import start_scheduler
    start_scheduler()


@app.on_event("shutdown")
def shutdown_scheduler():
    from cron.scheduler import stop_scheduler
    stop_scheduler()

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


def _get_supabase():
    from supabase import create_client
    return create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))


async def _rodar_pipeline(job_id: str, tema: str, formatos: list[str], clinica_id: Optional[str]):
    """Roda o pipeline em background e persiste o resultado no Supabase."""
    sb = _get_supabase()

    # Marca job como em progresso
    sb.table("jobs_campanha").update({"status": "processando"}).eq("id", job_id).execute()

    try:
        from pipeline import executar_campanha as _exec
        resultado = await asyncio.to_thread(_exec, tema, formatos, False)

        sb.table("jobs_campanha").update({
            "status": "concluido",
            "briefing": resultado["briefing"],
            "conteudo_final": resultado["conteudo_final"],
            "score": int(resultado["meta"]["score_final"]),
            "aprovado": resultado["meta"]["aprovado"],
            "notas_revisao": resultado["notas_revisao"],
            "tentativas": resultado["meta"]["tentativas"],
            "duracao_segundos": resultado["meta"]["duracao_segundos"],
            "concluido_em": datetime.now().isoformat(),
        }).eq("id", job_id).execute()

    except Exception as e:
        sb.table("jobs_campanha").update({
            "status": "erro",
            "erro": str(e)[:500],
        }).eq("id", job_id).execute()


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.post("/campanha")
async def gerar_campanha(req: CampanhaRequest, background_tasks: BackgroundTasks, x_api_key: str = Header(None)):
    verificar_api_key(x_api_key)

    formatos_validos = {"instagram", "email", "whatsapp", "stories"}
    formatos = [f for f in req.formatos if f in formatos_validos] or ["instagram", "email", "whatsapp"]

    job_id = str(uuid.uuid4())
    criado_em = datetime.now().isoformat()

    try:
        sb = _get_supabase()
        sb.table("jobs_campanha").insert({
            "id": job_id,
            "status": "pendente",
            "tema": req.tema,
            "formatos": formatos,
            "clinica_id": req.clinica_id,
            "criado_em": criado_em,
        }).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao criar job: {e}")

    background_tasks.add_task(_rodar_pipeline, job_id, req.tema, formatos, req.clinica_id)

    return {"job_id": job_id, "status": "pendente", "criado_em": criado_em}


@app.get("/campanha/status/{job_id}")
async def status_campanha(job_id: str, x_api_key: str = Header(None)):
    verificar_api_key(x_api_key)
    try:
        sb = _get_supabase()
        result = sb.table("jobs_campanha").select("*").eq("id", job_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Job não encontrado")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/campanhas")
async def listar_campanhas(clinica_id: Optional[str] = None, limite: int = 20, x_api_key: str = Header(None)):
    verificar_api_key(x_api_key)
    try:
        sb = _get_supabase()
        query = sb.table("jobs_campanha").select("*").order("criado_em", desc=True).limit(limite)
        if clinica_id:
            query = query.eq("clinica_id", clinica_id)
        result = query.execute()
        return {"campanhas": result.data, "total": len(result.data)}
    except Exception as e:
        return {"campanhas": [], "total": 0}


async def _gerar_e_salvar_imagens(job_id: str, briefing: str, formatos: list[str]):
    """Gera imagens em background e persiste no Supabase ao concluir."""
    try:
        from agente_imagens import AgenteImagens
        agente = AgenteImagens()
        imagens = await asyncio.to_thread(agente.gerar_para_campanha, briefing, formatos)
        _get_supabase().table("jobs_campanha").update({"imagens": imagens}).eq("id", job_id).execute()
    except Exception as e:
        print(f"[imagens] erro no background para job {job_id}: {e}")


@app.post("/campanha/{job_id}/imagens")
async def gerar_imagens_campanha(job_id: str, background_tasks: BackgroundTasks, x_api_key: str = Header(None)):
    verificar_api_key(x_api_key)
    sb = _get_supabase()

    result = sb.table("jobs_campanha").select("briefing, formatos, status").eq("id", job_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    job = result.data[0]
    if job["status"] != "concluido":
        raise HTTPException(status_code=400, detail=f"Job ainda não concluído (status: {job['status']})")

    background_tasks.add_task(_gerar_e_salvar_imagens, job_id, job["briefing"], job["formatos"])

    return {"job_id": job_id, "status": "gerando"}


@app.get("/admin/testar-automacao")
async def testar_automacao(x_api_key: str = Header(None)):
    verificar_api_key(x_api_key)
    import io, contextlib
    import cron.automacao as _automacao
    from cron.automacao import run_automacao
    buffer = io.StringIO()
    # Desabilita geração de imagens em testes manuais para não consumir crédito OpenAI
    _original_gerar_imagens = _automacao.gerar_imagens
    _automacao.gerar_imagens = lambda job_id: print("  [teste] geração de imagens desabilitada")
    try:
        with contextlib.redirect_stdout(buffer):
            await asyncio.to_thread(run_automacao)
        return {"status": "ok", "log": buffer.getvalue()}
    except Exception as e:
        return {"status": "erro", "log": buffer.getvalue(), "erro": str(e)}
    finally:
        _automacao.gerar_imagens = _original_gerar_imagens


@app.get("/campanha/{campanha_id}")
async def buscar_campanha(campanha_id: str, x_api_key: str = Header(None)):
    verificar_api_key(x_api_key)
    try:
        sb = _get_supabase()
        result = sb.table("jobs_campanha").select("*").eq("id", campanha_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Não encontrada")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
