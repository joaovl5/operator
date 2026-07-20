"""JWT helpers for extracting ChatGPT account identifiers."""

import base64
from collections.abc import Mapping

from pydantic import TypeAdapter, ValidationError

_ACCOUNT_ID_CLAIMS = (
  "chatgpt_account_id",
  "https://auth.openai.com/account_id",
  "https://api.openai.com/auth/account_id",
  "account_id",
)
_JWT_PART_COUNT = 3


def add_base64_padding(value: str) -> str:
  """Add JWT-safe base64 padding when needed."""
  return value + ("=" * (-len(value) % 4))


def decode_jwt_payload(token: str) -> Mapping[str, object] | None:
  """Decode a JWT payload without verifying its signature."""
  parts = token.split(".")
  if len(parts) != _JWT_PART_COUNT:
    return None

  try:
    payload_bytes = base64.urlsafe_b64decode(
      add_base64_padding(parts[1])
    )
    return TypeAdapter(dict[str, object]).validate_json(payload_bytes)
  except ValidationError, ValueError:
    return None


def extract_account_id_from_id_token(
  id_token: str | None,
) -> str | None:
  """Extract the preferred ChatGPT account identifier
  from an ID token."""
  if not id_token:
    return None

  payload = decode_jwt_payload(id_token)
  if not isinstance(payload, Mapping):
    return None

  for claim_name in _ACCOUNT_ID_CLAIMS:
    claim_value = payload.get(claim_name)
    if isinstance(claim_value, str) and claim_value.strip():
      return claim_value

  return None


__all__ = [
  "add_base64_padding",
  "decode_jwt_payload",
  "extract_account_id_from_id_token",
]
