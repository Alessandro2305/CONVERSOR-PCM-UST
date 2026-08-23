import io
import re
import base64
import pandas as pd
import pdfplumber
from fastapi import FastAPI, UploadFile, File, HTTPException
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

def limpar_codigo(codigo) -> str:
    """Extrai apenas a sequência numérica."""
    if pd.isna(codigo) or codigo is None:
        return ""
    return re.sub(r'\D', '', str(codigo)).strip()


@app.post("/escrever-no-pdf-original")
async def escrever_no_pdf_original(
    pdf_file: UploadFile = File(...),
    excel_depara: UploadFile = File(...)
):
    try:
        # 1. Carregar Planilha Excel (De/Para)
        excel_bytes = await excel_depara.read()
        try:
            df_depara = pd.read_excel(io.BytesIO(excel_bytes), engine='openpyxl')
        except Exception:
            df_depara = pd.read_excel(io.BytesIO(excel_bytes))

        col_ref = next((c for c in df_depara.columns if "REF" in str(c).upper()), None)
        col_item = next((c for c in df_depara.columns if "ITEM" in str(c).upper() or "CÓDIGO" in str(c).upper() or "CODIGO" in str(c).upper()), None)
        col_desc = next((c for c in df_depara.columns if "DESC" in str(c).upper()), None)

        if not col_ref or not col_item:
            raise HTTPException(status_code=400, detail="Colunas 'Referencia' e 'Código Item' não encontradas no Excel.")

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

        # 2. Ler PDF Original
        pdf_bytes = await pdf_file.read()
        reader = PdfReader(io.BytesIO(pdf_bytes))
        writer = PdfWriter()

        itens_encontrados = []
        codigos_processados = set()

        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf_plumber:
            for page_idx, original_page in enumerate(reader.pages):
                plumber_page = pdf_plumber.pages[page_idx]
                words = plumber_page.extract_words()

                page_width = float(original_page.mediabox.width)
                page_height = float(original_page.mediabox.height)

                packet = io.BytesIO()
                can = canvas.Canvas(packet, pagesize=(page_width, page_height))
                escreveu_algo = False

                for word in words:
                    texto = word['text']
                    cod_limpo = limpar_codigo(texto)

                    if cod_limpo and len(cod_limpo) >= 4 and word['x0'] < 130:
                        if cod_limpo in mapa_sol:
                            cod_sol = mapa_sol[cod_limpo]
                            descricao = mapa_desc.get(cod_limpo, "SEM DESCRIÇÃO")

                            if cod_limpo not in codigos_processados:
                                codigos_processados.add(cod_limpo)
                                itens_encontrados.append({
                                    "status": "Convertido",
                                    "codigo_original": texto,
                                    "codigo_sol": f"SOL-{cod_sol}",
                                    "descricao": descricao
                                })

                            x0 = word['x0']
                            y_top = word['top']
                            h = word['bottom'] - word['top']
                            y0 = page_height - y_top - h

                            can.setFont("Helvetica-Bold", 6.5)
                            can.setFillColor(HexColor("#2563eb"))
                            can.drawString(x0 + 52, y0 + 1, f"SOL-{cod_sol}")
                            escreveu_algo = True

                        elif cod_limpo not in codigos_processados:
                            codigos_processados.add(cod_limpo)
                            itens_encontrados.append({
                                "status": "Não encontrado",
                                "codigo_original": texto,
                                "codigo_sol": "—",
                                "descricao": "SEM DESCRIÇÃO"
                            })

                can.save()
                packet.seek(0)

                # Preserva a página original e mescla a camada de texto por cima
                page_to_add = original_page
                if escreveu_algo:
                    overlay_pdf = PdfReader(packet)
                    page_to_add.merge_page(overlay_pdf.pages[0])

                writer.add_page(page_to_add)

        output_stream = io.BytesIO()
        writer.write(output_stream)
        output_stream.seek(0)

        # Converte o PDF final para Base64
        pdf_base64 = base64.b64encode(output_stream.getvalue()).decode('utf-8')

        return {
            "pdf_base64": pdf_base64,
            "itens": itens_encontrados
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")