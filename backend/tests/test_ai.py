import json

import pytest
from fastapi.testclient import TestClient

from app.ai import AIUnavailable, Ollama
from app.config import Settings
from app.main import create_app
from app.retrieval import bm25, cosine
from conftest import make_pdf


def test_bm25_ranks_relevant_page_first():
    scores = bm25('replication factor', ['Virtual machines isolate operating systems.', 'The replication factor is three.', 'Replication provides availability.'])
    assert scores[1] > scores[2] > scores[0]
    assert bm25('the and or', ['content']) == [0.0]


def test_cosine():
    assert cosine([1, 0], [1, 0]) == 1
    assert cosine([1, 0], [0, 1]) == 0
    assert cosine([0, 0], [0, 0]) == -1


@pytest.mark.parametrize('paragraphs', [
    [{'text': 'An invented citation.', 'source_ids': [99]}],
    [{'text': 'No citations.', 'source_ids': []}],
    [{'text': 'Boolean is not an ID.', 'source_ids': [True]}],
    [{'text': '', 'source_ids': [1]}],
    ['not a paragraph object'],
])
def test_invalid_ai_citations_are_rejected(monkeypatch, paragraphs):
    ai = Ollama(Settings())
    monkeypatch.setattr(ai, 'post', lambda *_: {'message': {'content': json.dumps({'insufficient_evidence': False, 'paragraphs': paragraphs})}})
    with pytest.raises(AIUnavailable):
        ai.answer('Question?', [{'id': 1, 'text': 'Evidence.'}])


def test_embedding_dimension_validation(monkeypatch):
    ai = Ollama(Settings(embed_dim=3))
    monkeypatch.setattr(ai, 'post', lambda *_: {'embeddings': [[1, 2]]})
    with pytest.raises(AIUnavailable):
        ai.embed(['test'])


def test_ollama_contract_and_fallback(tmp_path, monkeypatch):
    settings = Settings(database_url=f'sqlite:///{tmp_path}/ai.db', data_dir=tmp_path, ai_mode='ollama', embed_dim=3)
    app = create_app(settings)
    requests = []
    def provider(path, payload):
        requests.append((path, payload))
        if path == '/api/embed':
            return {'embeddings': [[1, 0, 0] for _ in payload['input']]}
        return {'message': {'content': json.dumps({'insufficient_evidence': False, 'paragraphs': [{'text': 'HDFS replicates blocks three times.', 'source_ids': [1]}]})}}
    monkeypatch.setattr(app.state.ai, 'post', provider)
    with TestClient(app) as client:
        client.post('/api/auth/register', json={'username': 'localai', 'password': 'strong-password'})
        doc = client.post('/api/documents', files={'file': ('notes.pdf', make_pdf(['HDFS replication factor is three.']))}).json()['document']
        assert doc['indexed_model'] == settings.embed_model
        result = client.post('/api/ask', json={'question': 'How many copies of each block?'}).json()['result']
        assert result['mode'] == 'ai'
        assert result['paragraphs'][0]['source_ids'] == [1]
        chat = next(payload for path, payload in requests if path == '/api/chat')
        assert chat['stream'] is False
        assert chat['format']['type'] == 'object'
        assert 'untrusted' in chat['messages'][0]['content']
        def unavailable(*args, **kwargs):
            raise AIUnavailable('Ollama is offline.')
        monkeypatch.setattr(app.state.ai, 'post', unavailable)
        fallback = client.post('/api/ask', json={'question': 'HDFS replication factor?'}).json()['result']
        assert fallback['mode'] == 'excerpt'
        assert fallback['warning']
        assert fallback['sources'][0]['page'] == 1
        assert client.post(f"/api/documents/{doc['id']}/reindex").status_code == 503


def test_long_pages_chunk_with_overlap_without_crossing_pages():
    from app.pdf import extract_chunks
    text = ' '.join(f'word{i}' for i in range(500))
    pages, chunks = extract_chunks(make_pdf([text, 'second page']), 200, 1500)
    assert pages == 2
    first = [content for page, content in chunks if page == 1]
    assert len(first) == 3
    assert 'word190' in first[0] and 'word190' in first[1]
    assert chunks[-1] == (2, 'second page')
