import io
import re
import base64
import traceback
import openpyxl
import pdfplumber
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
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

def extrair_codigo_inteligente(texto, tipo="principal") -> str:
    """ Limpeza flexível que preserva letras e números para ambos os casos,
        removendo CNH/CASE apenas se for a aba CNH.
    """
    if not texto:
        return ""
    txt = str(texto).upper().strip()
    
    if tipo == "cnh":
        txt = re.sub(r'CNH', '', txt)
        txt = re.sub(r'CASE', '', txt)
    
    # Preserva letras (A-Z), números (0-9), hífens (-), pontos (.) e barras (/)
    return re.sub(r'[^A-Z0-9\-\./]', '', txt)

@app.post("/api/escrever-no-pdf-original")
async def escrever_no_pdf_original(
    pdf_file: UploadFile = File(...),
    excel_depara: UploadFile = File(...),
    tipo: str = Form("principal")  # Recebe se é 'principal' ou 'cnh'
):
    try:
        # 1. Leitura Completa da Planilha Excel (Varre colunas dinamicamente)
        excel_bytes = await excel_depara.read()
        wb = openpyxl.load_workbook(filename=io.BytesIO(excel_bytes), data_only=True)

        mapa_sol = {}
        mapa_desc = {}

        sheet = wb['C'] if 'C' in wb.sheetnames else wb.active

        for row in sheet.iter_rows(min_row=2, values_only=True):
            if not row or all(v is None for v in row):
                continue

            valores_linha = [str(v).strip() for v in row if v is not None and str(v).strip() != ""]
            if not valores_linha:
                continue
            
            raw_sol = valores_linha[0].replace(".0", "")
            raw_desc = valores_linha[1] if len(valores_linha) > 1 else "SEM DESCRIÇÃO"

            for val in valores_linha:
                chave = extrair_codigo_inteligente(val, tipo)
                if chave and len(chave) >= 2 and chave not in ["NONE", "NAN"]:
                    mapa_sol[chave] = raw_sol
                    mapa_desc[chave] = raw_desc

        print(f"DEBUG: Total de chaves mapeadas no Excel: {len(mapa_sol)}")

        # 2. Processamento do PDF (Sem travas restritas de coordenada horizontal)
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

                words = page_pdfplumber.extract_words()
                print(f"DEBUG: Página {page_idx} extraiu {len(words)} palavras.")

                for word in words:
                    texto_bruto = word['text'].strip()
                    x1 = word['x1']
                    y_pos = page_height - word['bottom']

                    # Filtro de altura (ignora apenas o cabeçalho superior extremo da página)
                    if y_pos < (page_height - 60):
                        if any(term in texto_bruto.upper() for term in ["CODIGO", "PECAS", "DESCRICAO", "LUBRIFICANTES", "QUANTIDADE"]):
                            continue

                        cod_limpo = extrair_codigo_inteligente(texto_bruto, tipo)

                        if len(cod_limpo) >= 2:
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

                                # Escreve o código SOL convertido em cima/frente do original
                                x_escrita = x1 + 4
                                can.setFillColor(colors.white)
                                can.rect(x_escrita - 1, y_pos - 1, 52, 9, fill=1, stroke=0)
                                
                                can.setFont("Helvetica-Bold", 6.5)
                                can.setFillColor(colors.HexColor("#0284c7"))
                                can.drawString(x_escrita, y_pos, cod_sol)
                                escreveu_algo = True

                            elif cod_limpo not in codigos_processados and len(cod_limpo) >= 4:
                                # Opcional: registra itens não encontrados que pareçam códigos relevantes
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