from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
import pdfplumber
import pandas as pd
import io
import re
import os

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

def limpar_codigo(codigo: str) -> str:
    """Extrai apenas a sequência numérica."""
    if not codigo:
        return ""
    return re.sub(r'\D', '', str(codigo)).strip()

@app.get("/", response_class=HTMLResponse)
async def carregar_interface():
    caminho_html = os.path.join(os.path.dirname(__file__), "interface.html")
    if os.path.exists(caminho_html):
        with open(caminho_html, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Arquivo interface.html não encontrado.</h1>"

@app.post("/converter-pdf/")
async def converter_pdf(
    pdf_file: UploadFile = File(...), 
    excel_depara: UploadFile = File(...)
):
    try:
        # 1. Carregar Planilha Excel
        excel_bytes = await excel_depara.read()
        try:
            df_depara = pd.read_excel(io.BytesIO(excel_bytes), engine='openpyxl')
        except Exception:
            df_depara = pd.read_excel(io.BytesIO(excel_bytes))
        
        col_ref = next((c for c in df_depara.columns if "REF" in str(c).upper()), None)
        col_item = next((c for c in df_depara.columns if "ITEM" in str(c).upper() or "CÓDIGO" in str(c).upper() or "CODIGO" in str(c).upper()), None)
        col_desc = next((c for c in df_depara.columns if "DESC" in str(c).upper()), None)

        if not col_ref or not col_item:
            raise HTTPException(status_code=400, detail="Colunas 'Referencia' e 'Código Item' não encontradas.")

        df_depara['CÓDIGO_BUSCA'] = df_depara[col_ref].apply(limpar_codigo)

        renomear_map = {col_item: "CODIGO SOL"}
        if col_desc:
            renomear_map[col_desc] = "DESCRICAO"
        df_depara.rename(columns=renomear_map, inplace=True)

        # 2. Ler PDF Original
        linhas_pdf = []
        pdf_bytes = await pdf_file.read()
        
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if row and any(row):
                            valor_bruto = next((str(cell).strip() for cell in row if cell), "")
                            if valor_bruto and valor_bruto.upper() not in ["CÓDIGO", "CODIGO", "ITEM", "DESCRICAO", "REFERENCIA"]:
                                codigo_numerico = limpar_codigo(valor_bruto)
                                if codigo_numerico:
                                    linhas_pdf.append({
                                        "CÓDIGO": valor_bruto,
                                        "CÓDIGO_BUSCA": codigo_numerico
                                    })

        if not linhas_pdf:
            return []

        df_pdf = pd.DataFrame(linhas_pdf)
        df_resultado = pd.merge(df_pdf, df_depara, on="CÓDIGO_BUSCA", how="left")
        df_resultado.drop(columns=["CÓDIGO_BUSCA", col_ref], inplace=True, errors="ignore")

        for col in df_resultado.columns:
            df_resultado[col] = df_resultado[col].astype(str)
        
        df_resultado.replace(["nan", "None", "NaN", "<NA>"], "", inplace=True)
        df_resultado.fillna("", inplace=True)
        
        return df_resultado.to_dict(orient="records")

    except Exception as e:
        print(f"Erro no processamento: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/escrever-no-pdf-original/")
async def escrever_no_pdf_original(
    pdf_file: UploadFile = File(...),
    excel_depara: UploadFile = File(...)
):
    """Lê o PDF original e escreve o Código SOL na frente, sem pontos."""
    try:
        # 1. Carrega os dados De/Para do Excel
        excel_bytes = await excel_depara.read()
        try:
            df_depara = pd.read_excel(io.BytesIO(excel_bytes), engine='openpyxl')
        except Exception:
            df_depara = pd.read_excel(io.BytesIO(excel_bytes))

        col_ref = next((c for c in df_depara.columns if "REF" in str(c).upper()), None)
        col_item = next((c for c in df_depara.columns if "ITEM" in str(c).upper() or "CÓDIGO" in str(c).upper() or "CODIGO" in str(c).upper()), None)

        if not col_ref or not col_item:
            raise HTTPException(status_code=400, detail="Colunas 'Referencia' e 'Código Item' não encontradas no Excel.")

        df_depara['CÓDIGO_BUSCA'] = df_depara[col_ref].apply(limpar_codigo)
        
        mapa_sol = {}
        for _, row in df_depara.iterrows():
            chave = limpar_codigo(row[col_ref])
            if chave:
                val = str(row[col_item]).strip()
                if val and val.lower() != "nan":
                    mapa_sol[chave] = val

        # 2. Leitura do PDF Original
        pdf_bytes = await pdf_file.read()
        reader = PdfReader(io.BytesIO(pdf_bytes))
        writer = PdfWriter()

        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf_plumber:
            for page_idx, page in enumerate(reader.pages):
                plumber_page = pdf_plumber.pages[page_idx]
                words = plumber_page.extract_words()

                page_width = float(page.mediabox.width)
                page_height = float(page.mediabox.height)

                packet = io.BytesIO()
                can = canvas.Canvas(packet, pagesize=(page_width, page_height))

                for word in words:
                    texto = word['text']
                    cod_limpo = limpar_codigo(texto)

                    if cod_limpo in mapa_sol and len(cod_limpo) >= 4 and word['x0'] < 130:
                        # Remove decimais e pontos do código SOL
                        raw_sol = str(mapa_sol[cod_limpo]).replace(".0", "").replace(".", "").strip()
                        cod_sol = raw_sol

                        x0 = word['x0']
                        y_top = word['top']
                        h = word['bottom'] - word['top']
                        y0 = page_height - y_top - h

                        can.setFont("Helvetica-Bold", 6.5)
                        can.setFillColor(HexColor("#2563eb"))
                        can.drawString(x0 + 52, y0 + 1, cod_sol)

                can.save()
                packet.seek(0)

                overlay_pdf = PdfReader(packet)
                if len(overlay_pdf.pages) > 0:
                    page.merge_page(overlay_pdf.pages[0])

                writer.add_page(page)

        output_stream = io.BytesIO()
        writer.write(output_stream)
        output_stream.seek(0)

        return Response(
            content=output_stream.getvalue(),
            media_type="application/pdf",
            headers={"Content-Disposition": "inline; filename=Orcamento_SOL.pdf"}
        )

    except Exception as e:
        print(f"Erro ao modificar PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))