"""
Single-user path: mood + interest text + budget + group size -> filtered,
ranked list of activities. This is the building block the group recommender
(group.py) calls once per group member before aggregating.
"""
from vectorizer import load_activities, ActivityIndex
from filters import filter_activities


def recommend_for_user(index: ActivityIndex, df_full,
                        mood_text, max_budget_tier='medium', group_size=1,
                        weather_ok_for_outdoor=True, categories=None, top_k=5):
    """
    index: a pre-built ActivityIndex (fit once over the FULL df, reused across users
        so every user's score is comparable/on the same TF-IDF vector space)
    df_full: the same df the index was built on
    mood_text: free-text description of mood/interest, e.g.
        "feeling energetic, want to be around people, love trying new food"
    Returns: filtered df with an added 'score' column, sorted best-first, top_k rows.
    """
    filtered = filter_activities(df_full, max_budget_tier, group_size,
                                  weather_ok_for_outdoor, categories)
    if filtered.empty:
        return filtered.assign(score=[])

    # score against the FULL index, then subset to filtered rows, so scores
    # stay comparable across different users/filters
    all_scores = index.score(mood_text)
    filtered = filtered.copy()
    filtered['score'] = filtered.index.map(lambda i: all_scores[i])
    return filtered.sort_values('score', ascending=False).head(top_k)


if __name__ == '__main__':
    df = load_activities()
    index = ActivityIndex(df)
    result = recommend_for_user(
        index, df,
        mood_text="feeling low energy, want something relaxing and quiet",
        max_budget_tier='low', group_size=1, top_k=5
    )
    print("Top picks:")
    print(result[['name', 'category', 'mood_tags', 'cost_tier', 'score']].to_string(index=False))
