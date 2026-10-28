"""
Collapse the 5,698-row venue-level dataset into a generic ACTIVITY TYPE taxonomy.
Each activity type = one recommendable "thing to do" (not a specific address).
Each type gets up to 3 real sample venues attached (name + locality only, no
precision lat/long matching) drawn from the merged dataset, when available.

Output columns:
  activity_id, name, category, source_basis, description, indoor_outdoor,
  cost_tier, cost_min_inr, cost_max_inr, group_size_min, group_size_max,
  duration, energy_level, mood_tags,
  sample_venue_1, sample_venue_1_locality,
  sample_venue_2, sample_venue_2_locality,
  sample_venue_3, sample_venue_3_locality
"""
import csv
from collections import defaultdict

rows = list(csv.DictReader(open('unified_activities.csv')))
zomato = [r for r in rows if r['source'] == 'zomato']
osm = [r for r in rows if r['source'] == 'osm']
bored = [r for r in rows if r['source'] == 'bored_api']

OUT_FIELDS = [
    'activity_id', 'name', 'category', 'source_basis', 'description',
    'indoor_outdoor', 'cost_tier', 'cost_min_inr', 'cost_max_inr',
    'group_size_min', 'group_size_max', 'duration', 'energy_level', 'mood_tags',
    'sample_venue_1', 'sample_venue_1_locality',
    'sample_venue_2', 'sample_venue_2_locality',
    'sample_venue_3', 'sample_venue_3_locality',
]

activity_types = []
next_id = 1

def new_id():
    global next_id
    aid = f"AT{next_id:04d}"
    next_id += 1
    return aid

def attach_samples(row, venue_rows):
    picks = venue_rows[:3]
    row['sample_venue_1'] = picks[0]['name'] if len(picks) > 0 else ''
    row['sample_venue_1_locality'] = picks[0]['locality'] if len(picks) > 0 else ''
    row['sample_venue_2'] = picks[1]['name'] if len(picks) > 1 else ''
    row['sample_venue_2_locality'] = picks[1]['locality'] if len(picks) > 1 else ''
    row['sample_venue_3'] = picks[2]['name'] if len(picks) > 2 else ''
    row['sample_venue_3_locality'] = picks[2]['locality'] if len(picks) > 2 else ''
    return row

# ---------- 1. FOOD types, derived from top Zomato cuisines ----------
TOP_CUISINES = ['North Indian', 'Chinese', 'South Indian', 'Biryani', 'Continental',
                 'Mughlai', 'Seafood', 'Italian', 'Andhra', 'Cafe', 'Desserts', 'Street Food']

by_cuisine = defaultdict(list)
for r in zomato:
    cuisines = [c.strip() for c in r['description'].split(',')]
    for c in cuisines:
        if c in TOP_CUISINES:
            by_cuisine[c].append(r)

COST_TIER_ORDER = {'low': 0, 'medium': 1, 'high': 2, 'premium': 3, 'unknown': 1}

for cuisine in TOP_CUISINES:
    venues = by_cuisine.get(cuisine, [])
    if not venues:
        continue
    # cost tier = most common tier among matching venues
    tiers = defaultdict(int)
    for v in venues:
        tiers[v['cost_tier']] += 1
    common_tier = max(tiers.items(), key=lambda x: x[1])[0]
    row = {
        'activity_id': new_id(),
        'name': f"Try {cuisine} food",
        'category': 'food',
        'source_basis': 'zomato_derived',
        'description': f"Eat out at a {cuisine} restaurant or eatery",
        'indoor_outdoor': 'indoor',
        'cost_tier': common_tier,
        'cost_min_inr': '', 'cost_max_inr': '',
        'group_size_min': 1, 'group_size_max': 8,
        'duration': 'hours',
        'energy_level': 'low',
        'mood_tags': '',
    }
    attach_samples(row, venues)
    activity_types.append(row)

