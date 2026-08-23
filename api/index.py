import io
import re
import pandas as pd
import pdfplumber
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor

app = FastAPI(redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def limpar_codigo(codigo) -> str:
    if pd.isna(codigo) or codigo is None:
        return ""
    return re.sub(r'\D', '', str(codigo)).strip()

@app.post("/escrever-no-pdf-original/")
@app.post("/escrever-no-pdf-original")
async def escrever_no_pdf_original(
    pdf_file: UploadFile = File(...),
    excel_depara: UploadFile = File(...)
):
    try:
        excel_bytes = await excel_depara.read()
        try:
            df_depara = pd.read_excel(io.BytesIO(excel_bytes), engine='openpyxl')
        except Exception:
            df_depara = pd.read_excel(io.BytesIO(excel_bytes))

        col_ref = next((c for c in df_depara.columns if "REF" in str(c).upper()), None)
        col_item = next((c for c in df_depara.columns if "ITEM" in str(c).upper() or "CÓDIGO" in str(c).upper() or "CODIGO" in str(c).upper()), None)

        if not col_ref or not col_item:
            raise HTTPException(status_code=400, detail="Colunas 'Referencia' e 'Código Item' não encontradas.")

        mapa_sol = {}
        for _, row in df_depara.iterrows():
            chave = limpar_codigo(row[col_ref])
            if chave:
                val = str(row[col_item]).strip()
                if val and val.lower() != "nan":
                    mapa_sol[chave] = val

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
                escreveu_algo = False

                for word in words:
                    texto = word['text']
                    cod_limpo = limpar_codigo(texto)

                    # Filtra os códigos da coluna CÓDIGO (x0 < 130pt)
                    if cod_limpo in mapa_sol and len(cod_limpo) >= 4 and word['x0'] < 130:
                        raw_sol = str(mapa_sol[cod_limpo]).replace(".0", "").replace(".", "").strip()
                        cod_sol = f"SOL-{raw_sol}" if not raw_sol.startswith("SOL") else raw_sol

                        # Pega onde TERMINA o código original (x1)
                        x_fim_codigo = word['x1']
                        y_top = word['top']
                        h = word['bottom'] - word['top']
                        y_baseline = page_height - y_top - (h * 0.75)

                        can.setFont("Helvetica-Bold", 6)
                        can.setFillColor(HexColor("#2563eb"))
                        
                        # Escreve à direita do código original
                        can.drawString(x_fim_codigo + 6, y_baseline, cod_sol)
                        escreveu_algo = True

                can.save()
                packet.seek(0)

                if escreveu_algo:
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
            headers={"Content-Disposition": "attachment; filename=Orcamento_SOL.pdf"}
        )

    except Exception as e:
        print(f"Erro ao modificar PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))