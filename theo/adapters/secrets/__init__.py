"""Secrets adapters wrapping external backends."""

from .aws import AWSSecretsAdapter
from .vault import VaultSecretsAdapter

__all__ = ["AWSSecretsAdapter", "VaultSecretsAdapter"]
