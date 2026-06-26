from nicegui import ui
import requests
import asyncio

# 1. State Store
state = {
    'loading': False,
    'ticker': '',
    'report': None,
    'raw_data': None,
    'error': None
}

# 2. UI Head Configuration (Custom Fonts & Styling overrides)
ui.add_head_html("""
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body, p, span, h1, h2, h3, h4, h5, h6, li, .q-btn, .q-field, .q-input, .q-item {
            font-family: 'Plus Jakarta Sans', sans-serif;
        }
        .space-grotesk {
            font-family: 'Space Grotesk', sans-serif !important;
        }
        /* Custom scrollbar for raw data tables */
        ::-webkit-scrollbar {
            width: 6px;
            height: 6px;
        }
        ::-webkit-scrollbar-track {
            background: #0B0F17;
        }
        ::-webkit-scrollbar-thumb {
            background: #1F2937;
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #374151;
        }
    </style>
""")

# Enable Dark Mode globally
ui.dark_mode().enable()

# 3. Dynamic Refreshable Dashboard Content
@ui.refreshable
def dashboard_content():
    if state['loading']:
        with ui.column().classes('w-full items-center justify-center py-24 gap-4'):
            ui.spinner(size='xl', color='primary').classes('text-blue-500')
            ui.label(f"Analyzing {state['ticker'].upper()}...").classes('space-grotesk text-xl font-semibold text-slate-100')
            ui.label("Fetching Upstox fundamentals, parsing weekly OHLC candles, digesting news, and running LLM report synthesis. This may take a minute.").classes('text-slate-400 text-sm max-w-md text-center leading-relaxed')
        return

    if state['error']:
        with ui.column().classes('w-full items-center justify-center py-20 gap-3'):
            ui.icon('warning', size='xl').classes('text-rose-500')
            ui.label('Analysis Failed').classes('space-grotesk text-xl font-bold text-rose-500')
            ui.label(state['error']).classes('text-slate-300 text-sm max-w-lg text-center bg-rose-950/20 border border-rose-900/30 p-4 rounded-xl')
        return

    if not state['report']:
        with ui.column().classes('w-full items-center justify-center py-24 gap-3'):
            ui.icon('trending_up', size='xl').classes('text-slate-700')
            ui.label('Intelligence Engine Idle').classes('space-grotesk text-xl font-bold text-slate-400')
            ui.label('Enter a stock ticker symbol in the sidebar and click "Run Research Agent" to generate a report.').classes('text-slate-500 text-sm max-w-sm text-center')
        return

    # Extract Data from State
    report = state['report']
    raw_data = state['raw_data']
    company = report.get('company', {})
    profile = report.get('profile', {})
    price_analysis = report.get('price_analysis', {})

    # Company Meta Title Block
    with ui.column().classes('w-full mb-6 gap-1'):
        ui.label(f"{company.get('name', state['ticker'].upper())} ({company.get('symbol', state['ticker'].upper())})").classes('space-grotesk text-3xl font-bold text-white')
        with ui.row().classes('gap-2 items-center text-sm text-slate-400'):
            ui.label(f"Sector: {company.get('sector', 'N/A')}")

    # Grid of 4 KPI Metric Cards
    with ui.grid().classes('grid-cols-1 md:grid-cols-4 gap-4 w-full mb-8'):
        # 1. Market Cap INR
        with ui.card().classes('bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-center'):
            ui.label('Market Cap (INR)').classes('text-xs text-slate-400 font-semibold uppercase tracking-wider')
            ui.label(profile.get('market_cap_inr', 'N/A')).classes('text-xl font-bold text-slate-100 mt-1')

        # 2. Market Cap USD
        with ui.card().classes('bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-center'):
            ui.label('Market Cap (USD)').classes('text-xs text-slate-400 font-semibold uppercase tracking-wider')
            ui.label(profile.get('market_cap_usd', 'N/A')).classes('text-xl font-bold text-slate-100 mt-1')

        # 3. Technical Trend Card (Safe Parse to avoid overflows)
        trend_val = price_analysis.get('trend', 'N/A')
        if len(trend_val) > 20:
            if "bull" in trend_val.lower():
                short_trend = "Bullish"
            elif "bear" in trend_val.lower():
                short_trend = "Bearish"
            else:
                short_trend = "Neutral/Mixed"
            trend_desc = trend_val
        else:
            short_trend = trend_val
            trend_desc = ""

        trend_color = "text-emerald-400" if "bull" in short_trend.lower() else ("text-rose-400" if "bear" in short_trend.lower() else "text-amber-400")
        with ui.card().classes('bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-center'):
            ui.label('Technical Trend').classes('text-xs text-slate-400 font-semibold uppercase tracking-wider')
            ui.label(short_trend).classes(f'text-xl font-bold {trend_color} mt-1')
            if trend_desc:
                ui.label(trend_desc).classes('text-slate-500 text-xs mt-2 leading-tight')

        # 4. 52-Week Range
        with ui.card().classes('bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-center'):
            ui.label('52-Week Range').classes('text-xs text-slate-400 font-semibold uppercase tracking-wider')
            ui.label(price_analysis.get('fifty_two_week_range', 'N/A')).classes('text-xl font-bold text-slate-100 mt-1')

    # Core Panel Tabs Layout
    with ui.tabs().classes('w-full border-b border-slate-800 mb-6') as tabs:
        tab_report = ui.tab('📋 AI Analysis Report').classes('text-slate-400 hover:text-white px-6 py-3 font-semibold')
        tab_raw = ui.tab('📊 Raw Upstox Data & Tables').classes('text-slate-400 hover:text-white px-6 py-3 font-semibold')
        
    with ui.tab_panels(tabs, value=tab_report).classes('w-full bg-transparent p-0'):
        # TAB 1: AI Analysis Report
        with ui.tab_panel(tab_report).classes('p-0 gap-6 flex flex-col'):
            # Executive Thesis Card
            with ui.card().classes('bg-slate-900 border-l-4 border-l-emerald-500 border border-slate-800 rounded-xl p-6 w-full shadow-lg'):
                ui.label('Executive Investment Thesis').classes('space-grotesk text-lg font-bold text-emerald-400 mb-2')
                ui.markdown(report.get('summary', '')).classes('text-slate-300 text-sm leading-relaxed')
                
            # 3 Pillars Grid (Insights, Risks, Opportunities)
            with ui.grid().classes('grid-cols-1 md:grid-cols-3 gap-6 w-full mt-2'):
                # Key Insights
                with ui.card().classes('bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-md'):
                    ui.label('💡 Key Insights').classes('space-grotesk text-md font-bold text-blue-400 mb-4')
                    for ins in report.get('insights', []):
                        with ui.row().classes('items-start gap-2 mb-3'):
                            ui.label('•').classes('text-blue-400 text-lg leading-none')
                            ui.label(ins).classes('text-slate-300 text-sm leading-relaxed flex-1')

                # Key Risks
                with ui.card().classes('bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-md'):
                    ui.label('⚠️ Key Risks').classes('space-grotesk text-md font-bold text-rose-400 mb-4')
                    for rsk in report.get('risks', []):
                        with ui.row().classes('items-start gap-2 mb-3'):
                            ui.label('•').classes('text-rose-400 text-lg leading-none')
                            ui.label(rsk).classes('text-slate-300 text-sm leading-relaxed flex-1')

                # Opportunities
                with ui.card().classes('bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-md'):
                    ui.label('📈 Opportunities').classes('space-grotesk text-md font-bold text-emerald-400 mb-4')
                    for opp in report.get('opportunities', []):
                        with ui.row().classes('items-start gap-2 mb-3'):
                            ui.label('•').classes('text-emerald-400 text-lg leading-none')
                            ui.label(opp).classes('text-slate-300 text-sm leading-relaxed flex-1')
                        
            # News Section
            ui.label('📰 Recent Digested News & Events').classes('space-grotesk text-xl font-bold text-slate-100 mt-8 mb-4')
            news_events = report.get('news_and_events', [])
            if news_events:
                for item in news_events:
                    sentiment = item.get('sentiment', 'neutral').upper()
                    sent_color = "text-emerald-400" if "POS" in sentiment else ("text-rose-400" if "NEG" in sentiment else "text-amber-400")
                    badge_bg = "bg-emerald-500/10 border-emerald-500/20" if "POS" in sentiment else ("bg-rose-500/10 border-rose-500/20" if "NEG" in sentiment else "bg-amber-500/10 border-amber-500/20")
                    
                    with ui.expansion(f"{item.get('event', 'News Event')}", icon='feed').classes('bg-slate-900 border border-slate-800 rounded-xl overflow-hidden mb-3'):
                        with ui.column().classes('p-4 gap-2'):
                            ui.label(item.get('summary', '')).classes('text-slate-300 text-sm leading-relaxed')
                            with ui.row().classes(f'{badge_bg} border rounded px-2.5 py-0.5 items-center mt-2'):
                                ui.label(f"{sentiment} | IMPACT: {item.get('impact', 'N/A').upper()}").classes(f'text-[10px] font-bold {sent_color} tracking-wider')
            else:
                ui.label('No recent news events parsed for this stock.').classes('text-slate-500 text-sm italic')
                
        # TAB 2: Raw Preprocessed Tables
        with ui.tab_panel(tab_raw).classes('p-0 flex flex-col gap-4'):
            ui.label('Raw Preprocessed Tables').classes('space-grotesk text-xl font-bold text-slate-100 mb-4')
            if raw_data:
                for category, content in raw_data.items():
                    with ui.expansion(f"Data - {category}", icon='table_chart').classes('bg-slate-900 border border-slate-800 rounded-xl overflow-hidden mb-3'):
                        ui.markdown(content).classes('text-slate-300 text-sm p-5 w-full overflow-x-auto')
            else:
                ui.label('No raw preprocessed data found in response.').classes('text-slate-500 text-sm italic')

