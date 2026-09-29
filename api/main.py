from collections import defaultdict
import base64
import io
import os
import re
import unicodedata

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
from pypdf import PdfReader, PdfWriter


# ============================================================
# CONFIGURAÇÃO
# ============================================================

app = FastAPI(
    title="Conversor PCM UST",
    description="Conversor de código original para Código Item (SOL) e CNH",
    version="1.1.1"
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
    Valida colunas para o Conversor Principal:
      - Código Item
      - Referencia
      - Descrição
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
                "A planilha principal não possui as colunas necessárias. "
                "São esperadas: 'Código Item', 'Referencia' e 'Descrição'. "
                f"Faltando: {', '.join(faltando)}."
            )
        )

    return colunas


def validar_planilha_cnh(df):
    """
    Valida colunas para o Conversor CNH.
    Ajuste os nomes dos campos abaixo caso a planilha da CNH utilize 
    cabeçalhos diferentes no Excel (ex: 'Codigo CNH', 'Item CNH', etc.).
    """
    colunas = {
        "codigo_cnh": None,
        "referencia": None,
        "descricao": None,
    }

    for coluna in df.columns:
        nome = normalizar(coluna)

        if "CNH" in nome and ("CODIGO" in nome or "ITEM" in nome):
            colunas["codigo_cnh"] = coluna
        elif nome in ("REFERENCIA", "CODIGOORIGINAL", "REF"):
            colunas["referencia"] = coluna
        elif "DESCRICAO" in nome:
            colunas["descricao"] = coluna

    # Fallback caso venha com nomenclaturas padrão caso não ache específico de CNH
    if not colunas["codigo_cnh"]:
        for coluna in df.columns:
            nome = normalizar(coluna)
            if nome == "CODIGOITEM":
                colunas["codigo_cnh"] = coluna
                break

    faltando = [
        chave
        for chave, coluna in colunas.items()
        if coluna is None
    ]

    if faltando:
        raise HTTPException(
            status_code=400,
            detail=(
                "A planilha CNH não possui as colunas necessárias. "
                "Verifique se contém colunas para código CNH, Referência e Descrição. "
                f"Faltando: {', '.join(faltando)}."
            )
        )

    return colunas


def montar_indice(df, colunas, tipo="principal"):
    """
    Cria o índice de busca: referencia normalizada -> lista de registros.
    """
    indice = defaultdict(list)

    coluna_codigo = colunas["codigo_item"] if tipo == "principal" else colunas["codigo_cnh"]
    coluna_ref = colunas["referencia"]
    coluna_desc = colunas["descricao"]

    for _, linha in df.iterrows():
        referencia_original = texto_limpo(linha[coluna_ref])
        referencia_normalizada = normalizar(referencia_original)

        if not referencia_normalizada:
            continue

        codigo_item = texto_limpo(linha[coluna_codigo])

        if codigo_item.endswith(".0"):
            codigo_item = codigo_item[:-2]

        descricao = texto_limpo(linha[coluna_desc])

        registro = {
            "codigo_item": codigo_item,
            "referencia": referencia_original,
            "descricao": descricao,
        }

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
                detail="O PDF não possui texto extraível ou é escaneado."
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
    tokens = re.findall(r"[A-Za-z0-9]+", texto.upper())
    candidatos = []
    vistos = set()

    for token in tokens:
        normalizado = normalizar(token)
        if len(normalizado) < 3:
            continue
        if normalizado not in vistos:
            vistos.add(normalizado)
            candidatos.append((normalizado, token))

    limite = min(6, len(tokens))
    for tamanho in range(2, limite + 1):
        for i in range(len(tokens) - tamanho + 1):
            partes = tokens[i:i + tamanho]
            combinado = normalizar("".join(partes))

            if len(combinado) < 4:
                continue

            if combinado not in vistos:
                vistos.add(combinado)
                candidatos.append((combinado, " ".join(partes)))

    return candidatos


def encontrar_referencias_no_pdf(texto, indice):
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
# PROCESSAMENTO CENTRAL
# ============================================================

def processar(pdf_bytes, excel_bytes, tipo="principal"):
    df = ler_planilha(excel_bytes)

    if tipo == "cnh":
        colunas = validar_planilha_cnh(df)
    else:
        colunas = validar_planilha_pcm(df)

    indice = montar_indice(df, colunas, tipo=tipo)
    texto_pdf = extrair_texto_pdf(pdf_bytes)
    referencias = encontrar_referencias_no_pdf(texto_pdf, indice)

    itens = []
    convertidos = 0
    pendentes = 0
    nao_encontrados = 0

    for referencia in referencias:
        chave = referencia["normalizado"]
        codigo_original = referencia["codigo_original"]
        registros = indice.get(chave, [])

        if not registros:
            nao_encontrados += 1
            itens.append({
                "status": "Não encontrado",
                "codigo_original": codigo_original,
                "codigo_convertido": "",
                "descricao": ""
            })
            continue

        codigos = list({
            r["codigo_item"]
            for r in registros
            if r["codigo_item"]
        })

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
                "descricao": "Referência encontrada em mais de um item. " + " | ".join(descricoes[:3])
            })

    pdf_saida = copiar_pdf(pdf_bytes)

    return {
        "total": len(itens),
        "convertidos": convertidos,
        "pendentes": pendentes,
        "nao_encontrados": nao_encontrados,
        "itens": itens,
        "pdf_base64": pdf_base64(pdf_saida),
        "observacao": f"Processamento concluído para o modo: {tipo.upper()}"
    }


# ============================================================
# ROTAS
# ============================================================

@app.post("/converter/principal")
async def converter_principal(
    file_pdf: UploadFile = File(...),
    file_excel: UploadFile = File(...)
):
    try:
        pdf_bytes = await file_pdf.read()
        excel_bytes = await file_excel.read()
        resultado = processar(pdf_bytes, excel_bytes, tipo="principal")
        return JSONResponse(content=resultado)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro no conversor principal: {e}")


@app.post("/converter/cnh")
async def converter_cnh(
    file_pdf: UploadFile = File(...),
    file_excel: UploadFile = File(...)
):
    try:
        pdf_bytes = await file_pdf.read()
        excel_bytes = await file_excel.read()
        resultado = processar(pdf_bytes, excel_bytes, tipo="cnh")
        return JSONResponse(content=resultado)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro no conversor CNH: {e}")


@app.get("/")
def inicio():
    return {"sistema": "Conversor PCM UST", "status": "online", "versao": "1.1.1"}


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)