"""
Storing a password without being able to read it back.

Argon2id, which is what the Password Hashing Competition settled on and what
OWASP recommends today. The library picks the cost parameters and keeps them
inside the hash, so a stored hash stays verifiable after the cost is raised.

Nothing here ever logs, returns or compares a password in the clear.
"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()

# A floor, and no composition rules. Demanding a capital, a digit and a symbol
# pushes people to "Senha123!" — predictable, and shorter in practice than what
# they would have chosen on their own. Length is what buys resistance.
MIN_LENGTH = 10


def too_short(password: str) -> bool:
    return len(password) < MIN_LENGTH


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def matches(stored: str, password: str) -> bool:
    """
    Whether the password matches. A stored hash that is corrupt or was written
    by some other scheme answers False rather than raising: the caller is a
    login attempt, and there is nothing it could do differently.
    """
    try:
        return _hasher.verify(stored, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def stale(stored: str) -> bool:
    """
    Whether this hash was made with weaker parameters than today's. The hash
    carries its own cost, so raising the cost is answered on the next login
    rather than by asking everyone to change their password.
    """
    try:
        return _hasher.check_needs_rehash(stored)
    except InvalidHashError:
        return True
