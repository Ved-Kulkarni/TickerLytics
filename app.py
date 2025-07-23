from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import pandas as pd
import yfinance as yf
import datetime
import numpy as np
from sklearn.linear_model import LinearRegression
import plotly.graph_objs as go
import os

app = Flask(__name__)
CORS(app)

# ========== DATA PREPARATION ==========
def prepare_stock_data(stock_data):
    if isinstance(stock_data.columns, pd.MultiIndex):
        stock_data.columns = ['_'.join(col).strip() for col in stock_data.columns.values]

    column_mapping = {}
    for col in stock_data.columns:
        col_lower = col.lower()
        if 'close' in col_lower:
            column_mapping[col] = 'Adj Close' if 'adj' in col_lower else 'Close'
        elif 'volume' in col_lower:
            column_mapping[col] = 'Volume'
        elif 'open' in col_lower:
            column_mapping[col] = 'Open'
        elif 'high' in col_lower:
            column_mapping[col] = 'High'
        elif 'low' in col_lower:
            column_mapping[col] = 'Low'

    if column_mapping:
        stock_data = stock_data.rename(columns=column_mapping)

    stock_data.index = pd.to_datetime(stock_data.index)
    return stock_data

# ========== ANALYSIS FUNCTIONS ==========
def create_price_chart(stock_data, title):
    price_col = 'Adj Close' if 'Adj Close' in stock_data.columns else 'Close'

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=stock_data.index.strftime('%Y-%m-%d').tolist(),
        y=stock_data[price_col].tolist(),
        mode='lines',
        name='Stock Price',
        line=dict(color='#2E86AB', width=2)
    ))

    fig.update_layout(
        title=title,
        xaxis_title='Date',
        yaxis_title='Price ($)',
        template='plotly_white',
        height=500
    )

    return fig.to_dict()

def stock_price_analysis(stock_data):
    stock_data = prepare_stock_data(stock_data)
    return create_price_chart(stock_data, 'Stock Price Analysis')

def moving_average_analysis(stock_data):
    stock_data = prepare_stock_data(stock_data)
    price_col = 'Adj Close' if 'Adj Close' in stock_data.columns else 'Close'

    stock_data['MA50'] = stock_data[price_col].rolling(window=50).mean()
    stock_data['MA200'] = stock_data[price_col].rolling(window=200).mean()
    stock_data = stock_data.dropna(subset=['MA50', 'MA200'])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=stock_data.index.strftime('%Y-%m-%d').tolist(),
        y=stock_data[price_col].tolist(),
        mode='lines',
        name='Price',
        line=dict(color='#2E86AB')
    ))
    fig.add_trace(go.Scatter(
        x=stock_data.index.strftime('%Y-%m-%d').tolist(),
        y=stock_data['MA50'].tolist(),
        mode='lines',
        name='50-Day MA',
        line=dict(color='#A23B72')
    ))
    fig.add_trace(go.Scatter(
        x=stock_data.index.strftime('%Y-%m-%d').tolist(),
        y=stock_data['MA200'].tolist(),
        mode='lines',
        name='200-Day MA',
        line=dict(color='#F18F01')
    ))

    fig.update_layout(title='Moving Average Analysis', template='plotly_white')
    return fig.to_dict()

def volume_analysis(stock_data):
    stock_data = prepare_stock_data(stock_data)
    if 'Volume' not in stock_data.columns:
        raise ValueError("Volume data not available for this stock")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=stock_data.index.strftime('%Y-%m-%d').tolist(),
        y=stock_data['Volume'].tolist(),
        mode='lines',
        name='Volume',
        line=dict(color='#C73E1D'),
        fill='tozeroy'
    ))

    fig.update_layout(title='Volume Analysis', template='plotly_white')
    return fig.to_dict()

