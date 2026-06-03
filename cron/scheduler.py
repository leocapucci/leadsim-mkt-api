"""
cron/scheduler.py
Agendador de automação LeadSim MKT via APScheduler.

Horários (America/Sao_Paulo):
  Segunda  15h → campanha para publicar às 18h
  Quarta   6h  → campanha para publicar às 9h
  Sexta    6h  → campanha para publicar às 9h
  Domingo  15h → campanha para publicar às 18h

Uso standalone: python cron/scheduler.py
Ou via FastAPI startup: importar start_scheduler() em api/main.py
"""

import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("leadsim.scheduler")

_scheduler: BackgroundScheduler | None = None


def _job_automacao():
    logger.info("[scheduler] Iniciando run_automacao...")
    try:
        from cron.automacao import run_automacao
        run_automacao()
        logger.info("[scheduler] run_automacao concluída.")
    except Exception as e:
        logger.error(f"[scheduler] Erro em run_automacao: {e}")


def _job_publicador():
    logger.info("[scheduler] Verificando publicações agendadas...")
    try:
        from cron.publicador import run_publicador
        run_publicador()
    except Exception as e:
        logger.error(f"[scheduler] Erro em run_publicador: {e}")


def start_scheduler() -> BackgroundScheduler:
    global _scheduler

    if _scheduler and _scheduler.running:
        logger.info("[scheduler] Scheduler já está rodando.")
        return _scheduler

    _scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")

    # Segunda-feira às 15h
    _scheduler.add_job(
        _job_automacao,
        trigger=CronTrigger(day_of_week="mon", hour=15, minute=0, timezone="America/Sao_Paulo"),
        id="automacao_segunda",
        name="Automação Segunda 15h",
        replace_existing=True,
    )

    # Quarta-feira às 6h
    _scheduler.add_job(
        _job_automacao,
        trigger=CronTrigger(day_of_week="wed", hour=6, minute=0, timezone="America/Sao_Paulo"),
        id="automacao_quarta",
        name="Automação Quarta 6h",
        replace_existing=True,
    )

    # Sexta-feira às 6h
    _scheduler.add_job(
        _job_automacao,
        trigger=CronTrigger(day_of_week="fri", hour=6, minute=0, timezone="America/Sao_Paulo"),
        id="automacao_sexta",
        name="Automação Sexta 6h",
        replace_existing=True,
    )

    # Domingo às 15h
    _scheduler.add_job(
        _job_automacao,
        trigger=CronTrigger(day_of_week="sun", hour=15, minute=0, timezone="America/Sao_Paulo"),
        id="automacao_domingo",
        name="Automação Domingo 15h",
        replace_existing=True,
    )

    # Publicador — a cada 5 minutos
    _scheduler.add_job(
        _job_publicador,
        trigger=IntervalTrigger(minutes=5),
        id="publicador_5min",
        name="Publicador Instagram 5min",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("[scheduler] APScheduler iniciado com 5 jobs agendados (4 automação + 1 publicador).")
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[scheduler] APScheduler encerrado.")


if __name__ == "__main__":
    import time
    logger.info("Iniciando scheduler em modo standalone...")
    start_scheduler()
    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        stop_scheduler()
