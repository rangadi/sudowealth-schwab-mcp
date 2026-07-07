from __future__ import annotations

import pytest

from schwab_mcp.manual_login import _extract_code


@pytest.mark.parametrize(
    "pasted",
    [
        "https://host.example/callback?code=ABC%40&session=xyz",
        "https://host.example/callback?session=xyz&code=ABC%40",
        "?code=ABC%40&session=xyz",
        "code=ABC%40",
        "ABC@",
    ],
)
def test_extract_code_variants(pasted):
    # '%40' decodes to '@', which Schwab appends to authorization codes.
    assert _extract_code(pasted) == "ABC@"
