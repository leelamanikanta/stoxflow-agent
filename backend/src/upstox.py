from datetime import datetime
import requests
from dotenv import load_dotenv
import os
import datetime


# Load the environment variables from the .env file
load_dotenv() 



def get_company_profile(isin: str):
    url = f"https://api.upstox.com/v2/fundamentals/{isin}/profile"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        "Accept": "application/json",
        "Authorization": f"Bearer {os.getenv('UPSTOX_API_KEY')}"
    }
    response = requests.get(url, headers=headers,verify=False)
    
    return response.json()

def get_company_news(instrument_key:str):

    # 'https://api.upstox.com/v2/news?category=instrument_keys&instrument_keys=NSE_EQ%7CINE040H01021' \
    instrument_key = instrument_key.replace("|", "%7C")
    url = f"https://api.upstox.com/v2/news?category=instrument_keys&instrument_keys={instrument_key}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        "Accept": "application/json",
        "Authorization": f"Bearer {os.getenv('UPSTOX_API_KEY')}"
    }

    response = requests.get(url, headers=headers,verify=False)
    
    return response.json()


def get_key_ratios(isin: str):
    url = f"https://api.upstox.com/v2/fundamentals/{isin}/key-ratios"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        "Accept": "application/json",
        "Authorization": f"Bearer {os.getenv('UPSTOX_API_KEY')}"
    }
    response = requests.get(url, headers=headers,verify=False)
    
    return response.json()

def get_shareholding_pattern(isin: str):
    url = f"https://api.upstox.com/v2/fundamentals/{isin}/share-holdings"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        "Accept": "application/json",
        "Authorization": f"Bearer {os.getenv('UPSTOX_API_KEY')}"
    }
    response = requests.get(url, headers=headers,verify=False)
    
    return response.json()
    
def get_income_statement(isin:str):
    url = f"https://api.upstox.com/v2/fundamentals/{isin}/income-statement?type=consolidated&time_period=yearly&fs=true"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        "Accept": "application/json",
        "Authorization": f"Bearer {os.getenv('UPSTOX_API_KEY')}"
    }
    response = requests.get(url, headers=headers,verify=False)
    
    return response.json()

def  get_cashflow_statement(isin:str):
    url = f"https://api.upstox.com/v2/fundamentals/{isin}/cash-flow?type=consolidated&fs=true"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        "Accept": "application/json",
        "Authorization": f"Bearer {os.getenv('UPSTOX_API_KEY')}"
    }
    response = requests.get(url, headers=headers,verify=False)
    
    return response.json()
    
def get_balance_sheet(isin:str):
    url = f"https://api.upstox.com/v2/fundamentals/{isin}/balance-sheet?type=consolidated&fs=true"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        "Accept": "application/json",
        "Authorization": f"Bearer {os.getenv('UPSTOX_API_KEY')}"
    }
    response = requests.get(url, headers=headers,verify=False)
    
    return response.json()

def get_corporate_actions(isin:str):
    url = f"https://api.upstox.com/v2/fundamentals/{isin}/corporate-actions"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        "Accept": "application/json",
        "Authorization": f"Bearer {os.getenv('UPSTOX_API_KEY')}"
    }
    response = requests.get(url, headers=headers,verify=False)
    
    return response.json()


def get_competitors(instrument_key: str):
    instrument_key = instrument_key.replace("|", "%7C")
    url = f"https://api.upstox.com/v2/fundamentals/{instrument_key}/competitors"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        "Accept": "application/json",
        "Authorization": f"Bearer {os.getenv('UPSTOX_API_KEY')}"
    }
    response = requests.get(url, headers=headers,verify=False)
    
    return response.json()



def get_ohlc_data(instrument_key: str, interval="week", start_date_years="5"):
    # 1. Safely encode the vertical bar for Upstox URLs
    instrument_key = instrument_key.replace("|", "%7C")
    
    # 2. Compute date windows accurately (Avoids the 'years' keyword crash)
    end_date_obj = datetime.date.today()
    start_date_obj = end_date_obj - datetime.timedelta(days=int(start_date_years) * 365)
    
    # 3. Format as 'YYYY-MM-DD' strings
    to_date = end_date_obj.strftime("%Y-%m-%d")
    from_date = start_date_obj.strftime("%Y-%m-%d")
    
    # 4. Correct Upstox V2 URL format structure: /{instrumentKey}/{interval}/{to_date}/{from_date}
    url = f'https://api.upstox.com/v2/historical-candle/{instrument_key}/{interval}/{to_date}/{from_date}' 

    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': f"Bearer {os.getenv('UPSTOX_API_KEY')}"
    }
    
    response = requests.get(url, headers=headers, verify=False)
    return response.json()
