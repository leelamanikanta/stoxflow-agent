
from .upstox import get_ohlc_data
from datetime import datetime
import pandas as pd
from .upstox import get_key_ratios,get_shareholding_pattern,get_income_statement,get_cashflow_statement,get_balance_sheet,get_corporate_actions,get_competitors


def process_key_ratios(instrument):
    key_ratios = get_key_ratios(instrument)
    key_ratios = key_ratios.get("data",{})
    # 1. Build the clean, raw data table
    table_str = "### Key Ratios (Company vs Sector)\n"
    table_str += "| Metric | Company | Sector |\n"
    table_str += "|---|---|---|\n"

    insights = []
    if key_ratios:
        for key_ration in key_ratios:
            metric_name = key_ration.get("name")
            company_value = key_ration.get("company_value","0")
            sector_value = key_ration.get("sector_value","0")

            # Add raw row to table
            table_str += f"| **{metric_name}** | {company_value} | {sector_value} |\n"

            # 2. Compute background math for the LLM
            def parse_numeric(val_str):
                try:
                    return float(val_str.replace('%', '').strip())
                except (ValueError, AttributeError):
                    return 0.0
                
            comp_float = parse_numeric(company_value)
            sect_float = parse_numeric(sector_value)

            if sect_float == 0: # Avoid division by zero
                continue

            # Determine Valuation Premiums/Discounts
            if metric_name in ['P/E', 'P/B', 'EV/EBITDA']:
                if comp_float > sect_float:
                    variance = ((comp_float - sect_float) / sect_float) * 100
                    insights.append(f"- **VALUATION**: Trading at a {variance:.1f}% {metric_name} premium to its sector.")
                elif comp_float < sect_float:
                    variance = ((sect_float - comp_float) / sect_float) * 100
                    insights.append(f"- **VALUATION**: Trading at a {variance:.1f}% {metric_name} discount to its sector.")
                
            # Determine Efficiency Spreads
            elif metric_name in ['ROA', 'ROE', 'ROCE']:
                spread = comp_float - sect_float
                if spread > 0:
                    insights.append(f"- **EFFICIENCY**: Outperforming sector {metric_name} by a spread of +{spread:.2f}%.")
                elif spread < 0:
                    insights.append(f"- **EFFICIENCY**: Underperforming sector {metric_name} by a spread of {spread:.2f}%.")


    # 3. Combine Table and Insights
    final_output = table_str + "\n#### Pre-Calculated Financial Anomalies\n"
    if insights:
        final_output += "\n".join(insights) + "\n\n"
    else:
        final_output += "- No significant anomalies detected.\n\n"
        
    return final_output


