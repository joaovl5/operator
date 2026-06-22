"""Builds an Advanced Alchemy config for usage in its CLI."""

from operator_db_at2.connection.alchemy import build_alchemy_config
from operator_shared.settings.loader import load_operator_settings

op_cfg = load_operator_settings()

config = build_alchemy_config(op_cfg)
