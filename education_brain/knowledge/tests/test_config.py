from knowledge.core.config import Settings


def test_settings_accepts_release_style_debug_values():
    assert Settings(debug="release").debug is False
    assert Settings(debug="production").debug is False
    assert Settings(debug="development").debug is True


def test_settings_builds_milvus_token_from_user_and_password():
    settings = Settings(milvus_user="root", milvus_password="milvus")

    assert settings.effective_milvus_token == "root:milvus"


def test_settings_prefers_explicit_milvus_token():
    settings = Settings(
        milvus_user="root",
        milvus_password="milvus",
        milvus_token="custom-token",
    )

    assert settings.effective_milvus_token == "custom-token"
