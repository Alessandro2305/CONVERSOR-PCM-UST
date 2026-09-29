document.addEventListener("DOMContentLoaded", () => {
    // URL do seu Back-end no Railway com HTTPS
    const API_URL = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1" 
        ? "http://localhost:8000" 
        : "https://conversor-pcm-ust-production-8a82.up.railway.app";

    // ----------------------------------------------------
    // ABA 1: CONVERSOR PRINCIPAL
    // ----------------------------------------------------
    const btnProcessarPrincipal = document.getElementById("btnProcessar");
    
    btnProcessarPrincipal?.addEventListener("click", async () => {
        const filePdf = document.getElementById("pdfInput")?.files[0];
        const fileExcel = document.getElementById("excelInput")?.files[0];

        if (!filePdf || !fileExcel) {
            alert("Por favor, selecione o arquivo PDF e a planilha Excel!");
            return;
        }

        const formData = new FormData();
        formData.append("file_pdf", filePdf);
        formData.append("file_excel", fileExcel);

        btnProcessarPrincipal.disabled = true;
        
        try {
            const response = await fetch(`${API_URL}/converter/principal`, {
                method: "POST",
                body: formData
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || "Erro no processamento principal.");
            }

            const data = await response.json();
            renderizarResultados(data, "");

            if (data.pdf_base64) {
                converterBase64ParaDownload(data.pdf_base64, `Convertido_Principal_${Date.now()}.pdf`);
            }

            alert("Processamento concluído com sucesso!");

        } catch (error) {
            alert(`Falha: ${error.message}`);
        } finally {
            btnProcessarPrincipal.disabled = false;
        }
    });


    // ----------------------------------------------------
    // ABA 2: CONVERSOR CNH
    // ----------------------------------------------------
    const btnProcessarCNH = document.getElementById("btnProcessarCNH");

    btnProcessarCNH?.addEventListener("click", async () => {
        const filePdf = document.getElementById("pdfInputCNH")?.files[0];
        const fileExcel = document.getElementById("excelInputCNH")?.files[0];

        if (!filePdf || !fileExcel) {
            alert("Por favor, selecione o PDF e a planilha para a CNH!");
            return;
        }

        const formData = new FormData();
        formData.append("file_pdf", filePdf);
        formData.append("file_excel", fileExcel);

        btnProcessarCNH.disabled = true;

        try {
            const response = await fetch(`${API_URL}/converter/cnh`, {
                method: "POST",
                body: formData
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || "Erro no processamento CNH.");
            }

            const data = await response.json();
            renderizarResultados(data, "CNH");

            if (data.pdf_base64) {
                converterBase64ParaDownload(data.pdf_base64, `Convertido_CNH_${Date.now()}.pdf`);
            }

            alert("Processamento CNH concluído com sucesso!");

        } catch (error) {
            alert(`Falha: ${error.message}`);
        } finally {
            btnProcessarCNH.disabled = false;
        }
    });


    // ----------------------------------------------------
    // FUNÇÕES AUXILIARES
    // ----------------------------------------------------
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