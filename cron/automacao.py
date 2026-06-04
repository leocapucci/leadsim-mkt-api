"""
cron/automacao.py
Automação periódica de campanhas LeadSim MKT.

Fluxo por clínica:
  1. Busca clínicas ativas (campanha_ativa = true)
  2. Escolhe tema não usado nas últimas 2 semanas
  3. Gera campanha via pipeline (polling)
  4. Dispara geração de imagens
  5. Envia WhatsApp para whatsapp_responsavel
  6. Marca job como "aguardando_aprovacao"

Uso: python cron/automacao.py
"""

import os
import sys
import time
import random
import requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

SUPABASE_URL       = os.getenv("SUPABASE_URL")
SUPABASE_KEY       = os.getenv("SUPABASE_KEY")
API_BASE           = os.getenv("API_BASE_URL", "https://leadsim-mkt-api.onrender.com")
API_KEY            = os.getenv("LEADSIM_INTERNAL_KEY", "leadsim-dev-key")
# EVOLUTION_URL      = os.getenv("EVOLUTION_API_URL", "http://localhost:8080")
# EVOLUTION_KEY      = os.getenv("EVOLUTION_API_KEY", "")
# EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "chronos")
WHATSAPP_TOKEN    = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "")
FRONTEND_URL       = "https://leadsim-beauty.vercel.app"

POLL_INTERVAL = 10    # segundos entre polls
POLL_TIMEOUT  = 600   # timeout máximo (10 min)


# ─────────────────────────────────────────
# SUPABASE HELPERS
# ─────────────────────────────────────────

def _sb_headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def buscar_clinicas_ativas() -> list[dict]:
    res = requests.get(
        f"{SUPABASE_URL}/rest/v1/clinicas",
        headers=_sb_headers(),
        params={
            "campanha_ativa": "eq.true",
            "select": "id,nome,whatsapp_responsavel,temas_campanha,formatos_campanha",
        },
    )
    res.raise_for_status()
    return res.json()


def temas_usados_recentemente(clinica_id: str) -> set[str]:
    duas_semanas_atras = (datetime.now(timezone.utc) - timedelta(weeks=2)).isoformat()
    res = requests.get(
        f"{SUPABASE_URL}/rest/v1/jobs_campanha",
        headers=_sb_headers(),
        params={
            "clinica_id": f"eq.{clinica_id}",
            "criado_em": f"gte.{duas_semanas_atras}",
            "select": "tema",
        },
    )
    res.raise_for_status()
    return {row["tema"] for row in res.json()}


def marcar_aguardando_aprovacao(job_id: str) -> None:
    requests.patch(
        f"{SUPABASE_URL}/rest/v1/jobs_campanha",
        headers={**_sb_headers(), "Prefer": "return=minimal"},
        params={"id": f"eq.{job_id}"},
        json={"status": "aguardando_aprovacao"},
    )


def marcar_job_erro(job_id: str, erro: str) -> None:
    requests.patch(
        f"{SUPABASE_URL}/rest/v1/jobs_campanha",
        headers={**_sb_headers(), "Prefer": "return=minimal"},
        params={"id": f"eq.{job_id}"},
        json={"status": "erro", "erro": erro[:500]},
    )


def marcar_erro_whatsapp(job_id: str) -> None:
    requests.patch(
        f"{SUPABASE_URL}/rest/v1/jobs_campanha",
        headers={**_sb_headers(), "Prefer": "return=minimal"},
        params={"id": f"eq.{job_id}"},
        json={"status": "aguardando_aprovacao", "erro": "WhatsApp não entregue — aprovação manual necessária"},
    )


# ─────────────────────────────────────────
# LÓGICA DE TEMA
# ─────────────────────────────────────────

def escolher_tema(temas: list[str], usados: set[str]) -> str | None:
    disponiveis = [t for t in temas if t not in usados]
    if not disponiveis:
        disponiveis = temas  # todos recentemente usados: repete aleatório
    return random.choice(disponiveis) if disponiveis else None


# ─────────────────────────────────────────
# CHAMADAS AO BACKEND
# ─────────────────────────────────────────

def criar_campanha(tema: str, formatos: list[str], clinica_id: str) -> str:
    """Inicia a campanha e retorna job_id."""
    res = requests.post(
        f"{API_BASE}/campanha",
        headers={"x-api-key": API_KEY, "Content-Type": "application/json"},
        json={"tema": tema, "formatos": formatos, "clinica_id": clinica_id},
        timeout=30,
    )
    res.raise_for_status()
    return res.json()["job_id"]


