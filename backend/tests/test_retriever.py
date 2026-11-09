import numpy as np

from app.retriever import QUERY_PREFIX, ResumeIndex, rrf_fuse


def const_embed(texts):
    return np.ones((len(texts), 4)) / 2.0


def test_rrf_fuse_prefers_item_ranked_well_in_both():
    assert rrf_fuse([[0, 1, 2], [1, 2, 0]])[0] == 1  # 1/62+1/61 > 1/61+1/63


def test_rrf_fuse_exact_scores_and_ties():
    # 0 and 2 tie at 1/61+1/62 (beats 1 at 2/63); tie keeps lower index first
    assert rrf_fuse([[2, 0, 1], [0, 2, 1]]) == [0, 2, 1]


def test_rrf_fuse_partial_rankings():
    # item 2 appears only in the second ranking
    assert rrf_fuse([[0], [2, 0, 1]]) == [0, 2, 1]


def test_top_finds_keyword_chunk():
    chunks = ["Graphic design and branding", "Managed PostgreSQL databases", "Team lunches"]
    assert ResumeIndex(chunks, const_embed).top("PostgreSQL", 1) == ["Managed PostgreSQL databases"]


def test_keyword_in_most_chunks_still_ranks_matches_first():
    # "python" appears in 2 of 3 chunks: Okapi IDF would go negative here
    chunks = ["Python scripts", "Cooking", "Python Python services"]
    top2 = ResumeIndex(chunks, const_embed).top("Python", 2)
    assert set(top2) == {"Python scripts", "Python Python services"}


def test_top_uses_embeddings():
    chunks = ["alpha", "beta", "gamma"]

    def embed(texts):
        out = []
        for t in texts:
            if t.startswith(QUERY_PREFIX) or t == "gamma":
                out.append([1.0, 0.0])
            else:
                out.append([0.0, 1.0])
        return np.array(out)

    # BM25 has no overlap for "databases", so the embedding rank decides
    assert ResumeIndex(chunks, embed).top("databases", 1) == ["gamma"]


def test_top_returns_all_when_fewer_than_n():
    assert ResumeIndex(["only one"], const_embed).top("Python", 3) == ["only one"]


def test_embeds_chunks_once():
    calls = []

    def counting(texts):
        calls.append(list(texts))
        return const_embed(texts)

    idx = ResumeIndex(["a b", "c d", "e f"], counting)
    for q in ["x", "y", "z"]:
        idx.top(q)
    assert len(calls) == 4  # 1 for chunks + 3 queries
    assert all(len(c) == 1 for c in calls[1:])
