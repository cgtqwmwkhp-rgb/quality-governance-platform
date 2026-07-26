"""PX-285 / PX-165: Safety Insights deep-run requires external-processing acknowledgment."""

from src.api.routes.safety_insights import EXTERNAL_PROCESSING_ACK_REQUIRED, DeepRunCreate


def test_deep_run_create_defaults_acknowledgment_to_false():
    payload = DeepRunCreate()
    assert payload.external_processing_acknowledged is False


def test_ack_required_copy_names_processors():
    assert "Gemini" in EXTERNAL_PROCESSING_ACK_REQUIRED
    assert "Claude" in EXTERNAL_PROCESSING_ACK_REQUIRED
    assert "Perplexity" in EXTERNAL_PROCESSING_ACK_REQUIRED
