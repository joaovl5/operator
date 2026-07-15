from collections.abc import Sequence

import sqlalchemy as sa
from advanced_alchemy.types import (
  GUID,
  ORA_JSONB,
  Bool,
  DateTimeUTC,
  EncryptedString,
  EncryptedText,
  FernetBackend,
  JsonB,
  OneTimeCode,
  PasswordHash,
  StoredObject,
  TOTPSecret,
)
from advanced_alchemy.types.encrypted_string import PGCryptoBackend
from advanced_alchemy.types.password_hash.argon2 import Argon2Hasher
from advanced_alchemy.types.password_hash.passlib import PasslibHasher
from advanced_alchemy.types.password_hash.pwdlib import PwdlibHasher

from operator_db.objects.utils import PydanticJSON

sa.GUID = GUID
sa.Bool = Bool
sa.DateTimeUTC = DateTimeUTC
sa.JsonB = JsonB
sa.ORA_JSONB = ORA_JSONB
sa.EncryptedString = EncryptedString
sa.EncryptedText = EncryptedText
sa.StoredObject = StoredObject
sa.PasswordHash = PasswordHash
sa.Argon2Hasher = Argon2Hasher
sa.PasslibHasher = PasslibHasher
sa.PwdlibHasher = PwdlibHasher
sa.FernetBackend = FernetBackend
sa.PGCryptoBackend = PGCryptoBackend
sa.TOTPSecret = TOTPSecret
sa.OneTimeCode = OneTimeCode
sa.PydanticJSON = PydanticJSON

type AlembicRev = str | Sequence[str] | None

__all__ = (
  "AlembicRev",
  "sa",
)
