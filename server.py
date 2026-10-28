import os
import sys
import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from pydantic import BaseModel, Field

# Ensure app package is importable
APP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app')
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from version import __version__, APP_NAME, SERVICE_NAME, BUILD_METADATA
from vectorizer import load_activities, ActivityIndex
from single_user import recommend_for_user
from group import GroupMember, recommend_for_group

# Initialize FastAPI App
app = FastAPI(
    title=APP_NAME,
    description="Bangalore Hangout Recommender — AI-Powered Solo and Group Activity Planning Engine",
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pre-load dataset and TF-IDF index at startup
DF_ACTIVITIES = load_activities()
INDEX = ActivityIndex(DF_ACTIVITIES)

WEB_HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web', 'hangout_finder.html')


def extract_venues(row):
    venues = []
    for i in range(1, 4):
        v = row.get(f'sample_venue_{i}')
        if pd.notna(v) and str(v).strip():
            loc = row.get(f'sample_venue_{i}_locality')
            if pd.notna(loc) and str(loc).strip():
                venues.append(f"{v} ({loc})")
            else:
                venues.append(str(v))
    return venues


class SingleRecommendationRequest(BaseModel):
    mood_text: str = Field(..., description="relaxed, quiet evening, good food")
    max_budget_tier: str = Field(default="medium", description="medium")
    group_size: int = Field(default=2, ge=1, le=50)
    top_k: int = Field(default=5, ge=1, le=20)


class MemberItem(BaseModel):
    name: str = Field(..., description="Ayush")
    mood_text: str = Field(..., description="energetic, want to be social and try something new")


class GroupRecommendationRequest(BaseModel):
    members: List[MemberItem]
    max_budget_tier: str = Field(default="medium", description="medium")
    total_group_size: Optional[int] = None
    weather_ok_for_outdoor: bool = True
    strategy: str = Field(default="average", description="average")  # 'average' | 'least_misery' | 'borda'
    top_k: int = Field(default=5, ge=1, le=20)


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    if not os.path.exists(WEB_HTML_PATH):
        raise HTTPException(status_code=404, detail="Web application interface not found")
    with open(WEB_HTML_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    # Inject current version dynamically
    content = content.replace("{{APP_VERSION}}", __version__)
    return HTMLResponse(content=content)


@app.get("/health")
async def health_check():
    """
    Kubernetes liveness and readiness probe endpoint.
    Returns HTTP 200 with service health status and build version.
    """
    return JSONResponse(
        status_code=200,
        content={
            "status": "UP",
            "version": __version__,
            "service": SERVICE_NAME,
            "application": APP_NAME,
            "author": "Ayush Bomanwar",
            "prn": "1262243601",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "activities_indexed": len(DF_ACTIVITIES),
            "database": "loaded",
            "environment": "production"
        }
    )


@app.get("/api/version")
async def get_version():
    return {
        "version": __version__,
        "app_name": APP_NAME,
        "service": SERVICE_NAME,
        "author": "Ayush Bomanwar",
        "prn": "1262243601",
        "status": "UP",
        "features": [
            "TF-IDF Semantic Vectorization",
            "Multi-Criteria Hard Filtering",
            "Social-Choice Aggregation (Average, Least Misery, Borda Count)",
            "Bangalore Zomato & OSM Venues"
        ]
    }


@app.get("/api/activities")
async def get_activities_summary():
    categories = sorted(DF_ACTIVITIES['category'].dropna().unique().tolist())
    cost_tiers = sorted(DF_ACTIVITIES['cost_tier'].dropna().unique().tolist())
    return {
        "total_activities": len(DF_ACTIVITIES),
        "categories": categories,
        "cost_tiers": cost_tiers,
        "sample_activities": DF_ACTIVITIES[['name', 'category', 'mood_tags', 'cost_tier']].head(5).to_dict(orient="records")
    }


@app.post("/api/recommend/single")
async def recommend_single(req: SingleRecommendationRequest):
    try:
        results = recommend_for_user(
            INDEX,
            DF_ACTIVITIES,
            mood_text=req.mood_text,
            max_budget_tier=req.max_budget_tier,
            group_size=req.group_size,
            top_k=req.top_k
        )
        records = []
        for _, row in results.iterrows():
            records.append({
                "name": row['name'],
                "category": row['category'],
                "description": row['description'],
                "mood_tags": row['mood_tags'],
                "cost_tier": row['cost_tier'],
                "sample_venues": extract_venues(row),
                "score": round(float(row['score']), 4)
            })
        return {
            "mode": "single",
            "query": req.mood_text,
            "budget_tier": req.max_budget_tier,
            "count": len(records),
            "recommendations": records
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/recommend/group")
async def recommend_group(req: GroupRecommendationRequest):
    if not req.members:
        raise HTTPException(status_code=400, detail="Group requires at least one member")
    strategy = req.strategy.lower()
    if strategy not in ['average', 'least_misery', 'borda']:
        raise HTTPException(status_code=400, detail="Strategy must be one of: average, least_misery, borda")
    
    try:
        group_members = [GroupMember(m.name, m.mood_text) for m in req.members]
        result_df, score_table = recommend_for_group(
            group_members,
            max_budget_tier=req.max_budget_tier,
            total_group_size=req.total_group_size,
            weather_ok_for_outdoor=req.weather_ok_for_outdoor,
            strategy=strategy,
            top_k=req.top_k
        )
        if result_df.empty:
            return {
                "mode": "group",
                "strategy": strategy,
                "count": 0,
                "recommendations": []
            }
        
        output = []
        for _, row in result_df.iterrows():
            member_breakdown = {}
            for m in req.members:
                score_col = f"score_{m.name}"
                if score_col in row:
                    member_breakdown[m.name] = round(float(row[score_col]), 3)
            
            output.append({
                "name": row['name'],
                "category": row['category'],
                "description": row['description'],
                "mood_tags": row['mood_tags'],
                "cost_tier": row['cost_tier'],
                "sample_venues": extract_venues(row),
                "group_score": round(float(row['group_score']), 3),
                "member_scores": member_breakdown
            })
            
        return {
            "mode": "group",
            "strategy": strategy,
            "member_count": len(req.members),
            "count": len(output),
            "recommendations": output
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
