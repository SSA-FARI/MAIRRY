import secrets

import bcrypt


def create_unusable_demo_password_hash() -> str:
    """Hash a cryptographically random, immediately discarded password for the demo row."""
    random_password = secrets.token_urlsafe(32).encode("utf-8")
    return bcrypt.hashpw(random_password, bcrypt.gensalt()).decode("ascii")
