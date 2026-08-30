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
    # Remove qualquer caractere que não seja letra ou número e converte para maiúsculo
    texto = re.sub(r'[^A-Z0-9]', '', str(codigo).strip().upper())
    # Normaliza tirando o sufixo CNH caso exista (ex: 84561324CNH -> 84561324)
    return re.sub(r'CNH$', '', texto)

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
        # 1. Leitura Completa de Todas as Abas do Excel para Mapeamento Global
        excel_bytes = await excel_depara.read()
        wb = openpyxl.load_workbook(filename=io.BytesIO(excel_bytes), data_only=True)

        mapa_sol = {}
        mapa_desc = {}

        # Prioriza aba chamada 'C', 'CNH' ou percorre todas
        abas_para_ler = []
        for name in wb.sheetnames:
            if name.strip().upper() in ['C', 'CNH', 'CASE', 'DEPARA', 'DE-PARA']:
                abas_para_ler.insert(0, wb[name])
            else:
                abas_para_ler.append(wb[name])

        for sheet in abas_para_ler:
            for row in sheet.iter_rows(min_row=2, values_only=True):
                if not row or all(v is None for v in row):
                    continue

                raw_sol = str(row[0] or '').replace(".0", "").strip()
                raw_desc = str(row[1] or '').strip() if len(row) > 1 and row[1] else "SEM DESCRIÇÃO"

                if not raw_sol or raw_sol.lower() in ["none", "nan"]:
                    continue

                # Percorre as colunas procurando a chave original do item
                for idx in range(len(row)):
                    if row[idx] is not None:
                        chave = limpar_codigo(row[idx])
                        if chave and len(chave) >= 3 and chave not in ["NONE", "NAN"]:
                            if chave not in mapa_sol:
                                mapa_sol[chave] = raw_sol
                                mapa_desc[chave] = raw_desc

        # 2. Processamento de Leitura e Escrita do PDF
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

                    matrix = tm if tm is not None and len(tm) >= 6 else cm
                    x_pos = matrix[4] if matrix and len(matrix) >= 6 else 0
                    y_pos = matrix[5] if matrix and len(matrix) >= 6 else 0

                    cod_chave = limpar_codigo(texto_bruto)

                    # REGRAS DE FILTRO AJUSTADAS PARA O DOCUMENTO DA AGRICASE:
                    # - Posição X da coluna do Código: entre 30 e 130
                    # - Posição Y da Tabela de Peças: abaixo do cabeçalho da OS (y_pos < height - 200)
                    if 30 <= x_pos <= 130 and y_pos < (page_height - 200) and len(cod_chave) >= 4:
                        
                        # Descarta títulos e cabeçalhos
                        if "CODIGO" in cod_chave or "PECAS" in cod_chave or "DESCRICAO" in cod_chave:
                            return

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

                            # Escreve a SOL logo à frente da coluna CÓDIGO (em X = 135)
                            can.setFont("Helvetica-Bold", 7.5)
                            can.setFillColor(colors.HexColor("#0284c7")) # Azul destaque
                            can.drawString(135, y_pos, cod_sol)
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