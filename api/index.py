import io
import re
import base64
import traceback
import pandas as pd
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def limpar_codigo(val):
    if pd.isna(val) or val is None:
        return ""
    val_str = str(val).strip()
    return re.sub(r'[^A-Za-z0-9]', '', val_str).upper()

@app.post("/api/escrever-no-pdf-original")
@app.post("/escrever-no-pdf-original")
async def escrever_no_pdf_original(
    pdf_file: UploadFile = File(...),
    excel_depara: UploadFile = File(...)
):
    try:
        pdf_bytes = await pdf_file.read()
        excel_bytes = await excel_depara.read()

        # 1. Excel De/Para
        try:
            df_depara = pd.read_excel(io.BytesIO(excel_bytes), engine='openpyxl')
        except Exception:
            df_depara = pd.read_excel(io.BytesIO(excel_bytes))

        col_ref = next((c for c in df_depara.columns if "REF" in str(c).upper()), None)
        col_item = next((c for c in df_depara.columns if "ITEM" in str(c).upper() or "CÓDIGO" in str(c).upper() or "CODIGO" in str(c).upper()), None)
        col_desc = next((c for c in df_depara.columns if "DESC" in str(c).upper()), None)

        if not col_ref or not col_item:
            raise HTTPException(status_code=400, detail="Colunas de Referência e Código Item não encontradas no Excel.")

        mapa_sol = {}
        mapa_desc = {}
        for _, row in df_depara.iterrows():
            chave = limpar_codigo(row[col_ref])
            if chave:
                val_sol = str(row[col_item]).strip()
                if val_sol and val_sol.lower() != "nan":
                    mapa_sol[chave] = val_sol.replace(".0", "").replace(".", "").strip()
                if col_desc and pd.notna(row[col_desc]):
                    mapa_desc[chave] = str(row[col_desc]).strip()

        # 2. Leitura com PyPDF (Leve e rápida)
        reader = PdfReader(io.BytesIO(pdf_bytes))
        writer = PdfWriter()
        itens_encontrados = []
        codigos_processados = set()

        for page_idx, page in enumerate(reader.pages):
            texto_pagina = page.extract_text() or ""
            palavras = texto_pagina.split()

            packet = io.BytesIO()
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)
            can = canvas.Canvas(packet, pagesize=(page_width, page_height))
            escreveu = False

            for palavra in palavras:
                cod_limpo = limpar_codigo(palavra)
                if cod_limpo in mapa_sol and cod_limpo not in codigos_processados:
                    codigos_processados.add(cod_limpo)
                    raw_sol = mapa_sol[cod_limpo]
                    descricao = mapa_desc.get(cod_limpo, "SEM DESCRIÇÃO")
                    cod_sol = f"SOL-{raw_sol}" if not raw_sol.startswith("SOL") else raw_sol

                    itens_encontrados.append({
                        "status": "Convertido",
                        "codigo_original": palavra,
                        "codigo_sol": cod_sol,
                        "descricao": descricao
                    })

            can.save()
            packet.seek(0)
            writer.add_page(page)

        output_stream = io.BytesIO()
        writer.write(output_stream)
        output_stream.seek(0)
        pdf_b64 = base64.b64encode(output_stream.getvalue()).decode('utf-8')

        return {
            "itens": itens_encontrados,
            "pdf_base64": pdf_b64
        }

    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        print("ERRO:", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Erro na Function: {str(e)}")