document.addEventListener("DOMContentLoaded", () => {
    // ----------------------------------------------------
    // ABA 1: CONVERSOR PRINCIPAL (Alfanumérico: Letras e Números)
    // ----------------------------------------------------
    const pdfInputPrincipal = document.getElementById("pdfInput");
    const excelInputPrincipal = document.getElementById("excelInput");
    const btnProcessarPrincipal = document.getElementById("btnProcessar");
    const progressContainerPrincipal = document.getElementById("progressContainer");
    const progressBarPrincipal = document.getElementById("progressBar");
    const progressTextPrincipal = document.getElementById("progressText");
    const progressPercentPrincipal = document.getElementById("progressPercent");

    btnProcessarPrincipal?.addEventListener("click", async () => {
        const filePdf = pdfInputPrincipal?.files[0];
        const fileExcel = excelInputPrincipal?.files[0];

        if (!filePdf || !fileExcel) {
            alert("Por favor, selecione o PDF e a planilha de conversão principal!");
            return;
        }

        const formData = new FormData();
        formData.append("file_pdf", filePdf);
        formData.append("file_excel", fileExcel);

        btnProcessarPrincipal.disabled = true;
        if (progressContainerPrincipal) progressContainerPrincipal.style.display = "block";
        atualizarProgresso(10, "Enviando arquivos para o Conversor Principal...", progressBarPrincipal, progressTextPrincipal, progressPercentPrincipal);

        try {
            const response = await fetch("http://localhost:8000/converter/principal", {
                method: "POST",
                body: formData
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || "Erro no processamento principal.");
            }

            atualizarProgresso(70, "Processando dados e gerando tabela...", progressBarPrincipal, progressTextPrincipal, progressPercentPrincipal);
            
            const data = await response.json();

            // 1. Preenche a tabela e as métricas principais na tela
            renderizarResultados(data, "");

            atualizarProgresso(90, "Gerando PDF convertido...", progressBarPrincipal, progressTextPrincipal, progressPercentPrincipal);
            
            // 2. Converte o Base64 recebido em PDF e dispara o download automático
            if (data.pdf_base64) {
                converterBase64ParaDownload(data.pdf_base64, `Convertido_Principal_${Date.now()}.pdf`);
            }

            atualizarProgresso(100, "Processamento concluído com sucesso!", progressBarPrincipal, progressTextPrincipal, progressPercentPrincipal);
            await new Promise(r => setTimeout(r, 1000));

        } catch (error) {
            alert(`Falha: ${error.message}`);
            if (progressTextPrincipal) progressTextPrincipal.textContent = "Falha no processamento.";
        } finally {
            btnProcessarPrincipal.disabled = false;
            setTimeout(() => { if (progressContainerPrincipal) progressContainerPrincipal.style.display = "none"; }, 1500);
        }
    });


    // ----------------------------------------------------
    // ABA 2: CONVERSOR CNH (Apenas números, ignorando letras)
    // ----------------------------------------------------
    const pdfInputCNH = document.getElementById("pdfInputCNH");
    const excelInputCNH = document.getElementById("excelInputCNH");
    const btnProcessarCNH = document.getElementById("btnProcessarCNH");
    const progressContainerCNH = document.getElementById("progressContainerCNH");
    const progressBarCNH = document.getElementById("progressBarCNH");
    const progressTextCNH = document.getElementById("progressTextCNH");
    const progressPercentCNH = document.getElementById("progressPercentCNH");

    btnProcessarCNH?.addEventListener("click", async () => {
        const filePdf = pdfInputCNH?.files[0];
        const fileExcel = excelInputCNH?.files[0];

        if (!filePdf || !fileExcel) {
            alert("Por favor, selecione o PDF e a planilha para a CNH!");
            return;
        }

        const formData = new FormData();
        formData.append("file_pdf", filePdf);
        formData.append("file_excel", fileExcel);

        btnProcessarCNH.disabled = true;
        if (progressContainerCNH) progressContainerCNH.style.display = "block";
        atualizarProgresso(10, "Enviando arquivos para o Conversor CNH...", progressBarCNH, progressTextCNH, progressPercentCNH);

        try {
            const response = await fetch("http://localhost:8000/converter/cnh", {
                method: "POST",
                body: formData
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || "Erro no processamento CNH.");
            }

            atualizarProgresso(70, "Ignorando letras e preenchendo tabela CNH...", progressBarCNH, progressTextCNH, progressPercentCNH);
            
            const data = await response.json();

            // 1. Preenche a tabela e as métricas específicas da CNH
            renderizarResultados(data, "CNH");

            atualizarProgresso(90, "Gerando PDF CNH convertido...", progressBarCNH, progressTextCNH, progressPercentCNH);
            
            // 2. Converte o Base64 da CNH em PDF e dispara o download automático
            if (data.pdf_base64) {
                converterBase64ParaDownload(data.pdf_base64, `Convertido_CNH_${Date.now()}.pdf`);
            }

            atualizarProgresso(100, "Processamento CNH concluído com sucesso!", progressBarCNH, progressTextCNH, progressPercentCNH);
            await new Promise(r => setTimeout(r, 1000));

        } catch (error) {
            alert(`Falha: ${error.message}`);
            if (progressTextCNH) progressTextCNH.textContent = "Falha no processamento CNH.";
        } finally {
            btnProcessarCNH.disabled = false;
            setTimeout(() => { if (progressContainerCNH) progressContainerCNH.style.display = "none"; }, 1500);
        }
    });


    // ----------------------------------------------------
    // FUNÇÕES AUXILIARES
    // ----------------------------------------------------
    function atualizarProgresso(porcentagem, texto, barra, txtStatus, badge) {
        if (barra) barra.style.width = porcentagem + "%";
        if (txtStatus) txtStatus.textContent = texto;
        if (badge) badge.textContent = porcentagem + "%";
    }

    function converterBase64ParaDownload(base64Data, nomeArquivo) {
        const byteCharacters = atob(base64Data);
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
            byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        const blob = new Blob([byteArray], { type: 'application/pdf' });
        
        const blobUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = nomeArquivo;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(blobUrl);
    }

    function renderizarResultados(data, prefixo = "") {
        const tbody = document.getElementById(prefixo === "CNH" ? "tabelaDadosCNH" : "tabelaDados");
        const contador = document.getElementById(prefixo === "CNH" ? "contadorItensCNH" : "contadorItens");
        
        // Atualiza métricas dinâmicas na interface
        const elTotal = document.getElementById(prefixo === "CNH" ? "mTotalCNH" : "mTotal");
        const elConvertidos = document.getElementById(prefixo === "CNH" ? "mConvertidosCNH" : "mConvertidos");
        const elPendentes = document.getElementById(prefixo === "CNH" ? "mPendentesCNH" : "mPendentes");
        const elNaoEncontrados = document.getElementById(prefixo === "CNH" ? "mNaoEncontradosCNH" : "mNaoEncontrados");

        if (elTotal) elTotal.textContent = data.total || 0;
        if (elConvertidos) elConvertidos.textContent = data.convertidos || 0;
        if (elPendentes) elPendentes.textContent = data.pendentes || 0;
        if (elNaoEncontrados) elNaoEncontrados.textContent = data.nao_encontrados || 0;
        
        if (contador) contador.textContent = `${data.itens?.length || 0} itens identificados`;

        if (!tbody) return;
        tbody.innerHTML = "";

        if (!data.itens || data.itens.length === 0) {
            tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: #64748b;">Nenhum item encontrado.</td></tr>`;
            return;
        }

        data.itens.forEach(item => {
            const tr = document.createElement("tr");
            
            let classeStatusBadge = "badge-convertido";
            if (item.status === "Pendente") classeStatusBadge = "badge-pendente";
            if (item.status === "Não encontrado") classeStatusBadge = "badge-nao-encontrado";

            tr.innerHTML = `
                <td><span class="${classeStatusBadge}">${item.status}</span></td>
                <td><strong>${item.codigo_original}</strong></td>
                <td><span style="color: #0284c7; font-weight: bold;">${item.codigo_convertido}</span></td>
                <td>${item.descricao}</td>
            `;
            tbody.appendChild(tr);
        });
    }
});