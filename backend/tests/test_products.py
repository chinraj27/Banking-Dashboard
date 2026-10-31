def test_list_all_products(client, demo_headers):
    r = client.get("/api/products", headers=demo_headers)
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 9
    assert {p["category"] for p in data} == {"savings", "credit_card", "loan", "investment"}


def test_numbers_are_masked(client, demo_headers):
    data = client.get("/api/products", headers=demo_headers).json()["data"]
    raw = "50100234567891", "4539871200123456"
    assert not any(n in str(data) for n in raw)
    savings = next(p for p in data if p["name"] == "Premier Savings Account")
    assert savings["details"]["account_number"].endswith("7891")
    assert "*" in savings["masked_number"]


def test_filter_by_category(client, demo_headers):
    r = client.get("/api/products", params={"category": "loan"}, headers=demo_headers)
    assert {p["category"] for p in r.json()["data"]} == {"loan"}
    r2 = client.get("/api/products/category/credit_card", headers=demo_headers)
    assert len(r2.json()["data"]) == 2


def test_filter_by_status(client, demo_headers):
    r = client.get("/api/products", params={"status": "pending"}, headers=demo_headers)
    data = r.json()["data"]
    assert len(data) == 1 and data[0]["name"] == "Travel Elite Card"


def test_search_by_name(client, demo_headers):
    r = client.get("/api/products", params={"search": "savings"}, headers=demo_headers)
    names = [p["name"] for p in r.json()["data"]]
    assert "Premier Savings Account" in names and "Student Savings Account" in names
    assert "Platinum Rewards Card" not in names


def test_search_is_safe_against_sql_injection(client, demo_headers):
    r = client.get("/api/products", params={"search": "x' OR '1'='1"}, headers=demo_headers)
    assert r.status_code == 200
    assert r.json()["data"] == []


def test_sort_by_balance(client, demo_headers):
    r = client.get("/api/products", params={"sort_by": "balance", "order": "desc"}, headers=demo_headers)
    balances = [p["balance"] for p in r.json()["data"]]
    assert balances == sorted(balances, reverse=True)


def test_invalid_query_values_are_rejected(client, demo_headers):
    assert client.get("/api/products", params={"category": "crypto"}, headers=demo_headers).status_code == 422
    assert client.get("/api/products", params={"sort_by": "colour"}, headers=demo_headers).status_code == 422


def test_product_detail_includes_metadata(client, demo_headers):
    products = client.get("/api/products", params={"category": "investment"}, headers=demo_headers).json()["data"]
    pid = next(p["id"] for p in products if p["name"] == "Balanced Growth Portfolio")
    r = client.get(f"/api/products/{pid}", headers=demo_headers)
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["details"]["returns_percent"] == 14.17
    assert body["metadata"]["risk_level"] == "Moderate"


def test_product_not_found(client, demo_headers):
    assert client.get("/api/products/99999", headers=demo_headers).status_code == 404


def test_customers_cannot_see_each_others_products(client, demo_headers):
    client.post(
        "/api/auth/register",
        json={"email": "other@example.com", "full_name": "Other Person", "password": "Passw0rdOK"},
    )
    other = {
        "Authorization": "Bearer "
        + client.post("/api/auth/login", json={"email": "other@example.com", "password": "Passw0rdOK"}).json()[
            "data"
        ]["access_token"]
    }
    assert client.get("/api/products", headers=other).json()["data"] == []
    pid = client.get("/api/products", headers=demo_headers).json()["data"][0]["id"]
    assert client.get(f"/api/products/{pid}", headers=other).status_code == 404


def test_transactions(client, demo_headers):
    r = client.get("/api/transactions", params={"limit": 5}, headers=demo_headers)
    rows = r.json()["data"]
    assert r.status_code == 200 and 0 < len(rows) <= 5
    dates = [x["created_at"] for x in rows]
    assert dates == sorted(dates, reverse=True)
    credits = client.get("/api/transactions", params={"txn_type": "credit"}, headers=demo_headers).json()["data"]
    assert credits and all(t["txn_type"] == "credit" for t in credits)


def test_transactions_limit_validation(client, demo_headers):
    assert client.get("/api/transactions", params={"limit": 1000}, headers=demo_headers).status_code == 422
