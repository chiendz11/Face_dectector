from app.core.config import Settings


def test_deepface_settings_normalize_known_model_dimensions() -> None:
    settings = Settings(
        embedding_provider="deepface",
        model_name="Facenet512",
        embedding_dimensions=16,
    )

    assert settings.embedding_dimensions == 512


def test_hash_settings_keep_configured_dimensions() -> None:
    settings = Settings(
        embedding_provider="hash",
        model_name="Facenet512",
        embedding_dimensions=16,
    )

    assert settings.embedding_dimensions == 16
