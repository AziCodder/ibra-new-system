from app.core.security import hash_password, verify_password


def test_hash_and_verify_correct_password():
    hashed = hash_password("my_secret_123")
    assert verify_password("my_secret_123", hashed)


def test_wrong_password_rejected():
    hashed = hash_password("correct_password")
    assert not verify_password("wrong_password", hashed)


def test_different_hashes_for_same_password():
    h1 = hash_password("same_pass")
    h2 = hash_password("same_pass")
    assert h1 != h2
