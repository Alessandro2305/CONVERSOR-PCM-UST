from fastapi import APIRouter, File, HTTPException, UploadFile
import os
import re
import pandas as pd
from pypdf import PdfReader, PdfWriter 
import base64

router = APIRouter()

TEMP_DIR = "temp_output"
os.makedirs(TEMP_DIR, exist_ok=True)

def processar_pdf_com_regras(pdf_path: str, df_excel: pd.DataFrame, modo: str) -> str:
    """
    Processa o PDF aplicando a regra correspondente à aba.
    modo == 'principal': busca códigos alfanuméricos (letras + números)
    modo == 'cnh': ignora letras, buscando apenas padrões numéricos puros
    """
    reader = PdfReader(pdf_path)
    writer = PdfWriter()

    for page in reader.pages:
        text = page.extract_text() or ""
        
        if modo == "principal":
            codigos_encontrados = re.findall(r"\b[A-Z0-9]{4,}\b", text)
        elif modo == "cnh":
            codigos_encontrados = re.findall(r"\b\d{4,}\b", text)
            
        # Lógica de substituição do PDF entra aqui...
        writer.add_page(page)

    output_pdf_path = os.path.join(TEMP_DIR, f"convertido_{modo}.pdf")
    with open(output_pdf_path, "wb") as output_file:
        writer.write(output_file)

    return output_pdf_path


@router.post("/converter/principal")
async def converter_principal(
    file_pdf: UploadFile = File(...), file_excel: UploadFile = File(...)
):
    try:
        pdf_path = os.path.join(TEMP_DIR, file_pdf.filename)
        excel_path = os.path.join(TEMP_DIR, file_excel.filename)

        with open(pdf_path, "wb") as buffer:
            buffer.write(await file_pdf.read())
        with open(excel_path, "wb") as buffer:
            buffer.write(await file_excel.read())

        df_excel = pd.read_excel(excel_path)

        # Exemplo simulado de itens retornados para a tabela principal
        itens_tabela = [
            {
                "status": "Convertido",
                "codigo_original": "ABC1234",
                "codigo_convertido": "SOL9876",
                "descricao": "Item Alfanumérico Exemplo",
            }
        ]

        output_pdf_path = processar_pdf_com_regras(pdf_path, df_excel, modo="principal")

        with open(output_pdf_path, "rb") as f:
            pdf_bytes = f.read()
        pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

        return {
            "itens": itens_tabela,
            "pdf_base64": pdf_base64,
            "total": len(itens_tabela),
            "convertidos": sum(1 for i in itens_tabela if i["status"] == "Convertido"),
            "pendentes": 0,
            "nao_encontrados": 0,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro ao processar conversor principal: {str(e)}"
        )


@router.post("/converter/cnh")
async def converter_cnh(
    file_pdf: UploadFile = File(...), file_excel: UploadFile = File(...)
):
    try:
        pdf_path = os.path.join(TEMP_DIR, file_pdf.filename)
        excel_path = os.path.join(TEMP_DIR, file_excel.filename)

        with open(pdf_path, "wb") as buffer:
            buffer.write(await file_pdf.read())
        with open(excel_path, "wb") as buffer:
            buffer.write(await file_excel.read())

        df_excel = pd.read_excel(excel_path)

        # Exemplo simulado de itens retornados para a tabela CNH (focado em números)
        itens_tabela = [
            {
                "status": "Convertido",
                "codigo_original": "56789",
                "codigo_convertido": "SOL1234",
                "descricao": "Item Numérico CNH Exemplo",
            }
        ]

        output_pdf_path = processar_pdf_com_regras(pdf_path, df_excel, modo="cnh")

        with open(output_pdf_path, "rb") as f:
            pdf_bytes = f.read()
        pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

        return {
            "itens": itens_tabela,
            "pdf_base64": pdf_base64,
            "total": len(itens_tabela),
            "convertidos": sum(1 for i in itens_tabela if i["status"] == "Convertido"),
            "pendentes": 0,
            "nao_encontrados": 0,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro ao processar conversor CNH: {str(e)}"
        )