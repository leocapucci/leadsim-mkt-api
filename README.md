# LeadSim MKT — Agentes de IA (Fase 0)

Sistema multi-agente para geração de campanhas de marketing para clínicas de estética e harmonização facial.

## Arquitetura (Fase 0)

```
Pesquisador → Copywriter → Revisor (loop automático)
```

## Setup

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Configurar variáveis de ambiente
cp .env.example .env
# Edite o .env com suas chaves
```

### Variáveis obrigatórias
| Variável | Onde pegar |
|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com |
| `SUPABASE_URL` | Já tem: `ihxuxmkznmfxcqofzqpe.supabase.co` |
| `SUPABASE_KEY` | Dashboard Supabase → Settings → API |

### Variável opcional (mas recomendada)
| Variável | Onde pegar |
|---|---|
| `BRAVE_SEARCH_API_KEY` | api.search.brave.com (free tier: 2k buscas/mês) |

> Sem a chave Brave, o pesquisador usa dados simulados mas ainda funciona.

## Uso

### Campanha padrão
```bash
python pipeline.py
```

### Campanha com tema e formatos específicos
```bash
python pipeline.py --tema "skinbooster e hidratação profunda" --formatos instagram email
```

### Apenas Instagram
```bash
python pipeline.py --tema "toxina botulínica inverno 2025" --formatos instagram stories
```

### Modo silencioso (só resultado final)
```bash
python pipeline.py --tema "bioestimuladores" --silencioso
```

## Estrutura de arquivos

```
leadsim-agents/
├── core.py          # Classe base LeadSimAgent + ferramentas compartilhadas
├── agents.py        # Pesquisador, Copywriter, Revisor
├── pipeline.py      # Orquestrador + CLI
├── requirements.txt
├── .env.example
└── output/          # Campanhas geradas (JSON) — criado automaticamente
```

## Output

Cada campanha gera um arquivo `output/campanha_TEMA_DATA.json` com:
- `briefing` — inteligência de mercado do pesquisador
- `conteudo_final` — conteúdo aprovado pelo revisor
- `score_final` — nota de 1 a 10
- `notas_revisao` — feedback do revisor
- `meta` — dados da execução (tempo, tentativas, etc.)

## Supabase — tabela de memória

Para ativar memória longa entre campanhas, crie esta tabela:

```sql
create table agent_memory (
  id uuid default gen_random_uuid() primary key,
  key text unique not null,
  content text not null,
  metadata jsonb default '{}',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
```

## Próximos passos (Fase 1)

- [ ] LangGraph para orquestração com estado persistente
- [ ] Agente Publicador (n8n → WhatsApp + e-mail)
- [ ] Agente Analista (métricas + loop de feedback)
- [ ] Modo agendado (cron job no Vercel ou Render)
