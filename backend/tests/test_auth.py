from tests.conftest import login


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_register_and_login(client):
    r = client.post(
        "/api/auth/register",
        json={"email": "New.User@Example.com", "full_name": "New User", "password": "Passw0rdOK"},
    )
    assert r.status_code == 201
    assert r.json()["data"]["email"] == "new.user@example.com"
    assert "hashed_password" not in r.text

    headers = login(client, "new.user@example.com", "Passw0rdOK")
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["data"]["role"] == "customer"


def test_register_duplicate_email(client):
    body = {"email": "demo@bank.com", "full_name": "Dup User", "password": "Passw0rdOK"}
    r = client.post("/api/auth/register", json=body)
    assert r.status_code == 409
    assert r.json()["success"] is False


def test_register_weak_password_is_rejected_without_echo(client):
    r = client.post(
        "/api/auth/register",
        json={"email": "weak@example.com", "full_name": "Weak", "password": "onlyletters"},
    )
    assert r.status_code == 422
    assert "onlyletters" not in r.text


def test_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"email": "demo@bank.com", "password": "Nope1234"})
    assert r.status_code == 401
    assert r.json()["error"]["message"] == "Incorrect email or password"


def test_login_unknown_user_same_error(client):
    r = client.post("/api/auth/login", json={"email": "ghost@example.com", "password": "Nope1234"})
    assert r.status_code == 401
    assert r.json()["error"]["message"] == "Incorrect email or password"


def test_protected_route_requires_token(client):
    assert client.get("/api/products").status_code == 401
    assert client.get("/api/products", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_logout_revokes_session(client):
    headers = login(client, "demo@bank.com", "Demo@1234")
    assert client.get("/api/auth/me", headers=headers).status_code == 200
    assert client.post("/api/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/auth/me", headers=headers).status_code == 401
