import pytest

from operator_shared.forms import BaseForm


class SampleForm(BaseForm):
    value: str


def test_base_form_to_markdown_stays_explicitly_unimplemented() -> None:
    """The markdown WIP stays safe by failing explicitly instead of partially rendering."""
    form = SampleForm(value="hello")

    with pytest.raises(NotImplementedError, match="to_markdown"):
        _ = form.to_markdown()
