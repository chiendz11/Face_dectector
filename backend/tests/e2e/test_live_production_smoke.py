import pytest


pytestmark = pytest.mark.e2e


def test_live_production_read_only_admin_list(live_api) -> None:
    payload = live_api.list_employees()

    assert "items" in payload
    assert "total" in payload
    assert isinstance(payload["items"], list)
    assert isinstance(payload["total"], int)