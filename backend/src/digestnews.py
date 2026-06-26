import json
import requests
from bs4 import BeautifulSoup
import litellm
import os
from dotenv import load_dotenv

load_dotenv()

# Map GOOGLE_API_KEY to GEMINI_API_KEY for LiteLLM compat
if "GOOGLE_API_KEY" in os.environ and "GEMINI_API_KEY" not in os.environ:
    os.environ["GEMINI_API_KEY"] = os.environ["GOOGLE_API_KEY"]

# Define default models and configs
DEFAULT_LOCAL_MODEL = os.getenv("LOCAL_LLM_MODEL", "ollama/qwen2.5:3b")
DEFAULT_CLOUD_MODEL = os.getenv("CLOUD_LLM_MODEL", "gemini/gemini-2.5-flash-lite")
DEFAULT_CRAWL_NEWS = os.getenv("CRAWL_NEWS", "false").lower() in ("true", "1", "yes")

def digest_news(news_articles, company_profile, crawl=None):
    if crawl is None:
        crawl = DEFAULT_CRAWL_NEWS
    key_takeaways = []

    local_model = DEFAULT_LOCAL_MODEL
    if local_model and "/" not in local_model:
        local_model = f"ollama/{local_model}"
        
    cloud_model = DEFAULT_CLOUD_MODEL

    for article in news_articles:
        is_dict = isinstance(article, dict)
        heading = article.get("heading", "") if is_dict else ""
        summary = article.get("summary", "") if is_dict else ""
        link = article.get("article_link", "") if is_dict else article
        published_time = article.get("published_time") if is_dict else None

        if not link and not (heading or summary):
            continue

        article_body = None

        # 1. If crawl is enabled, try crawling the link
        if crawl and link:
            print(f"Crawling full article body from: {link}")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
            }
            try:
                response = requests.get(link, headers=headers, verify=False, timeout=8)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    paragraphs = soup.find_all('p')
                    body_text = "\n".join([p.get_text() for p in paragraphs]).strip()
                    if len(body_text) > 100:
                        article_body = body_text[:4000]
                        print("Successfully crawled full article body.")
                    else:
                        print(f"Scraped content from {link} was too short.")
                else:
                    print(f"Failed to crawl {link}: HTTP status {response.status_code}")
            except Exception as e:
                print(f"Scraping failed for {link}: {e}")

        # 2. If crawling failed or was not requested, try using the API summary
        if not article_body and (heading or summary):
            print(f"Using API Heading & Summary fallback for: {link or heading[:30]}")
            article_body = f"Heading: {heading}\nSummary: {summary}"

        # 3. Last resort: If we still don't have body (e.g. crawl=False but we only got a raw link string), try crawling
        if not article_body and link:
            print(f"No summary fallback available. Forcing crawl for raw link: {link}")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
            }
            try:
                response = requests.get(link, headers=headers, verify=False, timeout=8)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    paragraphs = soup.find_all('p')
                    body_text = "\n".join([p.get_text() for p in paragraphs]).strip()
                    if len(body_text) > 100:
                        article_body = body_text[:4000]
            except Exception as e:
                print(f"Forced crawling failed: {e}")

        if not article_body:
            print(f"Skipping article: no content could be retrieved.")
            continue

        system_prompt = (
            "You are an expert financial analyst. Your task is to analyze raw news article text (or heading and summary), "
            "extract key details relevant to a specific company/sector, and respond ONLY in JSON format."
        )

        user_prompt = f"""Target Company Profile:
{company_profile}

Article/News Content:
{article_body}

Task:
Extract key financial and sector-specific takeaways from the article. 

Respond EXACTLY in this JSON format:
{{
  "relevant": true or false,
  "sentiment": "positive", "negative", or "neutral",
  "impact_score": "high", "medium", or "low",
  "key_takeaways": [
    "First concrete fact/figure (e.g. profit amount, dividend date, or OPEC capacity cut)",
    "Second concrete fact/figure if available"
  ],
  "reason": "1-2 sentences explaining how this affects the company or its sector."
}}
"""

        text = None
        # 1. Attempt Local LLM via LiteLLM
        try:
            print(f"Attempting local LLM news digestion for: {link or heading[:30]} using {local_model}")
            chat_response = litellm.completion(
                model=local_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            text = chat_response.choices[0].message.content.strip()
        except Exception as ollama_err:
            print(f"Warning: Local LLM news digestion failed: {ollama_err}. Falling back to cloud model ({cloud_model})...")
            
            # 2. Fallback to Cloud LLM via LiteLLM
            try:
                chat_response = litellm.completion(
                    model=cloud_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.0,
                    max_tokens=500,
                    response_format={"type": "json_object"}
                )
                text = chat_response.choices[0].message.content.strip()
            except Exception as ex:
                print(f"Error: Cloud LLM news digestion failed: {ex}")
                continue

        if not text:
            continue

        try:
            if text.startswith("```"):
                lines = text.splitlines()
                if lines[0].strip().startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip().startswith("```"):
                    lines = lines[:-1]
                text = "\n".join(lines).strip()

            details = json.loads(text)
            relevant = details.get("relevant", False)
            if isinstance(relevant, str):
                relevant = relevant.lower() == "true"

            if relevant:
                key_takeaways.append({
                    "heading": heading or details.get("event") or "Market Event",
                    "news_link": link,
                    "published_time": published_time,
                    "sentiment": details.get("sentiment", "neutral"),
                    "impact_score": details.get("impact_score", "low"),
                    "takeaways": details.get("key_takeaways", []),
                    "reason": details.get("reason", "")
                })
        except json.JSONDecodeError:
            pass

    return key_takeaways
