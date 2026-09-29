from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import base64
import io
import os
import re
import pandas as pd

from pypdf import PdfReader, PdfWriter


# ============================================================
# CONFIGURAÇÃO DA API
# ============================================================

app = FastAPI(
    title="Conversor PCM UST",
    description="Sistema de conversão de códigos PDF x SOL",
    version="1.0.0"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def normalizar_texto(valor):
    """
    Normaliza valores vindos do Excel.
    """

    if valor is None:
        return ""

    if pd.isna(valor):
        return ""

    texto = str(valor).strip()

    # Remove .0 de números vindos do Excel
    if texto.endswith(".0"):
        texto = texto[:-2]

    return texto


def normalizar_codigo(valor):
    """
    Normaliza códigos para facilitar o cruzamento.
    """

    texto = normalizar_texto(valor)

    if not texto:
        return ""

    texto = texto.upper()

    # Remove espaços extras
    texto = re.sub(r"\s+", "", texto)

    return texto


def encontrar_coluna(df, possibilidades):
    """
    Procura uma coluna no Excel utilizando várias possibilidades.
    """

    mapa = {}

    for coluna in df.columns:
        nome = str(coluna).strip().upper()

        # Remove acentos simples
        nome = (
            nome.replace("Á", "A")
            .replace("À", "A")
            .replace("Ã", "A")
            .replace("Â", "A")
            .replace("É", "E")
            .replace("Ê", "E")
            .replace("Í", "I")
            .replace("Ó", "O")
            .replace("Ô", "O")
            .replace("Õ", "O")
            .replace("Ú", "U")
            .replace("Ç", "C")
        )

        nome = re.sub(r"[^A-Z0-9]", "", nome)

        mapa[nome] = coluna

    for possibilidade in possibilidades:

        nome = possibilidade.upper()

        nome = (
            nome.replace("Á", "A")
            .replace("À", "A")
            .replace("Ã", "A")
            .replace("Â", "A")
            .replace("É", "E")
            .replace("Ê", "E")
            .replace("Í", "I")
            .replace("Ó", "O")
            .replace("Ô", "O")
            .replace("Õ", "O")
            .replace("Ú", "U")
            .replace("Ç", "C")
        )

        nome = re.sub(r"[^A-Z0-9]", "", nome)

        if nome in mapa:
            return mapa[nome]

    return None


def localizar_colunas_excel(df):
    """
    Identifica automaticamente as principais colunas da planilha.
    """

    coluna_original = encontrar_coluna(
        df,
        [
            "CODIGO_ORIGINAL",
            "CÓDIGO_ORIGINAL",
            "CODIGO ORIGINAL",
            "CÓDIGO ORIGINAL",
            "CODIGO",
            "CÓDIGO",
            "COD",
            "ITEM",
            "PART_NUMBER",
            "PARTNUMBER",
            "PN",
        ]
    )

    coluna_sol = encontrar_coluna(
        df,
        [
            "CODIGO_SOL",
            "CÓDIGO_SOL",
            "CODIGO SOL",
            "CÓDIGO SOL",
            "SOL",
            "COD_SOL",
            "CÓDIGO INTERNO",
            "CODIGO INTERNO",
            "CODIGO_CONVERTIDO",
            "CÓDIGO_CONVERTIDO",
        ]
    )

    coluna_descricao = encontrar_coluna(
        df,
        [
            "DESCRICAO",
            "DESCRIÇÃO",
            "DESCRICAO DO ITEM",
            "DESCRIÇÃO DO ITEM",
            "DESCRIÇÃO ITEM",
            "ITEM DESCRICAO",
            "NOME",
            "MATERIAL",
        ]
    )

    return coluna_original, coluna_sol, coluna_descricao


def extrair_texto_pdf(pdf_bytes):
    """
    Extrai todo o texto do PDF.
    """

    try:

        reader = PdfReader(io.BytesIO(pdf_bytes))

        paginas = []

        for pagina in reader.pages:

            texto = pagina.extract_text()

            if texto:
                paginas.append(texto)

        return "\n".join(paginas)

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=f"Não foi possível ler o PDF: {str(e)}"
        )


