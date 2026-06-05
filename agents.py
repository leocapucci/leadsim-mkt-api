"""
leadsim_agents/agents.py
Os 3 agentes da Fase 0:
  1. Pesquisador  — inteligência de mercado e tendências
  2. Copywriter   — geração de conteúdo multi-canal
  3. Revisor      — qualidade, tom e aderência à marca
"""

from core import LeadSimAgent, web_search, save_to_memory, load_from_memory


# ─────────────────────────────────────────
# 1. PESQUISADOR
# ─────────────────────────────────────────

class Pesquisador(LeadSimAgent):

    def __init__(self, vertical: str = "estetica"):
        self.vertical = vertical
        super().__init__(
            role="Agente Pesquisador",
            goal="Levantar inteligência de mercado sobre o segmento de estética e harmonização facial para embasar campanhas do LeadSim Beauty.",
            backstory="Você é especialista em análise de mercado de saúde estética no Brasil. Conhece as principais clínicas, procedimentos em alta, sazonalidade do setor e comportamento de consumo do público de harmonização facial."
        )

    @property
    def system_prompt(self) -> str:
        if self.vertical == "politico":
            return "Você é um especialista em comunicação política e gestão pública brasileira. Pesquise sobre o tema considerando o contexto municipal brasileiro, realizações de gestão, obras públicas, serviços à população e agenda política local."
        return super().system_prompt

    def pesquisar_tendencias(self, tema: str) -> str:
        """Pesquisa tendências e contexto de mercado para um tema."""
        print(f"\n🔍 Pesquisador → buscando: {tema}")

        if self.vertical == "politico":
            tendencias = web_search(f"gestão pública {tema} prefeitura realizações obras 2024 2025")
            conteudo   = web_search(f"comunicação política {tema} redes sociais engajamento cidadãos")
        else:
            tendencias = web_search(f"tendências {tema} clínicas estética Brasil 2025")
            conteudo   = web_search(f"conteúdo marketing {tema} Instagram engajamento estética")

        if self.vertical == "politico":
            task = f"""Analise as informações abaixo e produza um briefing estruturado para o tema de gestão pública: "{tema}"

DADOS COLETADOS:
Contexto de gestão:
{tendencias}

Comunicação e engajamento:
{conteudo}

Entregue um briefing com:
1. **Contexto político/administrativo** (2-3 pontos mais relevantes)
2. **Oportunidades de comunicação** (o que a população quer ouvir)
3. **Ângulos de conteúdo** (3-5 ganchos para posts sobre realizações)
4. **Tom recomendado** (como comunicar ao cidadão)
5. **Palavras-chave e hashtags** (top 10 para o tema)"""
        else:
            task = f"""Analise as informações abaixo e produza um briefing de mercado estruturado para o tema: "{tema}"

DADOS COLETADOS:
Tendências do setor:
{tendencias}

Conteúdo de alto desempenho:
{conteudo}

Entregue um briefing com:
1. **Contexto de mercado** (2-3 pontos mais relevantes)
2. **Oportunidades para clínicas** (o que está em alta agora)
3. **Ângulos de conteúdo** (3-5 ganchos para posts e e-mails)
4. **Tom recomendado** (como falar com esse público nesse momento)
5. **Palavras-chave e hashtags** (top 10 para o tema)"""

        resultado = self.run(task)

        # Salva na memória para campanhas futuras
        save_to_memory(
            key=f"briefing_{tema.lower().replace(' ', '_')}",
            content=resultado,
            metadata={"tema": tema, "tipo": "briefing_mercado"}
        )

        return resultado


# ─────────────────────────────────────────
# 2. COPYWRITER
# ─────────────────────────────────────────

