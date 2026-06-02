from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Literal

from pipeline import executar_campanha

app = FastAPI(
    title="LeadSim MKT API",
    description="Sistema multi-agente de marketing para clínicas de estética",
    version="0.1.0",
)

FORMATOS_VALIDOS = Literal["instagram", "email", "whatsapp", "stories"]


class CampanhaRequest(BaseModel):
    tema: str = "harmonização facial com bioestimuladores"
    formatos: list[FORMATOS_VALIDOS] = ["instagram", "email", "whatsapp"]


@app.get("/")
def health():
    return {"status": "ok", "service": "LeadSim MKT API", "version": "0.1.0"}


@app.post("/campanha")
def gerar_campanha(req: CampanhaRequest):
    try:
        resultado = executar_campanha(tema=req.tema, formatos=list(req.formatos), verbose=False)
        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