def extrair_codigos_do_pdf(texto):
    """
    Identifica possíveis códigos dentro do PDF.

    A função procura códigos alfanuméricos e numéricos.
    """

    if not texto:
        return []

    encontrados = []

    linhas = texto.splitlines()

    for linha in linhas:

        linha = linha.strip()

        if not linha:
            continue

        # ----------------------------------------------------
        # Procura códigos com letras/números
        # Exemplos:
        # ABC-123
        # 12345
        # 10.123.456
        # AB12345
        # ----------------------------------------------------

        tokens = re.findall(
            r"\b[A-Z0-9][A-Z0-9._/-]{2,}\b",
            linha.upper()
        )

        for token in tokens:

            token = token.strip(".,;:()[]{}")

            if len(token) < 3:
                continue

            # Ignora palavras comuns
            palavras_ignoradas = {
                "ITEM",
                "TOTAL",
                "DATA",
                "HORA",
                "STATUS",
                "CODIGO",
                "CÓDIGO",
                "DESCRICAO",
                "DESCRIÇÃO",
                "QUANTIDADE",
                "UNIDADE",
                "PAGINA",
                "PÁGINA",
                "SOL",
            }

            if token in palavras_ignoradas:
                continue

            encontrados.append(token)

    # Remove duplicados preservando ordem
    resultado = list(dict.fromkeys(encontrados))

    return resultado


def criar_pdf_saida(pdf_bytes):
    """
    Cria uma cópia válida do PDF original.
    """

    try:

        reader = PdfReader(io.BytesIO(pdf_bytes))

        writer = PdfWriter()

        for pagina in reader.pages:
            writer.add_page(pagina)

        saida = io.BytesIO()

        writer.write(saida)

        saida.seek(0)

        return saida.read()

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Erro ao gerar PDF de saída: {str(e)}"
        )


def pdf_para_base64(pdf_bytes):
    """
    Converte PDF para Base64.
    """

    return base64.b64encode(pdf_bytes).decode("utf-8")


def montar_indice_excel(df, coluna_original, coluna_sol, coluna_descricao):
    """
    Cria um índice rápido para localizar códigos.
    """

    indice = {}

    for _, linha in df.iterrows():

        codigo_original = normalizar_codigo(
            linha[coluna_original]
        )

        codigo_sol = normalizar_texto(
            linha[coluna_sol]
        )

        descricao = normalizar_texto(
            linha[coluna_descricao]
        )

        if not codigo_original:
            continue

        indice[codigo_original] = {
            "codigo_convertido": codigo_sol,
            "descricao": descricao
        }

    return indice


def processar_conversao(pdf_bytes, excel_bytes, tipo="principal"):
    """
    Processo principal de conversão.
    """

    # ========================================================
    # 1. LER EXCEL
    # ========================================================

    try:

        df = pd.read_excel(
            io.BytesIO(excel_bytes)
        )

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=f"Erro ao abrir a planilha Excel: {str(e)}"
        )

    if df.empty:

        raise HTTPException(
            status_code=400,
            detail="A planilha Excel está vazia."
        )


    # ========================================================
    # 2. IDENTIFICAR COLUNAS
    # ========================================================

    (
        coluna_original,
        coluna_sol,
        coluna_descricao
    ) = localizar_colunas_excel(df)


    if not coluna_original:

        raise HTTPException(
            status_code=400,
            detail=(
                "Não encontrei a coluna do código original na planilha. "
                "Use uma coluna como CODIGO, CÓDIGO ORIGINAL ou CODIGO_ORIGINAL."
            )
        )


    if not coluna_sol:

        raise HTTPException(
            status_code=400,
            detail=(
                "Não encontrei a coluna do código SOL na planilha. "
                "Use uma coluna como SOL, CODIGO SOL ou CODIGO_SOL."
            )
        )


    if not coluna_descricao:

        # Se não existir descrição, cria uma coluna virtual
        df["DESCRICAO"] = ""

        coluna_descricao = "DESCRICAO"


    # ========================================================
    # 3. CRIAR ÍNDICE
    # ========================================================

    indice = montar_indice_excel(
        df,
        coluna_original,
        coluna_sol,
        coluna_descricao
    )


    # ========================================================
    # 4. LER PDF
    # ========================================================

    texto_pdf = extrair_texto_pdf(
        pdf_bytes
    )


    # ========================================================
    # 5. EXTRAIR CÓDIGOS
    # ========================================================

    codigos_pdf = extrair_codigos_do_pdf(
        texto_pdf
    )


    # ========================================================
    # 6. SE NÃO ENCONTROU CÓDIGOS
    # ========================================================

    if not codigos_pdf:

        return {
            "total": 0,
            "convertidos": 0,
            "pendentes": 0,
            "nao_encontrados": 0,
            "itens": [],
            "mensagem": (
                "Nenhum código foi identificado no PDF."
            ),
            "pdf_base64": pdf_para_base64(
                criar_pdf_saida(pdf_bytes)
            )
        }


    # ========================================================
    # 7. CRUZAR PDF X EXCEL
    # ========================================================

    itens = []

    convertidos = 0
    pendentes = 0
    nao_encontrados = 0


    for codigo in codigos_pdf:

        codigo_normalizado = normalizar_codigo(
            codigo
        )


        # ----------------------------------------------------
        # ENCONTRADO
        # ----------------------------------------------------

        if codigo_normalizado in indice:

            registro = indice[
                codigo_normalizado
            ]

            codigo_convertido = registro[
                "codigo_convertido"
            ]

            descricao = registro[
                "descricao"
            ]


            if codigo_convertido:

                status = "Convertido"

                convertidos += 1

            else:

                status = "Pendente"

                pendentes += 1


            itens.append(
                {
                    "status": status,
                    "codigo_original": codigo,
                    "codigo_convertido": codigo_convertido,
                    "descricao": descricao
                }
            )

        else:

            # ------------------------------------------------
            # NÃO ENCONTRADO
            # ------------------------------------------------

            nao_encontrados += 1

            itens.append(
                {
                    "status": "Não encontrado",
                    "codigo_original": codigo,
                    "codigo_convertido": "",
                    "descricao": "Código não encontrado na planilha"
                }
            )


    # ========================================================
    # 8. GERAR PDF
    # ========================================================

    pdf_saida = criar_pdf_saida(
        pdf_bytes
    )


    # ========================================================
    # 9. RESULTADO
    # ========================================================

    resultado = {

        "total": len(itens),

        "convertidos": convertidos,

        "pendentes": pendentes,

        "nao_encontrados": nao_encontrados,

        "itens": itens,

        "pdf_base64": pdf_para_base64(
            pdf_saida
        )
    }


    return resultado


