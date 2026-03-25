"""Shared typing helpers for Operator settings."""

from collections.abc import Mapping
from os import PathLike

type OperatorSettingsPath = str | PathLike[str]
type OperatorSettingsSource = Mapping[str, object]
