document.addEventListener('DOMContentLoaded', () => {
    const runBtn = document.getElementById('runBtn');
    const clearBtn = document.getElementById('clearBtn');

    const instructionEl = document.getElementById('instruction');
    const targetEl = document.getElementById('targetUrl');
    const executeCheckbox = document.getElementById('executeMode');

    const outputEl = document.getElementById('resultContainer');
    const statusEl = document.getElementById('status');

    const historyContainer = document.getElementById('historyContainer');
    const historySearch = document.getElementById('historySearch');
    const historyStatusFilter = document.getElementById('historyStatusFilter');

    /* ----------------------------
       LOAD HISTORY
    ---------------------------- */
    async function loadHistory() {
        try {
            const res = await fetch('/api/history');
            const history = await res.json();
            historyContainer.innerHTML = '';

            const search = (historySearch.value || '').toLowerCase();
            const statusFilter = historyStatusFilter.value;

            history
                .filter(h =>
                    h.instruction.toLowerCase().includes(search) &&
                    (statusFilter === 'ALL' ||
                        h.full_report.status === statusFilter)
                )
                .forEach(run => {
                    const div = document.createElement('div');
                    div.className = 'history-item';
                    div.innerHTML = `
                        <h4>
                            <span class="status-tag ${run.full_report.status}">
                                ${run.full_report.status}
                            </span>
                            ${run.instruction}
                        </h4>
                        <p class="history-meta">
                            ${new Date(run.timestamp).toLocaleString()}
                        </p>
                    `;
                    div.onclick = () => renderRunReport(run.full_report);
                    historyContainer.appendChild(div);
                });
        } catch {
            historyContainer.innerHTML = 'Failed to load history';
        }
    }

    /* ----------------------------
       RENDER RUN REPORT
    ---------------------------- */
    function renderRunReport(data) {
        let html = `
            <div class="summary-box">
                <p><b>Run ID:</b> ${data.id}</p>
                <p><b>Status:</b> ${data.status}</p>
                <p><b>Duration:</b> ${data.duration}s</p>
                <p><b>Total Steps:</b> ${data.total_steps}</p>
                <p><b>Passed:</b> ${data.passed_steps}</p>
                <p><b>Failed:</b> ${data.failed_steps}</p>
            </div>

            <!-- DOWNLOAD BUTTONS -->
            <div style="margin: 15px 0;">
                <a href="/api/download/json/${data.id}"
                   class="secondary small" target="_blank">
                   Download JSON
                </a>
                &nbsp;
                <a href="/api/download/pdf/${data.id}"
                   class="primary small" target="_blank">
                   Download PDF
                </a>
            </div>

            <div class="steps-list">
        `;

        (data.step_results || []).forEach(step => {
    html += `
    <div class="step-card">
        <div class="step-header">
            <span>Step ${step.step}</span>
            <span class="status-tag ${step.status}">
                ${step.status.toUpperCase()}
            </span>
        </div>

        <div>
            <b>Action:</b> ${step.action}
            ${step.detail ? `<p>${step.detail}</p>` : ""}
        </div>

        ${step.screenshot ? `
            <img src="${step.screenshot}"
                 style="width:100%;border-radius:10px;margin-top:10px;">
        ` : ""}
    </div>
    `;
});

        html += `</div>`;
        outputEl.innerHTML = html;
    }

    /* ----------------------------
       RUN TEST
    ---------------------------- */
    runBtn.addEventListener('click', async () => {
        const instruction = instructionEl.value.trim();
        const target = targetEl.value.trim();
        const mode = executeCheckbox.checked ? 'execute' : 'simulate';

        if (!instruction) {
            alert('Enter instruction');
            return;
        }

        statusEl.textContent =
            mode === 'execute' ? 'Executing...' : 'Simulating...';

        outputEl.innerHTML = `
<div style="opacity:0.7; line-height:1.6;">
  🤖 AI is analyzing instruction...<br>
  ⚙️ Generating steps...<br>
  🚀 Executing test...
</div>
`;

        try {
            const res = await fetch('/api/run_test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ instruction, target, mode })
            });

            const data = await res.json();
            renderRunReport(data.result);
            statusEl.textContent = 'Finished';
            loadHistory();
        } catch (e) {
            statusEl.textContent = 'Error';
            outputEl.innerHTML = 'Failed to run test';
        }
    });

    /* ----------------------------
       CLEAR BUTTON (FIXED)
    ---------------------------- */
    clearBtn.addEventListener('click', () => {
        instructionEl.value = '';
        targetEl.value = '';

        outputEl.innerHTML = `
            <div class="empty-state">
                No output yet. Run a test above!
            </div>
        `;

        statusEl.textContent = 'Status: Waiting for input...';

        historySearch.value = '';
        historyStatusFilter.value = 'ALL';
    });

    /* ----------------------------
       HISTORY FILTERS
    ---------------------------- */
    historySearch.addEventListener('input', loadHistory);
    historyStatusFilter.addEventListener('change', loadHistory);

    loadHistory();
});




function scrollToWorkspace() {
    document.getElementById("workspace").scrollIntoView({
        behavior: "smooth"
    });
}
function revealOnScroll() {
    const sections = document.querySelectorAll(".fade-section");

    sections.forEach(section => {
        const rect = section.getBoundingClientRect();

        if (rect.top < window.innerHeight * 0.85) {
            section.classList.add("visible");
        }
    });
}

window.addEventListener("scroll", revealOnScroll);
window.addEventListener("load", revealOnScroll);


const section = document.querySelector(".how-it-works");

window.addEventListener("scroll", () => {
    const sectionTop = section.getBoundingClientRect().top;
    const triggerPoint = window.innerHeight - 100;

    if (sectionTop < triggerPoint) {
        section.classList.add("show");
    }
});


window.onload = () => {
    window.scrollTo(0, 0);
};

window.onload = function () {
    document.querySelector("textarea").value = "";
    document.querySelector("input").value = "";
};
window.onload = function () {
    localStorage.removeItem("instruction");
    localStorage.removeItem("target");

    document.querySelector("textarea").value = "";
    document.querySelector("input").value = "";
};