import base64
import io
import json

import pytest
from PIL import Image

from app.main import engine
from test_accounts_openai import users, login
from test_shared_api import configure, respond


def page():
    out = io.BytesIO()
    Image.new('RGB', (100, 100), '#ffdd00').save(out, 'PNG')
    return {'name': 'page.png', 'mime': 'image/png', 'data': base64.b64encode(out.getvalue()).decode()}


REGION = {'id': 'a', 'source': 'Name', 'text': 'Họ tên', 'x': 100, 'y': 100, 'width': 200,
          'height': 50, 'font_size': 40, 'bold': True, 'align': 'left', 'color': '#202020'}


def test_form_route_requires_account(users):
    _, client, _, _ = users
    assert client.post('/api/form-translate', json={'output': 'layout', 'file': page()}).status_code == 401


def test_native_page_image_and_anchor_preserved_with_shared_admin_api(users, monkeypatch):
    store, client, admin, user = users
    login(client)
    configure(client)
    bodies = respond(monkeypatch, {'source_language': 'en', 'regions': [{**REGION, 'x': 104}]})
    login(client, 'user')
    file = page()
    result = client.post('/api/form-translate', json={'source': 'auto', 'target': 'vi', 'output': 'layout', 'file': file, 'hints': [REGION]})
    assert result.status_code == 200, result.text
    assert result.json()['regions'][0]['x'] == REGION['x']
    assert bodies[0]['input'][0]['content'][1]['image_url'].endswith(file['data'])
    assert bodies[0]['text']['format']['schema']['properties']['regions']
    assert store.usage()[0]['input_tokens'] > 0


@pytest.mark.parametrize('regions', [[], [REGION, REGION], [{**REGION, 'width': -1}], [{**REGION, 'text': ''}]])
def test_missing_or_invalid_regions_never_complete(users, monkeypatch, regions):
    _, client, _, _ = users
    login(client)
    configure(client)
    respond(monkeypatch, {'source_language': 'en', 'regions': regions})
    result = client.post('/api/form-translate', json={'output': 'layout', 'file': page(), 'hints': [REGION]})
    assert result.status_code == 422
    assert not engine.lock.locked()


def test_docx_text_ids_must_be_complete_and_unique(users, monkeypatch):
    _, client, _, _ = users
    login(client)
    configure(client)
    request = {'output': 'segments', 'segments': [{'id': '1', 'text': 'Hello ', 'context': 'Hello world.'}, {'id': '2', 'text': 'world.', 'context': 'Hello world.'}]}
    respond(monkeypatch, {'source_language': 'en', 'translations': [{'id': '2', 'text': 'thế giới.'}, {'id': '1', 'text': 'Xin chào '}]})
    result = client.post('/api/form-translate', json=request)
    assert result.status_code == 200, result.text
    respond(monkeypatch, {'source_language': 'en', 'translations': [{'id': '1', 'text': 'Xin chào'}]})
    assert client.post('/api/form-translate', json=request).status_code == 422


def test_invalid_input_is_rejected_before_paid_call(users, monkeypatch):
    _, client, _, _ = users
    login(client)
    monkeypatch.setattr(engine, '_response', lambda *a: pytest.fail('No paid call on invalid data'))
    assert client.post('/api/form-translate', json={'output': 'layout', 'file': page(), 'hints': [{**REGION, 'x': -1}]}).status_code == 422
    assert client.post('/api/form-translate', json={'output': 'segments', 'segments': [{'id': '1', 'text': 'a', 'context': 'a'}, {'id': '1', 'text': 'b', 'context': 'b'}]}).status_code == 422