def aguardar_conclusao(job_id: str) -> dict:
    """Polling até status = concluido ou erro. Retorna o job completo."""
    inicio = time.time()
    while True:
        res = requests.get(
            f"{API_BASE}/campanha/status/{job_id}",
            headers={"x-api-key": API_KEY},
            timeout=15,
        )
        res.raise_for_status()
        job = res.json()
        status = job.get("status")

        if status == "concluido":
            return job
        if status == "erro":
            raise RuntimeError(f"Pipeline falhou: {job.get('erro', 'desconhecido')}")
        if time.time() - inicio > POLL_TIMEOUT:
            raise TimeoutError(f"Timeout aguardando job {job_id}")

        print(f"  [{job_id[:8]}] status={status} — aguardando {POLL_INTERVAL}s...")
        time.sleep(POLL_INTERVAL)


def gerar_imagens(job_id: str) -> None:
    """Dispara geração de imagens (fire-and-forget no backend)."""
    res = requests.post(
        f"{API_BASE}/campanha/{job_id}/imagens",
        headers={"x-api-key": API_KEY},
        timeout=30,
    )
    if not res.ok:
        print(f"  [!] Aviso: falha ao disparar imagens para {job_id}: {res.text}")


# ─────────────────────────────────────────
# WHATSAPP
# ─────────────────────────────────────────

def enviar_whatsapp(telefone: str, clinica_nome: str, tema: str, conteudo: str, job_id: str) -> bool:
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        print("  [!] WHATSAPP_TOKEN ou WHATSAPP_PHONE_ID não configurados")
        return False

    aprovacao_url = f"https://leadsim-mkt-api.onrender.com/campanha/aprovar/{job_id}"
    mensagem = (
        f"🎯 *LeadSim Agente MKT*\n\n"
        f"Nova campanha gerada para *{clinica_nome}*\n"
        f"Tema: {tema}\n\n"
        f"Acesse para aprovar ou reprovar:\n{aprovacao_url}"
    )

    try:
        response = requests.post(
            f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_ID}/messages",
            headers={
                "Authorization": f"Bearer {WHATSAPP_TOKEN}",
                "Content-Type": "application/json"
            },
            json={
                "messaging_product": "whatsapp",
                "to": telefone,
                "type": "text",
                "text": {"body": mensagem}
            },
            timeout=30
        )
        if response.status_code == 200:
            print(f"  WhatsApp ✓ enviado → {telefone}")
            return True
        else:
            print(f"  [x] Erro WhatsApp: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"  [!] Erro ao enviar WhatsApp para {telefone}: {e}")
        return False


# ─────────────────────────────────────────
# FUNÇÃO PRINCIPAL
# ─────────────────────────────────────────

def run_automacao():
    print(f"\n{'='*55}")
    print(f"  LeadSim MKT — Automação  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*55}\n")

    clinicas = buscar_clinicas_ativas()
    print(f"Clínicas ativas: {len(clinicas)}\n")

    for clinica in clinicas:
        cid      = clinica["id"]
        nome     = clinica["nome"]
        tel      = clinica.get("whatsapp_responsavel", "")
        temas    = clinica.get("temas_campanha") or []
        formatos = clinica.get("formatos_campanha") or ["instagram", "whatsapp"]

        print(f"[{nome}]")

        if not temas:
            print("  Sem temas configurados — pulando.\n")
            continue

        usados = temas_usados_recentemente(cid)
        tema   = escolher_tema(temas, usados)
        if not tema:
            print("  Nenhum tema disponível — pulando.\n")
            continue

        print(f"  Tema escolhido: {tema}")

        job_id = None
        try:
            job_id = criar_campanha(tema, formatos, cid)
            print(f"  Job criado: {job_id}")

            job = aguardar_conclusao(job_id)
            print(f"  Campanha concluída. Score: {job.get('score')}")

            gerar_imagens(job_id)
            print(f"  Imagens disparadas.")

            if tel:
                ok = enviar_whatsapp(tel, nome, tema, job.get("conteudo_final", ""), job_id)
                if not ok:
                    print(f"  WhatsApp FALHOU — aguardando 30s e tentando novamente...")
                    time.sleep(30)
                    ok = enviar_whatsapp(tel, nome, tema, job.get("conteudo_final", ""), job_id)

                if ok:
                    print(f"  WhatsApp ✓ enviado → {tel}")
                else:
                    print(f"  WhatsApp FALHOU após 2 tentativas — marcando erro_whatsapp")
                    marcar_erro_whatsapp(job_id)
            else:
                print("  Sem whatsapp_responsavel configurado.")

            marcar_aguardando_aprovacao(job_id)
            print(f"  Status: aguardando_aprovacao\n")

        except Exception as e:
            print(f"  ERRO: {e}\n")
            if job_id:
                marcar_job_erro(job_id, str(e))


if __name__ == "__main__":
    run_automacao()
