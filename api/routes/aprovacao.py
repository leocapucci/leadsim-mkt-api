"""
api/routes/aprovacao.py
Endpoint de aprovação/reprovação de campanhas via WhatsApp.
"""

import os
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class AprovacaoRequest(BaseModel):
    aprovado: bool
    whatsapp_origem: str


def _get_supabase():
    from supabase import create_client
    return create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))


def proximo_horario_publicacao() -> str:
    """
    Próximos horários de publicação:
      Segunda (0) e Domingo (6) → 18h
      Quarta  (2) e Sexta   (4) →  9h
    """
    agenda = {0: 18, 2: 9, 4: 9, 6: 18}
    agora  = datetime.now(timezone.utc)

    for delta in range(8):
        candidato = agora + timedelta(days=delta)
        weekday   = candidato.weekday()
        if weekday in agenda:
            ts = candidato.replace(
                hour=agenda[weekday], minute=0, second=0, microsecond=0
            )
            if ts > agora:
                return ts.isoformat()

    return (agora + timedelta(days=1)).isoformat()  # fallback


@router.post("/aprovar/{job_id}")
async def aprovar_campanha(job_id: str, req: AprovacaoRequest):
    sb = _get_supabase()

    result = sb.table("jobs_campanha").select("status").eq("id", job_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    status_atual = result.data[0]["status"]
    if status_atual not in ("aguardando_aprovacao", "concluido"):
        raise HTTPException(
            status_code=400,
            detail=f"Job não está aguardando aprovação (status atual: {status_atual})"
        )

    novo_status = "aprovado" if req.aprovado else "reprovado"
    update_data: dict = {
        "status": novo_status,
        "aprovado_por_whatsapp": req.whatsapp_origem,
        "aprovado_em": datetime.now(timezone.utc).isoformat(),
    }

    if req.aprovado:
        update_data["publicar_em"] = proximo_horario_publicacao()

    sb.table("jobs_campanha").update(update_data).eq("id", job_id).execute()

    return {
        "job_id": job_id,
        "status": novo_status,
        "publicar_em": update_data.get("publicar_em"),
    }
