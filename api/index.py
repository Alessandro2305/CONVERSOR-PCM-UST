import io
import re
import base64
import pandas as pd
import pdfplumber
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib import colors

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
        # 1. Carregar Planilha Excel com múltiplos fallbacks
        excel_bytes = await excel_depara.read()
        df_depara = None
        
        try:
            df_depara = pd.read_excel(io.BytesIO(excel_bytes), engine='openpyxl')
        except Exception:
            try:
                df_depara = pd.read_excel(io.BytesIO(excel_bytes), engine='xlrd')
            except Exception:
                try:
                    df_depara = pd.read_excel(io.BytesIO(excel_bytes))
                except Exception as ex_excel:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Não foi possível ler o arquivo Excel. Verifique se o formato é válido (.xlsx ou .xls). Erro: {str(ex_excel)}"
                    )

        # Mapeamento dinâmico de colunas
        col_ref = next((c for c in df_depara.columns if "REF" in str(c).upper()), None)
        col_item = next((c for c in df_depara.columns if any(k in str(c).upper() for k in ["ITEM", "CÓDIGO", "CODIGO"])), None)
        col_desc = next((c for c in df_depara.columns if "DESC" in str(c).upper()), None)

        if not col_ref or not col_item:
            colunas_encontradas = ", ".join([str(c) for c in df_depara.columns])
            raise HTTPException(
                status_code=400, 
                detail=f"Colunas necessárias não encontradas no Excel. Colunas detectadas: [{colunas_encontradas}]"
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

        # 2. Processar PDF
        pdf_bytes = await pdf_file.read()
        try:
            reader_base = PdfReader(io.BytesIO(pdf_bytes))
        except Exception as ex_pdf:
            raise HTTPException(status_code=400, detail=f"Arquivo PDF inválido ou corrompido: {str(ex_pdf)}")

        writer = PdfWriter()
        itens_encontrados = []
        codigos_processados = set()

        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf_plumber:
            for page_idx, plumber_page in enumerate(pdf_plumber.pages):
                page_base = reader_base.pages[page_idx]
                words = plumber_page.extract_words() or []

                page_width = float(plumber_page.width)
                page_height = float(plumber_page.height)

                packet = io.BytesIO()
                can = canvas.Canvas(packet, pagesize=(page_width, page_height))
                escreveu_algo = False

                for word in words:
                    texto = str(word.get('text', '')).strip()
                    cod_limpo = limpar_codigo(texto)

                    eh_codigo_peca = (texto.upper().endswith("CNH") or cod_limpo in mapa_sol)
                    
                    if word.get('x0', 999) < 130 and "/" not in texto and eh_codigo_peca:
                        if cod_limpo in mapa_sol:
                            raw_sol = mapa_sol[cod_limpo]
                            descricao = mapa_desc.get(cod_limpo, "SEM DESCRIÇÃO")
                            cod_sol = f"SOL-{raw_sol}" if not raw_sol.startswith("SOL") else raw_sol

                            if cod_limpo not in codigos_processados:
                                codigos_processados.add(cod_limpo)
                                itens_encontrados.append({
                                    "status": "Convertido",
                                    "codigo_original": texto,
                                    "codigo_sol": cod_sol,
                                    "descricao": descricao
                                })

                            x_fim_codigo = float(word['x1'])
                            y_top = float(word['top'])
                            h = float(word['bottom']) - float(word['top'])
                            y_baseline = page_height - y_top - (h * 0.75)

                            can.setFont("Helvetica-Bold", 6)
                            can.setFillColor(colors.HexColor("#2563eb"))
                            can.drawString(x_fim_codigo + 4, y_baseline, cod_sol)
                            escreveu_algo = True

                        else:
                            if cod_limpo and cod_limpo not in codigos_processados:
                                codigos_processados.add(cod_limpo)
                                itens_encontrados.append({
                                    "status": "Não encontrado",
                                    "codigo_original": texto,
                                    "codigo_sol": "—",
                                    "descricao": "SEM DESCRIÇÃO"
                                })

                if escreveu_algo:
                    can.save()
                    packet.seek(0)
                    overlay_pdf = PdfReader(packet)
                    if len(overlay_pdf.pages) > 0:
                        page_base.merge_page(overlay_pdf.pages[0])

                writer.add_page(page_base)

        output_stream = io.BytesIO()
        writer.write(output_stream)
        output_stream.seek(0)

        pdf_b64 = base64.b64encode(output_stream.getvalue()).decode('utf-8')

        return {
            "pdf_base64": pdf_b64,
            "itens": itens_encontrados
        }

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        print(f"Erro ao modificar PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Falha de processamento no servidor: {str(e)}")