# ============================================================
# ROTA PRINCIPAL
# ============================================================

@app.post("/converter/principal")
async def converter_principal(
    file_pdf: UploadFile = File(...),
    file_excel: UploadFile = File(...)
):

    try:

        # ----------------------------------------------------
        # Validar PDF
        # ----------------------------------------------------

        if not file_pdf.filename.lower().endswith(".pdf"):

            raise HTTPException(
                status_code=400,
                detail="O arquivo enviado não é um PDF válido."
            )


        # ----------------------------------------------------
        # Validar Excel
        # ----------------------------------------------------

        extensao_excel = file_excel.filename.lower()

        if not (
            extensao_excel.endswith(".xlsx")
            or extensao_excel.endswith(".xls")
        ):

            raise HTTPException(
                status_code=400,
                detail="A planilha deve ser .xlsx ou .xls."
            )


        pdf_bytes = await file_pdf.read()

        excel_bytes = await file_excel.read()


        if not pdf_bytes:

            raise HTTPException(
                status_code=400,
                detail="O PDF está vazio."
            )


        if not excel_bytes:

            raise HTTPException(
                status_code=400,
                detail="A planilha está vazia."
            )


        resultado = processar_conversao(
            pdf_bytes,
            excel_bytes,
            tipo="principal"
        )


        return JSONResponse(
            content=resultado
        )


    except HTTPException:
        raise

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Erro interno no conversor principal: {str(e)}"
        )


# ============================================================
# ROTA CNH
# ============================================================

@app.post("/converter/cnh")
async def converter_cnh(
    file_pdf: UploadFile = File(...),
    file_excel: UploadFile = File(...)
):

    try:

        # ----------------------------------------------------
        # Validar PDF
        # ----------------------------------------------------

        if not file_pdf.filename.lower().endswith(".pdf"):

            raise HTTPException(
                status_code=400,
                detail="O arquivo enviado não é um PDF válido."
            )


        # ----------------------------------------------------
        # Validar Excel
        # ----------------------------------------------------

        extensao_excel = file_excel.filename.lower()

        if not (
            extensao_excel.endswith(".xlsx")
            or extensao_excel.endswith(".xls")
        ):

            raise HTTPException(
                status_code=400,
                detail="A planilha deve ser .xlsx ou .xls."
            )


        pdf_bytes = await file_pdf.read()

        excel_bytes = await file_excel.read()


        if not pdf_bytes:

            raise HTTPException(
                status_code=400,
                detail="O PDF está vazio."
            )


        if not excel_bytes:

            raise HTTPException(
                status_code=400,
                detail="A planilha está vazia."
            )


        resultado = processar_conversao(
            pdf_bytes,
            excel_bytes,
            tipo="cnh"
        )


        return JSONResponse(
            content=resultado
        )


    except HTTPException:
        raise

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Erro interno no conversor CNH: {str(e)}"
        )


# ============================================================
# ROTA DE TESTE
# ============================================================

@app.get("/")
def inicio():

    return {
        "sistema": "Conversor PCM UST",
        "status": "online",
        "versao": "1.0.0"
    }


@app.get("/health")
def health():

    return {
        "status": "ok"
    }


# ============================================================
# EXECUÇÃO LOCAL
# ============================================================

if __name__ == "__main__":

    import uvicorn

    port = int(
        os.environ.get(
            "PORT",
            8000
        )
    )

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )