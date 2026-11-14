import pytest
from app import accounts


@pytest.fixture(autouse=True)
def isolated_account_database(tmp_path, monkeypatch):
    # Tests never use deployment credentials or make a paid provider request.
    database = accounts.Store(tmp_path / 'isolated.sqlite')
    database.init()
    monkeypatch.setattr(accounts, 'store', database)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
