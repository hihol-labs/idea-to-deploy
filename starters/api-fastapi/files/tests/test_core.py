from app.services.core import service_ready


def test_service_ready() -> None:
    assert service_ready()