class Copywriter(LeadSimAgent):

    def __init__(self, vertical: str = "estetica"):
        self.vertical = vertical
        super().__init__(
            role="Agente Copywriter",
            goal="Criar conteúdo persuasivo e autêntico para clínicas de harmonização facial — posts, e-mails e scripts de WhatsApp que convertem.",
            backstory="Você é copywriter especializado em marketing de saúde estética e procedimentos de harmonização facial. Domina a linguagem do público que busca procedimentos premium, sabe equilibrar aspiração com credibilidade médica e conhece as restrições do CFM para publicidade na área de saúde."
        )

    @property
    def system_prompt(self) -> str:
        if self.vertical == "politico":
            return "Você é um especialista em comunicação política de gestão pública. Crie conteúdo que destaque realizações, obras e serviços do gestor público para a população. Tom: próximo do cidadão, direto, sem juridiquês, inspirador. NUNCA crie conteúdo de ataque a adversários, fake news ou conteúdo eleitoral de campanha. Foque em gestão e realizações concretas."
        return super().system_prompt

    def gerar_conteudo(self, briefing: str, formatos: list[str] = None, perfil_clinica: dict = None) -> dict:
        """
        Gera conteúdo em múltiplos formatos a partir de um briefing.
        formatos: lista de ['instagram', 'email', 'whatsapp', 'stories']
        """
        if formatos is None:
            formatos = ["instagram", "email", "whatsapp"]

        print(f"\n✍️  Copywriter → gerando {', '.join(formatos)}")

        formatos_instrucoes = {
            "instagram": "3 posts para feed (legenda + 5 hashtags cada, máx 2.200 chars)",
            "email": "1 e-mail de campanha (assunto + corpo, tom consultivo, CTA claro)",
            "whatsapp": "2 mensagens de WhatsApp (curtas, diretas, com emoji moderado, máx 300 chars cada)",
            "stories": "3 frames de Stories (texto curto por frame, narrativa sequencial)"
        }

        instrucoes_selecionadas = "\n".join([
            f"- **{f.upper()}**: {formatos_instrucoes.get(f, f)}"
            for f in formatos
        ])

        perfil_bloco = ""
        if perfil_clinica:
            perfil_bloco = f"""
PERFIL DA CLÍNICA:
Clínica: {perfil_clinica.get('nome', '')}
Especialidades: {perfil_clinica.get('especialidades', '')}
Público-alvo: {perfil_clinica.get('publico_alvo', '')}
Tom de voz: {perfil_clinica.get('tom_de_voz', '')}
Gere o conteúdo respeitando exatamente esse tom de voz e focando nessas especialidades para esse público.
"""

        task = f"""Com base no briefing abaixo, crie o seguinte conteúdo de marketing para clínicas de harmonização facial:

{instrucoes_selecionadas}
{perfil_bloco}
IMPORTANTE:
- Nunca prometa resultados garantidos (restrição CFM)
- Use linguagem que valoriza a expertise do médico/clínica
- O LeadSim Beauty / Chronos™ pode ser mencionado como tecnologia diferencial da clínica
- Inclua CTAs claros (agendar avaliação, conhecer o procedimento, etc.)

BRIEFING:
{briefing}"""

        resultado = self.run(task)

        # Estrutura o resultado por formato
        conteudo_por_formato = {
            "raw": resultado,
            "formatos": formatos,
            "briefing_usado": briefing[:200] + "..."
        }

        save_to_memory(
            key=f"conteudo_{formatos[0]}_{hash(briefing) % 10000}",
            content=resultado,
            metadata={"formatos": formatos, "tipo": "conteudo_gerado"}
        )

        return conteudo_por_formato


# ─────────────────────────────────────────
# 3. REVISOR
# ─────────────────────────────────────────

