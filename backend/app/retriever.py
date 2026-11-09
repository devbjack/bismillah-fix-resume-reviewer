import re
from typing import Callable

import numpy as np
from rank_bm25 import BM25Plus

Embed = Callable[[list[str]], np.ndarray]  # rows L2-normalized
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


def _tokens(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def rrf_fuse(rankings: list[list[int]], k: int = 60) -> list[int]:
    """Reciprocal Rank Fusion; each ranking lists item indices best-first (rank 1 = first)."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(sorted(scores), key=lambda i: -scores[i])  # ties keep the lower index first


class ResumeIndex:
    def __init__(self, chunks: list[str], embed: Embed):
        self.chunks = chunks
        self.embed = embed
        self.chunk_tokens = [set(_tokens(c)) for c in chunks]
        self.bm25 = BM25Plus([_tokens(c) for c in chunks])
        self.vectors = embed(chunks)

    def top(self, requirement: str, n: int = 3) -> list[str]:
        query = _tokens(requirement)
        bm25_scores = self.bm25.get_scores(query)
        # only chunks that share a word with the requirement get a BM25 rank
        matching = [i for i, toks in enumerate(self.chunk_tokens) if toks.intersection(query)]
        bm25_rank = sorted(matching, key=lambda i: -bm25_scores[i])
        q = self.embed([QUERY_PREFIX + requirement])[0]
        sims = self.vectors @ q
        emb_rank = sorted(range(len(self.chunks)), key=lambda i: -sims[i])
        return [self.chunks[i] for i in rrf_fuse([bm25_rank, emb_rank])[:n]]
