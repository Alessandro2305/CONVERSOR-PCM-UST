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

    let itensProcessados = [];

    // DEFINE O ENDPOINT CORRETO DA API (Ajuste se o domínio for diferente)
    const API_ENDPOINT = '/api/escrever-no-pdf-original';

    // Função utilitária para conversão de Base64 para Blob sem estouro de memória
    function base64ToBlob(base64Data, contentType = 'application/pdf') {
        const byteCharacters = atob(base64Data);
        const byteArrays = [];
        const sliceSize = 512;

        for (let offset = 0; offset < byteCharacters.length; offset += sliceSize) {
            const slice = byteCharacters.slice(offset, offset + sliceSize);
            const byteNumbers = new Array(slice.length);
            for (let i = 0; i < slice.length; i++) {
                byteNumbers[i] = slice.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
            byteArrays.push(byteArray);
        }
        return new Blob(byteArrays, { type: contentType });
    }

    // Higienização contra XSS
    function escapeHtml(str) {
        return String(str ?? '—')
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Formata tamanho em KB/MB
    function formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // Atualiza etapa visual do Stepper
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

    // Atualiza métricas
    function atualizarMetricas(total = 0, convertidos = 0, pendentes = 0, naoEncontrados = 0) {
        if (mTotal) mTotal.textContent = total;
        if (mConvertidos) mConvertidos.textContent = convertidos;
        if (mPendentes) mPendentes.textContent = pendentes;
        if (mNaoEncontrados) mNaoEncontrados.textContent = naoEncontrados;
        if (contadorItens) contadorItens.textContent = `${total} itens identificados`;
    }

    // Disparo manual do input de arquivos
    const cardPdf = pdfInput?.closest('.upload-caixa')?.querySelector('.drop-card');
    const cardExcel = excelInput?.closest('.upload-caixa')?.querySelector('.drop-card');

    cardPdf?.addEventListener('click', (e) => {
        if (e.target !== pdfInput) pdfInput?.click();
    });

    cardExcel?.addEventListener('click', (e) => {
        if (e.target !== excelInput) excelInput?.click();
    });

    // Eventos de alteração dos inputs
    pdfInput?.addEventListener("change", (e) => {
        const file = e.target.files[0];
        if (file) {
            if (pdfName) pdfName.textContent = file.name;
            if (pdfSize) pdfSize.textContent = formatBytes(file.size);
            if (pdfCheck) pdfCheck.style.display = "block";
            verificarStatusUpload();
        }
    });

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

    // Suporte a Drag and Drop
    document.querySelectorAll(".drop-card").forEach(dropArea => {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropArea.addEventListener(eventName, e => e.preventDefault());
        });

        dropArea.addEventListener('drop', e => {
            const dt = e.dataTransfer;
            const files = dt.files;
            const input = dropArea.querySelector('input[type="file"]');
            
            if (files.length > 0 && input) {
                const container = new DataTransfer();
                container.items.add(files[0]);
                input.files = container.files;
                input.dispatchEvent(new Event('change'));
            }
        });
    });

    // Processar Arquivos via API Serverless
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
            const response = await fetch(API_ENDPOINT, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                let mensagemErro = `Erro ${response.status}: Falha de comunicação com o servidor.`;
                try {
                    const errorData = await response.json();
                    if (errorData.detail) mensagemErro = errorData.detail;
                } catch (_) {
                    // Trata retornos que não sejam JSON (ex: HTML de erro 500 do servidor)
                }
                throw new Error(mensagemErro);
            }

            const data = await response.json();
            itensProcessados = data.itens || [];

            // Renderiza dados na interface
            renderizarTabelaEMetricas(itensProcessados);

            // Download automático e otimizado do PDF
            if (data.pdf_base64) {
                const blob = base64ToBlob(data.pdf_base64, 'application/pdf');
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

    // Renderização segura da tabela e atualização de métricas
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
                <td>${escapeHtml(item.codigo_original)}</td>
                <td class="sol-code">${escapeHtml(item.codigo_sol)}</td>
                <td>${escapeHtml(item.descricao)}</td>
            `;

            tbody.appendChild(tr);
        });

        atualizarMetricas(listaItens.length, convertidos, pendentes, naoEncontrados);
    }

    // Exportação dos dados para Excel
    btnExportar?.addEventListener("click", () => {
        if (!itensProcessados || itensProcessados.length === 0) {
            alert("Nenhum dado disponível para exportação. Processe os arquivos primeiro!");
            return;
        }

        setStep(4);

        const dadosFormatados = itensProcessados.map(item => ({
            "Status": item.status || '',
            "Código Original": item.codigo_original || '',
            "Código SOL": item.codigo_sol || '',
            "Descrição": item.descricao || ''
        }));

        const worksheet = XLSX.utils.json_to_sheet(dadosFormatados);
        const workbook = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(workbook, worksheet, "Resultados");

        XLSX.writeFile(workbook, "Resultado_Conversao_PCM.xlsx");
    });

    // Reset completo do formulário
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
