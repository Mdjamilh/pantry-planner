from pantry_planner.security import hash_password, verify_password


def test_hash_and_verify() -> None:
    h = hash_password("correct horse battery")
    assert h.startswith("$argon2id$")
    assert verify_password(h, "correct horse battery")
    assert not verify_password(h, "wrong")


def test_garbage_hash_is_rejected_not_raised() -> None:
    assert not verify_password("not-a-hash", "anything")
