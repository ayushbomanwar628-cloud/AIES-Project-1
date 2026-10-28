import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure repo root and app/ are in python path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(REPO_ROOT, 'app')
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from version import __version__
from vectorizer import load_activities, ActivityIndex, COST_TIER_RANK
from filters import filter_activities
from single_user import recommend_for_user
from group import GroupMember, recommend_for_group, aggregate_average, aggregate_least_misery, aggregate_borda
from server import app


@pytest.fixture(scope="module")
def dataset():
    df = load_activities(recommendable_only=True)
    return df


@pytest.fixture(scope="module")
def index(dataset):
    return ActivityIndex(dataset)


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_01_load_activities_dataset(dataset):
    """Test 1: Verify dataset loading, schema integrity, and cost rank mapping."""
    assert not dataset.empty, "Activities dataset should not be empty"
    assert len(dataset) >= 150, f"Expected at least 150 recommendable activities, found {len(dataset)}"
    
    expected_cols = {'name', 'category', 'mood_tags', 'cost_tier', 'cost_rank', 'recommendable'}
    assert expected_cols.issubset(set(dataset.columns)), f"Missing expected columns: {expected_cols - set(dataset.columns)}"
    
    # Verify cost tier ranks are integer mappings
    assert set(dataset['cost_rank'].unique()).issubset({0, 1, 2, 3, 4})
    assert dataset['name'].notna().all(), "All activities must have a non-null name"


def test_02_activity_index_tfidf(dataset, index):
    """Test 2: Verify TF-IDF index fitting and query scoring bounds."""
    query = "relaxed quiet evening reflective and peaceful"
    scores = index.score(query)
    
    assert len(scores) == len(dataset), "Index must return exactly one score per activity"
    assert (scores >= 0.0).all(), "Cosine similarity scores must be non-negative"
    assert (scores <= 1.000001).all(), "Cosine similarity scores cannot exceed 1.0"
    assert scores.max() > 0.05, "Top match score should be meaningful for relevant query"


def test_03_filters_budget_and_group_size(dataset):
    """Test 3: Verify hard constraint filtering (budget tiers and group sizes)."""
    # Filter with low budget (rank <= 1) and group size 4
    low_filtered = filter_activities(dataset, max_budget_tier='low', group_size=4)
    assert not low_filtered.empty, "Should find activities for low budget and group size 4"
    
    # Assert every activity in low_filtered has cost_rank <= 1
    assert (low_filtered['cost_rank'] <= 1).all(), "Low budget filter permitted higher tier activities"
    
    # Assert outdoor weather filtering works
    rainy_filtered = filter_activities(dataset, weather_ok_for_outdoor=False)
    assert not rainy_filtered.empty
    assert (rainy_filtered['indoor_outdoor'] == 'indoor').all(), "Outdoor activities included when weather_ok=False"


def test_04_single_user_recommendation(dataset, index):
    """Test 4: Verify single-user recommendation pipeline and ranking order."""
    query = "energetic competitive social"
    top_k = 5
    results = recommend_for_user(index, dataset, mood_text=query, max_budget_tier='medium', group_size=2, top_k=top_k)
    
    assert len(results) == top_k, f"Expected {top_k} recommendations, received {len(results)}"
    assert 'score' in results.columns
    # Check descending order
    scores = results['score'].tolist()
    assert scores == sorted(scores, reverse=True), "Recommendations must be sorted descending by match score"


def test_05_group_aggregation_average():
    """Test 5: Verify Average group aggregation strategy (mean happiness maximization)."""
    members = [
        GroupMember("Riya", "chill relaxed quiet"),
        GroupMember("Arjun", "energetic active adventurous"),
        GroupMember("Priya", "food social cafe")
    ]
    result_df, score_table = recommend_for_group(members, max_budget_tier='high', strategy='average', top_k=3)
    
    assert not result_df.empty, "Group recommendation returned empty DataFrame"
    assert 'group_score' in result_df.columns
    
    # Check that each row's group_score matches the mean of member scores
    for _, row in result_df.iterrows():
        member_scores = [row[f'score_{m.name}'] for m in members]
        expected_mean = sum(member_scores) / len(member_scores)
        assert pytest.approx(row['group_score'], abs=1e-4) == expected_mean


def test_06_group_aggregation_least_misery():
    """Test 6: Verify Least Misery aggregation strategy (protect worst-off member)."""
    members = [
        GroupMember("Riya", "relaxing quiet reading"),
        GroupMember("Arjun", "intense competitive sports"),
        GroupMember("Priya", "movie and snacks")
    ]
    result_df, score_table = recommend_for_group(members, max_budget_tier='high', strategy='least_misery', top_k=3)
    
    assert not result_df.empty
    for _, row in result_df.iterrows():
        member_scores = [row[f'score_{m.name}'] for m in members]
        expected_min = min(member_scores)
        assert pytest.approx(row['group_score'], abs=1e-4) == expected_min


def test_07_group_aggregation_borda():
    """Test 7: Verify Borda Count rank-order voting aggregation strategy."""
    members = [
        GroupMember("MemberA", "music arts and culture"),
        GroupMember("MemberB", "outdoors and nature")
    ]
    result_df, score_table = recommend_for_group(members, max_budget_tier='high', strategy='borda', top_k=4)
    
    assert not result_df.empty
    scores = result_df['group_score'].tolist()
    # Borda scores must be sorted descending
    assert scores == sorted(scores, reverse=True)
    # Scores must be greater than or equal to 0
    assert all(s >= 0 for s in scores)


def test_08_fastapi_health_and_api_endpoints(client):
    """Test 8: Verify REST API endpoints (/health, /api/version, and /api/recommend/single)."""
    # 1. Health Probe Endpoint
    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    data = health_resp.json()
    assert data["status"] == "UP"
    assert data["version"] == __version__
    assert data["author"] == "Ayush Bomanwar"
    assert data["prn"] == "1262243601"
    
    # 2. Version API Endpoint
    ver_resp = client.get("/api/version")
    assert ver_resp.status_code == 200
    assert ver_resp.json()["version"] == __version__
    
    # 3. Single Recommendation API Endpoint
    post_resp = client.post("/api/recommend/single", json={
        "mood_text": "creative artistic and peaceful",
        "max_budget_tier": "medium",
        "group_size": 2,
        "top_k": 3
    })
    assert post_resp.status_code == 200
    recs = post_resp.json()
    assert recs["count"] == 3
    assert len(recs["recommendations"]) == 3
    assert "name" in recs["recommendations"][0]
