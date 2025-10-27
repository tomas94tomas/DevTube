import app.main as main

def test_healthz_status_code():
    client = main.app.test_client()
    r = client.get("/healthz")
    assert r.status_code == 200
    assert b"OK" in r.data

def test_index_page_loads():
    client = main.app.test_client()
    r = client.get("/")
    assert r.status_code == 200
