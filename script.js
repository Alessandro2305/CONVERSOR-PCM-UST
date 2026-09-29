
document.addEventListener("DOMContentLoaded", () => {
    "use strict";

    // =========================================================
    // 1. CONFIGURAÇÃO
    // =========================================================

    const API_URL =
        window.location.hostname === "localhost" ||
        window.location.hostname === "127.0.0.1"
            ? "http://localhost:8000"
            : "https://conversor-pcm-ust-production-8a82.up.railway.app";

    const CHAVE_HISTORICO = "pcm_ust_historico_v1";

    // Resultados separados para cada conversor
    const resultados = {
        principal: null,
        cnh: null
    };

    // Referências dos elementos HTML
    const $ = (id) => document.getElementById(id);

    // =========================================================
    // 2. FUNÇÕES GERAIS
    // =========================================================

    function definirTexto(id, texto) {
        const elemento = $(id);

        if (elemento) {
            elemento.textContent = texto ?? "";
        }
    }

    function formatarTamanho(bytes) {
        if (!bytes) return "0 Bytes";

        const unidades = ["Bytes", "KB", "MB", "GB"];
        const indice = Math.min(
            Math.floor(Math.log(bytes) / Math.log(1024)),
            unidades.length - 1
        );

        return (
            (bytes / Math.pow(1024, indice)).toFixed(2) +
            " " +
            unidades[indice]
        );
    }

    function formatarData(data) {
        return new Date(data).toLocaleString("pt-BR", {
            dateStyle: "short",
            timeStyle: "short"
        });
    }

    function formatarNumero(numero) {
        return Number(numero || 0).toLocaleString("pt-BR");
    }

    function escaparHTML(valor) {
        return String(valor ?? "").replace(/[&<>"']/g, (caractere) => {
            const entidades = {
                "&": "&amp;",
                "<": "&lt;",
                ">": "&gt;",
                '"': "&quot;",
                "'": "&#039;"
            };

            return entidades[caractere];
        });
    }

    function mostrarErro(mensagem) {
        alert(mensagem || "Ocorreu um erro inesperado.");
    }

    // =========================================================
    // 3. NAVEGAÇÃO DO MENU LATERAL
    // =========================================================

    const botoesMenu = document.querySelectorAll(".btn-caixa");

    function ativarAba(nomeAba, atualizarMenu = true) {
        const abaSelecionada = $(nomeAba);

        if (!abaSelecionada) {
            mostrarErro(
                "A aba solicitada ainda não existe no HTML: " + nomeAba
            );
            return;
        }

        document.querySelectorAll(".aba-conteudo").forEach((aba) => {
            aba.classList.remove("active");
            aba.style.display = "none";
        });

        abaSelecionada.classList.add("active");
        abaSelecionada.style.display = "block";

        if (atualizarMenu) {
            botoesMenu.forEach((botao) => {
                botao.classList.toggle(
                    "active",
                    botao.dataset.aba === nomeAba
                );
            });
        }
    }

    botoesMenu.forEach((botao) => {
        botao.addEventListener("click", () => {
            const nomeAba = botao.dataset.aba;

            if (nomeAba) {
                ativarAba(nomeAba);
            }
        });
    });

    // Inicializa a aba selecionada no HTML
    const abaInicial = document.querySelector(".aba-conteudo.active");

    if (abaInicial) {
        ativarAba(abaInicial.id);
    } else if ($("aba-conversor")) {
        ativarAba("aba-conversor");
    }

    // =========================================================
    // 4. UPLOAD DOS ARQUIVOS
    // =========================================================

    function configurarUpload(inputId, nomeId, tamanhoId, checkId) {
        const input = $(inputId);
        const nome = $(nomeId);
        const tamanho = $(tamanhoId);
        const check = $(checkId);

        if (!input) return;

        input.addEventListener("change", () => {
            const arquivo = input.files?.[0];

            if (!arquivo) {
                if (check) check.style.display = "none";
                return;
            }

            if (nome) {
                nome.textContent = arquivo.name;
                nome.style.color = "#0284c7";
                nome.style.fontWeight = "bold";
            }

            if (tamanho) {
                tamanho.textContent = formatarTamanho(arquivo.size);
            }

            if (check) {
                check.style.display = "inline-block";
                check.style.color = "#16a34a";
            }
        });
    }

    // Conversor principal
    configurarUpload("pdfInput", "pdfName", "pdfSize", "pdfCheck");
    configurarUpload("excelInput", "excelName", "excelSize", "excelCheck");

    // Conversor CNH
    configurarUpload(
        "pdfInputCNH",
        "pdfNameCNH",
        "pdfSizeCNH",
        "pdfCheckCNH"
    );

    configurarUpload(
        "excelInputCNH",
        "excelNameCNH",
        "excelSizeCNH",
        "excelCheckCNH"
    );

    // =========================================================
    // 5. BARRA DE PROGRESSO
    // =========================================================

    const progresso = {
        principal: null,
        cnh: null
    };

    function atualizarProgresso(tipo, percentual, mensagem) {
        const sufixo = tipo === "cnh" ? "CNH" : "";

        const container = $("progressContainer" + sufixo);
        const barra = $("progressBar" + sufixo);
        const texto = $("progressText" + sufixo);
        const porcentagem = $("progressPercent" + sufixo);

        if (container) container.style.display = "block";

        const valor = Math.max(0, Math.min(100, percentual));

        if (barra) barra.style.width = valor + "%";
        if (texto && mensagem) texto.textContent = mensagem;

        if (porcentagem) {
            porcentagem.textContent = Math.round(valor) + "%";
        }
    }

    function iniciarProgresso(tipo) {
        pararProgresso(tipo);

        atualizarProgresso(tipo, 5, "Enviando arquivos para processamento...");

        let percentual = 5;

        progresso[tipo] = setInterval(() => {
            if (percentual < 90) {
                percentual += percentual < 40 ? 8 : 3;

                atualizarProgresso(
                    tipo,
                    Math.min(percentual, 90),
                    percentual < 35
                        ? "Enviando arquivos..."
                        : percentual < 65
                            ? "Lendo PDF e cruzando códigos com Excel..."
                            : "Preparando os resultados..."
                );
            }
        }, 500);
    }

    function pararProgresso(tipo, sucesso = false) {
        if (progresso[tipo]) {
            clearInterval(progresso[tipo]);
            progresso[tipo] = null;
        }

        if (sucesso) {
            atualizarProgresso(tipo, 100, "Processamento concluído.");
        }

        const sufixo = tipo === "cnh" ? "CNH" : "";
        const container = $("progressContainer" + sufixo);

        // Mantém o resultado de sucesso visível por um momento.
        if (!sucesso && container) {
            container.style.display = "none";
        }
    }

    // =========================================================
    // 6. DOWNLOAD DO PDF
    // =========================================================

    function baixarPDF(base64, nomeArquivo) {
        if (!base64) return;

        try {
            const conteudo = base64.includes(",")
                ? base64.split(",")[1]
                : base64;

            const binario = atob(conteudo);
            const tamanho = 1024 * 512;
            const partes = [];

            for (let inicio = 0; inicio < binario.length; inicio += tamanho) {
                const trecho = binario.slice(inicio, inicio + tamanho);
                const bytes = new Uint8Array(trecho.length);

                for (let i = 0; i < trecho.length; i++) {
                    bytes[i] = trecho.charCodeAt(i);
                }

                partes.push(bytes);
            }

            const blob = new Blob(partes, {
                type: "application/pdf"
            });

            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");

            link.href = url;
            link.download = nomeArquivo;

            document.body.appendChild(link);
            link.click();
            link.remove();

            // Aguarda o navegador iniciar o download antes de liberar a URL.
            setTimeout(() => URL.revokeObjectURL(url), 1000);
        } catch (erro) {
            console.error("Erro ao gerar o download do PDF:", erro);
            mostrarErro("Não foi possível gerar o download do PDF.");
        }
    }

    // =========================================================
    // 7. RENDERIZAÇÃO DOS RESULTADOS
    // =========================================================

    function obterClasseStatus(status) {
        const valor = String(status || "").toLowerCase();

        if (valor.includes("não encontrado") || valor.includes("nao encontrado")) {
            return "badge-nao-encontrado";
        }

        if (valor.includes("pendente")) {
            return "badge-pendente";
        }

        return "badge-convertido";
    }

    function renderizarResultados(data, tipo) {
        const cnh = tipo === "cnh";
        const sufixo = cnh ? "CNH" : "";

        const tbody = $("tabelaDados" + sufixo);
        const contador = $("contadorItens" + sufixo);

        const total = Number(data.total ?? data.itens?.length ?? 0);
        const convertidos = Number(data.convertidos ?? 0);
        const pendentes = Number(data.pendentes ?? 0);
        const naoEncontrados = Number(data.nao_encontrados ?? 0);

        definirTexto("mTotal" + sufixo, formatarNumero(total));
        definirTexto("mConvertidos" + sufixo, formatarNumero(convertidos));
        definirTexto("mPendentes" + sufixo, formatarNumero(pendentes));
        definirTexto(
            "mNaoEncontrados" + sufixo,
            formatarNumero(naoEncontrados)
        );

        const itens = Array.isArray(data.itens) ? data.itens : [];

        if (contador) {
            contador.textContent =
                formatarNumero(itens.length) +
                (itens.length === 1 ? " item identificado" : " itens identificados");
        }

        if (!tbody) return;

        tbody.innerHTML = "";

        if (itens.length === 0) {
            const linha = document.createElement("tr");
            const celula = document.createElement("td");

            celula.colSpan = 4;
            celula.style.textAlign = "center";
            celula.style.color = "#64748b";
            celula.textContent =
                data.mensagem || "Nenhum item encontrado.";

            linha.appendChild(celula);
            tbody.appendChild(linha);

            return;
        }

        itens.forEach((item) => {
            const linha = document.createElement("tr");

            const celulaStatus = document.createElement("td");
            const badge = document.createElement("span");

            badge.className = obterClasseStatus(item.status);
            badge.textContent = item.status || "Sem status";

            celulaStatus.appendChild(badge);

            const celulaOriginal = document.createElement("td");
            const codigoOriginal = document.createElement("strong");

            codigoOriginal.textContent = item.codigo_original ?? "";
            celulaOriginal.appendChild(codigoOriginal);

            const celulaConvertido = document.createElement("td");
            const codigoConvertido = document.createElement("span");

            codigoConvertido.style.color = "#0284c7";
            codigoConvertido.style.fontWeight = "bold";
            codigoConvertido.textContent = item.codigo_convertido ?? "";

            celulaConvertido.appendChild(codigoConvertido);

            const celulaDescricao = document.createElement("td");
            celulaDescricao.textContent = item.descricao ?? "";

            linha.append(
                celulaStatus,
                celulaOriginal,
                celulaConvertido,
                celulaDescricao
            );

            tbody.appendChild(linha);
        });
    }

    // =========================================================
    // 8. HISTÓRICO DE PROCESSAMENTOS
    // =========================================================

    function carregarHistorico() {
        try {
            const dados = localStorage.getItem(CHAVE_HISTORICO);
            const historico = dados ? JSON.parse(dados) : [];

            return Array.isArray(historico) ? historico : [];
        } catch (erro) {
            console.error("Erro ao ler histórico:", erro);
            return [];
        }
    }

    function salvarHistorico(registro) {
        try {
            const historico = carregarHistorico();

            historico.unshift(registro);

            // Limita a 500 registros para evitar crescimento excessivo.
            localStorage.setItem(
                CHAVE_HISTORICO,
                JSON.stringify(historico.slice(0, 500))
            );

            atualizarHistorico();
        } catch (erro) {
            console.error("Erro ao salvar histórico:", erro);
            mostrarErro(
                "O processamento terminou, mas não foi possível salvar o histórico local."
            );
        }
    }

    function atualizarHistorico() {
        const historico = carregarHistorico();
        const tbody = $("historicoTbody");

        let totalConvertidos = 0;
        let tempoTotalSegundos = 0;

        historico.forEach((registro) => {
            totalConvertidos += Number(registro.convertidos || 0);
            tempoTotalSegundos += Number(registro.tempo_segundos || 0);
        });

        definirTexto(
            "historicoTotalConvertidos",
            formatarNumero(totalConvertidos)
        );

        const minutos = Math.round(tempoTotalSegundos / 60);

        definirTexto(
            "historicoTempoTotal",
            formatarNumero(minutos) + " min"
        );

        if (!tbody) return;

        tbody.innerHTML = "";

        if (historico.length === 0) {
            const linha = document.createElement("tr");
            const celula = document.createElement("td");

            celula.colSpan = 4;
            celula.style.textAlign = "center";
            celula.style.color = "#64748b";
            celula.textContent = "Nenhum processamento registrado.";

            linha.appendChild(celula);
            tbody.appendChild(linha);

            return;
        }

        historico.forEach((registro) => {
            const linha = document.createElement("tr");

            const data = document.createElement("td");
            data.textContent = formatarData(registro.data);

            const convertidos = document.createElement("td");
            convertidos.textContent = formatarNumero(registro.convertidos);

            const total = document.createElement("td");
            total.textContent = formatarNumero(registro.total);

            const tempo = document.createElement("td");
            tempo.textContent =
                Number(registro.tempo_segundos || 0).toLocaleString("pt-BR", {
                    maximumFractionDigits: 1
                }) + " s";

            linha.append(data, convertidos, total, tempo);
            tbody.appendChild(linha);
        });
    }

    const btnLimparHistorico = $("btnLimparHistorico");

    btnLimparHistorico?.addEventListener("click", () => {
        if (!confirm("Deseja apagar todo o histórico deste navegador?")) {
            return;
        }

        try {
            localStorage.removeItem(CHAVE_HISTORICO);
            atualizarHistorico();
            alert("Histórico local apagado.");
        } catch (erro) {
            mostrarErro("Não foi possível apagar o histórico.");
        }
    });

    // =========================================================
    // 9. PROCESSAMENTO DOS ARQUIVOS
    // =========================================================

    async function processarArquivos(tipo) {
        const cnh = tipo === "cnh";

        const pdfInput = $(cnh ? "pdfInputCNH" : "pdfInput");
        const excelInput = $(cnh ? "excelInputCNH" : "excelInput");

        const botao = $(cnh ? "btnProcessarCNH" : "btnProcessar");

        const arquivoPDF = pdfInput?.files?.[0];
        const arquivoExcel = excelInput?.files?.[0];

        if (!arquivoPDF || !arquivoExcel) {
            mostrarErro(
                cnh
                    ? "Selecione o PDF e a planilha Excel do Conversor CNH."
                    : "Selecione o PDF e a planilha Excel do Conversor Principal."
            );
            return;
        }

        if (!arquivoPDF.name.toLowerCase().endsWith(".pdf")) {
            mostrarErro("O arquivo do documento precisa ser um PDF.");
            return;
        }

        const nomeExcel = arquivoExcel.name.toLowerCase();

        if (
            !nomeExcel.endsWith(".xlsx") &&
            !nomeExcel.endsWith(".xls")
        ) {
            mostrarErro("A planilha precisa estar no formato .xlsx ou .xls.");
            return;
        }

        const endpoint = cnh
            ? "/converter/cnh"
            : "/converter/principal";

        const formData = new FormData();

        formData.append("file_pdf", arquivoPDF);
        formData.append("file_excel", arquivoExcel);

        const textoOriginal = cnh
            ? "PROCESSAR ARQUIVOS CNH"
            : "PROCESSAR ARQUIVOS";

        const inicio = performance.now();

        if (botao) {
            botao.disabled = true;
            botao.textContent = "Processando...";
        }

        iniciarProgresso(tipo);

        try {
            const response = await fetch(API_URL + endpoint, {
                method: "POST",
                body: formData
            });

            let data;

            try {
                data = await response.json();
            } catch {
                throw new Error(
                    "O servidor retornou uma resposta inválida. Verifique o backend."
                );
            }

            if (!response.ok) {
                const detalhe = typeof data.detail === "string"
                    ? data.detail
                    : JSON.stringify(data.detail || data);

                throw new Error(
                    detalhe || "Erro HTTP " + response.status
                );
            }

            if (!Array.isArray(data.itens)) {
                throw new Error(
                    "O servidor não retornou a lista de itens esperada."
                );
            }

            resultados[tipo] = data;

            renderizarResultados(data, tipo);

            const duracao = (performance.now() - inicio) / 1000;

            salvarHistorico({
                data: new Date().toISOString(),
                tipo: cnh ? "CNH" : "Principal",
                total: Number(data.total ?? data.itens.length),
                convertidos: Number(data.convertidos ?? 0),
                pendentes: Number(data.pendentes ?? 0),
                nao_encontrados: Number(data.nao_encontrados ?? 0),
                tempo_segundos: duracao,
                nome_pdf: arquivoPDF.name,
                nome_excel: arquivoExcel.name,
                itens: data.itens
            });

            pararProgresso(tipo, true);

            if (data.pdf_base64) {
                baixarPDF(
                    data.pdf_base64,
                    (cnh ? "Convertido_CNH_" : "Convertido_Principal_") +
                        Date.now() +
                        ".pdf"
                );
            }

            alert(
                "Processamento concluído!\n\n" +
                "Total de itens: " + formatarNumero(data.total) + "\n" +
                "Convertidos: " + formatarNumero(data.convertidos) + "\n" +
                "Pendentes: " + formatarNumero(data.pendentes) + "\n" +
                "Não encontrados: " +
                    formatarNumero(data.nao_encontrados)
            );

        } catch (erro) {
            console.error("Erro no processamento:", erro);

            pararProgresso(tipo);

            mostrarErro(
                "Falha no processamento:\n" +
                (erro.message || "Erro desconhecido") +
                "\n\nVerifique a conexão com a API e os arquivos enviados."
            );

        } finally {
            if (botao) {
                botao.disabled = false;
                botao.textContent = textoOriginal;
            }
        }
    }

    $("btnProcessar")?.addEventListener("click", () => {
        processarArquivos("principal");
    });

    $("btnProcessarCNH")?.addEventListener("click", () => {
        processarArquivos("cnh");
    });

    // =========================================================
    // 10. EXPORTAÇÃO PARA EXCEL
    // =========================================================

    function exportarExcel(tipo) {
        const cnh = tipo === "cnh";
        const dados = resultados[tipo];

        if (!dados || !Array.isArray(dados.itens) || dados.itens.length === 0) {
            mostrarErro(
                "Não há resultados para exportar. Processe os arquivos primeiro."
            );
            return;
        }

        if (typeof XLSX === "undefined") {
            mostrarErro(
                "A biblioteca XLSX não foi carregada. Verifique a conexão com a internet e a inclusão do arquivo xlsx.full.min.js no HTML."
            );
            return;
        }

        try {
            const linhas = dados.itens.map((item) => ({
                "STATUS": item.status || "",
                "CÓDIGO ORIGINAL": item.codigo_original || "",
                [cnh ? "CÓDIGO CNH (CONVERTIDO)" : "CÓDIGO SOL (CONVERTIDO)"]:
                    item.codigo_convertido || "",
                "DESCRIÇÃO DO ITEM": item.descricao || ""
            }));

            const planilha = XLSX.utils.json_to_sheet(linhas);

            planilha["!cols"] = [
                { wch: 20 },
                { wch: 25 },
                { wch: 30 },
                { wch: 60 }
            ];

            const resumo = XLSX.utils.aoa_to_sheet([
                ["CONVERSOR PCM UST"],
                [cnh ? "Conversor CNH" : "Conversor Principal"],
                [],
                ["Indicador", "Quantidade"],
                ["Total de itens", Number(dados.total || 0)],
                ["Convertidos", Number(dados.convertidos || 0)],
                ["Pendentes", Number(dados.pendentes || 0)],
                ["Não encontrados", Number(dados.nao_encontrados || 0)],
                [],
                ["Data da exportação", formatarData(new Date())]
            ]);

            resumo["!cols"] = [
                { wch: 30 },
                { wch: 25 }
            ];

            const livro = XLSX.utils.book_new();

            XLSX.utils.book_append_sheet(
                livro,
                resumo,
                "Resumo"
            );

            XLSX.utils.book_append_sheet(
                livro,
                planilha,
                "Resultados"
            );

            const nomeArquivo =
                (cnh ? "Resultado_CNH_" : "Resultado_Principal_") +
                new Date().toISOString().slice(0, 10) +
                ".xlsx";

            XLSX.writeFile(livro, nomeArquivo);

        } catch (erro) {
            console.error("Erro na exportação:", erro);
            mostrarErro("Não foi possível gerar a planilha Excel.");
        }
    }

    $("btnExportar")?.addEventListener("click", () => {
        exportarExcel("principal");
    });

    $("btnExportarCNH")?.addEventListener("click", () => {
        exportarExcel("cnh");
    });

    // =========================================================
    // 11. LIMPAR CONVERSOR
    // =========================================================

    function limparConversor(tipo) {
        const cnh = tipo === "cnh";
        const sufixo = cnh ? "CNH" : "";

        const prefixoInput = cnh ? "CNH" : "";

        const idsArquivos = cnh
            ? ["pdfInputCNH", "excelInputCNH"]
            : ["pdfInput", "excelInput"];

        if (
            !confirm(
                "Deseja limpar os arquivos e resultados deste conversor?"
            )
        ) {
            return;
        }

        idsArquivos.forEach((id) => {
            const input = $(id);

            if (input) input.value = "";
        });

        const nomes = cnh
            ? [
                ["pdfNameCNH", "Selecione o PDF..."],
                ["excelNameCNH", "Selecione a planilha..."]
            ]
            : [
                ["pdfName", "Selecione o PDF..."],
                ["excelName", "Selecione a planilha..."]
            ];

        nomes.forEach(([id, texto]) => {
            const elemento = $(id);

            if (elemento) {
                elemento.textContent = texto;
                elemento.style.color = "";
                elemento.style.fontWeight = "";
            }
        });

        const tamanhos = cnh
            ? ["pdfSizeCNH", "excelSizeCNH"]
            : ["pdfSize", "excelSize"];

        tamanhos.forEach((id) => definirTexto(id, ""));

        const checks = cnh
            ? ["pdfCheckCNH", "excelCheckCNH"]
            : ["pdfCheck", "excelCheck"];

        checks.forEach((id) => {
            const elemento = $(id);

            if (elemento) elemento.style.display = "none";
        });

        resultados[tipo] = null;

        const tbody = $("tabelaDados" + sufixo);

        if (tbody) tbody.innerHTML = "";

        definirTexto("mTotal" + sufixo, "0");
        definirTexto("mConvertidos" + sufixo, "0");
        definirTexto("mPendentes" + sufixo, "0");
        definirTexto("mNaoEncontrados" + sufixo, "0");
        definirTexto("contadorItens" + sufixo, "0 itens identificados");

        pararProgresso(tipo);

        // Reinicia a barra visual.
        atualizarProgresso(tipo, 0, "Aguardando arquivos...");

        const container = $("progressContainer" + sufixo);

        if (container) container.style.display = "none";
    }

    $("btnLimpar")?.addEventListener("click", () => {
        limparConversor("principal");
    });

    $("btnLimparCNH")?.addEventListener("click", () => {
        limparConversor("cnh");
    });

    // =========================================================
    // 12. INICIALIZAÇÃO DO HISTÓRICO
    // =========================================================

    atualizarHistorico();

    // =========================================================
    // 13. INFORMAÇÕES PARA DIAGNÓSTICO
    // =========================================================

    console.info("Conversor PCM UST iniciado.");
    console.info("API configurada:", API_URL);

});