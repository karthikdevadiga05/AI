"""Reproducible, tiny retrieval smoke benchmark. Not a general accuracy claim."""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app

CASES = [
    ('distributed-systems-notes.pdf', 'What is the HDFS replication factor?', 2),
    ('distributed-systems-notes.pdf', 'What is the monthly downtime budget?', 3),
    ('distributed-systems-notes.pdf', 'How are missing heartbeats detected during recovery?', 4),
    ('distributed-systems-notes.pdf', 'What are independent computers in a distributed system?', 1),
    ('gfs-architecture-notes.pdf', 'How does the primary replica order writes?', 2),
    ('gfs-architecture-notes.pdf', 'Which server manages filesystem metadata?', 1),
]


def main():
    results = []
    with tempfile.TemporaryDirectory() as directory:
        settings = Settings(database_url=f'sqlite:///{directory}/eval.db', data_dir=Path(directory), ai_mode='excerpt')
        with TestClient(create_app(settings)) as client:
            client.post('/api/auth/register', json={'username': 'evaluation', 'password': 'evaluation-only-password'})
            ids = {}
            for name in sorted({name for name, _, _ in CASES}):
                response = client.post('/api/documents', files={'file': (name, (ROOT / 'samples' / name).read_bytes())})
                response.raise_for_status()
                ids[name] = response.json()['document']['id']
            for name, question, expected in CASES:
                response = client.post('/api/ask', json={'question': question, 'document_ids': [ids[name]]})
                response.raise_for_status()
                pages = [s['page'] for s in response.json()['result']['sources']]
                rank = pages.index(expected) + 1 if expected in pages else None
                results.append({'question': question, 'document': name, 'expected_page': expected, 'retrieved_pages': pages,
                                'hit_at_1': rank == 1, 'hit_at_3': rank is not None and rank <= 3, 'reciprocal_rank': 1 / rank if rank else 0})
            no_evidence = client.post('/api/ask', json={'question': 'Who won Wimbledon?'}).json()['result']['insufficient_evidence']
    report = {'benchmark': 'Six synthetic questions over two original demo PDFs',
              'limitations': 'Small deterministic smoke benchmark. Does not measure AI answer correctness, real-world accuracy, or performance at scale.',
              'mode': 'excerpt', 'cases': len(results),
              'hit_at_1': sum(r['hit_at_1'] for r in results) / len(results),
              'hit_at_3': sum(r['hit_at_3'] for r in results) / len(results),
              'mrr': sum(r['reciprocal_rank'] for r in results) / len(results),
              'unrelated_question_abstained': no_evidence, 'results': results}
    output = ROOT / 'docs' / 'evaluation.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'results'}, indent=2))


if __name__ == '__main__':
    main()
