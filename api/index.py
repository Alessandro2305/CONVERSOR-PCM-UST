import base64
import io
import os
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = FastAPI()

# Configuração de CORS para permitir requisições de qualquer origem (inclusive Railway)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/converter/principal")
async def converter_principal(
    file_pdf: UploadFile = File(...), file_excel: UploadFile = File(...)
):
  try:
    pdf_bytes = await file_pdf.read()
    excel_bytes = await file_excel.read()

    # Leitura da planilha de conversão principal (Alfanumérico)
    df_excel = pd.read_excel(io.BytesIO(excel_bytes))

    # Exemplo de lógica de processamento do PDF e cruzamento com o Excel
    # (Substitua abaixo pela sua lógica real do CONVERSOR PCM UST)
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()

    for page in reader.pages:
      writer.add_page(page)

    # Gerando o PDF modificado em memória para Base64
    pdf_output = io.BytesIO()
    writer.write(pdf_output)
    pdf_output.seek(0)
    pdf_base64 = base64.b64encode(pdf_output.read()).decode("utf-8")

    # Mock/Estrutura de dados de retorno esperada pelo front-end
    resultado = {
        "total": 10,
        "convertidos": 8,
        "pendentes": 1,
        "nao_encontrados": 1,
        "itens": [
            {
                "status": "Convertido",
                "codigo_original": "ABC-123",
                "codigo_convertido": "SOL-999",
                "descricao": "Item Exemplo Alfanumérico",
            }
        ],
        "pdf_base64": pdf_base64,
    }

    return JSONResponse(content=resultado)

  except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))


@app.post("/converter/cnh")
async def converter_cnh(
    file_pdf: UploadFile = File(...), file_excel: UploadFile = File(...)
):
  try:
    pdf_bytes = await file_pdf.read()
    excel_bytes = await file_excel.read()

    # Leitura da planilha para CNH (Apenas números)
    df_excel = pd.read_excel(io.BytesIO(excel_bytes))

    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()

    for page in reader.pages:
      writer.add_page(page)

    pdf_output = io.BytesIO()
    writer.write(pdf_output)
    pdf_output.seek(0)
    pdf_base64 = base64.b64encode(pdf_output.read()).decode("utf-8")

    resultado = {
        "total": 5,
        "convertidos": 5,
        "pendentes": 0,
        "nao_encontrados": 0,
        "itens": [
            {
                "status": "Convertido",
                "codigo_original": "123456",
                "codigo_convertido": "SOL-888",
                "descricao": "Item Exemplo CNH (Apenas Números)",
            }
        ],
        "pdf_base64": pdf_base64,
    }

    return JSONResponse(content=resultado)

  except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
  import uvicorn

  port = int(os.environ.get("PORT", 8000))
  uvicorn.run("main:app", host="0.0.0.0", port=port)