def preprocess_shareholding_pattern(instrument):
    """
    Parses and flattens the Upstox nested shareholding pattern JSON payload.
    Extracts chronological trends, handles missing periods safely, and generates
    a concise Markdown table along with institutional momentum highlights.
    """

    response = get_shareholding_pattern(instrument)
    if not response or response.get("status") != "success":
        return "### Shareholding Pattern\nData unavailable or failed request.\n"
        
    data_entries = response.get("data", [])
    if not data_entries:
        return "### Shareholding Pattern\nNo data entries found.\n"

    # 1. Identify all unique reporting periods across categories and sort them chronologically
    all_periods = set()
    for entry in data_entries:
        for hist in entry.get("history", []):
            if "period" in hist:
                all_periods.add(hist["period"])
                
    # To sort reliably (e.g., 'Jun 2025' before 'Mar 2026'), convert temporarily to dates
    from datetime import datetime
    try:
        sorted_periods = sorted(list(all_periods), key=lambda x: datetime.strptime(x, "%b %Y"))
    except ValueError:
        # Fallback if date strings deviate from '%b %Y' format
        sorted_periods = sorted(list(all_periods))

    if not sorted_periods:
        return "### Shareholding Pattern\nNo valid reporting periods detected.\n"

    oldest_period = sorted_periods[0]
    latest_period = sorted_periods[-1]

    # 2. Construct Markdown Table Columns dynamically based on sorted periods
    table_str = f"### Shareholding Pattern Trend ({oldest_period} to {latest_period})\n"
    headers = ["Category"] + sorted_periods + ["Net Change"]
    table_str += "| " + " | ".join(headers) + " |\n"
    table_str += "| " + " | ".join(["---"] * len(headers)) + " |\n"

    insights = []

    # 3. Process each category row
    for entry in data_entries:
        category = entry.get("category", "unknown").upper()
        history = entry.get("history", [])
        
        # Map out period to value for quick table lookups
        hist_map = {h.get("period"): h.get("value", 0.0) for h in history}
        
        # Build the table row strings
        row_values = []
        for period in sorted_periods:
            val = hist_map.get(period, "-")
            row_values.append(f"{val}%" if isinstance(val, (int, float)) else str(val))
            
        # Extract initial and latest values to calculate absolute shift/delta
        old_val = hist_map.get(oldest_period, 0.0)
        new_val = hist_map.get(latest_period, 0.0)
        net_change = new_val - old_val
        
        row_values.append(f"{net_change:+.2f}%")
        table_str += f"| **{category}** | " + " | ".join(row_values) + " |\n"
        
        # 4. Generate highly dense structural flags for the master prompt
        trend_arrow = "🟢 Accumulation" if net_change > 0.05 else ("🔴 Distribution" if net_change < -0.05 else "⚪ Stable")
        
        if category in ['PROMOTERS', 'FII', 'MUTUAL_ FUNDS', 'OTHER_DII']:
            insights.append(f"- **{category}**: Currently holds {new_val}% ({trend_arrow} of {net_change:+.2f}% over the tracked timeline)")

    final_output = table_str + "\n#### Institutional Momentum Flags\n"
    if insights:
        final_output += "\n".join(insights) + "\n\n"
    else:
        final_output += "- No meaningful institutional shifts recorded.\n\n"
        
    return final_output




    
def preprocess_cashflow_statement(instrument):
    """
    Parses the Upstox Cash Flow Statement JSON.
    Generates a chronological markdown table and extracts structural 
    liquidity flags (e.g., Operating Cash Flow growth vs Capex spend).
    """
    response = get_cashflow_statement(instrument)
    if not response or response.get("status") != "success":
        return "### Cash Flow Statement\nData unavailable or failed request.\n"
        
    data = response.get("data", {})
    units = data.get("units_in", "crore")
    full_statement = data.get("full_statement", [])
    
    if not full_statement:
        return "### Cash Flow Statement\nNo statement items found.\n"

    # 1. Identify and sort periods chronologically
    periods = set()
    for item in full_statement:
        for hist in item.get("history", []):
            if "period" in hist:
                periods.add(hist["period"])
                
    try:
        sorted_periods = sorted(list(periods), key=lambda x: datetime.strptime(x, "%b %Y"))
    except ValueError:
        sorted_periods = sorted(list(periods))

    # 2. Build the Markdown Table
    table_str = f"### Cash Flow Statement (in {units.capitalize()}s)\n"
    headers = ["Particular"] + sorted_periods
    table_str += "| " + " | ".join(headers) + " |\n"
    table_str += "|---" * len(headers) + "|\n"
    
    cfo_history, cfi_history = {}, {}
    end_cash_history = {}

    for item in full_statement:
        particular = item.get("particular", "Unknown")
        history = {h.get("period"): h.get("value", 0) for h in item.get("history", [])}
        
        # Track specific metrics for insight generation
        if particular == "Cash flow from Operations":
            cfo_history = history
        elif particular == "Cash flow from Investing":
            cfi_history = history
        elif particular == "Cash (End of the year)":
            end_cash_history = history
            
        row_values = []
        for p in sorted_periods:
            val = history.get(p, "-")
            # Format nicely with commas
            row_values.append(f"{val:,}" if isinstance(val, (int, float)) else str(val))
            
        table_str += f"| **{particular}** | " + " | ".join(row_values) + " |\n"

    # 3. Generate Analytical Flags
    insights = []
    oldest_period = sorted_periods[0]
    latest_period = sorted_periods[-1]
    
    # Analyze Operating Cash Flow Generation
    if cfo_history:
        old_cfo = cfo_history.get(oldest_period, 0)
        new_cfo = cfo_history.get(latest_period, 0)
        if old_cfo and old_cfo != 0:
            cfo_growth = ((new_cfo - old_cfo) / abs(old_cfo)) * 100
            trend = "🟢 Strong expansion" if cfo_growth > 10 else ("🔴 Contraction" if cfo_growth < 0 else "⚪ Stable")
            insights.append(f"- **OPERATIONS**: Cash from operations shifted from {old_cfo:,} to {new_cfo:,} ({trend} of {cfo_growth:+.1f}% over the timeline).")

    # Proxy Free Cash Flow Check (CFO + CFI) 
    # (Note: CFI is usually negative due to Capex/Investments)
    if cfo_history and cfi_history:
        latest_cfo = cfo_history.get(latest_period, 0)
        latest_cfi = cfi_history.get(latest_period, 0)
        proxy_fcf = latest_cfo + latest_cfi
        if proxy_fcf > 0:
            insights.append(f"- **FREE CASH FLOW**: The core business is generating excess cash (Proxy FCF: +{proxy_fcf:,} {units}s) after accounting for investing outflows.")
        else:
            insights.append(f"- **CAPITAL INTENSITY**: The company is burning cash on investments faster than operations can fund it (Proxy FCF: {proxy_fcf:,} {units}s).")

    # Final Liquidity Check
    if end_cash_history:
        old_cash = end_cash_history.get(oldest_period, 0)
        new_cash = end_cash_history.get(latest_period, 0)
        insights.append(f"- **LIQUIDITY**: End-of-year cash reserves moved from {old_cash:,} to {new_cash:,} {units}s.")

    final_output = table_str + "\n#### Structural Cash Flow Flags\n"
    if insights:
        final_output += "\n".join(insights) + "\n\n"
    else:
        final_output += "- No structural anomalies detected.\n\n"
        
    return final_output


