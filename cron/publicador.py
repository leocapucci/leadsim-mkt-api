"""
cron/publicador.py
Publicador automático de campanhas aprovadas no Instagram.

Fluxo:
  1. Busca jobs com status="aprovado" e publicar_em <= agora
  2. Para cada job, busca credenciais Instagram da clínica
  3. Publica via Graph API v19.0 (container → publish → permalink)
  4. Atualiza status para "publicado" e salva permalink

Uso: python cron/publicador.py
Ou chamado pelo scheduler a cada 5 minutos.
"""

import os
import sys
import logging
import requests
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GRAPH_BASE   = "https://graph.facebook.com/v19.0"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("leadsim.publicador")


# ─────────────────────────────────────────
# SUPABASE HELPERS
# ─────────────────────────────────────────

def _sb_headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def buscar_jobs_prontos() -> list[dict]:
    """Busca jobs aprovados com publicar_em <= agora."""
    agora = datetime.now(timezone.utc).isoformat()
    res = requests.get(
        f"{SUPABASE_URL}/rest/v1/jobs_campanha",
        headers=_sb_headers(),
        params={
            "status": "eq.aprovado",
            "publicar_em": f"lte.{agora}",
            "select": "id,clinica_id,tema,imagens,conteudo_final,publicacoes",
        },
    )
    res.raise_for_status()
    return res.json()


def buscar_credenciais_clinica(clinica_id: str) -> dict | None:
    """Retorna instagram_account_id e instagram_access_token da clínica."""
    res = requests.get(
        f"{SUPABASE_URL}/rest/v1/clinicas",
        headers=_sb_headers(),
        params={
            "id": f"eq.{clinica_id}",
            "select": "nome,instagram_account_id,instagram_access_token",
        },
    )
    res.raise_for_status()
    data = res.json()
    return data[0] if data else None


def atualizar_job_publicado(job_id: str, publicacoes: dict) -> None:
    requests.patch(
        f"{SUPABASE_URL}/rest/v1/jobs_campanha",
        headers={**_sb_headers(), "Prefer": "return=minimal"},
        params={"id": f"eq.{job_id}"},
        json={"status": "publicado", "publicacoes": publicacoes},
    )


def atualizar_job_erro_publicacao(job_id: str, erro: str) -> None:
    requests.patch(
        f"{SUPABASE_URL}/rest/v1/jobs_campanha",
        headers={**_sb_headers(), "Prefer": "return=minimal"},
        params={"id": f"eq.{job_id}"},
        json={"status": "erro_publicacao", "erro": erro[:500]},
    )


# ─────────────────────────────────────────
# GRAPH API
# ─────────────────────────────────────────

def publicar_instagram(account_id: str, access_token: str, image_url: str, caption: str) -> dict:
    """
    Fluxo Instagram Graph API:
      1. POST /{account_id}/media        → creation_id
      2. POST /{account_id}/media_publish → post_id
      3. GET  /{post_id}?fields=permalink → permalink
    """
    # Step 1 — cria container
    r1 = requests.post(
        f"{GRAPH_BASE}/{account_id}/media",
        json={"image_url": image_url, "caption": caption, "access_token": access_token},
        timeout=30,
    )
    r1_data = r1.json()
    if not r1.ok:
        raise RuntimeError(f"Graph /media error: {r1_data.get('error', {}).get('message', r1_data)}")

    creation_id = r1_data.get("id")
    if not creation_id:
        raise RuntimeError("Graph /media não retornou creation_id")

    # Step 2 — publica
    r2 = requests.post(
        f"{GRAPH_BASE}/{account_id}/media_publish",
        json={"creation_id": creation_id, "access_token": access_token},
        timeout=30,
    )
    r2_data = r2.json()
    if not r2.ok:
        raise RuntimeError(f"Graph /media_publish error: {r2_data.get('error', {}).get('message', r2_data)}")

    post_id = r2_data.get("id")
    if not post_id:
        raise RuntimeError("Graph /media_publish não retornou post_id")

    # Step 3 — permalink
    r3 = requests.get(
        f"{GRAPH_BASE}/{post_id}",
        params={"fields": "permalink", "access_token": access_token},
        timeout=15,
    )
    permalink = r3.json().get("permalink", f"https://www.instagram.com/p/{post_id}")

    return {"post_id": post_id, "permalink": permalink}


# ─────────────────────────────────────────
# FUNÇÃO PRINCIPAL
# ─────────────────────────────────────────

def run_publicador():
    logger.info("[publicador] Verificando jobs prontos para publicar...")

    jobs = buscar_jobs_prontos()
    if not jobs:
        logger.info("[publicador] Nenhum job pronto.")
        return

    logger.info(f"[publicador] {len(jobs)} job(s) para publicar.")

    for job in jobs:
        job_id    = job["id"]
        clinica_id = job.get("clinica_id")
        tema       = job.get("tema", "")
        imagens    = job.get("imagens") or {}
        conteudo   = job.get("conteudo_final", "")
        publicacoes = job.get("publicacoes") or {}

        logger.info(f"[publicador] Job {job_id[:8]} — tema: {tema}")

        # Busca credenciais
        if not clinica_id:
            logger.warning(f"  Sem clinica_id — pulando.")
            continue

        clinica = buscar_credenciais_clinica(clinica_id)
        if not clinica:
            logger.warning(f"  Clínica {clinica_id} não encontrada — pulando.")
            continue

        account_id   = clinica.get("instagram_account_id")
        access_token = clinica.get("instagram_access_token")
        nome_clinica = clinica.get("nome", "")

        if not account_id or not access_token:
            logger.warning(f"  [{nome_clinica}] Sem credenciais Instagram — pulando.")
            continue

        # Busca URL da imagem (formato instagram ou primeiro disponível)
        image_url = (
            imagens.get("instagram", {}).get("url")
            or next((v.get("url") for v in imagens.values() if v.get("url")), None)
        )

        if not image_url:
            logger.warning(f"  [{nome_clinica}] Sem imagem disponível — pulando.")
            continue

        # Caption: 3 primeiras linhas do conteúdo
        caption = "\n".join(conteudo.strip().splitlines()[:3]) if conteudo else tema

        try:
            resultado = publicar_instagram(account_id, access_token, image_url, caption)
            post_id   = resultado["post_id"]
            permalink = resultado["permalink"]

            publicacoes["instagram"] = {
                "post_id": post_id,
                "permalink": permalink,
                "publicado_em": datetime.now(timezone.utc).isoformat(),
            }

            atualizar_job_publicado(job_id, publicacoes)
            logger.info(f"  [{nome_clinica}] ✓ Publicado: {permalink}")

        except Exception as e:
            logger.error(f"  [{nome_clinica}] ERRO ao publicar: {e}")
            atualizar_job_erro_publicacao(job_id, str(e))


if __name__ == "__main__":
    run_publicador()
