const d = window.analyticsData || {};

function chartColors() {
    return {
        grid: "rgba(148, 163, 184, 0.16)",
        text: "#64748b"
    };
}

const c = chartColors();

new Chart(document.getElementById("skillsChart"), {
    type: "bar",
    data: {
        labels: (d.top_skills || []).map(x => x.skill),
        datasets: [{
            label: "Candidates",
            data: (d.top_skills || []).map(x => x.count),
            borderRadius: 8
        }]
    },
    options: {
        indexAxis: "y",
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
            x: { beginAtZero: true, grid: { color: c.grid }, ticks: { color: c.text, precision: 0 } },
            y: { grid: { display: false }, ticks: { color: c.text } }
        }
    }
});

new Chart(document.getElementById("experienceChart"), {
    type: "doughnut",
    data: {
        labels: (d.experience_distribution || []).map(x => x.range),
        datasets: [{ data: (d.experience_distribution || []).map(x => x.count), borderWidth: 0 }]
    },
    options: {
        responsive: true,
        cutout: "68%",
        plugins: { legend: { position: "bottom", labels: { usePointStyle: true, padding: 18 } } }
    }
});

new Chart(document.getElementById("formatChart"), {
    type: "doughnut",
    data: {
        labels: (d.format_distribution || []).map(x => x.format),
        datasets: [{ data: (d.format_distribution || []).map(x => x.count), borderWidth: 0 }]
    },
    options: {
        responsive: true,
        cutout: "68%",
        plugins: { legend: { position: "bottom", labels: { usePointStyle: true, padding: 18 } } }
    }
});

new Chart(document.getElementById("educationChart"), {
    type: "bar",
    data: {
        labels: (d.top_education || []).map(x => x.education),
        datasets: [{
            label: "Detected",
            data: (d.top_education || []).map(x => x.count),
            borderRadius: 8
        }]
    },
    options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
            x: { grid: { display: false }, ticks: { color: c.text, maxRotation: 35, minRotation: 0 } },
            y: { beginAtZero: true, grid: { color: c.grid }, ticks: { color: c.text, precision: 0 } }
        }
    }
});
