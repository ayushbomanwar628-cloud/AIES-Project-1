"""
Loads the tagged activity dataset and builds TF-IDF embeddings for semantic
matching between a user's mood/interest text and activity descriptions.

TF-IDF is used as the baseline embedding method (matches the project synopsis).
To upgrade to real sentence embeddings later, swap TfidfVectorizer +
cosine_similarity for a sentence-transformers model (e.g. 'all-MiniLM-L6-v2')
- the rest of the pipeline (filters.py, single_user.py, group.py) doesn't need
to change, since they only depend on getting a similarity score per activity.
"""
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import os
DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         '..', 'data', 'activity_types_tagged.csv')

COST_TIER_RANK = {'free': 0, 'low': 1, 'medium': 2, 'high': 3, 'premium': 4, 'unknown': 2}


def load_activities(recommendable_only=True):
    df = pd.read_csv(DATA_PATH)
    df['mood_tags'] = df['mood_tags'].fillna('')
    df['description'] = df['description'].fillna('')
    if recommendable_only:
        df = df[df['recommendable'] == True].reset_index(drop=True)
    df['cost_rank'] = df['cost_tier'].map(COST_TIER_RANK).fillna(2).astype(int)
    return df


def build_text_corpus(df):
    """Combine fields into one text blob per activity for TF-IDF fitting."""
    return (
        df['name'] + ' ' +
        df['category'] + ' ' +
        df['description'] + ' ' +
        df['mood_tags'].str.replace(',', ' ') + ' ' +
        df['energy_level']
    ).tolist()


class ActivityIndex:
    """Fits TF-IDF once over the activity pool; scores any query text against it."""

    def __init__(self, df):
        self.df = df
        corpus = build_text_corpus(df)
        self.vectorizer = TfidfVectorizer(stop_words='english')
        self.matrix = self.vectorizer.fit_transform(corpus)

    def score(self, query_text):
        """Returns a similarity score (0-1ish) for every row in self.df, in order."""
        query_vec = self.vectorizer.transform([query_text])
        sims = cosine_similarity(query_vec, self.matrix).flatten()
        return sims


if __name__ == '__main__':
    df = load_activities()
    print(f"Loaded {len(df)} recommendable activities")
    index = ActivityIndex(df)
    scores = index.score("relaxed quiet evening reflective")
    top5 = scores.argsort()[::-1][:5]
    print("\nTop 5 matches for 'relaxed quiet evening reflective':")
    for i in top5:
        print(f"  {df.iloc[i]['name']} (score={scores[i]:.3f}, mood_tags={df.iloc[i]['mood_tags']})")
