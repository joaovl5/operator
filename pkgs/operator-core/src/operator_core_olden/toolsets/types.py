from typing import Literal

from operator_shared.forms import BaseForm


class ToolSuccess(BaseForm):
  success: Literal[True] = True


class ToolError(BaseForm):
  error_code: str
  error_detail: str
