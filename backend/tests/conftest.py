from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.config import Settings
from app.main import create_app


def make_pdf(pages):
    stream = BytesIO()
    pdf = canvas.Canvas(stream)
    for text in pages:
        cursor = pdf.beginText(40, 780)
        for line in text.splitlines():
            cursor.textLine(line)
        pdf.drawText(cursor)
        pdf.showPage()
    pdf.save()
    return stream.getvalue()


@pytest.fixture
def app(tmp_path):
    settings = Settings(database_url=f'sqlite:///{tmp_path}/test.db', data_dir=tmp_path,
                        ai_mode='excerpt', app_origin='http://testserver')
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client


@pytest.fixture
def signed_in(client):
    response = client.post('/api/auth/register', json={'username': 'student', 'password': 'test-password-123'})
    assert response.status_code == 201
    return client


@pytest.fixture
def uploaded(signed_in):
    raw = make_pdf([
        'Cloud computing uses shared computing resources. Virtualization isolates operating systems.',
        'HDFS stores files as blocks. The default replication factor is three.\nA NameNode manages metadata and DataNodes store block replicas.',
        'A service level agreement defines availability targets. Uptime is measured as a percentage.',
    ])
    result = signed_in.post('/api/documents', files={'file': ('cloud-notes.pdf', raw, 'application/pdf')})
    assert result.status_code == 201, result.text
    return result.json()['document']
