import re

from app.domains.auth.passwords import create_unusable_demo_password_hash

BCRYPT_HASH_PATTERN = re.compile(r"^\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}$")


def test_unusable_demo_password_is_stored_only_as_bcrypt_hash() -> None:
    first_hash = create_unusable_demo_password_hash()
    second_hash = create_unusable_demo_password_hash()

    assert BCRYPT_HASH_PATTERN.fullmatch(first_hash)
    assert BCRYPT_HASH_PATTERN.fullmatch(second_hash)
    assert first_hash != second_hash