# ---------- 2. OSM-derived types (entertainment, wellness, arts_culture, shopping) ----------
OSM_TYPE_LABELS = {
    'cinema': ('Watch a movie', 'entertainment', 'low'),
    'bowling_alley': ('Go bowling', 'entertainment', 'medium'),
    'amusement_arcade': ('Play at an arcade', 'entertainment', 'medium'),
    'escape_game': ('Try an escape room', 'entertainment', 'medium'),
    'museum': ('Visit a museum', 'arts_culture', 'low'),
    'gallery': ('Visit an art gallery', 'arts_culture', 'low'),
    'arts_centre': ('Catch a show at an arts centre', 'arts_culture', 'low'),
    'mall': ('Go shopping at a mall', 'shopping', 'medium'),
    'park': ('Relax at a park', 'outdoor', 'low'),
    'garden': ('Walk through a garden', 'outdoor', 'low'),
}

by_osm_tag = defaultdict(list)
for r in osm:
    tag = r['description']  # raw OSM tag stashed here by merge_pipeline
    by_osm_tag[tag].append(r)

# wellness needs its own grouping since 'sport' values vary (yoga, fitness, gym...)
wellness_venues = [r for r in osm if r['category'] == 'wellness']

for tag, (label, category, energy) in OSM_TYPE_LABELS.items():
    venues = by_osm_tag.get(tag, [])
    if not venues:
        continue
    row = {
        'activity_id': new_id(),
        'name': label,
        'category': category,
        'source_basis': 'osm_derived',
        'description': f"OSM tag: {tag}",
        'indoor_outdoor': 'outdoor' if category == 'outdoor' else 'indoor',
        'cost_tier': 'medium' if category in ('entertainment', 'shopping') else 'low',
        'cost_min_inr': '', 'cost_max_inr': '',
        'group_size_min': 1, 'group_size_max': 8,
        'duration': 'hours',
        'energy_level': energy,
        'mood_tags': '',
    }
    attach_samples(row, venues)
    activity_types.append(row)

if wellness_venues:
    row = {
        'activity_id': new_id(),
        'name': 'Fitness / yoga session',
        'category': 'wellness',
        'source_basis': 'osm_derived',
        'description': 'Gym, yoga studio or fitness centre visit',
        'indoor_outdoor': 'indoor',
        'cost_tier': 'medium',
        'cost_min_inr': '', 'cost_max_inr': '',
        'group_size_min': 1, 'group_size_max': 4,
        'duration': 'hours',
        'energy_level': 'high',
        'mood_tags': '',
    }
    attach_samples(row, wellness_venues)
    activity_types.append(row)

# ---------- 3. Bored API generic types (no real venues, e.g. social/learning/community) ----------
for r in bored:
    row = {
        'activity_id': new_id(),
        'name': r['name'],
        'category': r['category'],
        'source_basis': 'bored_api',
        'description': r['description'] or r['bored_type_raw'],
        'indoor_outdoor': r['indoor_outdoor'],
        'cost_tier': r['cost_tier'],
        'cost_min_inr': r['cost_min_inr'],
        'cost_max_inr': r['cost_max_inr'],
        'group_size_min': r['group_size_min'],
        'group_size_max': r['group_size_max'],
        'duration': r['duration'],
        'energy_level': r['energy_level'],
        'mood_tags': r['mood_tags'],
        'sample_venue_1': '', 'sample_venue_1_locality': '',
        'sample_venue_2': '', 'sample_venue_2_locality': '',
        'sample_venue_3': '', 'sample_venue_3_locality': '',
    }
    activity_types.append(row)

# ---------- write output ----------
with open('activity_types.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=OUT_FIELDS)
    w.writeheader()
    for row in activity_types:
        w.writerow({k: row.get(k, '') for k in OUT_FIELDS})

print(f"Built {len(activity_types)} activity types")
by_cat = defaultdict(int)
by_basis = defaultdict(int)
for row in activity_types:
    by_cat[row['category']] += 1
    by_basis[row['source_basis']] += 1
print("By category:", dict(by_cat))
print("By source basis:", dict(by_basis))
