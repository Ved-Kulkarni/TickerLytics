from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import pandas as pd
import yfinance as yf
import datetime
import numpy as np
from sklearn.linear_model import LinearRegression
import plotly.graph_objs as go

app = Flask(__name__)
CORS(app)

# ==================== DATA PREPARATION ====================
def prepare_stock_data(stock_data):
    """Prepares the stock data DataFrame by cleaning column names."""
    if isinstance(stock_data.columns, pd.MultiIndex):
        stock_data.columns = ['_'.join(col).strip() for col in stock_data.columns.values]

    # Standardize column names
    column_mapping = {col: col_lower.capitalize() for col in stock_data.columns if (col_lower := col.lower()) in ['open', 'high', 'low', 'close', 'volume']}
    if 'adj close' in [c.lower() for c in stock_data.columns]:
         column_mapping[[c for c in stock_data.columns if c.lower() == 'adj close'][0]] = 'Adj Close'
    
    if column_mapping:
        stock_data = stock_data.rename(columns=column_mapping)
        
    stock_data.index = pd.to_datetime(stock_data.index)
    return stock_data

# ==================== ANALYSIS FUNCTIONS ====================
def create_price_chart(stock_data, title):
    """Creates a basic price chart."""
    price_col = 'Adj Close' if 'Adj Close' in stock_data.columns else 'Close'
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=stock_data.index,
        y=stock_data[price_col],
        mode='lines',
        name='Stock Price',
        line=dict(color='#667eea', width=2)
    ))
    fig.update_layout(title=title, template='plotly_white', yaxis_title='Price (USD)')
    return fig.to_dict()

def stock_price_analysis(stock_data):
    """Analysis for simple price view."""
    return create_price_chart(stock_data, 'Stock Price Analysis')

def moving_average_analysis(stock_data):
    """Analysis for moving averages."""
    price_col = 'Adj Close' if 'Adj Close' in stock_data.columns else 'Close'
    stock_data['MA50'] = stock_data[price_col].rolling(window=50).mean()
    stock_data['MA200'] = stock_data[price_col].rolling(window=200).mean()
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=stock_data.index, y=stock_data[price_col], mode='lines', name='Price', line=dict(color='#667eea')))
    fig.add_trace(go.Scatter(x=stock_data.index, y=stock_data['MA50'], mode='lines', name='50-Day MA', line=dict(color='#f5576c')))
    fig.add_trace(go.Scatter(x=stock_data.index, y=stock_data['MA200'], mode='lines', name='200-Day MA', line=dict(color='#f093fb')))
    fig.update_layout(title='Moving Average Analysis', template='plotly_white')
    return fig.to_dict()

def volume_analysis(stock_data):
    """Analysis for trading volume."""
    if 'Volume' not in stock_data.columns:
        raise ValueError("Volume data not available.")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=stock_data.index, y=stock_data['Volume'], name='Volume', marker_color='#764ba2'))
    fig.update_layout(title='Volume Analysis', template='plotly_white')
    return fig.to_dict()

def linear_regression_analysis(stock_data):
    """Performs linear regression and returns chart and stats."""
    price_col = 'Adj Close' if 'Adj Close' in stock_data.columns else 'Close'
    df = stock_data.copy().dropna(subset=[price_col])
    
    # Prepare data for regression
    X = np.arange(len(df)).reshape(-1, 1)
    y = df[price_col].values
    
    # Fit model
    model = LinearRegression()
    model.fit(X, y)
    
    df['Trend'] = model.predict(X)
    slope = round(model.coef_[0], 4)
    intercept = round(model.intercept_, 2)
    
    # Create chart
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df[price_col], mode='lines', name='Actual Price', line=dict(color='#667eea')))
    fig.add_trace(go.Scatter(x=df.index, y=df['Trend'], mode='lines', name='Trend Line', line=dict(color='#f5576c', dash='dash')))
    fig.update_layout(title='Linear Regression Trend Analysis', template='plotly_white')
    
    stats = {
        'slope': slope,
        'intercept': intercept,
        'trend_direction': 'Upward' if slope > 0 else 'Downward' if slope < 0 else 'Flat'
    }
    
    return fig.to_dict(), stats

# ==================== API ROUTES ====================
@app.route('/')
def dashboard():
    return render_template('index.html')

@app.route('/api/stock-data', methods=['POST'])
def get_stock_data():
    try:
        data = request.json
        stock_symbol = data['symbol']
        start_date = data['start_date']
        end_date = data['end_date']

        stock_data = yf.download(stock_symbol, start=start_date, end=end_date, progress=False)

        if stock_data.empty:
            return jsonify({'error': f'No data for symbol {stock_symbol}. Check symbol (e.g., RELIANCE.NS for Indian stocks) and date range.'}), 400

        stock_data = prepare_stock_data(stock_data)
        price_col = 'Adj Close' if 'Adj Close' in stock_data.columns else 'Close'
        
        latest_price = stock_data[price_col].iloc[-1]
        price_change = latest_price - stock_data[price_col].iloc[0]
        price_change_pct = (price_change / stock_data[price_col].iloc[0]) * 100

        return jsonify({
            'success': True,
            'latest_price': latest_price,
            'price_change': price_change,
            'price_change_pct': price_change_pct,
            'data_points': len(stock_data)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analysis/<analysis_type>', methods=['POST'])
def get_analysis(analysis_type):
    try:
        data = request.json
        stock_symbol = data['symbol']
        start_date = data['start_date']
        end_date = data['end_date']
        
        stock_data = yf.download(stock_symbol, start=start_date, end=end_date, progress=False)

        if stock_data.empty:
            return jsonify({'error': 'No data found for analysis.'}), 400
        
        stock_data = prepare_stock_data(stock_data)

        analysis_functions = {
            'price': lambda df: (stock_price_analysis(df), None),
            'moving-average': lambda df: (moving_average_analysis(df), None),
            'volume': lambda df: (volume_analysis(df), None),
            'regression': linear_regression_analysis
        }

        if analysis_type not in analysis_functions:
            return jsonify({'error': 'Invalid analysis type'}), 400
        
        chart_data, stats = analysis_functions[analysis_type](stock_data)
        
        response = {'chart_data': chart_data}
        if stats:
            response['stats'] = stats
            
        return jsonify(response)

    except ValueError as e: # Specifically for volume analysis error
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== MAIN ====================
if __name__ == '__main__':
    # For Railway deployment, it will use Gunicorn, not this.
    # The host and port are for local development.
    app.run(debug=True, host='0.0.0.0', port=5000)
