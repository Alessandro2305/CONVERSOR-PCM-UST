import io
import re
import base64
import traceback
import openpyxl
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

def extrair_apenas_codigo_limpo(texto) -> str:
    """ Limpa o código removendo CNH/CASE mesmo colados no número """
    if not texto:
        return ""
    txt = str(texto).upper().strip()
    # Remove CNH ou CASE do final ou do início
    txt = re.sub(r'CNH', '', txt)
    txt = re.sub(r'CASE', '', txt)
    # Remove qualquer caractere que não seja letra/número
    return re.sub(r'[^A-Z0-9]', '', txt)

@app.post("/api/escrever-no-pdf-original")
async def escrever_no_pdf_original(
    pdf_file: UploadFile = File(...),
    excel_depara: UploadFile = File(...)
):
    try:
        # 1. Leitura Completa da Planilha Excel
        excel_bytes = await excel_depara.read()
        wb = openpyxl.load_workbook(filename=io.BytesIO(excel_bytes), data_only=True)

        mapa_sol = {}
        mapa_desc = {}

        sheet = wb['C'] if 'C' in wb.sheetnames else wb.active

        for row in sheet.iter_rows(min_row=2, values_only=True):
            if not row or all(v is None for v in row):
                continue

            raw_sol = str(row[0] or '').replace(".0", "").strip()
            raw_desc = str(row[1] or '').strip() if len(row) > 1 and row[1] else "SEM DESCRIÇÃO"

            if not raw_sol or raw_sol.lower() in ["none", "nan"]:
                continue

            # Indexa todas as variações/colunas da planilha
            for cell in row:
                if cell is not None:
                    chave = extrair_apenas_codigo_limpo(cell)
                    if chave and len(chave) >= 3 and chave not in ["NONE", "NAN"]:
                        if chave not in mapa_sol:
                            mapa_sol[chave] = raw_sol
                            mapa_desc[chave] = raw_desc

        # 2. Processamento do PDF
        pdf_bytes = await pdf_file.read()
        reader_base = PdfReader(io.BytesIO(pdf_bytes))
        writer = PdfWriter()

        itens_encontrados = []
        codigos_processados = set()

        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf_plumber:
            for page_idx, page_pdfplumber in enumerate(pdf_plumber.pages):
                page_pypdf = reader_base.pages[page_idx]
                
                page_width = float(page_pdfplumber.width)
                page_height = float(page_pdfplumber.height)

                packet = io.BytesIO()
                can = canvas.Canvas(packet, pagesize=(page_width, page_height))
                escreveu_algo = False

                # Extrai palavras completas da página
                words = page_pdfplumber.extract_words()
                
                for word in words:
                    texto_bruto = word['text'].strip()
                    
                    x0 = word['x0']
                    x1 = word['x1']
                    # Converte coordenada Y do pdfplumber para o padrão do ReportLab
                    y_pos = page_height - word['bottom']

                    # CRITÉRIO AJUSTADO COM BASE NO SEU LAYOUT:
                    # - Posição X da coluna CÓDIGO (entre 20 e 150)
                    # - Posição Y (abaixo do cabeçalho de topo, Y < page_height - 120)
                    if x0 <= 150 and y_pos < (page_height - 120):
                        
                        # Ignora termos de cabeçalho
                        if any(term in texto_bruto.upper() for term in ["CODIGO", "PECAS", "DESCRICAO", "LUBRIFICANTES"]):
                            continue

                        cod_limpo = extrair_apenas_codigo_limpo(texto_bruto)

                        # Verifica se é um código válido de peça (numérico ou com CNH)
                        if len(cod_limpo) >= 4 and ("CNH" in texto_bruto.upper() or re.search(r'\d{4,}', cod_limpo)):
                            
                            if cod_limpo in mapa_sol:
                                raw_sol = mapa_sol[cod_limpo]
                                descricao = mapa_desc.get(cod_limpo, "SEM DESCRIÇÃO")
                                cod_sol = f"SOL-{raw_sol}" if not raw_sol.startswith("SOL") else raw_sol

                                if cod_limpo not in codigos_processados:
                                    codigos_processados.add(cod_limpo)
                                    itens_encontrados.append({
                                        "status": "Convertido",
                                        "codigo_original": texto_bruto,
                                        "codigo_sol": cod_sol,
                                        "descricao": descricao
                                    })

                                # Escreve na frente do código original (com tarja branca limpa)
                                x_escrita = x1 + 4
                                
                                can.setFillColor(colors.white)
                                can.rect(x_escrita - 1, y_pos - 1, 52, 9, fill=1, stroke=0)
                                
                                can.setFont("Helvetica-Bold", 6.5)
                                can.setFillColor(colors.HexColor("#0284c7"))
                                can.drawString(x_escrita, y_pos, cod_sol)
                                escreveu_algo = True

                            elif cod_limpo not in codigos_processados:
                                codigos_processados.add(cod_limpo)
                                itens_encontrados.append({
                                    "status": "Não encontrado",
                                    "codigo_original": texto_bruto,
                                    "codigo_sol": "—",
                                    "descricao": "SEM DESCRIÇÃO"
                                })

                if escreveu_algo:
                    can.save()
                    packet.seek(0)
                    overlay_pdf = PdfReader(packet)
                    if len(overlay_pdf.pages) > 0:
                        page_pypdf.merge_page(overlay_pdf.pages[0])

                writer.add_page(page_pypdf)

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