def preprocess_income_statement(instrument):
    """
    Parses the Upstox Income Statement JSON.
    Generates a chronological markdown table and computes Top-Line CAGR,
    Net Profit Margins, and flags severe EPS/Dilution anomalies.
    """
    response = get_income_statement(instrument)
    if not response or response.get("status") != "success":
        return "### Income Statement\nData unavailable or failed request.\n"
        
    data = response.get("data", {})
    units = data.get("units_in", "crore")
    full_statement = data.get("full_statement", [])
    
    if not full_statement:
        return "### Income Statement\nNo statement items found.\n"

    # 1. Sort periods chronologically
    periods = set()
    for item in full_statement:
        for hist in item.get("history", []):
            if "period" in hist:
                periods.add(hist["period"])
                
    try:
        sorted_periods = sorted(list(periods), key=lambda x: datetime.strptime(x, "%b %Y"))
    except ValueError:
        sorted_periods = sorted(list(periods))

    # 2. Build Markdown Table
    table_str = f"### Income Statement (in {units.capitalize()}s)\n"
    headers = ["Particular"] + sorted_periods
    table_str += "| " + " | ".join(headers) + " |\n"
    table_str += "|---" * len(headers) + "|\n"
    
    metrics = {}
    for item in full_statement:
        particular = item.get("particular", "Unknown")
        history = {h.get("period"): h.get("value", 0) for h in item.get("history", [])}
        metrics[particular] = history
        
        row_values = []
        for p in sorted_periods:
            val = history.get(p, "-")
            # Format nicely, but leave EPS as raw decimals
            if "EPS" in particular:
                row_values.append(f"{val}") 
            else:
                row_values.append(f"{val:,}" if isinstance(val, (int, float)) else str(val))
            
        table_str += f"| **{particular}** | " + " | ".join(row_values) + " |\n"

    # 3. Generate Structural Insights
    insights = []
    oldest = sorted_periods[0]
    latest = sorted_periods[-1]
    num_years = len(sorted_periods) - 1 if len(sorted_periods) > 1 else 1

    # A. Revenue Growth
    rev_history = metrics.get("Total Revenue", {})
    if rev_history:
        old_rev = rev_history.get(oldest, 0)
        new_rev = rev_history.get(latest, 0)
        if old_rev > 0:
            cagr = ((new_rev / old_rev) ** (1 / num_years) - 1) * 100
            insights.append(f"- **TOP-LINE GROWTH**: Total Revenue grew from {old_rev:,} to {new_rev:,} (CAGR: {cagr:.1f}%).")

    # B. Profitability & Margin Expansion/Contraction
    pat_history = metrics.get("Profit After Tax", {})
    if rev_history and pat_history:
        old_pat = pat_history.get(oldest, 0)
        new_pat = pat_history.get(latest, 0)
        
        old_margin = (old_pat / old_rev * 100) if old_rev else 0
        new_margin = (new_pat / new_rev * 100) if new_rev else 0
        
        margin_shift = new_margin - old_margin
        trend = "🟢 Margin Expansion" if margin_shift > 0 else "🔴 Margin Contraction"
        insights.append(f"- **PROFITABILITY**: Net Profit Margin shifted from {old_margin:.1f}% to {new_margin:.1f}% ({trend} of {margin_shift:+.1f}%).")

    # C. Dilution / Corporate Action Check via EPS vs PAT divergence
    eps_history = metrics.get("EPS - Basic", {})
    if eps_history and pat_history:
        old_eps = eps_history.get(oldest, 0)
        new_eps = eps_history.get(latest, 0)
        
        pat_growth = ((new_pat - old_pat) / old_pat) if old_pat else 0
        eps_growth = ((new_eps - old_eps) / old_eps) if old_eps else 0
        
        # If PAT grows but EPS drops heavily, it flags a structural share change
        if pat_growth > 0 and eps_growth < -0.20:
            insights.append(f"- **CAPITAL STRUCTURE ALERT**: Despite Net Profit growing, EPS dropped by {eps_growth*100:.1f}%. This mathematically guarantees a Stock Split, Bonus Issue, or severe equity dilution occurred in this window.")

    final_output = table_str + "\n#### Structural Income Flags\n"
    if insights:
        final_output += "\n".join(insights) + "\n\n"
    else:
        final_output += "- No structural anomalies detected.\n\n"
        
    return final_output




