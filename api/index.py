import io
import re
import base64
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
        # 1. Carregar Planilha Excel
        excel_bytes = await excel_depara.read()
        try:
            wb = openpyxl.load_workbook(filename=io.BytesIO(excel_bytes), data_only=True)
            sheet = wb.active
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Erro no Excel: {str(e)}")

        header = [str(cell.value or '').upper() for cell in sheet[1]]
        
        idx_ref = next((i for i, h in enumerate(header) if "REF" in h), None)
        idx_item = next((i for i, h in enumerate(header) if any(k in h for k in ["ITEM", "CÓDIGO", "CODIGO"])), None)
        idx_desc = next((i for i, h in enumerate(header) if "DESC" in h), None)

        if idx_ref is None or idx_item is None:
            raise HTTPException(status_code=400, detail=f"Colunas não encontradas no Excel. Detectadas: {header}")

        mapa_sol = {}
        mapa_desc = {}

        for row in sheet.iter_rows(min_row=2, values_only=True):
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

        # 2. Processar PDF rápido via pypdf
        pdf_bytes = await pdf_file.read()
        reader_base = PdfReader(io.BytesIO(pdf_bytes))
        writer = PdfWriter()

        itens_encontrados = []
        codigos_processados = set()

        for page_idx, page in enumerate(reader_base.pages):
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)

            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=(page_width, page_height))
            escreveu_algo = False

            # Extração de texto ultra rápida com posições
            def visitor_body(text, cm, tm, font_dict, font_size):
                nonlocal escreveu_algo
                texto_limpo = text.strip()
                cod_limpo = limpar_codigo(texto_limpo)

                # cm[4] é o X da palavra, cm[5] é o Y
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

                        can.setFont("Helvetica-Bold", 6)
                        can.setFillColor(colors.HexColor("#2563eb"))
                        can.drawString(x_pos + 60, y_pos, cod_sol)
                        escreveu_algo = True
                    else:
                        if cod_limpo and cod_limpo not in codigos_processados:
                            codigos_processados.add(cod_limpo)
                            itens_encontrados.append({
                                "status": "Não encontrado",
                                "codigo_original": texto_limpo,
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
        raise HTTPException(status_code=500, detail=f"Erro interno no servidor: {str(e)}")
