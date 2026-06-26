from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from backend.src.agent.research_agent import research_agent

app = FastAPI(title="StoxFlow API")

# Enable CORS so Streamlit can query it
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "Welcome to the Stock Research Agent API"}

@app.get("/api/v1/research/{ticker}")
async def research_stock(ticker: str):
    try:
        # Run the LangGraph agent
        result = research_agent.invoke({"stock_name": ticker, "errors": []})
        
        # Check if there were errors
        if result.get("errors"):
            raise HTTPException(status_code=500, detail=f"Agent encountered errors: {result['errors']}")
            
        report = result.get("synthesis_report")
        if not report:
            raise HTTPException(status_code=500, detail="Synthesis report was not generated.")
            
        # Return both the synthesis and the raw preprocessed metrics/tables
        return {
            "report": report,
            "preprocessing": result.get("preprocessing_results", {})
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))