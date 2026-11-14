(() => {
  const canvas = document.getElementById('trend-chart');
  if (!canvas || typeof Chart === 'undefined') return;
  const data = JSON.parse(document.getElementById('trend-data').textContent);
  new Chart(canvas, {
    type: 'bar', data: { labels: data.labels, datasets: [{ label: '受付件数', data: data.counts, backgroundColor: '#147d73', borderRadius: 5 }] },
    options: { animation: false, responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } }
  });
})();
