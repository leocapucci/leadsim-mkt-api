"""
leadsim_agents/pipeline.py

Orquestrador da Fase 0:
  Pesquisador → Copywriter → Revisor (com loop automático)

Uso:
  python pipeline.py

  ou com objetivo customizado:
  python pipeline.py --tema "bioestimuladores" --formatos instagram email whatsapp
"""

import argparse
import json
import os
from datetime import datetime
from agents import Pesquisador, Copywriter, Revisor


# ─────────────────────────────────────────
# PIPELINE PRINCIPAL
# ─────────────────────────────────────────

def executar_campanha(tema: str, formatos: list[str], verbose: bool = True) -> dict:
    """
    Executa o pipeline completo:
    1. Pesquisador levanta briefing de mercado
    2. Copywriter gera conteúdo baseado no briefing
    3. Revisor avalia e, se necessário, aciona reescrita (até 2x)

    Retorna dicionário com tudo que foi produzido.
    """

    separador = "─" * 55
    inicio = datetime.now()

    print(f"\n{separador}")
    print(f"  LeadSim MKT — Pipeline de Campanha")
    print(f"  Tema: {tema}")
    print(f"  Formatos: {', '.join(formatos)}")
    print(f"  Início: {inicio.strftime('%H:%M:%S')}")
    print(separador)

    # ── ETAPA 1: PESQUISA ──────────────────
    print("\n[1/3] Pesquisando mercado...")
    pesquisador = Pesquisador()
    briefing = pesquisador.pesquisar_tendencias(tema)

    if verbose:
        print(f"\n{'─'*40}")
        print("BRIEFING GERADO:")
        print(briefing)

    # ── ETAPA 2: GERAÇÃO DE CONTEÚDO ──────
    print("\n[2/3] Gerando conteúdo...")
    copywriter = Copywriter()
    resultado_copy = copywriter.gerar_conteudo(briefing, formatos)
    conteudo_inicial = resultado_copy["raw"]

    if verbose:
        print(f"\n{'─'*40}")
        print("CONTEÚDO INICIAL:")
        print(conteudo_inicial)

    # ── ETAPA 3: REVISÃO COM LOOP ──────────
    print("\n[3/3] Revisando conteúdo...")
    revisor = Revisor()
    resultado_revisao = revisor.revisar_com_reescrita(
        conteudo=conteudo_inicial,
        briefing=briefing,
        max_tentativas=2
    )

    # ── RESULTADO FINAL ────────────────────
    duracao = (datetime.now() - inicio).seconds
    aprovado = resultado_revisao.get("aprovado", False)
    score = resultado_revisao.get("score", 0)
    conteudo_final = resultado_revisao.get("conteudo_revisado", conteudo_inicial)

    print(f"\n{separador}")
    print(f"  CAMPANHA CONCLUÍDA")
    print(f"  Status: {'✅ APROVADA' if aprovado else '⚠️  APROVADA COM RESSALVAS'}")
    print(f"  Score: {score}/10")
    print(f"  Tentativas de revisão: {resultado_revisao.get('tentativas', 1)}")
    print(f"  Duração total: {duracao}s")
    print(separador)

    if verbose:
        print(f"\n{'─'*40}")
        print("CONTEÚDO FINAL APROVADO:")
        print(conteudo_final)
        print(f"\nNOTAS DO REVISOR: {resultado_revisao.get('notas_revisao', '')}")

    # Salva output em arquivo
    output = {
        "meta": {
            "tema": tema,
            "formatos": formatos,
            "data": inicio.isoformat(),
            "duracao_segundos": duracao,
            "score_final": score,
            "aprovado": aprovado,
            "tentativas": resultado_revisao.get("tentativas", 1)
        },
        "briefing": briefing,
        "conteudo_final": conteudo_final,
        "notas_revisao": resultado_revisao.get("notas_revisao", ""),
        "problemas_encontrados": resultado_revisao.get("problemas", []),
    }

    # Salva JSON com a campanha
    filename = f"campanha_{tema.lower().replace(' ', '_')}_{inicio.strftime('%Y%m%d_%H%M')}.json"
    output_path = os.path.join("output", filename)
    os.makedirs("output", exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n💾 Campanha salva em: {output_path}")

    return output


# ─────────────────────────────────────────
# CLI
# ─────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LeadSim MKT — Pipeline de Campanha")
    parser.add_argument(
        "--tema",
        type=str,
        default="harmonização facial com bioestimuladores",
        help="Tema da campanha (ex: 'bioestimuladores', 'skincare inverno')"
    )
    parser.add_argument(
        "--formatos",
        nargs="+",
        default=["instagram", "email", "whatsapp"],
        choices=["instagram", "email", "whatsapp", "stories"],
        help="Formatos de conteúdo a gerar"
    )
    parser.add_argument(
        "--silencioso",
        action="store_true",
        help="Não imprime conteúdo intermediário, só o resultado final"
    )

    args = parser.parse_args()

    executar_campanha(
        tema=args.tema,
        formatos=args.formatos,
        verbose=not args.silencioso
    )
