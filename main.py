import dash
from dash import dcc, html, Input, Output, State, callback
import plotly.graph_objects as go
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = dash.Dash(__name__)
server = app.server

styles = {
    'container': {'margin': '2%', 'fontFamily': 'Arial'},
    'header': {'color': '#2c3e50', 'borderBottom': '2px solid #3498db'},
    'error': {'color': 'red', 'fontWeight': 'bold'}
}

app.layout = html.Div(style=styles['container'], children=[
    html.H1("📈 Аналізатор акцій", style=styles['header']),

    html.Div([
        dcc.Dropdown(
            id='ticker-selector',
            options=[
                {'label': 'Apple (AAPL)', 'value': 'AAPL'},
                {'label': 'Microsoft (MSFT)', 'value': 'MSFT'}
            ],
            value='AAPL',
            style={'width': '200px', 'margin-right': '20px'}
        ),
        dcc.DatePickerRange(
            id='date-picker',
            min_date_allowed='2010-01-01',
            max_date_allowed=datetime.now().strftime('%Y-%m-%d'),
            start_date=(datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'),
            end_date=datetime.now().strftime('%Y-%m-%d')
        ),
        html.Button('🔄 Оновити', id='refresh-button', style={'margin-left': '20px'})
    ], style={'display': 'flex', 'align-items': 'center', 'margin-bottom': '20px'}),

    dcc.Loading(
        id="loading",
        type="circle",
        children=[
            dcc.Graph(id='price-chart'),
            dcc.Graph(id='volume-chart'),
            html.Div(id='stats-container', style={'margin-top': '20px'}),
            html.Div(id='error-message', style=styles['error'])
        ]
    ),

    dcc.Interval(id='auto-refresh', interval=3600 * 1000, n_intervals=0),
    dcc.Store(id='data-store')
])


def get_stock_data(ticker, start, end):
    try:
        df = yf.download(
            tickers=ticker,
            start=start,
            end=end,
            progress=False,
            auto_adjust=False
        )

        if df.empty:
            return None

        # Виправляємо мульті-індекс колонок
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = ['_'.join(col).strip() for col in df.columns.values]

        df = df.reset_index()
        df = df.rename(columns={'Date': 'TradeDate'}) if 'Date' in df.columns else df.rename(
            columns={'index': 'TradeDate'})

        # Видаляємо порожні рівні в назвах колонок
        df.columns = [col.split('_')[0] if isinstance(col, str) else col for col in df.columns]

        required = ['TradeDate', 'Open', 'High', 'Low', 'Close', 'Volume']
        if not all(col in df.columns for col in required):
            return None

        return df

    except Exception as e:
        logger.error(f"Помилка: {str(e)}")
        return None


@callback(
    [Output('data-store', 'data'),
     Output('error-message', 'children')],
    [Input('refresh-button', 'n_clicks'),
     Input('auto-refresh', 'n_intervals')],
    [State('ticker-selector', 'value'),
     State('date-picker', 'start_date'),
     State('date-picker', 'end_date')]
)
def update_data(n_clicks, n, ticker, start, end):
    if not all([ticker, start, end]):
        return None, "Оберіть тікер та дати"

    try:
        df = get_stock_data(ticker, start, end)
        if df is None:
            return None, "Помилка завантаження"

        return df.to_dict('records'), ""
    except Exception as e:
        return None, f"Помилка: {str(e)}"


@callback(
    [Output('price-chart', 'figure'),
     Output('volume-chart', 'figure'),
     Output('stats-container', 'children')],
    [Input('data-store', 'data')]
)
def update_charts(data):
    if not data:
        return go.Figure(), go.Figure(), ""

    try:
        df = pd.DataFrame.from_records(data)

        required = ['TradeDate', 'Open', 'High', 'Low', 'Close', 'Volume']
        if not all(col in df.columns for col in required):
            return go.Figure(), go.Figure(), "Відсутні необхідні колонки"

        price_fig = go.Figure(
            data=[go.Candlestick(
                x=df['TradeDate'],
                open=df['Open'],
                high=df['High'],
                low=df['Low'],
                close=df['Close']
            )],
            layout={'title': 'Динаміка цін'}
        )

        volume_fig = go.Figure(
            data=[go.Bar(
                x=df['TradeDate'],
                y=df['Volume'],
                marker_color='#3498db'
            )],
            layout={'title': 'Обсяги торгів'}
        )

        stats = df[['Open', 'High', 'Low', 'Close']].describe().round(2)
        stats_html = html.Div([
            html.H3("Статистика"),
            html.Table(
                [html.Tr([html.Th(col) for col in stats.columns])] +
                [html.Tr([html.Td(stat)] + [html.Td(stats[col][stat]) for col in stats.columns])
                 for stat in stats.index]
            )
        ])

        return price_fig, volume_fig, stats_html

    except Exception as e:
        logger.error(f"Помилка візуалізації: {str(e)}")
        return go.Figure(), go.Figure(), html.Div(f"Помилка: {str(e)}", style=styles['error'])


if __name__ == '__main__':
    app.run(debug=False)