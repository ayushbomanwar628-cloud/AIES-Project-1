"""
Hard-constraint filtering: applied BEFORE similarity ranking, since these are
non-negotiable (a ₹5000 activity doesn't become valid just because it scores
well on mood). Soft matching (mood/interest) happens after this, in vectorizer.py
+ single_user.py / group.py.
"""
from vectorizer import COST_TIER_RANK

BUDGET_TO_TIER_RANK = {
    'free': 0,
    'low': 1,      # up to ~₹300
    'medium': 2,   # up to ~₹1000
    'high': 3,     # up to ~₹2500
    'premium': 4,  # no cap
}


def filter_activities(df, max_budget_tier='medium', group_size=1,
                       weather_ok_for_outdoor=True, categories=None):
    """
    df: activities DataFrame (from vectorizer.load_activities)
    max_budget_tier: one of 'free','low','medium','high','premium' - the MOST
        the user/group is willing to spend; activities costing more are dropped
    group_size: number of people; activity must support this many
    weather_ok_for_outdoor: if False, outdoor activities are excluded
    categories: optional list of categories to restrict to (interest filter),
        e.g. ['food','wellness']. None = no restriction.
    """
    budget_rank = BUDGET_TO_TIER_RANK.get(max_budget_tier, 2)

    mask = (
        (df['cost_rank'] <= budget_rank) &
        (df['group_size_min'] <= group_size) &
        (df['group_size_max'] >= group_size)
    )

    if not weather_ok_for_outdoor:
        mask &= (df['indoor_outdoor'] != 'outdoor')

    if categories:
        mask &= df['category'].isin(categories)

    # IMPORTANT: no reset_index here — callers (single_user.py, group.py) map
    # TF-IDF similarity scores back onto rows using this original index, since
    # the ActivityIndex is fit once on the full df and scores are positional.
    filtered = df[mask]
    return filtered


if __name__ == '__main__':
    from vectorizer import load_activities
    df = load_activities()
    print(f"Before filtering: {len(df)}")
    filtered = filter_activities(df, max_budget_tier='low', group_size=3, weather_ok_for_outdoor=True)
    print(f"After budget<=low, group_size=3: {len(filtered)}")
    print(filtered[['name', 'category', 'cost_tier', 'group_size_max']].head(10).to_string(index=False))
