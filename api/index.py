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

def limpar_codigo(codigo) -> str:
    if codigo is None:
        return ""
    # Mantém apenas caracteres alfanuméricos em caixa alta
    return re.sub(r'[^A-Z0-9]', '', str(codigo).strip().upper())

def extrair_codigo_chave(texto) -> str:
    if not texto:
        return ""
    # Pega o primeiro token da string (ex: de "CE32717 Bucha" pega "CE32717")
    partes = str(texto).strip().split()
    if partes:
        return limpar_codigo(partes[0])
    return ""

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
        # 1. Carrega o Excel e FORÇA a seleção da ABA "C"
        excel_bytes = await excel_depara.read()
        wb = openpyxl.load_workbook(filename=io.BytesIO(excel_bytes), data_only=True)
        
        # Procura explicitamente a aba chamada 'C' (maiúscula ou minúscula)
        aba_alvo = None
        for sheet_name in wb.sheetnames:
            if sheet_name.strip().upper() == 'C':
                aba_alvo = wb[sheet_name]
                break
        
        # Caso a aba não tenha o nome exato 'C', usa a primeira aba disponível
        if aba_alvo is None:
            aba_alvo = wb.active

        mapa_sol = {}
        mapa_desc = {}

        # Mapeia a aba C: Coluna A = SOL (0) | Coluna B = Descrição (1) | Coluna C = Ref/John Deere (2)
        for row in aba_alvo.iter_rows(min_row=2, values_only=True):
            if not row or len(row) <= 2:
                continue
            
            ref_val = row[2]
            chave = limpar_codigo(ref_val)

            if chave and chave not in ["NONE", "NAN"]:
                item_val = str(row[0] or '').strip()
                if item_val and item_val.lower() not in ["none", "nan"]:
                    if chave not in mapa_sol:
                        mapa_sol[chave] = item_val.replace(".0", "").strip()
                        if len(row) > 1 and row[1]:
                            mapa_desc[chave] = str(row[1]).strip()

        # 2. Processamento do PDF
        pdf_bytes = await pdf_file.read()
        reader_base = PdfReader(io.BytesIO(pdf_bytes))
        writer = PdfWriter()

        itens_encontrados = []
        codigos_processados = set()

        for page in reader_base.pages:
            try:
                page_width = float(page.mediabox.width)
                page_height = float(page.mediabox.height)

                packet = io.BytesIO()
                can = canvas.Canvas(packet, pagesize=(page_width, page_height))
                escreveu_algo = False

                def visitor_body(text, cm, tm, font_dict, font_size):
                    nonlocal escreveu_algo
                    if not text:
                        return

                    texto_bruto = str(text).strip()
                    if not texto_bruto:
                        return

                    matrix = tm if tm is not None and len(matrix := tm) >= 6 else cm
                    x_pos = matrix[4] if matrix and len(matrix) >= 6 else 0
                    y_pos = matrix[5] if matrix and len(matrix) >= 6 else 0

                    # Isolamos a chave principal (ex: CE32717)
                    cod_chave = extrair_codigo_chave(texto_bruto)

                    # Somente processa itens localizados na coluna da esquerda do documento PDF (x < 180)
                    if x_pos < 180 and len(cod_chave) >= 3 and "/" not in texto_bruto:
                        
                        if cod_chave in mapa_sol:
                            raw_sol = mapa_sol[cod_chave]
                            descricao = mapa_desc.get(cod_chave, "SEM DESCRIÇÃO")
                            cod_sol = f"SOL-{raw_sol}" if not raw_sol.startswith("SOL") else raw_sol

                            if cod_chave not in codigos_processados:
                                codigos_processados.add(cod_chave)
                                itens_encontrados.append({
                                    "status": "Convertido",
                                    "codigo_original": texto_bruto,
                                    "codigo_sol": cod_sol,
                                    "descricao": descricao
                                })

                            # Escreve a SOL ao lado no PDF
                            can.setFont("Helvetica-Bold", 12)
                            can.setFillColor(colors.HexColor("#1d4ed8"))
                            can.drawString(x_pos + 70, y_pos, cod_sol)
                            escreveu_algo = True

                        elif cod_chave not in codigos_processados and not cod_chave.isdigit():
                            codigos_processados.add(cod_chave)
                            itens_encontrados.append({
                                "status": "Não encontrado",
                                "codigo_original": texto_bruto,
                                "codigo_sol": "—",
                                "descricao": "SEM DESCRIÇÃO"
                            })

                page.extract_text(visitor_text=visitor_body)

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