class Revisor(LeadSimAgent):

    def __init__(self, vertical: str = "estetica"):
        self.vertical = vertical
        super().__init__(
            role="Agente Revisor",
            goal="Garantir que todo conteúdo gerado seja de alta qualidade, esteja alinhado com a marca LeadSim, respeite as normas do CFM e seja aprovado antes de qualquer publicação.",
            backstory="Você é editor sênior especializado em comunicação médica e marketing de saúde estética. Conhece profundamente as normas do CFM para publicidade médica, os padrões de comunicação premium, e tem olhar aguçado para inconsistências de tom, promessas indevidas e oportunidades de melhoria."
        )

        if self.vertical == "politico":
            self.criterios = {
                "tom_publico": "Próximo do cidadão, direto, sem juridiquês, inspirador e acessível.",
                "foco_gestao": "Conteúdo é de gestão e realizações concretas — NÃO é de campanha eleitoral.",
                "sem_ataques": "Ausência total de ataques a adversários, críticas políticas ou conteúdo negativo.",
                "clareza_cta": "O próximo passo para o cidadão deve ser claro (acompanhar, conhecer, participar).",
                "relevancia":  "O conteúdo é pertinente às realizações e ao público-alvo do gestor.",
            }
        else:
            self.criterios = {
                "tom_marca": "Sofisticado, acolhedor, especialista. Evita excessos de gírias ou promessas agressivas.",
                "conformidade_cfm": "Sem promessas de resultados garantidos. Sem 'antes e depois' explícito no texto. Foco na expertise.",
                "clareza_cta": "O próximo passo para o leitor deve ser óbvio e não-invasivo.",
                "autenticidade": "Linguagem natural, não robótica. Parece escrito por um humano especialista.",
                "relevancia": "O conteúdo é pertinente ao momento do mercado e ao público-alvo.",
            }

    def revisar(self, conteudo: str, briefing: str = "", perfil_clinica: dict = None) -> dict:
        """
        Revisa o conteúdo. Retorna:
        - aprovado: bool
        - score: 1-10
        - problemas: lista
        - conteudo_revisado: versão corrigida (se necessário)
        """
        print(f"\n🔎 Revisor → avaliando conteúdo...")

        criterios_texto = "\n".join([
            f"- **{k.replace('_', ' ').title()}**: {v}"
            for k, v in self.criterios.items()
        ])

        perfil_bloco = ""
        if perfil_clinica:
            perfil_bloco = f"""
PERFIL DA CLÍNICA:
Clínica: {perfil_clinica.get('nome', '')}
Especialidades: {perfil_clinica.get('especialidades', '')}
Público-alvo: {perfil_clinica.get('publico_alvo', '')}
Tom de voz: {perfil_clinica.get('tom_de_voz', '')}
Avalie se o conteúdo está adequado a esse tom de voz e a esse público-alvo.
"""

        task = f"""Revise o conteúdo de marketing abaixo com critério rigoroso.

CRITÉRIOS DE AVALIAÇÃO:
{criterios_texto}
{perfil_bloco}
{"BRIEFING ORIGINAL:" + chr(10) + briefing if briefing else ""}

CONTEÚDO PARA REVISÃO:
{conteudo}

Avalie cada critério, identifique problemas, e entregue a versão revisada completa do conteúdo."""

        schema = {
            "type": "object",
            "properties": {
                "aprovado":          {"type": "boolean", "description": "true se score >= 7"},
                "score":             {"type": "integer", "minimum": 0, "maximum": 10},
                "problemas":         {"type": "array", "items": {"type": "string"}},
                "sugestoes":         {"type": "array", "items": {"type": "string"}},
                "conteudo_revisado": {"type": "string", "description": "Conteúdo completo revisado"},
                "notas_revisao":     {"type": "string"},
            },
            "required": ["aprovado", "score", "problemas", "sugestoes", "conteudo_revisado", "notas_revisao"],
        }

        try:
            resultado = self.run_structured(task, schema, tool_name="submeter_revisao")
            # Garantir tipos corretos
            resultado["score"] = int(resultado.get("score", 0))
            resultado["aprovado"] = bool(resultado.get("aprovado", False))
        except Exception as e:
            resultado = {
                "aprovado": False,
                "score": 0,
                "problemas": [f"Erro na revisão estruturada: {e}"],
                "sugestoes": [],
                "conteudo_revisado": conteudo,
                "notas_revisao": str(e),
            }

        return resultado

    def revisar_com_reescrita(self, conteudo: str, briefing: str = "", max_tentativas: int = 2, perfil_clinica: dict = None) -> dict:
        """
        Loop de revisão: se reprovado, pede reescrita ao Copywriter
        e revisa novamente. Retorna resultado final.
        """
        copywriter = Copywriter(vertical=self.vertical)

        tentativa = 1
        resultado = self.revisar(conteudo, briefing, perfil_clinica)

        while not resultado.get("aprovado") and tentativa <= max_tentativas:
            print(f"\n🔄 Revisor → reprovado (score {resultado.get('score')}). Tentativa {tentativa}/{max_tentativas}")
            print(f"   Problemas: {resultado.get('problemas', [])}")

            # Pede reescrita direcionada
            problemas = "\n".join([f"- {p}" for p in resultado.get("problemas", [])])
            sugestoes = "\n".join([f"- {s}" for s in resultado.get("sugestoes", [])])

            reescrita_task = f"""O revisor apontou os seguintes problemas no conteúdo. Corrija-os e reescreva:

PROBLEMAS ENCONTRADOS:
{problemas}

SUGESTÕES DO REVISOR:
{sugestoes}

CONTEÚDO ORIGINAL:
{conteudo}

{"BRIEFING:" + chr(10) + briefing if briefing else ""}

Entregue o conteúdo completamente reescrito, corrigindo todos os problemas apontados."""

            conteudo = copywriter.run(reescrita_task)
            resultado = self.revisar(conteudo, briefing, perfil_clinica)
            tentativa += 1

        resultado["tentativas"] = tentativa
        return resultado
