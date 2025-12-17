"""
Utilities for handling secret values.

Provides functions to safely convert Pydantic SecretStr to plain strings.
"""

from pydantic import SecretStr


def secret_to_str(secret: SecretStr | None) -> str | None:
    """
    Convert Pydantic SecretStr to plain string.

    Args:
        secret: SecretStr instance or None

    Returns:
        str | None: Plain string value or None if input is None

    Example:
        >>> api_key = SecretStr("sk-1234567890")
        >>> secret_to_str(api_key)
        'sk-1234567890'
        >>> secret_to_str(None)
        None
    """
    if secret is None:
        return None

    return secret.get_secret_value()
