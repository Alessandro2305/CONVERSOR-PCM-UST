document.addEventListener("DOMContentLoaded", () => {
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

    // --- CORREÇÃO DO CLIQUE DE SELEÇÃO DE ARQUIVOS ---
    // Atribuição direta de clique para os cards de upload
    const cardPdf = pdfInput?.closest('.upload-caixa')?.querySelector('.drop-card');
    const cardExcel = excelInput?.closest('.upload-caixa')?.querySelector('.drop-card');

    cardPdf?.addEventListener('click', (e) => {
        // Evita disparo duplo caso o input invisível receba o clique diretamente
        if (e.target !== pdfInput) {
            pdfInput.click();
        }
    });

    cardExcel?.addEventListener('click', (e) => {
        if (e.target !== excelInput) {
            excelInput.click();
        }
    });

    // Evento de alteração do arquivo PDF
    pdfInput?.addEventListener("change", (e) => {
        const file = e.target.files[0];
        if (file) {
            if (pdfName) pdfName.textContent = file.name;
            if (pdfSize) pdfSize.textContent = formatBytes(file.size);
            if (pdfCheck) pdfCheck.style.display = "block";
            verificarStatusUpload();
        }
    });

    // Evento de alteração da planilha Excel
    excelInput?.addEventListener("change", (e) => {
        const file = e.target.files[0];
        if (file) {
            if (excelName) excelName.textContent = file.name;
            if (excelSize) excelSize.textContent = formatBytes(file.size);
            if (excelCheck) excelCheck.style.display = "block";
            verificarStatusUpload();
        }
    });
