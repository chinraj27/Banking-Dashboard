def test_dashboard_stats(client, demo_headers):
    r = client.get("/api/dashboard/stats", headers=demo_headers)
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["total_products"] == 9
    assert d["active_products"] == 6
    assert d["total_balance"] == 173630.50  # two active savings accounts
    assert len(d["cashflow"]) == 6


def test_submit_application_updates_stats(client, demo_headers):
    before = client.get("/api/dashboard/stats", headers=demo_headers).json()["data"]["pending_applications"]
    r = client.post(
        "/api/applications",
        json={"category": "credit_card", "product_name": "Cashback Card", "requested_amount": 150000},
        headers=demo_headers,
    )
    assert r.status_code == 201
    assert r.json()["data"]["status"] == "pending"
    after = client.get("/api/dashboard/stats", headers=demo_headers).json()["data"]["pending_applications"]
    assert after == before + 1  # cache was invalidated
    names = [a["product_name"] for a in client.get("/api/applications", headers=demo_headers).json()["data"]]
    assert "Cashback Card" in names


def test_application_validation(client, demo_headers):
    bad = {"category": "mortgage", "product_name": "X"}
    assert client.post("/api/applications", json=bad, headers=demo_headers).status_code == 422
    neg = {"category": "loan", "product_name": "Loan", "requested_amount": -5}
    assert client.post("/api/applications", json=neg, headers=demo_headers).status_code == 422


def test_activity_log_recorded_in_mongo_store(client, demo_headers):
    r = client.get("/api/activity", headers=demo_headers)
    actions = {row["action"] for row in r.json()["data"]}
    assert "login" in actions


def test_admin_endpoint_rbac(client, demo_headers, admin_headers):
    assert client.get("/api/admin/users", headers=demo_headers).status_code == 403
    r = client.get("/api/admin/users", headers=admin_headers)
    assert r.status_code == 200
    emails = [u["email"] for u in r.json()["data"]]
    assert "admin@bank.com" in emails
    assert "hashed_password" not in r.text
