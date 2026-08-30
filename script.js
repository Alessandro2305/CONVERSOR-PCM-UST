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

    // Elementos da Barra de Progresso
    const progressContainer = document.getElementById("progressContainer");
    const progressBar = document.getElementById("progressBar");
    const progressPercent = document.getElementById("progressPercent");
    const progressText = document.getElementById("progressText");

    // ENDPOINT OFICIAL NO RENDER
    const API_ENDPOINT = 'https://conversor-pcm-ust.onrender.com/api/escrever-no-pdf-original';

    function formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function escapeHtml(str) {
        return String(str ?? '—')
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

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

    function atualizarMetricas(total = 0, convertidos = 0, pendentes = 0, naoEncontrados = 0) {
        if (mTotal) mTotal.textContent = total;
        if (mConvertidos) mConvertidos.textContent = convertidos;
        if (mPendentes) mPendentes.textContent = pendentes;
        if (mNaoEncontrados) mNaoEncontrados.textContent = naoEncontrados;
        if (contadorItens) contadorItens.textContent = `${total} itens identificados`;
    }

    function setProgress(percent, label) {
        if (progressBar) progressBar.style.width = `${percent}%`;
        if (progressPercent) progressPercent.textContent = `${percent}%`;
        if (progressText && label) progressText.textContent = label;
    }

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

    // Processar Arquivos com Barra de Progresso
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

        btnProcessar.disabled = true;
        if (progressContainer) progressContainer.style.display = "block";

        setProgress(10, "Enviando arquivos para o servidor...");
        const inicioTempo = Date.now(); // Marca inicio da execução

        let atualPercent = 10;
        const intervalProgresso = setInterval(() => {
            if (atualPercent < 90) {
                atualPercent += 10;
                if (atualPercent > 90) atualPercent = 90;
                setProgress(atualPercent, "Cruzando dados e convertendo códigos SOL...");
            }
        }, 150);

        try {
            const response = await fetch(API_ENDPOINT, {
                method: 'POST',
                body: formData
            });

            clearInterval(intervalProgresso);

            if (!response.ok) {
                let detErro = "Erro no servidor de processamento.";
                try {
                    const errorData = await response.json();
                    if (errorData.detail) detErro = errorData.detail;
                } catch (_) { }
                throw new Error(detErro);
            }

            const data = await response.json();

            // 1. Atualiza tabela e métricas na aba Conversor
            const metricas = renderizarTabelaEMetricas(data.itens || []);

            // 2. Cálculo do tempo decorrido em minutos (mínimo de 1 min para exibição)
            const fimTempo = Date.now();
            const duracaoSegundos = Math.round((fimTempo - inicioTempo) / 1000);
            const duracaoMinutos = Math.max(1, Math.round(duracaoSegundos / 60));

            // 3. REGISTRA NO HISTÓRICO LOCALSTORAGE
            registrarHistorico(metricas.convertidos, metricas.total, duracaoMinutos);

            // 4. Download do PDF
            if (data.pdf_base64) {
                const byteCharacters = atob(data.pdf_base64);
                const byteNumbers = new Array(byteCharacters.length);
                for (let i = 0; i < byteCharacters.length; i++) {
                    byteNumbers[i] = byteCharacters.charCodeAt(i);
                }
                const byteArray = new Uint8Array(byteNumbers);
                const blob = new Blob([byteArray], { type: 'application/pdf' });
                const blobUrl = URL.createObjectURL(blob);

                const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
                if (isMobile) {
                    window.open(blobUrl, '_blank');
                } else {
                    const a = document.createElement('a');
                    a.href = blobUrl;
                    a.download = `Orcamento_SOL_${Date.now()}.pdf`;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                }
            }

            // 5. Barra de progresso 100%
            setProgress(100, "Processamento concluído com sucesso!");
            setStep(3);

            await new Promise(r => setTimeout(r, 1500));

        } catch (error) {
            clearInterval(intervalProgresso);
            setProgress(0, "Falha no processamento.");
            console.error("Erro no processamento:", error);
            alert(`Falha no processamento: ${error.message}`);
        } finally {
            btnProcessar.disabled = false;
            if (progressContainer) progressContainer.style.display = "none";
            setProgress(0, "Processando arquivos...");
        }
    });

    function renderizarTabelaEMetricas(listaItens) {
        if (!tbody) return { total: 0, convertidos: 0 };
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
        return { total: listaItens.length, convertidos };
    }

    btnExportar?.addEventListener("click", () => {
        setStep(4);
        alert("Resultado pronto para exportação!");
    });

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
        atualizarMetricas(0, 0, 0, 0);
        setStep(1);
    });

    // Navegação pelas abas da barra lateral
    document.querySelectorAll('.btn-caixa').forEach(btn => {
        btn.addEventListener('click', () => {
            const targetAba = btn.getAttribute('data-aba');
            if (!targetAba) return;

            document.querySelectorAll('.btn-caixa').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            document.querySelectorAll('.aba-conteudo').forEach(aba => {
                aba.style.display = 'none';
                aba.classList.remove('active');
            });

            const abaAtiva = document.getElementById(targetAba);
            if (abaAtiva) {
                abaAtiva.style.display = 'block';
                abaAtiva.classList.add('active');
            }

            if (targetAba === 'aba-historico') {
                renderizarHistorico();
            }
        });
    });

    // Registra o lote processado no localStorage
    function registrarHistorico(qtdConvertidos, totalItens, tempoMinutos) {
        const agora = new Date();
        const dataFormatada = agora.toLocaleDateString('pt-BR') + ' ' + agora.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });

        const lote = {
            data: dataFormatada,
            convertidos: qtdConvertidos,
            total: totalItens,
            tempo: tempoMinutos
        };

        const historico = JSON.parse(localStorage.getItem('pcm_historico')) || [];
        historico.unshift(lote);
        localStorage.setItem('pcm_historico', JSON.stringify(historico));
    }

    // Renderiza a tabela do Histórico e soma os totais
    function renderizarHistorico() {
        const historico = JSON.parse(localStorage.getItem('pcm_historico')) || [];
        const tbodyHistorico = document.getElementById('historicoTbody');
        if (!tbodyHistorico) return;

        tbodyHistorico.innerHTML = '';
        let somaConvertidos = 0;
        let somaTempo = 0;

        if (historico.length === 0) {
            tbodyHistorico.innerHTML = '<tr><td colspan="4" style="text-align:center;">Nenhum registro no histórico.</td></tr>';
            const elTotal = document.getElementById('historicoTotalConvertidos');
            const elTempo = document.getElementById('historicoTempoTotal');
            if (elTotal) elTotal.innerText = '0';
            if (elTempo) elTempo.innerText = '0 min';
            return;
        }

        historico.forEach(item => {
            somaConvertidos += Number(item.convertidos);
            somaTempo += Number(item.tempo);

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${item.data}</td>
                <td><strong>${item.convertidos}</strong></td>
                <td>${item.total}</td>
                <td>${item.tempo} min</td>
            `;
            tbodyHistorico.appendChild(tr);
        });

        const elTotal = document.getElementById('historicoTotalConvertidos');
        const elTempo = document.getElementById('historicoTempoTotal');
        if (elTotal) elTotal.innerText = somaConvertidos;
        if (elTempo) elTempo.innerText = `${somaTempo} min`;
    }

    document.getElementById('btnLimparHistorico')?.addEventListener('click', () => {
    if (confirm('Deseja realmente apagar todo o histórico de execuções?')) {
        // Remove do LocalStorage (substitua pelo nome exato da chave usada no seu script)
        localStorage.removeItem('historicoConversor'); 
        
        // Zera a tabela na tela
        document.getElementById('historicoTbody').innerHTML = '';
        
        // Zera os contadores de topo
        if(document.getElementById('historicoTotalConvertidos')) {
            document.getElementById('historicoTotalConvertidos').innerText = '0';
        }
        if(document.getElementById('historicoTempoTotal')) {
            document.getElementById('historicoTempoTotal').innerText = '0 min';
        }
    }
});
});