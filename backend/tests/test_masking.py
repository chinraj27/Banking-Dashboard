from app.core.masking import mask_number
from app.core.security import hash_password, verify_password


def test_mask_account_number():
    assert mask_number("50100234567891") == "**** **** ** 7891"


def test_mask_card_number():
    assert mask_number("4539871200123456") == "**** **** **** 3456"


def test_mask_empty():
    assert mask_number(None) is None


def test_password_hash_roundtrip():
    hashed = hash_password("Secret123")
    assert hashed != "Secret123"
    assert verify_password("Secret123", hashed)
    assert not verify_password("wrong", hashed)
