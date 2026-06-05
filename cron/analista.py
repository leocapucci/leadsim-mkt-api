"""
cron/analista.py
Agente Analista — monitora métricas 48h após publicação.

Fluxo:
  1. Busca jobs com status="publicado" publicados há 47-49h
  2. Para cada job, busca métricas do post no Instagram via Graph API
  3. Usa Claude para gerar conclusão sobre performance
  4. Faz append em historico_performance da clínica no Supabase
  5. Marca job como status="analisado"
"""

import os
import sys
import json
import requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

SUPABASE_URL    = os.getenv("SUPABASE_URL")
SUPABASE_KEY    = os.getenv("SUPABASE_KEY")
ANTHROPIC_KEY   = os.getenv("ANTHROPIC_API_KEY")

GRAPH_API_BASE  = "https://graph.facebook.com/v19.0"


# ─────────────────────────────────────────
# SUPABASE HELPERS
# ─────────────────────────────────────────

def _sb_headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def buscar_jobs_para_analisar() -> list[dict]:
    agora = datetime.now(timezone.utc)
    limite_inicio = (agora - timedelta(hours=49)).isoformat()
    limite_fim    = (agora - timedelta(hours=47)).isoformat()

    res = requests.get(
        f"{SUPABASE_URL}/rest/v1/jobs_campanha",
        headers=_sb_headers(),
        params={
            "status":       "eq.publicado",
            "publicado_em": f"gte.{limite_inicio}",
            "publicado_em": f"lte.{limite_fim}",
            "select":       "id,tema,score,clinica_id,instagram_post_id,publicado_em",
        },
    )
    res.raise_for_status()
    return res.json()


def buscar_clinica(clinica_id: str) -> dict:
    res = requests.get(
        f"{SUPABASE_URL}/rest/v1/clinicas",
        headers=_sb_headers(),
        params={
            "id":     f"eq.{clinica_id}",
            "select": "id,nome,instagram_access_token,historico_performance",
        },
    )
    res.raise_for_status()
    dados = res.json()
    return dados[0] if dados else {}


def atualizar_historico(clinica_id: str, historico_atual: list, novo_registro: dict) -> None:
    historico_atual = historico_atual or []
    historico_atual.append(novo_registro)
    requests.patch(
        f"{SUPABASE_URL}/rest/v1/clinicas",
        headers={**_sb_headers(), "Prefer": "return=minimal"},
        params={"id": f"eq.{clinica_id}"},
        json={"historico_performance": historico_atual},
    )


def marcar_analisado(job_id: str) -> None:
    requests.patch(
        f"{SUPABASE_URL}/rest/v1/jobs_campanha",
        headers={**_sb_headers(), "Prefer": "return=minimal"},
        params={"id": f"eq.{job_id}"},
        json={"status": "analisado"},
    )


# ─────────────────────────────────────────
# INSTAGRAM GRAPH API
# ─────────────────────────────────────────

def buscar_metricas_instagram(post_id: str, access_token: str) -> dict:
    campos = "like_count,comments_count,timestamp"
    res = requests.get(
        f"{GRAPH_API_BASE}/{post_id}",
        params={"fields": campos, "access_token": access_token},
        timeout=15,
    )
    if not res.ok:
        print(f"  [!] Erro ao buscar dados do post {post_id}: {res.text}")
        return {}
    dados = res.json()

    insights_res = requests.get(
        f"{GRAPH_API_BASE}/{post_id}/insights",
        params={
            "metric":       "reach,impressions,saved",
            "access_token": access_token,
        },
        timeout=15,
    )
    insights = {}
    if insights_res.ok:
        for item in insights_res.json().get("data", []):
            insights[item["name"]] = item.get("values", [{}])[0].get("value", 0)

    return {
        "likes":       dados.get("like_count", 0),
        "comentarios": dados.get("comments_count", 0),
        "alcance":     insights.get("reach", 0),
        "impressoes":  insights.get("impressions", 0),
        "salvamentos": insights.get("saved", 0),
    }


# ─────────────────────────────────────────
# CLAUDE — ANÁLISE DE PERFORMANCE
# ─────────────────────────────────────────

def analisar_com_claude(tema: str, metricas: dict, score_gerado: int) -> str:
    from anthropic import Anthropic
    client = Anthropic(api_key=ANTHROPIC_KEY)

    prompt = f"""Você é analista de marketing de clínicas de estética. Analise os resultados abaixo e gere uma conclusão direta e objetiva.

Tema da campanha: {tema}
Score gerado pelo revisor: {score_gerado}/10

Métricas coletadas 48h após publicação:
- Likes: {metricas.get('likes', 0)}
- Comentários: {metricas.get('comentarios', 0)}
- Alcance: {metricas.get('alcance', 0)}
- Impressões: {metricas.get('impressoes', 0)}
- Salvamentos: {metricas.get('salvamentos', 0)}

Gere UMA conclusão objetiva no formato:
"Alta performance — priorizar tema [tema]" OU "Baixa performance — evitar tema [tema]"

Seguida de 1-2 frases explicando o principal indicador que levou a essa conclusão.
Seja direto e prático."""

    res = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    return res.content[0].text.strip()


def inferir_sentimento(metricas: dict) -> str:
    score = (
        metricas.get("likes", 0) * 1
        + metricas.get("comentarios", 0) * 3
        + metricas.get("salvamentos", 0) * 5
    )
    if score >= 50:
        return "positivo"
    if score >= 10:
        return "neutro"
    return "negativo"


# ─────────────────────────────────────────
# FUNÇÃO PRINCIPAL
# ─────────────────────────────────────────

def run_analista():
    print(f"\n{'='*55}")
    print(f"  LeadSim MKT — Analista  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*55}\n")

    jobs = buscar_jobs_para_analisar()
    print(f"Jobs para analisar (48h): {len(jobs)}\n")

    if not jobs:
        print("  Nenhum job na janela de 48h.\n")
        return

    for job in jobs:
        job_id    = job["id"]
        tema      = job.get("tema", "")
        score     = job.get("score", 0) or 0
        clinica_id = job.get("clinica_id")
        post_id   = job.get("instagram_post_id")

        print(f"[{job_id[:8]}] Tema: {tema}")

        clinica = buscar_clinica(clinica_id) if clinica_id else {}
        access_token = clinica.get("instagram_access_token", "")

        if post_id and access_token:
            metricas = buscar_metricas_instagram(post_id, access_token)
            print(f"  Métricas: {metricas}")
        else:
            metricas = {"likes": 0, "alcance": 0, "impressoes": 0, "salvamentos": 0, "comentarios": 0}
            print("  Sem post_id ou access_token — métricas zeradas.")

        metricas["sentimento"] = inferir_sentimento(metricas)

        conclusao = analisar_com_claude(tema, metricas, score)
        print(f"  Conclusão: {conclusao}")

        registro = {
            "job_id":        job_id,
            "tema":          tema,
            "data":          datetime.now(timezone.utc).isoformat(),
            "score_gerado":  score,
            "metricas":      metricas,
            "conclusao":     conclusao,
        }

        historico = clinica.get("historico_performance") or []
        atualizar_historico(clinica_id, historico, registro)
        marcar_analisado(job_id)
        print(f"  Status → analisado. Histórico atualizado.\n")


if __name__ == "__main__":
    run_analista()
