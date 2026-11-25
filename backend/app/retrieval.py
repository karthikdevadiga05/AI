"""Small-corpus BM25 + vector retrieval with reciprocal rank fusion."""
import math
import re
from collections import Counter

from sqlalchemy import select

from .db import Chunk, Document

STOPWORDS = set('a an the and or of to in for is are was were be been on at by with from this that it as how what why when where which who explain describe compare between does do can could would should about tell me please document documents according'.split())


def tokens(text):
    return [t for t in re.findall(r'\b\w+\b', text.lower()) if t not in STOPWORDS and len(t) > 1]


def bm25(query, texts):
    terms = set(tokens(query))
    corpus = [Counter(tokens(t)) for t in texts]
    if not corpus or not terms:
        return [0.0] * len(texts)
    lengths = [sum(c.values()) for c in corpus]
    average = sum(lengths) / len(corpus) or 1
    df = Counter(t for c in corpus for t in c)
    scores = []
    for counts, length in zip(corpus, lengths):
        score = 0
        for term in terms:
            tf = counts[term]
            idf = math.log(1 + (len(corpus) - df[term] + .5) / (df[term] + .5))
            score += idf * tf * 2.5 / (tf + 1.5 * (.25 + .75 * length / average))
        scores.append(score)
    return scores


def cosine(a, b):
    if len(a) != len(b):
        return -1
    denominator = math.sqrt(sum(x*x for x in a) * sum(x*x for x in b))
    return sum(x*y for x, y in zip(a, b)) / denominator if denominator else -1


def retrieve(db, user_id, question, document_ids, query_vector=None, model=None, compare=False):
    query = select(Chunk, Document).join(Document).where(Document.user_id == user_id)
    if document_ids:
        query = query.where(Document.id.in_(document_ids))
    rows = list(db.execute(query))
    lexical = bm25(question, [c.content for c, _ in rows])
    lexical_order = sorted([i for i, score in enumerate(lexical) if score > 0], key=lambda i: lexical[i], reverse=True)
    semantic = {}
    if query_vector is not None:
        if db.bind.dialect.name == 'postgresql':
            # Native pgvector cosine distance; owner and document scope apply before ranking.
            distance = Chunk.embedding.cosine_distance(query_vector)
            vector_query = select(Chunk.id, distance).join(Document).where(
                Document.user_id == user_id, Document.indexed_model == model,
                Chunk.embedding.is_not(None),
            )
            if document_ids:
                vector_query = vector_query.where(Document.id.in_(document_ids))
            # Fetch enough candidates per comparison scope; exact search is deliberate for small corpora.
            distances = dict(db.execute(vector_query.order_by(distance).limit(200)).all())
            semantic = {i: 1 - distances[c.id] for i, (c, _) in enumerate(rows) if c.id in distances}
        else:
            semantic = {i: cosine(query_vector, c.embedding) for i, (c, d) in enumerate(rows)
                        if c.embedding is not None and d.indexed_model == model}
    semantic_order = sorted([i for i, value in semantic.items() if value >= .4], key=lambda i: semantic[i], reverse=True)
    fusion = Counter()
    for ranked in (lexical_order, semantic_order):
        for rank, i in enumerate(ranked, 1):
            fusion[i] += 1 / (60 + rank)
    order = sorted(fusion, key=lambda i: fusion[i], reverse=True)
    if compare:
        # Reserve evidence for each selected document rather than allowing one to dominate.
        chosen = []
        for document_id in document_ids:
            chosen.extend([i for i in order if rows[i][1].id == document_id][:2])
    else:
        chosen = order[:6]
    return [{'id': position, 'document_id': rows[i][1].id, 'document_name': rows[i][1].name,
             'page': rows[i][0].page, 'text': rows[i][0].content,
             'score': round(fusion[i], 5)} for position, i in enumerate(chosen, 1)]