def linear_regression_analysis(stock_data):
    stock_data = prepare_stock_data(stock_data)
    price_col = 'Adj Close' if 'Adj Close' in stock_data.columns else 'Close'
    prices = stock_data[price_col].values

    if len(prices) == 0:
        return {}, {}

    x = np.arange(len(prices)).reshape(-1, 1)
    y = prices.reshape(-1, 1)

    model = LinearRegression()
    model.fit(x, y)
    trend_line = model.predict(x).flatten()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=stock_data.index.strftime('%Y-%m-%d').tolist(),
        y=prices.tolist(),
        mode='lines',
        name='Price',
        line=dict(color='#2E86AB')
    ))
    fig.add_trace(go.Scatter(
        x=stock_data.index.strftime('%Y-%m-%d').tolist(),
        y=trend_line.tolist(),
        mode='lines',
        name='Trend Line',
        line=dict(color='#F18F01', dash='dash')
    ))

    fig.update_layout(title='Linear Regression Analysis', template='plotly_white')

    slope = float(model.coef_[0][0])
    intercept = float(model.intercept_[0])

    stats = {
        'slope': round(slope, 4),
        'intercept': round(intercept, 2),
        'trend_direction': "Upward" if slope > 0 else "Downward",
        'price_column_used': price_col
    }

    return fig.to_dict(), stats

# ========== ROUTES ==========
@app.route('/')
def dashboard():
    return render_template('index.html')

@app.route('/api/stock-data', methods=['POST'])
def get_stock_data():
    try:
        data = request.get_json(force=True)

        stock_symbol = data.get('symbol')
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')

        if not stock_symbol or not start_date_str or not end_date_str:
            return jsonify({'error': 'Missing required parameters'}), 400

        start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%d")

        if start_date >= end_date:
            return jsonify({'error': 'Start date must be before end date'}), 400

        stock_data = yf.download(
            stock_symbol,
            start=start_date,
            end=end_date + datetime.timedelta(days=1),
            auto_adjust=True,
            progress=False,
            threads=True
        )

        if stock_data.empty:
            return jsonify({
                'error': f'No data found for {stock_symbol}',
                'suggestions': [
                    'Check the symbol on Yahoo Finance',
                    'Try a different date range',
                    'For Indian stocks, use .NS suffix (e.g., RELIANCE.NS)'
                ]
            }), 400

        stock_data = prepare_stock_data(stock_data)
        price_col = 'Adj Close' if 'Adj Close' in stock_data.columns else 'Close'
        latest_price = stock_data[price_col].iloc[-1]
        price_change = latest_price - stock_data[price_col].iloc[0]
        price_change_pct = (price_change / stock_data[price_col].iloc[0]) * 100 if len(stock_data) > 1 else 0

        return jsonify({
            'success': True,
            'symbol': stock_symbol,
            'latest_price': round(latest_price, 2),
            'price_change': round(price_change, 2),
            'price_change_pct': round(price_change_pct, 2),
            'data_points': len(stock_data),
            'date_range': f"{start_date_str} to {end_date_str}"
        })

    except Exception as e:
        return jsonify({
            'error': str(e),
            'solution': 'Please check the stock symbol and date range'
        }), 500

@app.route('/api/analysis/<analysis_type>', methods=['POST'])
def get_analysis(analysis_type):
    try:
        data = request.get_json(force=True)

        stock_symbol = data.get('symbol')
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')

        if not stock_symbol or not start_date_str or not end_date_str:
            return jsonify({'error': 'Missing required parameters'}), 400

        start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%d")

        stock_data = yf.download(
            stock_symbol,
            start=start_date,
            end=end_date + datetime.timedelta(days=1),
            auto_adjust=True,
            progress=False,
            threads=True
        )

        if stock_data.empty:
            return jsonify({'error': 'No data found for analysis'}), 400

        stock_data = prepare_stock_data(stock_data)

        if analysis_type == 'price':
            return jsonify({'chart_data': stock_price_analysis(stock_data)})
        elif analysis_type == 'moving-average':
            return jsonify({'chart_data': moving_average_analysis(stock_data)})
        elif analysis_type == 'volume':
            try:
                return jsonify({'chart_data': volume_analysis(stock_data)})
            except ValueError as e:
                return jsonify({'error': str(e)}), 400
        elif analysis_type == 'regression':
            chart_data, stats = linear_regression_analysis(stock_data)
            return jsonify({'chart_data': chart_data, 'stats': stats})
        else:
            return jsonify({'error': 'Invalid analysis type'}), 400

    except Exception as e:
        return jsonify({
            'error': str(e),
            'solution': 'Please try again with different parameters'
        }), 500

# ========== MAIN ==========
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
