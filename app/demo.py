"""
Run this to see the whole pipeline work end to end:
  1. Single-user recommendation
  2. Group recommendation with all 3 aggregation strategies compared

Usage: python3 demo.py
"""
from vectorizer import load_activities, ActivityIndex
from single_user import recommend_for_user
from group import GroupMember, compare_strategies

def demo_single_user():
    print("=" * 60)
    print("SINGLE-USER DEMO")
    print("=" * 60)
    df = load_activities()
    index = ActivityIndex(df)
    result = recommend_for_user(
        index, df,
        mood_text="energetic, want to be social and try something new",
        max_budget_tier='medium', group_size=2, top_k=5
    )
    print(result[['name', 'category', 'mood_tags', 'cost_tier', 'score']].to_string(index=False))

def demo_group():
    print("\n" + "=" * 60)
    print("GROUP DEMO — mismatched moods/budgets, 3 members")
    print("=" * 60)
    members = [
        GroupMember('Riya', "I'm broke this week, want something cheap and relaxing"),
        GroupMember('Arjun', "high energy, want to be outside and active"),
        GroupMember('Priya', "want to try new food, don't mind spending a bit"),
    ]
    compare_strategies(members, max_budget_tier='medium', total_group_size=3, top_k=3)

if __name__ == '__main__':
    demo_single_user()
    demo_group()
