"""
Group recommendation: each member gives their own mood/interest text.
The system scores every candidate activity against EVERY member, then
combines those per-member scores using one of three aggregation strategies.
This is the core comparison your project evaluates.

Strategies:
  - average       : maximize mean happiness across the group
  - least_misery   : maximize the WORST member's score (nobody left unhappy)
  - borda          : rank-based voting -- each member ranks candidates,
                     points awarded by rank position, summed across members
                     (robust to one member's scores being on a different scale)

Hard constraints (budget, group size) are applied ONCE for the whole group
using the group's shared parameters (e.g. lowest budget among members, total
headcount) - see filter_activities() in filters.py. Soft mood/interest
matching is then computed per member and aggregated.
"""
import numpy as np
import pandas as pd
from vectorizer import load_activities, ActivityIndex
from filters import filter_activities


class GroupMember:
    def __init__(self, name, mood_text):
        self.name = name
        self.mood_text = mood_text


def score_all_members(index: ActivityIndex, filtered_df, members):
    """
    Returns a DataFrame: one row per filtered activity, one column per member
    with that member's similarity score, aligned by the filtered_df's index.
    """
    score_table = pd.DataFrame(index=filtered_df.index)
    for m in members:
        all_scores = index.score(m.mood_text)
        score_table[m.name] = filtered_df.index.map(lambda i: all_scores[i])
    return score_table


def aggregate_average(score_table):
    return score_table.mean(axis=1)


def aggregate_least_misery(score_table):
    return score_table.min(axis=1)


def aggregate_borda(score_table):
    """
    For each member, rank candidates best-to-worst, award points
    (N-1 for 1st place, N-2 for 2nd, ..., 0 for last). Sum across members.
    """
    n = len(score_table)
    points = pd.DataFrame(index=score_table.index, columns=score_table.columns, dtype=float)
    for col in score_table.columns:
        ranks = score_table[col].rank(ascending=False, method='first')  # 1 = best
        points[col] = n - ranks  # best gets n-1 points, worst gets 0
    return points.sum(axis=1)


AGGREGATORS = {
    'average': aggregate_average,
    'least_misery': aggregate_least_misery,
    'borda': aggregate_borda,
}


def recommend_for_group(members, max_budget_tier='medium', total_group_size=None,
                         weather_ok_for_outdoor=True, categories=None,
                         strategy='average', top_k=5):
    """
    members: list of GroupMember
    total_group_size: defaults to len(members) if not given
    strategy: 'average' | 'least_misery' | 'borda'
    Returns: (result_df, score_table) - result_df has activity info + the
        chosen strategy's aggregate score + each member's individual score,
        sorted best-first.
    """
    if total_group_size is None:
        total_group_size = len(members)

    df = load_activities()
    index = ActivityIndex(df)
    filtered = filter_activities(df, max_budget_tier, total_group_size,
                                  weather_ok_for_outdoor, categories)
    if filtered.empty:
        return filtered, pd.DataFrame()

    score_table = score_all_members(index, filtered, members)
    agg_scores = AGGREGATORS[strategy](score_table)

    result = filtered.copy()
    result['group_score'] = agg_scores
    for col in score_table.columns:
        result[f'score_{col}'] = score_table[col]

    result = result.sort_values('group_score', ascending=False).head(top_k)
    return result, score_table


def compare_strategies(members, max_budget_tier='medium', total_group_size=None,
                        weather_ok_for_outdoor=True, categories=None, top_k=3):
    """Convenience: run all three strategies on the same filtered pool, side by side."""
    if total_group_size is None:
        total_group_size = len(members)
    df = load_activities()
    index = ActivityIndex(df)
    filtered = filter_activities(df, max_budget_tier, total_group_size,
                                  weather_ok_for_outdoor, categories)
    if filtered.empty:
        print("No activities pass the group's hard constraints (budget/group size/weather).")
        return

    score_table = score_all_members(index, filtered, members)
    for strategy_name, fn in AGGREGATORS.items():
        agg = fn(score_table)
        top = agg.sort_values(ascending=False).head(top_k)
        print(f"\n=== {strategy_name.upper()} — top {top_k} ===")
        for idx in top.index:
            row = filtered.loc[idx]
            member_scores = ', '.join(f"{c}={score_table.loc[idx, c]:.2f}" for c in score_table.columns)
            print(f"  {row['name']}  (agg={agg[idx]:.3f} | {member_scores})")


if __name__ == '__main__':
    members = [
        GroupMember('Riya', "I'm broke this week, want something cheap and relaxing"),
        GroupMember('Arjun', "high energy, want to be outside and active"),
        GroupMember('Priya', "want to try new food, don't mind spending a bit"),
    ]
    compare_strategies(members, max_budget_tier='medium', total_group_size=3, top_k=3)
