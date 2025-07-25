let currentStockData = null;
let currentAnalysisType = null;

async function fetchStockData() {
  const symbol = document.getElementById('stockSymbol').value;
  const startDate = document.getElementById('startDate').value;
  const endDate = document.getElementById('endDate').value;

  if (!symbol || !startDate || !endDate) {
    showError('Please fill in all fields');
    return;
  }

  try {
    const fetchBtn = document.querySelector('.fetch-btn');
    fetchBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';
    fetchBtn.disabled = true;

    const response = await fetch('/api/stock-data', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol, start_date: startDate, end_date: endDate })
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();

    if (data.success) {
      currentStockData = { symbol, start_date: startDate, end_date: endDate };
      displayStockInfo(data);
      document.getElementById('analysisGrid').style.display = 'grid';
      hideError();
    } else {
      throw new Error(data.error || 'Failed to fetch stock data');
    }
  } catch (error) {
    console.error('Error fetching stock data:', error);
    showError(error.message || 'Failed to fetch stock data. Please try again.');
  } finally {
    const fetchBtn = document.querySelector('.fetch-btn');
    fetchBtn.innerHTML = '<i class="fas fa-search"></i> Analyze';
    fetchBtn.disabled = false;
  }
}

function displayStockInfo(data) {
  const stockInfo = document.getElementById('stockInfo');
  const stockSummary = document.getElementById('stockSummary');

  const changeColor = data.price_change >= 0 ? '#4CAF50' : '#f44336';
  const changeIcon = data.price_change >= 0 ? 'fa-arrow-up' : 'fa-arrow-down';

  stockSummary.innerHTML = `
    <div class="stat-card">
      <div class="stat-value">${data.currency}${data.latest_price.toFixed(2)}</div>
      <div class="stat-label">Latest Price</div>
    </div>
    <div class="stat-card" style="background: ${changeColor}; color: white;">
      <div class="stat-value">
        <i class="fas ${changeIcon}"></i> ${data.currency}${Math.abs(data.price_change).toFixed(2)}
      </div>
      <div class="stat-label">Price Change</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">${Math.abs(data.price_change_pct).toFixed(2)}%</div>
      <div class="stat-label">Percentage Change</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">${data.data_points}</div>
      <div class="stat-label">Data Points</div>
    </div>
  `;

  stockInfo.style.display = 'block';
  document.getElementById('chartContainer').style.display = 'none';
}

async function loadAnalysis(analysisType, event) {
  if (!currentStockData) {
    showError('Please fetch stock data first');
    return;
  }

  currentAnalysisType = analysisType;

  // Update active card
  document.querySelectorAll('.analysis-card').forEach(card => card.classList.remove('active'));
  if (event && event.currentTarget) event.currentTarget.classList.add('active');

  const chartContainer = document.getElementById('chartContainer');
  const chart = document.getElementById('chart');
  const statsPanel = document.getElementById('statsPanel');

  chartContainer.style.display = 'block';
  chart.innerHTML = '';
  statsPanel.style.display = 'none';

  try {
    const response = await fetch(`/api/analysis/${analysisType}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(currentStockData)
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();

    if (data.error) {
      throw new Error(data.error);
    }

    if (data.chart_data && data.chart_data.data && data.chart_data.layout) {
      data.chart_data.layout.autosize = true;
      data.chart_data.layout.height = null;
      data.chart_data.layout.width = null;
      data.chart_data.layout.margin = {
        l: 60,
        r: 40,
        b: 60,
        t: 40,
        pad: 4
      };

      Plotly.newPlot('chart', data.chart_data.data, data.chart_data.layout, {
        responsive: true
      });

      if (analysisType === 'regression' && data.stats) {
        displayRegressionStats(data.stats);
      }
    } else {
      throw new Error('Invalid chart data received');
    }
  } catch (error) {
    console.error('Error loading analysis:', error);
    chart.innerHTML = `<div class="error"><i class="fas fa-exclamation-triangle"></i> ${error.message || 'Failed to load analysis'}</div>`;
  }
}

function displayRegressionStats(stats) {
  const statsPanel = document.getElementById('statsPanel');
  statsPanel.innerHTML = `
    <h3 style="grid-column: 1/-1; text-align: center; margin-bottom: 10px;">Trend Analysis Statistics</h3>
    <div class="stat-card" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
      <div class="stat-value">${stats.trend_direction}</div>
      <div class="stat-label">Trend Direction</div>
    </div>
    <div class="stat-card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
      <div class="stat-value">${stats.slope}</div>
      <div class="stat-label">Slope</div>
    </div>
    <div class="stat-card" style="background: linear-gradient(135deg, #4ECDC4 0%, #44A08D 100%);">
      <div class="stat-value">${stats.intercept}</div>
      <div class="stat-label">Intercept</div>
    </div>
  `;
  statsPanel.style.display = 'grid';
}

function showError(message) {
  const errorElement = document.getElementById('errorMessage') || document.createElement('div');
  errorElement.id = 'errorMessage';
  errorElement.className = 'error';
  errorElement.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${message}`;
  if (!document.getElementById('errorMessage')) {
    const container = document.querySelector('.container');
    container.insertBefore(errorElement, container.children[2]);
  }
  errorElement.style.display = 'block';
}

function hideError() {
  const errorElement = document.getElementById('errorMessage');
  if (errorElement) errorElement.style.display = 'none';
}

// Set default end date to today
document.getElementById('endDate').value = new Date().toISOString().split('T')[0];

// Allow Enter key to trigger search
document.addEventListener('keypress', function(e) {
  if (e.key === 'Enter') {
    fetchStockData();
  }
});

// Auto re-render chart on resize
window.addEventListener('resize', function() {
  if (currentAnalysisType && currentStockData) {
    loadAnalysis(currentAnalysisType);
  }
});
