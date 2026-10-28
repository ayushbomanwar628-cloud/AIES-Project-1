"""
Fill in mood_tags and energy_level for activity_types.csv using rule-based
tagging (category + keyword matching). This is deliberately transparent and
explainable rather than a black-box LLM call, and gives you a clean baseline
you can later refine by hand or swap for LLM-generated tags.

Mood taxonomy used (a group member's "mood" maps onto one or more of these):
  relaxed, energetic, social, adventurous, creative, competitive,
  romantic, reflective

Also flags 'recommendable' = False for the Bored API 'chores'/'busywork'
category, since those are generic productivity tasks (e.g. "do laundry"),
not hangout activities. They stay in the data but are excluded from the
recommender's candidate pool by default.
"""
import csv

IN_PATH = '/home/claude/AIES/data/activity_types.csv'
OUT_PATH = '/home/claude/AIES/data/activity_types_tagged.csv'

# category -> default mood tags (applied first, keyword rules can add more)
CATEGORY_MOODS = {
    'food':         ['social', 'relaxed'],
    'entertainment':['social', 'energetic'],
    'wellness':     ['relaxed', 'reflective'],
    'arts_culture': ['reflective', 'creative'],
    'outdoor':      ['relaxed', 'adventurous'],
    'shopping':     ['social', 'energetic'],
    'learning':     ['creative', 'reflective'],
    'social':       ['social'],
    'community':    ['social', 'reflective'],
    'chores':       [],  # excluded from recommender pool, see 'recommendable' below
}

CATEGORY_ENERGY_DEFAULT = {
    'food': 'low', 'entertainment': 'medium', 'wellness': 'medium',
    'arts_culture': 'low', 'outdoor': 'medium', 'shopping': 'medium',
    'learning': 'low', 'social': 'medium', 'community': 'low', 'chores': 'low',
}

# keyword -> extra mood tags / energy override (checked against name+description, lowercased)
KEYWORD_RULES = [
    (['hike', 'trek', 'climb', 'adventure', 'sport', 'run', 'cycle', 'bike'],
     ['adventurous', 'energetic'], 'high'),
    (['bowling', 'arcade', 'escape', 'game', 'quiz', 'competition', 'tournament'],
     ['competitive', 'energetic'], 'high'),
    (['yoga', 'meditat', 'spa', 'massage'],
     ['relaxed', 'reflective'], 'low'),
    (['gym', 'fitness', 'workout', 'boxing', 'zumba'],
     ['energetic'], 'high'),
    (['museum', 'gallery', 'art', 'history', 'exhibit'],
     ['reflective', 'creative'], None),
    (['romantic', 'date', 'candle', 'sunset', 'fine dining'],
     ['romantic'], None),
    (['charity', 'volunteer', 'donate'],
     ['social', 'reflective'], 'low'),
    (['write', 'paint', 'draw', 'craft', 'diy', 'cook', 'bake', 'music', 'instrument'],
     ['creative'], None),
]

def tag_row(row):
    category = row['category']
    text = f"{row['name']} {row['description']}".lower()

    moods = set(CATEGORY_MOODS.get(category, []))
    energy = row.get('energy_level', '').strip() or CATEGORY_ENERGY_DEFAULT.get(category, 'medium')

    for keywords, extra_moods, energy_override in KEYWORD_RULES:
        if any(k in text for k in keywords):
            moods.update(extra_moods)
            if energy_override:
                energy = energy_override

    row['mood_tags'] = ','.join(sorted(moods)) if moods else ''
    row['energy_level'] = energy
    row['recommendable'] = 'False' if category == 'chores' else 'True'
    return row

def main():
    with open(IN_PATH, encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    fieldnames = list(rows[0].keys())
    if 'recommendable' not in fieldnames:
        fieldnames.append('recommendable')

    tagged = [tag_row(r) for r in rows]

    with open(OUT_PATH, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(tagged)

    excluded = sum(1 for r in tagged if r['recommendable'] == 'False')
    print(f"Tagged {len(tagged)} rows -> {OUT_PATH}")
    print(f"Excluded from recommender pool (chores/busywork): {excluded}")
    print(f"Recommendable pool size: {len(tagged) - excluded}")

    # quick mood distribution sanity check
    from collections import Counter
    mood_counts = Counter()
    for r in tagged:
        if r['recommendable'] == 'True':
            for m in r['mood_tags'].split(','):
                if m:
                    mood_counts[m] += 1
    print("\nMood tag distribution (recommendable pool):")
    for m, c in mood_counts.most_common():
        print(f"  {m}: {c}")

if __name__ == '__main__':
    main()
