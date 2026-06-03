"""
agente_imagens.py
Agente especializado em geração de imagens para campanhas de clínicas de estética.
Usa DALL-E 3 via OpenAI API.

Fluxo:
1. Recebe briefing + conteúdo gerado pelo Copywriter
2. Cria prompts otimizados para cada formato (Instagram, WhatsApp, Stories)
3. Gera imagens via DALL-E 3
4. Retorna URLs das imagens
"""

import os
import json
import requests
from core import LeadSimAgent
from dotenv import load_dotenv

load_dotenv()


# ─────────────────────────────────────────
# CONFIGURAÇÕES POR FORMATO
# ─────────────────────────────────────────

FORMATOS_CONFIG = {
    "instagram": {
        "size": "1024x1024",
        "quantidade": 2,
        "descricao": "post quadrado para feed do Instagram"
    },
    "whatsapp": {
        "size": "1024x1024",
        "quantidade": 1,
        "descricao": "imagem para mensagem de WhatsApp"
    },
    "stories": {
        "size": "1024x1024",
        "quantidade": 2,
        "descricao": "stories vertical para Instagram/WhatsApp"
    },
    "email": {
        "size": "1024x1024",
        "quantidade": 1,
        "descricao": "banner horizontal para e-mail marketing"
    }
}


# ─────────────────────────────────────────
# AGENTE DE IMAGENS
# ─────────────────────────────────────────

class AgenteImagens(LeadSimAgent):

    def __init__(self):
        super().__init__(
            role="Agente de Imagens",
            goal="Criar prompts precisos e gerar imagens fotorrealistas para campanhas de clínicas de estética premium, respeitando as diretrizes do CFM e as restrições da OpenAI.",
            backstory="""Você é especialista em direção de arte para clínicas de estética premium no Brasil.
Conhece profundamente as restrições do CFM para publicidade médica e as políticas da OpenAI para imagens médicas.

REGRAS CRÍTICAS que você sempre segue:
- NUNCA gere imagens de procedimentos invasivos (agulhas, seringas, cirurgias, sangue)
- SEMPRE foque em resultados: beleza natural, pele radiante, autoestima, confiança
- Use ambientes premium: clínicas clean, iluminação suave, tons neutros e dourados
- Mulheres brasileiras reais (28-45 anos), expressão serena e confiante
- Estética médica premium: não é spa, não é salão — é clínica especializada
- Evite antes/depois explícito — mostre apenas o resultado positivo"""
        )

    def criar_prompts(self, briefing: str, formatos: list[str]) -> dict:
        """Cria prompts otimizados para DALL-E 3 baseados no briefing."""
        print(f"\n[imagens] criando prompts para: {', '.join(formatos)}")

        formatos_desc = "\n".join([
            f"- {f.upper()}: {FORMATOS_CONFIG.get(f, {}).get('descricao', f)}"
            for f in formatos
        ])

        task = f"""Com base no briefing abaixo, crie prompts fotorrealistas para DALL-E 3.

FORMATOS NECESSÁRIOS:
{formatos_desc}

BRIEFING DA CAMPANHA:
{briefing[:800]}

---

Para cada formato, crie um prompt em INGLÊS (DALL-E 3 performa melhor em inglês) que:
1. Mostre mulher brasileira (28-45 anos) com resultado de harmonização facial — pele radiante, expressão serena e confiante
2. Ambiente de clínica estética premium — clean, sofisticado, iluminação suave
3. Tonalidade: dourado suave, off-white, tons nude — estética premium brasileira
4. Estilo: fotografia editorial de alta qualidade, não stock photo genérico
5. NUNCA mencione procedimentos, agulhas, médicos realizando procedimentos

Retorne SOMENTE um JSON válido neste formato (sem markdown):
{{
  "instagram": "prompt detalhado aqui",
  "whatsapp": "prompt detalhado aqui",
  "stories": "prompt detalhado aqui",
  "email": "prompt detalhado aqui"
}}

Inclua apenas os formatos solicitados: {', '.join(formatos)}"""

        resultado = self.run(task)

        try:
            import re
            clean = re.sub(r"```json|```", "", resultado).strip()
            prompts = json.loads(clean)
        except Exception:
            prompt_base = "Brazilian woman 35 years old, radiant skin, natural beauty, serene confident expression, premium aesthetic clinic environment, soft golden lighting, clean white interior, editorial photography style, high quality, professional"
            prompts = {f: prompt_base for f in formatos}

        return prompts

    def gerar_imagem(self, prompt: str, size: str = "1024x1024") -> str | None:
        """Gera uma imagem via DALL-E 3 e retorna a URL."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("  [!] OPENAI_API_KEY nao configurada — pulando imagens")
            return None

        try:
            response = requests.post(
                "https://api.openai.com/v1/images/generations",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-image-2",
                    "prompt": prompt,
                    "n": 1,
                    "size": size,
                    "quality": "auto"
                },
                timeout=200
            )

            if response.status_code == 200:
                url = response.json()["data"][0]["url"]
                print("  [ok] imagem gerada")
                return url
            else:
                error = response.json().get("error", {}).get("message", "Erro desconhecido")
                print(f"  [x] Erro DALL-E: {error}")
                return None

        except Exception as e:
            print(f"  [x] Erro ao gerar imagem: {e}")
            return None

    def gerar_para_campanha(self, briefing: str, formatos: list[str]) -> dict:
        """Pipeline completo: cria prompts e gera imagens para todos os formatos."""
        print(f"\n[imagens] iniciando geração para {len(formatos)} formato(s)")

        formatos_com_imagem = [f for f in formatos if f in FORMATOS_CONFIG]
        if not formatos_com_imagem:
            return {}

        prompts = self.criar_prompts(briefing, formatos_com_imagem)

        imagens = {}
        for formato in formatos_com_imagem:
            if formato not in prompts:
                continue

            config = FORMATOS_CONFIG[formato]
            print(f"  gerando imagem para {formato}...")

            url = self.gerar_imagem(prompt=prompts[formato], size=config["size"])
            if url:
                imagens[formato] = {
                    "url": url,
                    "prompt_usado": prompts[formato],
                    "size": config["size"]
                }

        print(f"  {len(imagens)}/{len(formatos_com_imagem)} imagens geradas")
        return imagens
