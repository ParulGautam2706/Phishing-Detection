document.addEventListener('DOMContentLoaded', () => {

    const scanButton = document.getElementById('scanButton');
    const searchInput = document.getElementById('searchInput');
    const resultArea = document.getElementById('resultArea');
    const tableBody = document.querySelector('#searchTable tbody');

    // Report Elements
    const reportBtn = document.getElementById("reportButton");
    const modal = document.getElementById("reportModal");
    const closeBtn = document.getElementById("closeModal");
    const cancelBtn = document.getElementById("cancelBtn");
    const reportForm = document.getElementById("reportForm");

    let scanCount = 0;

    // ================= SCAN FUNCTION =================
    const performScan = () => {
        const url = searchInput.value.trim();
        if (!url) return;

        resultArea.innerHTML = "Scanning...";

        fetch('/predict', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: url })
        })
        .then(res => res.json())
        .then(data => {

            scanCount++;

            // ✅ FIX: correct key
            const risk = data.risk ?? 0;
            const result = data.result ?? "Unknown";

            // 🎨 Color logic improved
            let color = "#2ecc71"; // green
            if (risk > 60) color = "#ff4d4d"; // red
            else if (risk > 20) color = "#f1c40f"; // yellow

            const date = new Date().toLocaleDateString();
            const time = new Date().toLocaleTimeString();

            // Result display
            resultArea.innerHTML =
                `<h2 style="color:${color}">
                    ${result} (${risk}%)
                </h2>`;

            // Table update
            const row = `<tr>
                <td>${scanCount}</td>
                <td style="max-width:200px; overflow:hidden;">${url}</td>
                <td>${date}</td>
                <td>${time}</td>
                <td style="color:${color}; font-weight:bold;">${risk}%</td>
                <td>${result}</td>
            </tr>`;

            tableBody.insertAdjacentHTML('afterbegin', row);

            searchInput.value = "";
            searchInput.focus();
        })
        .catch(err => {
            console.error(err);
            resultArea.innerHTML = "<h2 style='color:red;'>Error scanning URL</h2>";
        });
    };

    scanButton.addEventListener('click', performScan);

    searchInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") performScan();
    });

    // ================= REPORT MODAL =================
    reportBtn.onclick = () => modal.style.display = "block";
    closeBtn.onclick = () => modal.style.display = "none";
    cancelBtn.onclick = () => modal.style.display = "none";

    window.onclick = function(event) {
        if (event.target === modal) {
            modal.style.display = "none";
        }
    };

    // ================= REPORT SUBMIT =================
    reportForm.addEventListener("submit", function(e) {
        e.preventDefault();

        const email = document.getElementById("reportEmail").value;
        const url = document.getElementById("reportUrl").value;
        const type = document.getElementById("reportType").value;
        const message = document.getElementById("reportMessage").value;

        fetch("/report", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                email: email,
                url: url,
                issue: type,
                message: message
            })
        })
        .then(res => res.json())
        .then(data => {
            alert(data.message || "Report submitted successfully!");
            reportForm.reset();
            modal.style.display = "none";
        })
        .catch(err => {
            console.error(err);
            alert("Error submitting report");
        });
    });

});