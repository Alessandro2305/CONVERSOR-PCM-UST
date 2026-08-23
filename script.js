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
        mTotal.textContent = total;
        mConvertidos.textContent = convertidos;
        mPendentes.textContent = pendentes;
        mNaoEncontrados.textContent = naoEncontrados;
        contadorItens.textContent = `${total} itens identificados`;
    }

    // Eventos de seleção de arquivo PDF
    pdfInput?.addEventListener("change", (e) => {
        const file = e.target.files[0];
        if (file) {
            pdfName.textContent = file.name;
            pdfSize.textContent = formatBytes(file.size);
            pdfCheck.style.display = "block";
            verificarStatusUpload();
        }
    });

    // Eventos de seleção de arquivo Excel
    excelInput?.addEventListener("change", (e) => {
        const file = e.target.files[0];
        if (file) {
            excelName.textContent = file.name;
            excelSize.textContent = formatBytes(file.size);
            excelCheck.style.display = "block";
            verificarStatusUpload();
        }
    });

    function verificarStatusUpload() {
        if (pdfInput.files[0] && excelInput.files[0]) {
            setStep(2); // Muda Stepper para "Processar"
        } else {
            setStep(1);
        }
    }

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
            const response = await fetch('/escrever-no-pdf-original/', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error("Erro na resposta do servidor.");
            }

            // Se o servidor retornar o JSON com os dados extraídos/convertidos:
            const contentType = response.headers.get("content-type");
            if (contentType && contentType.includes("application/json")) {
                const data = await response.json();
                renderizarTabelaEMetricas(data.itens || []);
            } else {
                // Caso o backend devolva diretamente o arquivo PDF processado como Blob
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'resultado_processado.pdf';
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(url);
            }

            setStep(3); // Stepper -> Revisar Resultados

        } catch (error) {
            console.error("Erro no processamento:", error);
            alert("Ocorreu um erro ao conectar com o backend. Verifique se a API está online.");
        } finally {
            btnProcessar.innerHTML = textoOriginalBotao;
            btnProcessar.disabled = false;
        }
    });

    // Renderiza itens dinamicamente na tabela e recalcula os cards do painel
    function renderizarTabelaEMetricas(listaItens) {
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

    // Ação do Botão Exportar (Ativa a Etapa 4)
    btnExportar?.addEventListener("click", () => {
        setStep(4); // Stepper -> Exportar Excel
        alert("Iniciando o download dos resultados em Excel...");
    });

    // Limpar seleções e zerar telas
    btnLimpar?.addEventListener("click", () => {
        pdfInput.value = "";
        excelInput.value = "";
        
        pdfName.textContent = "Selecione o PDF...";
        pdfSize.textContent = "";
        pdfCheck.style.display = "none";

        excelName.textContent = "Selecione a planilha...";
        excelSize.textContent = "";
        excelCheck.style.display = "none";

        tbody.innerHTML = "";
        atualizarMetricas(0, 0, 0, 0);
        setStep(1);
    });
});

// Exemplo do trecho dentro de btnProcessar.addEventListener
const response = await fetch('/escrever-no-pdf-original/', {
    method: 'POST',
    body: formData
});

if (!response.ok) throw new Error("Erro na resposta do servidor.");

const data = await response.json();

// 1. Atualiza Tabela e Painel de Métricas
renderizarTabelaEMetricas(data.itens || []);

// 2. Faz o Download do PDF Modificado via Base64
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