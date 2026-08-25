Document.addEventListener("DOMContentLoaded", () => {
    // Elementos da DOM
    const pdfInput = document.getElementById("pdfInput");
    const excelInput = document.getElementById("excelInput");
    const pdfName = document.getElementById("pdfName");
    const pdfSize = document.getElementById("pdfSize");
    const pdfCheck = document.getElementById("pdfCheck");
    
    const excelName = document.getElementById("excelName");
    const excelSize = document.getElementById("excelSize");
    const excelCheck = document.getElementById("excelCheck");

    const btnProcessar = document.getElementById("btnProcessar");
    const btnExportar = document.getElementById("btnExportar");
    const btnLimpar = document.getElementById("btnLimpar");

    const mTotal = document.getElementById("mTotal");
    const mConvertidos = document.getElementById("mConvertidos");
    const mPendentes = document.getElementById("mPendentes");
    const mNaoEncontrados = document.getElementById("mNaoEncontrados");

    const tbody = document.getElementById("tabelaDados");
    const contadorItens = document.getElementById("contadorItens");

    // Variável global para armazenar os itens e permitir exportação Excel
    let itensProcessados = [];

    // Formata o tamanho do arquivo para KB/MB
    function formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // Atualiza etapa visual do Stepper (1, 2, 3 ou 4)
    function setStep(stepNumber) {
        const boxes = document.querySelectorAll(".container-box .box");
        boxes.forEach((box, index) => {
            if (index + 1 <= stepNumber) {
                box.classList.add("active");
            } else {
                box.classList.remove("active");
            }
        });
    }

    // Atualiza as métricas no painel de cards
    function atualizarMetricas(total = 0, convertidos = 0, pendentes = 0, naoEncontrados = 0) {
        if (mTotal) mTotal.textContent = total;
        if (mConvertidos) mConvertidos.textContent = convertidos;
        if (mPendentes) mPendentes.textContent = pendentes;
        if (mNaoEncontrados) mNaoEncontrados.textContent = naoEncontrados;
        if (contadorItens) contadorItens.textContent = `${total} itens identificados`;
    }

    // Evento seleção de PDF
    pdfInput?.addEventListener("change", (e) => {
        const file = e.target.files[0];
        if (file) {
            if (pdfName) pdfName.textContent = file.name;
            if (pdfSize) pdfSize.textContent = formatBytes(file.size);
            if (pdfCheck) pdfCheck.style.display = "block";
            verificarStatusUpload();
        }
    });

    // Evento seleção de Excel
    excelInput?.addEventListener("change", (e) => {
        const file = e.target.files[0];
        if (file) {
            if (excelName) excelName.textContent = file.name;
            if (excelSize) excelSize.textContent = formatBytes(file.size);
            if (excelCheck) excelCheck.style.display = "block";
            verificarStatusUpload();
        }
    });

    function verificarStatusUpload() {
        if (pdfInput?.files[0] && excelInput?.files[0]) {
            setStep(2);
        } else {
            setStep(1);
        }
    }

    // Suporte a Drag and Drop nas caixas de upload
    document.querySelectorAll(".drop-card").forEach(dropArea => {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropArea.addEventListener(eventName, e => e.preventDefault());
        });

        dropArea.addEventListener('drop', e => {
            const dt = e.dataTransfer;
            const files = dt.files;
            const input = dropArea.querySelector('input[type="file"]');
            
            if (files.length > 0 && input) {
                input.files = files;
                input.dispatchEvent(new Event('change'));
            }
        });
    });

    // Processar Arquivos
    btnProcessar?.addEventListener("click", async () => {
        const filePdf = pdfInput?.files[0];
        const fileExcel = excelInput?.files[0];

        if (!filePdf || !fileExcel) {
            alert("Por favor, selecione tanto o arquivo PDF quanto a planilha Excel!");
            return;
        }

        const formData = new FormData();
        formData.append("pdf_file", filePdf);
        formData.append("excel_depara", fileExcel);

        const textoOriginalBotao = btnProcessar.innerHTML;
        btnProcessar.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Processando...`;
        btnProcessar.disabled = true;

        try {
            // Substitua o trecho do fetch no script.js por:
const response = await fetch('/escrever-no-pdf-original', {
    method: 'POST',
    body: formData
});


            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || "Erro no processamento do servidor.");
            }

            const data = await response.json();
            itensProcessados = data.itens || [];

            // 1. Popula a tabela e atualiza os cards na tela
            renderizarTabelaEMetricas(itensProcessados);

            // 2. Faz o download do PDF gerado a partir do Base64
            if (data.pdf_base64) {
                const byteCharacters = atob(data.pdf_base64);
                const byteNumbers = new Array(byteCharacters.length);
                for (let i = 0; i < byteCharacters.length; i++) {
                    byteNumbers[i] = byteCharacters.charCodeAt(i);
                }
                const byteArray = new Uint8Array(byteNumbers);
                const blob = new Blob([byteArray], { type: 'application/pdf' });

                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'Orcamento_SOL.pdf';
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(url);
            }

            setStep(3);

        } catch (error) {
            console.error("Erro no processamento:", error);
            alert(`Falha no processamento: ${error.message}`);
        } finally {
            btnProcessar.innerHTML = textoOriginalBotao;
            btnProcessar.disabled = false;
        }
    });

    // Renderiza itens dinamicamente na tabela
    function renderizarTabelaEMetricas(listaItens) {
        if (!tbody) return;
        tbody.innerHTML = "";

        let convertidos = 0;
        let pendentes = 0;
        let naoEncontrados = 0;

        listaItens.forEach(item => {
            const tr = document.createElement("tr");

            let badgeHtml = "";
            if (item.status === "Convertido") {
                convertidos++;
                badgeHtml = `<span class="badge-status convertido"><i class="fa-solid fa-circle-check"></i> Convertido</span>`;
            } else if (item.status === "Pendente") {
                pendentes++;
                badgeHtml = `<span class="badge-status warning"><i class="fa-solid fa-clock"></i> Pendente</span>`;
            } else {
                naoEncontrados++;
                badgeHtml = `<span class="badge-status nao-encontrado"><i class="fa-solid fa-circle-xmark"></i> Não encontrado</span>`;
            }

            tr.innerHTML = `
                <td>${badgeHtml}</td>
                <td>${item.codigo_original || '—'}</td>
                <td class="sol-code">${item.codigo_sol || '—'}</td>
                <td>${item.descricao || '—'}</td>
            `;

            tbody.appendChild(tr);
        });

        atualizarMetricas(listaItens.length, convertidos, pendentes, naoEncontrados);
    }

    // Botão Exportar Excel usando SheetJS (xlsx.full.min.js)
    btnExportar?.addEventListener("click", () => {
        if (!itensProcessados || itensProcessados.length === 0) {
            alert("Nenhum dado disponível para exportação. Processes os arquivos primeiro!");
            return;
        }

        setStep(4);

        const dadosFormatados = itensProcessados.map(item => ({
            "Status": item.status,
            "Código Original": item.codigo_original,
            "Código SOL": item.codigo_sol,
            "Descrição": item.descricao
        }));

        const worksheet = XLSX.utils.json_to_sheet(dadosFormatados);
        const workbook = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(workbook, worksheet, "Resultados");

        XLSX.writeFile(workbook, "Resultado_Conversao_PCM.xlsx");
    });

    // Botão Limpar
    btnLimpar?.addEventListener("click", () => {
        if (pdfInput) pdfInput.value = "";
        if (excelInput) excelInput.value = "";
        
        if (pdfName) pdfName.textContent = "Selecione o PDF...";
        if (pdfSize) pdfSize.textContent = "";
        if (pdfCheck) pdfCheck.style.display = "none";

        if (excelName) excelName.textContent = "Selecione a planilha...";
        if (excelSize) excelSize.textContent = "";
        if (excelCheck) excelCheck.style.display = "none";

        if (tbody) tbody.innerHTML = "";
        itensProcessados = [];
        atualizarMetricas(0, 0, 0, 0);
        setStep(1);
    });
});
