"""
leadsim_agents/pipeline.py

Orquestrador Fase 0 + Agente de Imagens:
  Pesquisador -> Copywriter -> Agente de Imagens -> Revisor
"""

import argparse
import json
import os
import sys
from datetime import datetime
from agents import Pesquisador, Copywriter, Revisor

# Fix encoding no Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def executar_campanha(tema: str, formatos: list[str], verbose: bool = True) -> dict:

    separador = "-" * 55
    inicio = datetime.now()

    print(f"\n{separador}")
    print(f"  LeadSim MKT - Pipeline de Campanha")
    print(f"  Tema: {tema}")
    print(f"  Formatos: {', '.join(formatos)}")
    print(f"  Inicio: {inicio.strftime('%H:%M:%S')}")
    print(separador)

    # ETAPA 1: PESQUISA
    print("\n[1/3] Pesquisando mercado...")
    pesquisador = Pesquisador()
    briefing = pesquisador.pesquisar_tendencias(tema)

    if verbose:
        print(f"\n{'-'*40}")
        print("BRIEFING GERADO:")
        print(briefing)

    # ETAPA 2: GERAÇÃO DE CONTEÚDO
    print("\n[2/3] Gerando conteudo...")
    copywriter = Copywriter()
    resultado_copy = copywriter.gerar_conteudo(briefing, formatos)
    conteudo_inicial = resultado_copy["raw"]

    if verbose:
        print(f"\n{'-'*40}")
        print("CONTEUDO INICIAL:")
        print(conteudo_inicial)

    # ETAPA 3: REVISÃO
    print("\n[3/3] Revisando conteudo...")
    revisor = Revisor()
    resultado_revisao = revisor.revisar_com_reescrita(
        conteudo=conteudo_inicial,
        briefing=briefing,
        max_tentativas=1
    )

    # RESULTADO FINAL
    duracao = (datetime.now() - inicio).seconds
    aprovado = resultado_revisao.get("aprovado", False)
    score = resultado_revisao.get("score", 0)
    conteudo_final = resultado_revisao.get("conteudo_revisado", conteudo_inicial)

    print(f"\n{separador}")
    print(f"  CAMPANHA CONCLUIDA")
    print(f"  Score: {score}/10")
    print(f"  Duracao total: {duracao}s")
    print(separador)

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

    # Salva JSON
    slug = tema.lower().replace(' ', '_')[:50]
    filename = f"campanha_{slug}_{inicio.strftime('%Y%m%d_%H%M')}.json"
    output_path = os.path.join("output", filename)
    os.makedirs("output", exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nCampanha salva em: {output_path}")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LeadSim MKT - Pipeline de Campanha")
    parser.add_argument("--tema", type=str, default="harmonizacao facial com bioestimuladores")
    parser.add_argument("--formatos", nargs="+", default=["instagram", "whatsapp"],
                        choices=["instagram", "email", "whatsapp", "stories"])
    parser.add_argument("--silencioso", action="store_true")

    args = parser.parse_args()
    executar_campanha(
        tema=args.tema,
        formatos=args.formatos,
        verbose=not args.silencioso,
    )
