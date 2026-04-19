const depthCtx = document.getElementById('depthChart');
const heatCtx = document.getElementById('heatChart');
const signalEl = document.getElementById('signals');

const depthChart = new Chart(depthCtx, {
  type: 'bar',
  data: { labels: [], datasets: [
    { label: 'Bid Vol', data: [], backgroundColor: 'rgba(34,197,94,0.6)' },
    { label: 'Ask Vol', data: [], backgroundColor: 'rgba(239,68,68,0.6)' },
  ]},
  options: { responsive: true, scales: { x: { ticks: { color: '#e5e7eb' } }, y: { ticks: { color: '#e5e7eb' } } } }
});

const heatChart = new Chart(heatCtx, {
  type: 'line',
  data: { labels: [], datasets: [{ label: 'Intensity', data: [], borderColor: '#60a5fa' }] },
  options: { responsive: true, scales: { x: { ticks: { color: '#e5e7eb' } }, y: { ticks: { color: '#e5e7eb' } } } }
});

async function refreshSnapshot() {
  const res = await fetch('/orderbook/snapshot');
  const snap = await res.json();
  const bids = snap.bids.slice(0, 20);
  const asks = snap.asks.slice(0, 20);
  const labels = [...bids.map(b => `B ${b.price.toFixed(1)}`), ...asks.map(a => `A ${a.price.toFixed(1)}`)];
  const bidData = [...bids.map(b => b.volume), ...new Array(asks.length).fill(0)];
  const askData = [...new Array(bids.length).fill(0), ...asks.map(a => a.volume)];

  depthChart.data.labels = labels;
  depthChart.data.datasets[0].data = bidData;
  depthChart.data.datasets[1].data = askData;
  depthChart.update();

  const intensity = [...bids, ...asks].map(l => Math.log10(l.volume + 1));
  heatChart.data.labels = labels;
  heatChart.data.datasets[0].data = intensity;
  heatChart.update();
}

async function loadSignals() {
  const symbol = document.getElementById('symbol').value;
  const res = await fetch(`/signals?symbol=${encodeURIComponent(symbol)}&limit=100`);
  const data = await res.json();
  signalEl.textContent = data.map(s => `${s.ts} | ${s.signal_type} | ${s.side ?? '-'} | score=${s.score.toFixed(3)}`).join('\n');
}

document.getElementById('load').addEventListener('click', loadSignals);
setInterval(refreshSnapshot, 1500);
refreshSnapshot();
