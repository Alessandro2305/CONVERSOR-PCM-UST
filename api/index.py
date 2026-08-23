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
    # Remove qualquer caractere que não seja número
    return re.sub(r'\D', '', str(codigo)).strip()

@app.post("/escrever-no-pdf-original/")
@app.post("/escrever-no-pdf-original")
async def escrever_no_pdf_original(
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

                # Identifica a posição da tabela de peças para não pegar nada acima dela
                y_inicio_tabela = 300  # Valor padrão seguro caso não ache o texto do título
                for w in words:
                    if "PECAS" in w['text'].upper() or "LUBRIFICANTES" in w['text'].upper():
                        y_inicio_tabela = w['bottom']
                        break

                packet = io.BytesIO()
                can = canvas.Canvas(packet, pagesize=(page_width, page_height))
                escreveu_algo = False

                for word in words:
                    texto = word['text'].strip()
                    cod_limpo = limpar_codigo(texto)

                    # REGRAS DE FILTRO EXCLUSIVAS PARA A TABELA DE PEÇAS:
                    # 1. Posição Y deve ser ABAIXO da header do orçamentos/cabeçalho (word['top'] > y_inicio_tabela)
                    # 2. Posição X na coluna de códigos (x0 < 100)
                    # 3. O código precisa existir na planilha De/Para
                    if word['top'] > y_inicio_tabela and word['x0'] < 100 and cod_limpo in mapa_sol:
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

                        # Escreve o código SOL logo à direita do código original
                        x_fim_codigo = word['x1']
                        y_top = word['top']
                        h = word['bottom'] - word['top']
                        y_baseline = page_height - y_top - (h * 0.75)

                        can.setFont("Helvetica-Bold", 6)
                        can.setFillColor(HexColor("#2563eb"))
                        can.drawString(x_fim_codigo + 4, y_baseline, cod_sol)
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

        pdf_b64 = base64.b64encode(output_stream.getvalue()).decode('utf-8')

        return {
            "pdf_base64": pdf_b64,
            "itens": itens_encontrados
        }

    except Exception as e:
        print(f"Erro ao modificar PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))