from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import base64
import io
import os
import re
import unicodedata
from collections import defaultdict

import pandas as pd
from pypdf import PdfReader, PdfWriter


# ============================================================
# CONFIGURAÇÃO
# ============================================================

app = FastAPI(
    title="Conversor PCM UST",
    description="Conversor de código original para Código Item (SOL)",
    version="1.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# NORMALIZAÇÃO
# ============================================================

def normalizar(valor):
    """Converte um valor para texto comparável."""
    if valor is None:
        return ""

    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass

    texto = str(valor).strip().upper()

    # Remove acentos
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )

    # Mantém somente letras e números
    texto = re.sub(r"[^A-Z0-9]", "", texto)

    return texto


def texto_limpo(valor):
    """Texto normal sem alterar acentos."""
    if valor is None:
        return ""

    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass

    return str(valor).strip()


# ============================================================
# EXCEL
# ============================================================

def ler_planilha(excel_bytes):
    try:
        df = pd.read_excel(io.BytesIO(excel_bytes))
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Erro ao abrir a planilha Excel: {e}"
        )

    if df.empty:
        raise HTTPException(
            status_code=400,
            detail="A planilha Excel está vazia."
        )

    return df


def validar_planilha_pcm(df):
    """
    A planilha real enviada pelo usuário possui:
      Código Item
      Descrição
      Grupo
      Subgrupo
      Familia de Compra
      Codigo Marca
      Marca
      Referencia
      Homologado

    Para o conversor:
      Referencia  = código original
      Código Item = código SOL / código interno
      Descrição   = descrição do item
    """

    colunas = {
        "codigo_item": None,
        "referencia": None,
        "descricao": None,
    }

    for coluna in df.columns:
        nome = normalizar(coluna)

        if nome == "CODIGOITEM":
            colunas["codigo_item"] = coluna

        elif nome == "REFERENCIA":
            colunas["referencia"] = coluna

        elif nome == "DESCRICAO":
            colunas["descricao"] = coluna

    faltando = [
        chave
        for chave, coluna in colunas.items()
        if coluna is None
    ]

    if faltando:
        raise HTTPException(
            status_code=400,
            detail=(
                "A planilha não possui as colunas necessárias. "
                "Para esta planilha são esperadas: "
                "'Código Item', 'Referencia' e 'Descrição'. "
                f"Faltando: {', '.join(faltando)}."
            )
        )

    return colunas


def montar_indice(df, colunas):
    """
    Cria:
      referencia normalizada -> lista de registros

    A lista é importante porque existem referências duplicadas
    na planilha. Quando uma referência aponta para mais de um
    Código Item, o resultado fica Pendente em vez de escolher
    um código incorretamente.
    """

    indice = defaultdict(list)

    coluna_codigo = colunas["codigo_item"]
    coluna_ref = colunas["referencia"]
    coluna_desc = colunas["descricao"]

    for _, linha in df.iterrows():

        referencia_original = texto_limpo(
            linha[coluna_ref]
        )

        referencia_normalizada = normalizar(
            referencia_original
        )

        if not referencia_normalizada:
            continue

        codigo_item = texto_limpo(
            linha[coluna_codigo]
        )

        # Corrige códigos que o Excel transforma em 123.0
        if codigo_item.endswith(".0"):
            codigo_item = codigo_item[:-2]

        descricao = texto_limpo(
            linha[coluna_desc]
        )

        registro = {
            "codigo_item": codigo_item,
            "referencia": referencia_original,
            "descricao": descricao,
        }

        # Evita duplicar exatamente o mesmo registro
        if registro not in indice[referencia_normalizada]:
            indice[referencia_normalizada].append(registro)

    return indice


# ============================================================
# PDF
# ============================================================

def extrair_texto_pdf(pdf_bytes):
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))

        paginas = []

        for pagina in reader.pages:
            texto = pagina.extract_text() or ""
            paginas.append(texto)

        texto = "\n".join(paginas)

        if not texto.strip():
            raise HTTPException(
                status_code=400,
                detail=(
                    "O PDF não possui texto extraível. "
                    "Se o PDF for escaneado como imagem, será necessário "
                    "adicionar OCR."
                )
            )

        return texto

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Erro ao ler o PDF: {e}"
        )


def gerar_candidatos_pdf(texto):
    """
    Extrai candidatos do texto do PDF.

    Em vez de considerar qualquer palavra do PDF como código,
    procuramos tokens alfanuméricos e também combinações de
    tokens próximos. Isso permite referências como:

      712111
      DRT3500
      44952002
      UG000804 - 70438
      1 410 101 610
      000.090.15.51
    """

    tokens = re.findall(
        r"[A-Za-z0-9]+",
        texto.upper()
    )

    candidatos = []
    vistos = set()

    # Tokens individuais
    for token in tokens:
        normalizado = normalizar(token)

        if len(normalizado) < 3:
            continue

        if normalizado not in vistos:
            vistos.add(normalizado)
            candidatos.append((normalizado, token))

    # Combinações de até 6 tokens consecutivos.
    # Útil para referências separadas por espaço/hífen.
    limite = min(6, len(tokens))

    for tamanho in range(2, limite + 1):

        for i in range(len(tokens) - tamanho + 1):

            partes = tokens[i:i + tamanho]

            combinado = normalizar(
                "".join(partes)
            )

            if len(combinado) < 4:
                continue

            if combinado not in vistos:
                vistos.add(combinado)
                candidatos.append(
                    (
                        combinado,
                        " ".join(partes)
                    )
                )

    return candidatos


