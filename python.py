import io
import re
import base64
import pandas as pd
import pdfplumber
from fastapi import FastAPI, UploadFile, File, HTTPException
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor

app = FastAPI()

def limpar_codigo(codigo: str) -> str:
    """Extrai apenas a sequência numérica de um texto."""
    if not codigo:
        return ""
    return re.sub(r'\D', '', str(codigo)).strip()

@app.post("/escrever-no-pdf-original/")
async def escrever_no_pdf_original(
    pdf_file: UploadFile = File(...),
    excel_depara: UploadFile = File(...)
):
    """Lê o PDF original, injeta o Código SOL e retorna o PDF em Base64 + dados para a tabela/painel."""
    try:
        # 1. Carrega os dados De/Para do Excel
        excel_bytes = await excel_depara.read()
        try:
            df_depara = pd.read_excel(io.BytesIO(excel_bytes), engine='openpyxl')
        except Exception:
            df_depara = pd.read_excel(io.BytesIO(excel_bytes))

        # Mapeia colunas por padrão de nome
        col_ref = next((c for c in df_depara.columns if "REF" in str(c).upper()), None)
        col_item = next((c for c in df_depara.columns if "ITEM" in str(c).upper() or "CÓDIGO" in str(c).upper() or "CODIGO" in str(c).upper()), None)
        col_desc = next((c for c in df_depara.columns if "DESC" in str(c).upper()), None)

        if not col_ref or not col_item:
            raise HTTPException(
                status_code=400, 
                detail="Colunas 'Referencia' e 'Código Item' não encontradas no Excel."
            )

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

        # 2. Leitura e Injeção no PDF
        pdf_bytes = await pdf_file.read()
        reader = PdfReader(io.BytesIO(pdf_bytes))
        writer = PdfWriter()

        itens_encontrados = []
        codigos_processados = set()

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

                    # Filtra apenas códigos numéricos válidos posicionados na margem da esquerda
                    if cod_limpo and len(cod_limpo) >= 4 and word['x0'] < 130:
                        cod_sol = mapa_sol.get(cod_limpo, "")
                        descricao = mapa_desc.get(cod_limpo, "SEM DESCRIÇÃO")

                        if cod_limpo not in codigos_processados:
                            codigos_processados.add(cod_limpo)
                            
                            status = "Convertido" if cod_sol else "Não encontrado"
                            cod_sol_formatado = f"SOL-{cod_sol}" if cod_sol else "—"

                            itens_encontrados.append({
                                "status": status,
                                "codigo_original": texto,
                                "codigo_sol": cod_sol_formatado,
                                "descricao": descricao
                            })

                        # Escreve o novo Código SOL no PDF sobre o overlay
                        if cod_sol:
                            x0 = word['x0']
                            y_top = word['top']
                            h = word['bottom'] - word['top']
                            y0 = page_height - y_top - h

                            can.setFont("Helvetica-Bold", 6.5)
                            can.setFillColor(HexColor("#2563eb"))
                            can.drawString(x0 + 52, y0 + 1, f"SOL-{cod_sol}")

                can.save()
                packet.seek(0)

                overlay_pdf = PdfReader(packet)
                if len(overlay_pdf.pages) > 0:
                    page.merge_page(overlay_pdf.pages[0])

                writer.add_page(page)

        output_stream = io.BytesIO()
        writer.write(output_stream)
        output_stream.seek(0)

        pdf_base64 = base64.b64encode(output_stream.getvalue()).decode('utf-8')

        return {
            "pdf_base64": pdf_base64,
            "itens": itens_encontrados
        }

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        print(f"Erro ao modificar PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro interno no processamento: {str(e)}")