def preprocess_balance_sheet(instrument):
    """
    Parses the Upstox Balance Sheet JSON payload.
    Generates a chronological markdown table and computes critical 
    solvency, liquidity, and leverage ratios to flag structural risks.
    """
    response = get_balance_sheet(instrument)
    if not response or response.get("status") != "success":
        return "### Balance Sheet\nData unavailable or failed request.\n"
        
    data = response.get("data", {})
    units = data.get("units_in", "crore")
    full_statement = data.get("full_statement", [])
    
    if not full_statement:
        return "### Balance Sheet\nNo statement items found.\n"

    # 1. Sort periods chronologically
    periods = set()
    for item in full_statement:
        for hist in item.get("history", []):
            if "period" in hist:
                periods.add(hist["period"])
                
    try:
        sorted_periods = sorted(list(periods), key=lambda x: datetime.strptime(x, "%b %Y"))
    except ValueError:
        sorted_periods = sorted(list(periods))

    # 2. Build Markdown Table
    table_str = f"### Balance Sheet (in {units.capitalize()}s)\n"
    headers = ["Particular"] + sorted_periods
    table_str += "| " + " | ".join(headers) + " |\n"
    table_str += "|---" * len(headers) + "|\n"
    
    metrics = {}
    for item in full_statement:
        particular = item.get("particular", "Unknown")
        history = {h.get("period"): h.get("value", 0) for h in item.get("history", [])}
        metrics[particular] = history
        
        row_values = []
        for p in sorted_periods:
            val = history.get(p, "-")
            row_values.append(f"{val:,}" if isinstance(val, (int, float)) else str(val))
            
        table_str += f"| **{particular}** | " + " | ".join(row_values) + " |\n"

    # 3. Generate Structural Insights
    insights = []
    oldest = sorted_periods[0]
    latest = sorted_periods[-1]
    num_years = len(sorted_periods) - 1 if len(sorted_periods) > 1 else 1

    # A. Asset Expansion Growth
    assets = metrics.get("Total Assets", {})
    if assets:
        old_assets = assets.get(oldest, 0)
        new_assets = assets.get(latest, 0)
        if old_assets > 0:
            cagr = ((new_assets / old_assets) ** (1 / num_years) - 1) * 100
            insights.append(f"- **ASSET BASE**: Total Assets expanded from {old_assets:,} to {new_assets:,} (CAGR: {cagr:.1f}%).")

    # B. Short-term Liquidity (Current Ratio)
    curr_assets = metrics.get("Current Assets", {})
    curr_liabs = metrics.get("Current Liabilities", {})
    if curr_assets and curr_liabs:
        old_ca, new_ca = curr_assets.get(oldest, 0), curr_assets.get(latest, 0)
        old_cl, new_cl = curr_liabs.get(oldest, 0), curr_liabs.get(latest, 0)
        
        old_ratio = (old_ca / old_cl) if old_cl else 0
        new_ratio = (new_ca / new_cl) if new_cl else 0
        
        status = "🟢 Healthy" if new_ratio >= 1.0 else "🔴 Vulnerable"
        insights.append(f"- **SHORT-TERM LIQUIDITY**: Current Ratio shifted from {old_ratio:.2f}x to {new_ratio:.2f}x ({status} working capital coverage).")

    # C. Capital Structure & Leverage
    equity = metrics.get("Equity Capital", {})
    non_curr_liabs = metrics.get("Non-Current Liabilities", {})
    
    if equity and curr_liabs and non_curr_liabs:
        new_eq = equity.get(latest, 0)
        new_cl = curr_liabs.get(latest, 0)
        new_ncl = non_curr_liabs.get(latest, 0)
        total_liab_latest = new_cl + new_ncl
        
        if new_eq > 0:
            leverage = total_liab_latest / new_eq
            # Leverage rule of thumb: < 1 is conservative, > 2 is aggressive/risky
            lev_status = "🔴 Highly Leveraged" if leverage > 2.0 else ("🟢 Conservative" if leverage < 1.0 else "⚪ Moderate")
            insights.append(f"- **LEVERAGE**: The company operates with a Liabilities-to-Equity ratio of {leverage:.2f}x ({lev_status} capital structure).")

    final_output = table_str + "\n#### Structural Balance Sheet Flags\n"
    if insights:
        final_output += "\n".join(insights) + "\n\n"
    else:
        final_output += "- No structural anomalies detected.\n\n"
        
    return final_output


