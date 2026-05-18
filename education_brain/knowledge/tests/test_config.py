from knowledge.core.config import Settings


def test_settings_accepts_release_style_debug_values():
    assert Settings(debug="release").debug is False
    assert Settings(debug="production").debug is False
    assert Settings(debug="development").debug is True
    assert Settings(debug="WARN").debug is False
