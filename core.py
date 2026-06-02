"""
leadsim_agents/core.py
Base para todos os agentes do sistema LeadSim MKT.
Cada agente tem: papel, objetivo, ferramentas e um método run().
"""

import os
import json
import requests
from pathlib import Path
from anthropic import Anthropic
from dotenv import load_dotenv
from typing import Optional

_env_path = Path(__file__).parent / ".env"
load_dotenv(_env_path, override=True)
_api_key = os.getenv("ANTHROPIC_API_KEY")
if not _api_key:
    from dotenv import dotenv_values as _dv
    _api_key = _dv(_env_path).get("ANTHROPIC_API_KEY")

client = Anthropic(api_key=_api_key)
MODEL = "claude-sonnet-4-6"


# ─────────────────────────────────────────
# FERRAMENTAS COMPARTILHADAS
# ─────────────────────────────────────────

def web_search(query: str) -> str:
    """
    Busca na web usando a API do Brave Search.
    Substitua por SerpAPI, Tavily, ou qualquer outra.
    """
    api_key = os.getenv("BRAVE_SEARCH_API_KEY")
    if not api_key:
        return f"[SIMULADO] Resultados de busca para: {query}\n- Tendência 1: harmonização facial cresce 40% no Brasil em 2025\n- Tendência 2: bioestimuladores lideram procedimentos em clínicas premium\n- Tendência 3: conteúdo educativo gera 3x mais engajamento que promocional"

    resp = requests.get(
        "https://api.search.brave.com/res/v1/web/search",
        headers={"Accept": "application/json", "X-Subscription-Token": api_key},
        params={"q": query, "count": 5, "country": "BR", "lang": "pt-BR"},
        timeout=10
    )
    results = resp.json().get("web", {}).get("results", [])
    return "\n".join([f"- {r['title']}: {r['description']}" for r in results[:5]])


def save_to_memory(key: str, content: str, metadata: dict = None) -> str:
    """Salva resultado no Supabase para memória longa entre sessões."""
    try:
        from supabase import create_client
        sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
        sb.table("agent_memory").upsert({
            "key": key,
            "content": content,
            "metadata": metadata or {},
        }).execute()
        return f"Salvo na memória: {key}"
    except Exception as e:
        return f"[Memória indisponível - rodando sem Supabase]: {str(e)}"


def load_from_memory(key: str) -> str:
    """Recupera dado da memória longa no Supabase."""
    try:
        from supabase import create_client
        sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
        result = sb.table("agent_memory").select("content").eq("key", key).execute()
        if result.data:
            return result.data[0]["content"]
        return "Nenhuma memória encontrada para esta chave."
    except Exception:
        return "Memória indisponível."


# ─────────────────────────────────────────
# CLASSE BASE DOS AGENTES
# ─────────────────────────────────────────

class LeadSimAgent:
    """
    Agente base. Cada agente especializado herda desta classe.
    O método run() envia mensagens para Claude com o papel do agente
    definido no system prompt.
    """

    def __init__(self, role: str, goal: str, backstory: str):
        self.role = role
        self.goal = goal
        self.backstory = backstory
        self.history: list[dict] = []

    @property
    def system_prompt(self) -> str:
        brand_voice = os.getenv("LEADSIM_BRAND_VOICE", "profissional e acolhedor")
        target = os.getenv("LEADSIM_TARGET_AUDIENCE", "clínicas de estética no Brasil")
        return f"""Você é o {self.role} do sistema LeadSim MKT — uma plataforma de inteligência comercial para clínicas de estética e harmonização facial no Brasil.

Seu objetivo: {self.goal}

Contexto: {self.backstory}

Diretrizes da marca LeadSim:
- Voz da marca: {brand_voice}
- Público-alvo: {target}
- Produto principal: LeadSim Beauty / Chronos™ Link — análise de pele com IA para clínicas
- Sempre escreva em português brasileiro
- Seja específico, prático e orientado a resultados
- Nunca invente métricas ou estudos sem base

Quando receber uma tarefa, execute-a de forma completa e entregue o resultado final diretamente, sem perguntas desnecessárias."""

    def run(self, task: str, context: str = "") -> str:
        """
        Executa uma tarefa. O contexto pode conter resultados
        de agentes anteriores no pipeline.
        """
        user_message = task
        if context:
            user_message = f"CONTEXTO DOS AGENTES ANTERIORES:\n{context}\n\n---\n\nSUA TAREFA:\n{task}"

        self.history.append({"role": "user", "content": user_message})

        response = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            system=self.system_prompt,
            messages=self.history
        )

        result = response.content[0].text
        self.history.append({"role": "assistant", "content": result})
        return result

    def reset(self):
        """Limpa o histórico de conversa (nova campanha)."""
        self.history = []