# 4. Async Research Call Task
async def run_research(ticker_symbol: str):
    if not ticker_symbol:
        ui.notify('Please enter a stock symbol first.', type='warning')
        return

    state['loading'] = True
    state['ticker'] = ticker_symbol
    state['report'] = None
    state['raw_data'] = None
    state['error'] = None
    dashboard_content.refresh()

    try:
        # FastAPI call to background server
        response = await asyncio.to_thread(
            requests.get, f"http://127.0.0.1:8000/api/v1/research/{ticker_symbol}"
        )
        if response.status_code == 200:
            payload = response.json()
            state['report'] = payload.get("report")
            state['raw_data'] = payload.get("preprocessing")
        else:
            state['error'] = f"Backend returned error ({response.status_code}): {response.text}"
    except Exception as e:
        state['error'] = f"Failed to connect to FastAPI backend: {e}"
    finally:
        state['loading'] = False
        dashboard_content.refresh()

# 5. Page Layout Structure
with ui.left_drawer(value=True).classes('bg-slate-950 border-r border-slate-850 p-6 flex flex-col gap-6') as drawer:
    ui.label('📈 StoxFlow').classes('space-grotesk text-2xl font-bold text-white mb-2')
    
    # Input field
    ticker_input = ui.input(
        label='Stock Ticker Symbol', 
        placeholder='e.g. ONGC, TCS, HDFCBANK'
    ).classes('w-full').props('outlined dense dark')
    
    # Trigger button
    ui.button(
        'Run Research Agent', 
        on_click=lambda: run_research(ticker_input.value)
    ).classes('w-full bg-blue-600 hover:bg-blue-700 text-white rounded-lg py-2.5 font-semibold transition-all')

    ui.separator().classes('border-slate-800 my-2')

    # System Links
    ui.label('System URLs').classes('text-xs font-bold text-slate-400 uppercase tracking-wider')
    with ui.column().classes('gap-2 w-full'):
        ui.link('🔍 Phoenix Observability', 'http://localhost:6006', new_tab=True).classes('text-sm text-emerald-400 hover:text-emerald-300 transition-all')

    ui.separator().classes('border-slate-800 my-2')

    # Secrets Tips
    ui.label('🔑 Config & Secrets').classes('text-xs font-bold text-slate-400 uppercase tracking-wider')
    with ui.column().classes('gap-1 text-xs text-slate-500 leading-relaxed'):
        ui.label('Ensure .env at project root contains:')
        ui.label('• UPSTOX_API_KEY="..."').classes('font-mono text-[10px] text-slate-400')
        ui.label('• GEMINI_API_KEY="..."').classes('font-mono text-[10px] text-slate-400')
        ui.label('• LOCAL_LLM_MODEL="..."').classes('font-mono text-[10px] text-slate-400')

# Main Content panel container
with ui.column().classes('flex-1 p-8 md:p-12 w-full bg-slate-950 min-h-screen'):
    dashboard_content()

# Start NiceGUI application
ui.run(
    port=8080,
    title="StoxFlow Dashboard",
    reload=True
)
