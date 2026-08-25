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
    return re.sub(r'\D', '', str(codigo)).strip()

@app.post("/escrever-no-pdf-original/")
@app.post("/escrever-no-pdf-original")
async def escrever_no_pdf_original(
    pdf_file: UploadFile = File(...),
    excel_depara: UploadFile = File(...)
):
    try:
        # 1. Leitura Segura do Excel
        try:
            excel_bytes = await excel_depara.read()
            # Usando carregamento em memória padrão para evitar travamento de ponteiro read_only
            wb = openpyxl.load_workbook(filename=io.BytesIO(excel_bytes), data_only=True)
            sheet = wb.active
        except Exception as e:
            raise HTTPException(
                status_code=400, 
                detail=f"Erro ao abrir a planilha Excel. Certifique-se de ser um arquivo .xlsx válido. Detalhes: {str(e)}"
            )

        # 2. Mapeamento das Colunas
        rows = list(sheet.iter_rows(values_only=True))
        wb.close()  # Libera a memória imediatamente após extrair as linhas

        if not rows:
            raise HTTPException(status_code=400, detail="A planilha enviada está vazia.")

        header = [str(cell or '').upper().strip() for cell in rows[0]]
        
        idx_ref = next((i for i, h in enumerate(header) if "REF" in h), None)
        idx_item = next((i for i, h in enumerate(header) if any(k in h for k in ["ITEM", "CÓDIGO", "CODIGO"])), None)
        idx_desc = next((i for i, h in enumerate(header) if "DESC" in h), None)

        if idx_ref is None or idx_item is None:
            raise HTTPException(
                status_code=400, 
                detail=f"Colunas obrigatórias não encontradas no Excel. Colunas lidas: {header}"
            )

        mapa_sol = {}
        mapa_desc = {}

        for row in rows[1:]:
            if not row or len(row) <= max(idx_ref, idx_item):
                continue
            
            ref_val = row[idx_ref]
            chave = limpar_codigo(ref_val)

            if chave:
                item_val = str(row[idx_item] or '').strip()
                if item_val and item_val.lower() != "none":
                    mapa_sol[chave] = item_val.replace(".0", "").replace(".", "").strip()
                if idx_desc is not None and len(row) > idx_desc and row[idx_desc]:
                    mapa_desc[chave] = str(row[idx_desc]).strip()

        # 3. Processamento do PDF
        try:
            pdf_bytes = await pdf_file.read()
            reader_base = PdfReader(io.BytesIO(pdf_bytes))
        except Exception as e:
            raise HTTPException(
                status_code=400, 
                detail=f"Erro ao ler o arquivo PDF enviado. Detalhes: {str(e)}"
            )

        writer = PdfWriter()
        itens_encontrados = []
        codigos_processados = set()

        for page in reader_base.pages:
            try:
                page_width = float(page.mediabox.width)
                page_height = float(page.mediabox.height)

                anotacoes_pagina = []

                def visitor_body(text, cm, tm, font_dict, font_size):
                    if not text or not cm or len(cm) < 6:
                        return

                    texto_limpo = str(text).strip()
                    cod_limpo = limpar_codigo(texto_limpo)

                    x_pos = cm[4]
                    y_pos = cm[5]

                    eh_codigo_peca = (texto_limpo.upper().endswith("CNH") or cod_limpo in mapa_sol)

                    if x_pos < 130 and "/" not in texto_limpo and eh_codigo_peca:
                        if cod_limpo in mapa_sol:
                            raw_sol = mapa_sol[cod_limpo]
                            descricao = mapa_desc.get(cod_limpo, "SEM DESCRIÇÃO")
                            cod_sol = f"SOL-{raw_sol}" if not raw_sol.startswith("SOL") else raw_sol

                            if cod_limpo not in codigos_processados:
                                codigos_processados.add(cod_limpo)
                                itens_encontrados.append({
                                    "status": "Convertido",
                                    "codigo_original": texto_limpo,
                                    "codigo_sol": cod_sol,
                                    "descricao": descricao
                                })

                            anotacoes_pagina.append((x_pos + 60, y_pos, cod_sol))
                        else:
                            if cod_limpo and cod_limpo not in codigos_processados:
                                codigos_processados.add(cod_limpo)
                                itens_encontrados.append({
                                    "status": "Não encontrado",
                                    "codigo_original": texto_limpo,
                                    "codigo_sol": "—",
                                    "descricao": "SEM DESCRIÇÃO"
                                })

                # Extrai texto com segurança
                page.extract_text(visitor_text=visitor_body)

                # Desenha o Overlay apenas se houver o que escrever
                if anotacoes_pagina:
                    packet = io.BytesIO()
                    can = canvas.Canvas(packet, pagesize=(page_width, page_height))
                    can.setFont("Helvetica-Bold", 6)
                    can.setFillColor(colors.HexColor("#2563eb"))

                    for x, y, texto in anotacoes_pagina:
                        can.drawString(x, y, texto)

                    can.save()
                    packet.seek(0)
                    overlay_pdf = PdfReader(packet)
                    if len(overlay_pdf.pages) > 0:
                        page.merge_page(overlay_pdf.pages[0])

                writer.add_page(page)

            except Exception as page_err:
                # Em caso de página corrompida, preserva a página original sem travar a requisição
                print(f"Erro ao processar página: {str(page_err)}")
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
