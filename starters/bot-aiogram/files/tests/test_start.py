from bot.handlers.start import start_message


def test_start_message() -> None:
    assert "idea-to-deploy" in start_message()