def encontrar_referencias_no_pdf(texto, indice):
    """
    Cruza os candidatos extraídos do PDF com as referências
    existentes no Excel.

    Retorna somente códigos que realmente existem no Excel.
    """

    candidatos = gerar_candidatos_pdf(texto)

    encontrados = []
    vistos = set()

    conjunto_referencias = set(indice.keys())

    for normalizado, original in candidatos:

        if normalizado not in conjunto_referencias:
            continue

        if normalizado in vistos:
            continue

        vistos.add(normalizado)

        encontrados.append({
            "normalizado": normalizado,
            "codigo_original": original
        })

    return encontrados


# ============================================================
# PDF DE SAÍDA
# ============================================================

def copiar_pdf(pdf_bytes):
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        writer = PdfWriter()

        for pagina in reader.pages:
            writer.add_page(pagina)

        saida = io.BytesIO()
        writer.write(saida)

        return saida.getvalue()

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao gerar PDF de saída: {e}"
        )


def pdf_base64(pdf_bytes):
    return base64.b64encode(pdf_bytes).decode("utf-8")


# ============================================================
# PROCESSAMENTO
# ============================================================

def processar(pdf_bytes, excel_bytes, tipo="principal"):

    # --------------------------------------------------------
    # Excel
    # --------------------------------------------------------

    df = ler_planilha(excel_bytes)

    colunas = validar_planilha_pcm(df)

    indice = montar_indice(
        df,
        colunas
    )

    # --------------------------------------------------------
    # PDF
    # --------------------------------------------------------

    texto_pdf = extrair_texto_pdf(
        pdf_bytes
    )

    referencias = encontrar_referencias_no_pdf(
        texto_pdf,
        indice
    )

    itens = []

    convertidos = 0
    pendentes = 0
    nao_encontrados = 0

    # --------------------------------------------------------
    # Cruzamento
    # --------------------------------------------------------

    for referencia in referencias:

        chave = referencia["normalizado"]
        codigo_original = referencia["codigo_original"]

        registros = indice.get(
            chave,
            []
        )

        if not registros:
            nao_encontrados += 1

            itens.append({
                "status": "Não encontrado",
                "codigo_original": codigo_original,
                "codigo_convertido": "",
                "descricao": ""
            })

            continue

        # Remove códigos SOL duplicados
        codigos = list({
            r["codigo_item"]
            for r in registros
            if r["codigo_item"]
        })

        # ----------------------------------------------------
        # UMA REFERÊNCIA -> UM CÓDIGO SOL
        # ----------------------------------------------------

        if len(codigos) == 1:

            registro = next(
                r for r in registros
                if r["codigo_item"] == codigos[0]
            )

            convertidos += 1

            itens.append({
                "status": "Convertido",
                "codigo_original": codigo_original,
                "codigo_convertido": codigos[0],
                "descricao": registro["descricao"]
            })

        # ----------------------------------------------------
        # UMA REFERÊNCIA -> VÁRIOS CÓDIGOS
        # ----------------------------------------------------

        else:

            pendentes += 1

            descricoes = list({
                r["descricao"]
                for r in registros
                if r["descricao"]
            })

            itens.append({
                "status": "Pendente",
                "codigo_original": codigo_original,
                "codigo_convertido": " / ".join(codigos),
                "descricao": (
                    "Referência encontrada em mais de um item. "
                    + " | ".join(descricoes[:3])
                )
            })

    # --------------------------------------------------------
    # PDF de saída
    # --------------------------------------------------------

    pdf_saida = copiar_pdf(
        pdf_bytes
    )

    # --------------------------------------------------------
    # Resultado
    # --------------------------------------------------------

    return {
        "total": len(itens),
        "convertidos": convertidos,
        "pendentes": pendentes,
        "nao_encontrados": nao_encontrados,
        "itens": itens,
        "pdf_base64": pdf_base64(pdf_saida),
        "observacao": (
            "Código Item foi utilizado como código SOL e "
            "Referencia foi utilizada como código original."
        )
    }


# ============================================================
# ROTA PRINCIPAL
# ============================================================

@app.post("/converter/principal")
async def converter_principal(
    file_pdf: UploadFile = File(...),
    file_excel: UploadFile = File(...)
):

    try:

        if not file_pdf.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail="O arquivo do documento precisa ser PDF."
            )

        if not file_excel.filename.lower().endswith(
            (".xlsx", ".xls")
        ):
            raise HTTPException(
                status_code=400,
                detail="A planilha precisa ser .xlsx ou .xls."
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

        resultado = processar(
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
            detail=f"Erro no conversor principal: {e}"
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

        if not file_pdf.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail="O arquivo do documento precisa ser PDF."
            )

        if not file_excel.filename.lower().endswith(
            (".xlsx", ".xls")
        ):
            raise HTTPException(
                status_code=400,
                detail="A planilha precisa ser .xlsx ou .xls."
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

        resultado = processar(
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
            detail=f"Erro no conversor CNH: {e}"
        )


# ============================================================
# TESTES
# ============================================================

@app.get("/")
def inicio():
    return {
        "sistema": "Conversor PCM UST",
        "status": "online",
        "versao": "1.1.0"
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
