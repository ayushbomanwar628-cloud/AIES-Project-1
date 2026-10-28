"""
Unified activity-dataset merge pipeline for the Bangalore hangout recommender.

Combines three sources into ONE table with a shared schema:
  1. Bored API       -> generic activity taxonomy (already processed, no venues)
  2. Zomato Bangalore -> real food/cafe/bar venues
  3. OSM Overpass     -> real parks/entertainment/culture/shopping venues

Run each loader independently as its input file becomes available.
Missing inputs are skipped with a warning, not a crash.
"""
import json, csv, os

UNIFIED_FIELDS = [
    'source', 'source_id', 'name', 'category', 'bored_type_raw',
    'description', 'indoor_outdoor', 'cost_tier', 'cost_min_inr', 'cost_max_inr',
    'group_size_min', 'group_size_max', 'duration', 'energy_level', 'mood_tags',
    'kid_friendly', 'locality', 'latitude', 'longitude', 'venue_name', 'link',
]

def load_bored(path='/home/claude/work/bored_activities_extended.csv'):
    if not os.path.exists(path):
        print(f"[skip] Bored API extended file not found at {path}")
        return []
    with open(path, encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    print(f"[ok] Loaded {len(rows)} Bored API taxonomy rows")
    return rows

def cost_for_two_to_tier(cost):
    """Zomato 'pricing_for_2' (INR) -> our cost_tier bands."""
    try:
        cost = float(cost)
    except (TypeError, ValueError):
        return 'unknown', None, None
    if cost <= 300:
        return 'low', 0, 300
    elif cost <= 800:
        return 'medium', 300, 800
    elif cost <= 1500:
        return 'high', 800, 1500
    else:
        return 'premium', 1500, None

def load_zomato(path):
    """
    Matches the actual uploaded header:
    Restaurant_Name, Category, Pricing_for_2, Locality, Dining_Rating,
    Dining_Review_Count, Delivery_Rating, Delivery_Rating_Count, Website,
    Address, Phone_No, Latitude, Longitude
    """
    if not path or not os.path.exists(path):
        print(f"[skip] Zomato file not found at {path}")
        return []
    rows = []
    skipped_blank = 0
    with open(path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            name = (r.get('Restaurant_Name') or '').strip()
            if not name:
                skipped_blank += 1
                continue
            cost = r.get('Pricing_for_2')
            tier, cmin, cmax = cost_for_two_to_tier(cost)
            rows.append({
                'source': 'zomato',
                'source_id': r.get('Website') or name,
                'name': name,
                'category': 'food',
                'bored_type_raw': '',
                'description': r.get('Category', ''),  # cuisine list, e.g. "Asian, Burmese, ..."
                'indoor_outdoor': 'indoor',
                'cost_tier': tier,
                'cost_min_inr': cmin,
                'cost_max_inr': cmax,
                'group_size_min': 1,
                'group_size_max': 8,
                'duration': 'hours',
                'energy_level': 'low',
                'mood_tags': '',
                'kid_friendly': '',
                'locality': (r.get('Locality') or '').strip(),
                'latitude': r.get('Latitude', ''),
                'longitude': r.get('Longitude', ''),
                'venue_name': name,
                'link': r.get('Website') or '',
            })
    print(f"[ok] Loaded {len(rows)} Zomato rows from {path} (skipped {skipped_blank} blank rows)")
    return rows

# Rough OSM tag -> our category mapping (value -> category)
OSM_LEISURE_MAP = {
    'park': 'outdoor', 'garden': 'outdoor', 'nature_reserve': 'outdoor',
    'bowling_alley': 'entertainment', 'amusement_arcade': 'entertainment',
    'escape_game': 'entertainment', 'sports_centre': 'wellness',
    'fitness_centre': 'wellness',
}
OSM_AMENITY_MAP = {
    'cinema': 'entertainment', 'arts_centre': 'arts_culture',
}
OSM_TOURISM_MAP = {
    'museum': 'arts_culture', 'gallery': 'arts_culture', 'attraction': 'entertainment',
}
OSM_SHOP_MAP = {
    'mall': 'shopping', 'marketplace': 'shopping', 'clothes': 'shopping',
    'video_games': 'shopping',
}
# 'sport' tag is often multi-valued e.g. "fitness;yoga;gymnastics" -> treat any match as wellness
OSM_WELLNESS_SPORT_KEYWORDS = ['yoga', 'fitness', 'gym', 'climbing', 'zumba', 'boxing', 'gymnastics']

def classify_osm(props):
    if 'leisure' in props and props['leisure'] in OSM_LEISURE_MAP:
        return OSM_LEISURE_MAP[props['leisure']], props['leisure']
    if 'amenity' in props and props['amenity'] in OSM_AMENITY_MAP:
        return OSM_AMENITY_MAP[props['amenity']], props['amenity']
    if 'tourism' in props and props['tourism'] in OSM_TOURISM_MAP:
        return OSM_TOURISM_MAP[props['tourism']], props['tourism']
    if 'shop' in props and props['shop'] in OSM_SHOP_MAP:
        return OSM_SHOP_MAP[props['shop']], props['shop']
    if 'sport' in props:
        sport = props['sport'].lower()
        if any(k in sport for k in OSM_WELLNESS_SPORT_KEYWORDS):
            return 'wellness', props['sport']
    # fallback: whatever raw tag exists
    for k in ('leisure', 'amenity', 'tourism', 'shop', 'sport'):
        if k in props:
            return 'misc', props[k]
    return 'misc', 'unknown'

def load_osm(path):
    """
    Expects Overpass Turbo GeoJSON export. Confirmed shape:
    feature['id'], feature['geometry']['coordinates'] = [lon, lat],
    feature['properties'] carries tags like leisure/amenity/tourism/shop/sport + 'name'.
    """
    if not path or not os.path.exists(path):
        print(f"[skip] OSM file not found at {path}")
        return []
    with open(path, encoding='utf-8') as f:
        geo = json.load(f)
    rows = []
    skipped_unnamed = 0
    for feat in geo.get('features', []):
        props = feat.get('properties', {})
        name = props.get('name')
        if not name:
            skipped_unnamed += 1
            continue  # skip unnamed nodes, not useful for recommendations
        category, tag_value = classify_osm(props)
        coords = feat.get('geometry', {}).get('coordinates', [None, None])
        rows.append({
            'source': 'osm',
            'source_id': feat.get('id', name),
            'name': name,
            'category': category,
            'bored_type_raw': '',
            'description': tag_value,
            'indoor_outdoor': 'outdoor' if category == 'outdoor' else 'indoor',
            'cost_tier': 'unknown',
            'cost_min_inr': '',
            'cost_max_inr': '',
            'group_size_min': 1,
            'group_size_max': 8,
            'duration': 'hours',
            'energy_level': '',
            'mood_tags': '',
            'kid_friendly': '',
            'locality': props.get('addr:street', ''),
            'latitude': coords[1] if len(coords) > 1 else '',
            'longitude': coords[0] if len(coords) > 0 else '',
            'venue_name': name,
            'link': '',
        })
    print(f"[ok] Loaded {len(rows)} OSM rows from {path} (skipped {skipped_unnamed} unnamed nodes)")
    return rows

def merge(zomato_path=None, osm_path=None, out_path='/home/claude/work/unified_activities.csv'):
    all_rows = []
    all_rows += load_bored()
    all_rows += load_zomato(zomato_path)
    all_rows += load_osm(osm_path)

    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=UNIFIED_FIELDS)
        w.writeheader()
        for r in all_rows:
            w.writerow({k: r.get(k, '') for k in UNIFIED_FIELDS})

    print(f"\n[done] Merged {len(all_rows)} total rows -> {out_path}")
    by_source = {}
    for r in all_rows:
        by_source[r['source']] = by_source.get(r['source'], 0) + 1
    print("Breakdown by source:", by_source)

if __name__ == '__main__':
    # Update these paths once you've downloaded the files and uploaded them to this chat
    merge(
        zomato_path='/mnt/user-data/uploads/1790324423773_Bangalore_Restaurants.csv',
        osm_path='/mnt/user-data/uploads/export.geojson',
    )