def preprocess_corporate_actions(instrument):
    """
    Parses the Upstox Corporate Actions JSON payload.
    Separates routine dividends from major structural events (Splits/Bonus) 
    and generates explicit flags for the LLM to understand price chart gaps.
    """
    corporate_actions = get_corporate_actions(instrument)
    if not corporate_actions or corporate_actions.get("status") != "success":
        return "### Corporate Actions\nData unavailable or failed request.\n"

    actions = corporate_actions.get("data", [])
    if not actions:
        return "### Corporate Actions\nNo recent corporate actions found.\n"

    # Categorize actions into Dividends vs Structural Events
    dividends = []
    structural_events = []

    for action in actions:
        name = action.get("name", "").upper()
        # Fallback to 'Announcement date' or 'Unknown' if expiry_date is missing
        ex_date_str = action.get("expiry_date", "Unknown Date") 
        amount = action.get("amount", 0)
        ratio = action.get("ratio")
        
        # Flatten the event_details array into a key-value dictionary for easy lookup
        details_dict = {item["name"]: item["value"] for item in action.get("event_details", [])}
        
        if "DIVIDEND" in name:
            div_type = details_dict.get("Dividend type", "Dividend")
            dividends.append({
                "date": ex_date_str,
                "amount": amount if amount else 0,
                "type": div_type,
                "details": details_dict.get("Details", "")
            })
        else:
            # Captures Bonus Issues, Stock Splits, Rights Issues, etc.
            structural_events.append({
                "name": name,
                "date": ex_date_str,
                "ratio": ratio,
                "details": details_dict.get("Details", "")
            })

    # Build the Markdown Summary
    summary = "### Recent Corporate Actions\n"
    insights = []

    if dividends:
        total_div = sum([d["amount"] for d in dividends if isinstance(d["amount"], (int, float))])
        summary += f"- **Dividends Paid**: {len(dividends)} payout(s) tracked, totaling **Rs. {total_div:.2f} per share**.\n"
        # Highlight the most recent one
        summary += f"  - *Latest*: Rs. {dividends[0]['amount']} (Ex-Date: {dividends[0]['date']} - {dividends[0]['type']})\n"
        
        insights.append(f"**YIELD EVENT**: Company actively returns cash to shareholders (Rs. {total_div:.2f}/share distributed in the tracked window).")

    if structural_events:
        summary += "- **Structural Capital Events (Splits/Bonus/Rights)**:\n"
        for event in structural_events:
            ratio_str = f" (Ratio: {event['ratio']})" if event['ratio'] else ""
            summary += f"  - {event['name']}{ratio_str} | Ex-Date: {event['date']} | Details: {event['details']}\n"
            
            # This is the most crucial flag for an LLM interpreting price/EPS data
            insights.append(f"**CAPITAL RESTRUCTURING**: {event['name']} executed on {event['date']}. **WARNING**: This mathematically distorts historical price charts and EPS trajectory prior to this date.")

    # Combine data and flags
    final_output = summary + "\n#### Corporate Action Flags\n"
    if insights:
        final_output += "\n".join(f"- {insight}" for insight in insights) + "\n\n"
    else:
        final_output += "- No major structural actions (Splits/Bonus) detected.\n\n"

    return final_output




