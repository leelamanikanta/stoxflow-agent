from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from backend.src.parsesymbols import parse_symbols
from backend.src.upstox import get_company_profile, get_company_news
from backend.src.upstox_preprocess_data import (
    process_key_ratios, preprocess_shareholding_pattern,
    preprocess_income_statement, preprocess_balance_sheet,
    preprocess_cashflow_statement, preprocess_corporate_actions,
    preprocess_competitors, process_technical_data
)
from backend.src.digestnews import digest_news

import os
import litellm
import json
from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Dict, Any, Optional

from phoenix.otel import register
from openinference.instrumentation.langchain import LangChainInstrumentor
from openinference.instrumentation.litellm import LiteLLMInstrumentor


# 1. Register Phoenix to enable auto-instrumentation
tracer_provider = register(project_name="marketsense-agent")

LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
LiteLLMInstrumentor().instrument(tracer_provider=tracer_provider)


# 2. Define Agent State
class AgentState(TypedDict):
    stock_name: str
    symbol: Optional[str]
    name: Optional[str]
    instrument_full_name: Optional[str]
    profile_text: Optional[str]
    sector: Optional[str]
    market_cap_inr: Optional[str]
    market_cap_usd: Optional[str]
    preprocessing_results: Optional[Dict[str, Any]]
    news_articles: Optional[List[Dict[str, Any]]]
    digested_news: Optional[List[Dict[str, Any]]]
    synthesis_report: Optional[Dict[str, Any]]
    errors: List[str]


# 3. Define Graph Nodes
def resolve_company_node(state: AgentState) -> Dict[str, Any]:
    print("--- [Node] Resolving Company ---")
    stock_name = state["stock_name"]
    try:
        symbols_result = parse_symbols(stock_name)
        data_dict = json.loads(symbols_result)
        item = data_dict[0]
        return {
            "instrument_full_name": item["instrument_key"],
            "symbol": item["instrument_key"].split('|')[-1],
            "name": item["name"]
        }
    except Exception as e:
        return {"errors": state.get("errors", []) + [f"Resolution failed: {e}"]}


def fetch_company_data_node(state: AgentState) -> Dict[str, Any]:
    print("--- [Node] Fetching Company Data ---")
    if state.get("errors"):
        return {}
    symbol = state.get("symbol")
    instrument_full_name = state.get("instrument_full_name")
    if not symbol or not instrument_full_name:
        return {"errors": state.get("errors", []) + ["Missing symbol or instrument_full_name for fetching data."]}

    # Run API calls & Preprocessing concurrently
    # 1. Fetch Company profile
    profile = get_company_profile(symbol).get("data", {})
    profile_text = profile.get('company_profile') or 'No description available'
    sector = profile.get('sector') or 'N/A'
    market_cap_inr = profile.get('sector_market_cap_inr', {}).get('formatted', 'N/A')
    market_cap_usd = profile.get('sector_market_cap_usd', {}).get('formatted', 'N/A')
    
    # 2. Fetch Upstox News Articles
    news_articles = get_company_news(instrument_full_name).get("data", {}).get(instrument_full_name, [])

    # 3. Preprocess Fundamentals & Technicals Concurrently
    preprocessing_tasks = {
        "Key Ratios": (process_key_ratios, symbol),
        "Shareholding Pattern": (preprocess_shareholding_pattern, symbol),
        "Income Statement": (preprocess_income_statement, symbol),
        "Balance Sheet": (preprocess_balance_sheet, symbol),
        "Cashflow Statement": (preprocess_cashflow_statement, symbol),
        "Corporate Actions": (preprocess_corporate_actions, symbol),
        "Competitor Analysis": (preprocess_competitors, instrument_full_name),
        "Technical Analysis": (process_technical_data, instrument_full_name)
    }
    
    preprocessing_results = {}
    def run_task(name, func, args):
        try:
            return name, func(args)
        except Exception as e:
            return name, f"Error: {e}"
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(run_task, name, function, args): name for name, (function, args) in preprocessing_tasks.items()}
        for fut in as_completed(futures):
            name, res = fut.result()
            preprocessing_results[name] = res
            
    return {
        "profile_text": profile_text,
        "sector": sector,
        "market_cap_inr": market_cap_inr,
        "market_cap_usd": market_cap_usd,
        "news_articles": news_articles,
        "preprocessing_results": preprocessing_results
    }

    
def digest_news_node(state: AgentState) -> Dict[str, Any]:
    print("--- [Node] Digesting News ---")
    if state.get("errors"):
        return {}
    news_articles = state.get("news_articles", [])
    profile_text = state.get("profile_text", "")
    try:
        digested_news = digest_news(news_articles, profile_text)
        return {"digested_news": digested_news}
    except Exception as e:
        return {"errors": state.get("errors", []) + [f"Digesting news failed: {e}"]}


