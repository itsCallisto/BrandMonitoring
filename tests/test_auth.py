from backend.auth import hash_password, verify_password


def test_password_hash_round_trip() -> None:
    password = "correct horse battery staple"
    stored = hash_password(password)
    assert verify_password(password, stored)
    assert not verify_password("wrong password", stored)