def preprocess_competitors(instrument):
    """
    Parses the Upstox Competitors API response.
    Truncates long profile narrative fluff to conserve context window tokens,
    flattens the nested market cap fields, and calculates peer group scale metrics.
    """
    competitors = get_competitors(instrument)
    competitors = competitors.get("data",[])
    if not competitors:
        return "### Competitor Analysis\nNo competitor profiles found.\n"

    # 1. Build a clean, structured Peer Summary Table
    table_str = "### Competitor & Industry Peer Landscape\n"
    table_str += "| Peer Identifier | Sector | Market Cap (INR) | Core Business Focus |\n"
    table_str += "|---|---|---|---|\n"
    
    peer_caps = []
    
    for peer in competitors:
        # Extract clean symbol/ISIN from the composite instrument key
        raw_key = peer.get("instrument_key", "Unknown")
        clean_key = raw_key.split("|")[-1] if "|" in raw_key else raw_key
        
        sector = peer.get("sector", "Unknown")
        
        inr_data = peer.get("sector_market_cap_inr", {})
        cap_formatted = inr_data.get("formatted", "-")
        cap_value = inr_data.get("value", 0.0)
        
        # Clean and aggressively compress the narrative profile block
        profile = peer.get("company_profile", "")
        fluff_phrases = [
            "is an India-based company, which is engaged in the",
            "is an India-based oil company.",
            "The Company's segments include",
            "Its business interests span the entire"
        ]
        for fluff in fluff_phrases:
            profile = profile.replace(fluff, "")
        
        profile_clean = " ".join(profile.split()).strip()
        # Truncate to a tight token budget
        brief = profile_clean[:110] + "..." if len(profile_clean) > 110 else profile_clean

        table_str += f"| **{clean_key}** | {sector} | {cap_formatted} | {brief} |\n"
        
        if cap_value:
            peer_caps.append({"key": clean_key, "value": cap_value})

    # 2. Compute Peer Relative Scale Metrics
    insights = []
    if peer_caps:
        # Sort peers size down
        sorted_peers = sorted(peer_caps, key=lambda x: x["value"], reverse=True)
        largest_peer = sorted_peers[0]
        total_peer_mcap = sum(p["value"] for p in peer_caps)
        
        insights.append(f"- **MARKET DOMINANCE**: The dominant tracked peer is **{largest_peer['key']}** holding a market cap of {largest_peer['value']:,} Crores.")
        insights.append(f"- **PEER GROUP WEIGHT**: The tracked peer group represents a total aggregated market capitalization of **{total_peer_mcap:,.2f} Crores**.")
        
        if len(sorted_peers) > 1:
            ratio = sorted_peers[0]["value"] / sorted_peers[1]["value"]
            insights.append(f"- **COMPETITIVE GAP**: Market leader {sorted_peers[0]['key']} is **{ratio:.2f}x** larger than the next nearest competitor ({sorted_peers[1]['key']}).")

    final_output = table_str + "\n#### Competitive Landscape Flags\n"
    if insights:
        final_output += "\n".join(insights) + "\n\n"
    else:
        final_output += "- No clear peer concentration metrics recorded.\n\n"
        
    return final_output