def synthesize_report_node(state: AgentState) -> Dict[str, Any]:
    print("--- [Node] Synthesizing Research Report using Gemini ---")
    if state.get("errors"):
        return {}
    
    stock_name = state.get("stock_name", "")
    name = state.get("name", "")
    instrument_full_name = state.get("instrument_full_name", "")
    sector = state.get("sector", "")
    market_cap_inr = state.get("market_cap_inr", "N/A")
    market_cap_usd = state.get("market_cap_usd", "N/A")
    profile_text = state.get("profile_text", "")
    preprocessing_results = state.get("preprocessing_results") or {}
    digested_news = state.get("digested_news") or []
    
    fundamentals_text = "\n\n".join([
        f"## {n}\n{content}" 
        for n, content in preprocessing_results.items() if n != "Technical Analysis"
    ])
    technicals_text = preprocessing_results.get("Technical Analysis", "No technical analysis available.")
    
    news_summaries_text = ""
    if digested_news:
        for idx, item in enumerate(digested_news, 1):
            news_summaries_text += f"""
Article {idx}:
- Link: {item.get('news_link', 'N/A')}
- Sentiment: {item.get('sentiment', 'N/A')}
- Impact Score: {item.get('impact_score', 'N/A')}
- Takeaways: {", ".join(item.get('takeaways', []))}
- Reason: {item.get('reason', 'N/A')}
"""
    else:
        news_summaries_text = "No relevant news articles found."

    system_prompt = (
        "You are an elite financial analyst and investment researcher. "
        "Your task is to synthesize all profile, fundamental, technical, and news data "
        "for a given stock and produce a comprehensive, structured investment research report. "
        "Your response MUST be a valid JSON object matching the exact specified schema."
    )

    current_date = datetime.now().strftime("%Y-%m-%d")
    user_prompt = f"""
Today's Date: {current_date}
Company: {name} ({instrument_full_name})
Sector: {sector}
Market Capitalization (INR): {market_cap_inr}
Market Capitalization (USD): {market_cap_usd}

Company Profile Description:
{profile_text}

---
### Financial Fundamentals & Anomalies:
{fundamentals_text}

---
### Price Action & Technical Momentum:
{technicals_text}

---
### Recent Market News & Digested Takeaways:
{news_summaries_text}

---
### Assignment:
Synthesize the above data and generate a structured JSON investment report.
Be extremely objective, analytical, and flag any risks, anomalies, or competitive shifts clearly.

Your output must be a single JSON object structured EXACTLY as follows:
{{
  "company": {{
    "symbol": "{stock_name.upper()}",
    "name": "{name}",
    "sector": "{sector}"
  }},
  "profile": {{
    "description": "{profile_text[:200]}...",
    "market_cap_inr": "{market_cap_inr}",
    "market_cap_usd": "{market_cap_usd}"
  }},
  "fundamentals": {{
    "ratios_analysis": "Summarize valuation premium/discount and efficiency relative to sector.",
    "shareholding_analysis": "Summarize promoter, institutional holding trends and momentum flags.",
    "financials_analysis": "Summarize key observations from Balance Sheet, Cash Flow, and Income Statement."
  }},
  "price_analysis": {{
    "trend": "Identify macro trend (Bullish/Bearish) and relative position to 40-Week SMA.",
    "rsi_or_momentum": "Summarize recent price and volume momentum observations.",
    "fifty_two_week_range": "Low: X | High: Y"
  }},
  "news_and_events": [
    {{
      "event": "Headline or key theme of the news",
      "sentiment": "positive/negative/neutral",
      "impact": "high/medium/low",
      "summary": "Brief summary of the news and its impact."
    }}
  ],
  "insights": [
    "Key insight 1 (e.g. core growth drivers, margin expansions)",
    "Key insight 2 (e.g. cash conversion efficiency)"
  ],
  "risks": [
    "Risk 1 (e.g. debt levels, competitor size, promoter distribution)",
    "Risk 2 (e.g. technical breakdown below SMA)"
  ],
  "opportunities": [
    "Opportunity 1 (e.g. sector growth, valuation discount)",
    "Opportunity 2 (e.g. strong institutional accumulation)"
  ],
  "summary": "Provide a detailed executive investment thesis summarizing the overall outlook (bull/bear case) in 3-4 paragraphs."
}}
"""

    primary_model = os.getenv("CLOUD_LLM_MODEL", "gemini/gemini-2.5-flash-lite")
    if "/" not in primary_model:
        primary_model = f"gemini/{primary_model}"

    fallback_models = ["gemini/gemini-2.5-flash", "gemini/gemini-1.5-flash"]
    model_list = [primary_model] + [m for m in fallback_models if m != primary_model]

    response = None
    for model in model_list:
        try:
            print(f"Synthesizing report using {model}...")
            response = litellm.completion(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            break
        except Exception as e:
            print(f"Warning: {model} failed in research_agent.py: {e}. Trying fallback...")
            continue
            
    if not response:
        return {"errors": state.get("errors", []) + ["All cloud models failed to respond in research_agent.py"]}

    try:
        text = response.choices[0].message.content.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        report_json = json.loads(text)
        
        # Save to file
        os.makedirs("reports", exist_ok=True)
        output_filename = os.path.join("reports", f"research_{stock_name.upper()}.json")
        with open(output_filename, 'w', encoding='utf-8') as out_f:
            json.dump(report_json, out_f, indent=2, ensure_ascii=False)
        print(f"Saved full structured report to {output_filename}")
        
        return {"synthesis_report": report_json}

    except Exception as e:
        return {"errors": state.get("errors", []) + [f"Failed to parse or save synthesized report: {e}"]}


# 4. Build and Compile the Graph
workflow = StateGraph(AgentState)
workflow.add_node("resolve_company", resolve_company_node)
workflow.add_node("fetch_company_data", fetch_company_data_node)
workflow.add_node("digest_news", digest_news_node)
workflow.add_node("synthesize_report", synthesize_report_node)

workflow.set_entry_point("resolve_company")
workflow.add_edge("resolve_company", "fetch_company_data")
workflow.add_edge("fetch_company_data", "digest_news")
workflow.add_edge("digest_news", "synthesize_report")
workflow.add_edge("synthesize_report", END)

research_agent = workflow.compile()

if __name__ == "__main__":
    stock_name = input("Enter the stock name to research: ")
    research_agent.invoke({"stock_name": stock_name, "errors": []})    