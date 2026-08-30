import io
import re
import base64
import traceback
import openpyxl
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

def extrair_numeros_chaves(texto) -> str:
    if texto is None:
        return ""
    txt = str(texto).upper().strip()
    # Remove palavras/sufixos conhecidos para isolar a chave numerica/alfanumerica core
    txt = re.sub(r'^(CASE|VALTRA|MERCEDES|VOLVO|JOHN DEERE|CATERPILLAR|SKF|EATON)[-\s]*', '', txt)
    txt = re.sub(r'CNH$', '', txt)
    # Retorna apenas os caracteres alfanumericos limpos
    return re.sub(r'[^A-Z0-9]', '', txt)

@app.get("/")
@app.get("/api")
def root():
    return {"status": "ok", "message": "API Conversor PCM UST Operacional"}

@app.post("/escrever-no-pdf-original/")
@app.post("/escrever-no-pdf-original")
@app.post("/api/escrever-no-pdf-original/")
@app.post("/api/escrever-no-pdf-original")
async def escrever_no_pdf_original(
    pdf_file: UploadFile = File(...),
    excel_depara: UploadFile = File(...)
):
    try:
        # 1. Leitura Completa e Mapeamento Tolerante da Planilha Excel
        excel_bytes = await excel_depara.read()
        wb = openpyxl.load_workbook(filename=io.BytesIO(excel_bytes), data_only=True)

        mapa_sol = {}
        mapa_desc = {}

        # Mapeia todas as abas priorizando a aba 'C' ou a primeira ativa
        sheet = wb['C'] if 'C' in wb.sheetnames else wb.active

        for row in sheet.iter_rows(min_row=2, values_only=True):
            if not row or all(v is None for v in row):
                continue

            raw_sol = str(row[0] or '').replace(".0", "").strip()
            raw_desc = str(row[1] or '').strip() if len(row) > 1 and row[1] else "SEM DESCRIÇÃO"

            if not raw_sol or raw_sol.lower() in ["none", "nan"]:
                continue

            # Mapeia os códigos presentes na Coluna C (idx 2) e demais colunas
            indices = [2, 1, 0] + list(range(3, len(row)))
            for idx in indices:
                if idx < len(row) and row[idx] is not None:
                    val_str = str(row[idx])
                    chave_limpa = extrair_numeros_chaves(val_str)
                    
                    if chave_limpa and len(chave_limpa) >= 3 and chave_limpa not in ["NONE", "NAN"]:
                        if chave_limpa not in mapa_sol:
                            mapa_sol[chave_limpa] = raw_sol
                            mapa_desc[chave_limpa] = raw_desc

        # 2. Leitura do PDF e Cruzamento
        pdf_bytes = await pdf_file.read()
        reader_base = PdfReader(io.BytesIO(pdf_bytes))
        writer = PdfWriter()

        itens_encontrados = []
        codigos_processados = set()

        for page in reader_base.pages:
            try:
                page_width = float(page.mediabox.width)
                page_height = float(page.mediabox.height)

                texto_bruto_pagina = page.extract_text() or ""
                
                # Coleta termos alfanuméricos suspeitos de serem códigos
                candidatos = re.findall(r'\b[A-Z0-9]{4,20}\b', texto_bruto_pagina)

                # Mapeia posições Y dos textos para escrever
                posicoes_texto = []
                def visitor_body(text, cm, tm, font_dict, font_size):
                    if not text:
                        return
                    t = str(text).strip()
                    if not t:
                        return
                    matrix = tm if tm is not None and len(tm) >= 6 else cm
                    x = matrix[4] if matrix and len(matrix) >= 6 else 0
                    y = matrix[5] if matrix and len(matrix) >= 6 else 0
                    posicoes_texto.append((t, x, y))

                page.extract_text(visitor_text=visitor_body)

                packet = io.BytesIO()
                can = canvas.Canvas(packet, pagesize=(page_width, page_height))
                escreveu_algo = False

                ignorar = {"ORCAMENTO", "SERVICO", "EMITENTE", "ENDERECO", "CLIENTE", "CHASSI", "GARANT", "REVISAO", "CONJUNTO", "TRANSMISSAO", "DESCRICAO", "LUBRIFICANTES", "COMPONENTES", "ZLCF14208", "PARANAVAI", "USACUCAR", "TECNICO", "PECAS"}

                for token in candidatos:
                    if token.upper() in ignorar:
                        continue

                    chave_pdf = extrair_numeros_chaves(token)
                    if len(chave_pdf) < 3:
                        continue

                    if chave_pdf in mapa_sol:
                        raw_sol = mapa_sol[chave_pdf]
                        descricao = mapa_desc.get(chave_pdf, "SEM DESCRIÇÃO")
                        cod_sol = f"SOL-{raw_sol}" if not raw_sol.startswith("SOL") else raw_sol

                        if chave_pdf not in codigos_processados:
                            codigos_processados.add(chave_pdf)
                            itens_encontrados.append({
                                "status": "Convertido",
                                "codigo_original": token,
                                "codigo_sol": cod_sol,
                                "descricao": descricao
                            })

                        # Localiza Y para desenhar a marcação no PDF
                        y_pos_desenho = None
                        for txt_vis, x_vis, y_vis in posicoes_texto:
                            if token in txt_vis or chave_pdf in extrair_numeros_chaves(txt_vis):
                                if y_vis < (page_height - 180): # Ignora cabecalho superior
                                    y_pos_desenho = y_vis
                                    break

                        if y_pos_desenho is not None:
                            can.setFont("Helvetica-Bold", 7.5)
                            can.setFillColor(colors.HexColor("#0284c7"))
                            can.drawString(135, y_pos_desenho, cod_sol)
                            escreveu_algo = True

                    elif chave_pdf not in codigos_processados and not token.isdigit():
                        if "CNH" in token.upper() or len(token) >= 6:
                            codigos_processados.add(chave_pdf)
                            itens_encontrados.append({
                                "status": "Não encontrado",
                                "codigo_original": token,
                                "codigo_sol": "—",
                                "descricao": "SEM DESCRIÇÃO"
                            })

                if escreveu_algo:
                    can.save()
                    packet.seek(0)
                    overlay_pdf = PdfReader(packet)
                    if len(overlay_pdf.pages) > 0:
                        page.merge_page(overlay_pdf.pages[0])

                writer.add_page(page)

            except Exception:
                writer.add_page(page)

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
        tb = traceback.format_exc()
        print(f"CRITICAL ERROR: {tb}")
        raise HTTPException(status_code=500, detail=f"Erro interno no servidor: {str(e)}")