def process_technical_data(instrument_key):
    """
    Parses the indexed array structure of Upstox historical candles.
    Converts data into a Pandas DataFrame, extracts technical indicators,
    and returns a tight structural trajectory markdown block for the LLM.
    """
    response = get_ohlc_data(instrument_key)
    if not response or response.get("status") != "success":
        return "### Technical Price Action\nData unavailable or failed request.\n"
        
    data = response.get("data", {})
    candle_data = data.get("candles", [])
    if not candle_data:
        return "### Technical Price Action\nNo candles found in payload.\n"

    # 1. Map raw indices into a structured Pandas DataFrame
    df = pd.DataFrame(candle_data, columns=[
        "Timestamp", "Open", "High", "Low", "Close", "Volume", "Open_Interest"
    ])
    
    # Clean timestamp strings and convert to a clean date layout
    df["Date"] = pd.to_datetime(df["Timestamp"]).dt.strftime("%Y-%m-%d")
    df = df.sort_values("Date").reset_index(drop=True)

    # 2. Extract technical signatures (handling potential short series gracefully)
    latest_price = df["Close"].iloc[-1]
    
    # 52-Week High / Low calculations (assuming the array contains enough history)
    lookback_52w = min(52, len(df))
    fifty_two_week_high = df["High"].tail(lookback_52w).max()
    fifty_two_week_low = df["Low"].tail(lookback_52w).min()

    # Calculate time-series Moving Averages (Institutional standard proxies)
    # 40-Week SMA is the direct equivalent of the daily 200-period SMA
    if len(df) >= 40:
        df["SMA_40W"] = df["Close"].rolling(window=40).mean()
        above_40w_sma = latest_price > df["SMA_40W"].iloc[-1]
        trend_status = "ABOVE (Bullish Macro Structure)" if above_40w_sma else "BELOW (Bearish Macro Structure)"
    else:
        trend_status = "Insufficient history to calculate 40-Week structural baseline"

    # 3. Build Token-Optimized Markdown Block
    summary = "### Weekly Price Action & Market Momentum\n"
    summary += f"- **Current Close**: {latest_price:.2f}\n"
    summary += f"- **52-Week Asset Range**: Low: {fifty_two_week_low:.2f} | High: {fifty_two_week_high:.2f}\n"
    summary += f"- **Macro Trend Metric**: Price is currently {trend_status}.\n\n"
    
    summary += "#### Recent Price & Volume Momentum Table\n"
    summary += "| Week Ending | Open | High | Low | Close | Volume (Shares) |\n"
    summary += "|---|---|---|---|---|---|\n"
    
    # Feed only the last 12 reporting weeks to keep the context window highly concise
    for _, row in df.tail(12).iterrows():
        summary += f"| {row['Date']} | {row['Open']:.2f} | {row['High']:.2f} | {row['Low']:.2f} | {row['Close']:.2f} | {int(row['Volume']):,} |\n"
        
    return summary 