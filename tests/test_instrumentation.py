import os
import sys
from unittest.mock import MagicMock, patch
import pytest

# Add src to python path for testing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from schemas import ShotSetup
from agent import generate_cinematic_package


@patch("agent.client.models.generate_content")
@patch("agent.agento11y_client")
def test_generation_instrumentation_records_correct_agents(mock_agento11y, mock_gen_content):
    """Verifies that both agent identities (DoP reasoner & image renderer) are
    correctly recorded with the agento11y SDK, and that parent linkage is set."""

    # 1. Setup mock DOP text response
    mock_dop_resp = MagicMock()
    mock_dop_resp.parsed = ShotSetup(
        shot_type="Extreme Wide Shot (EWS)",
        camera_angle="Low Angle",
        focal_length="16mm",
        lighting_and_exposure="High contrast chiaroscuro",
        subject_action="Detective walks alone",
        environmental_context="Neon-lit rainy streets at night",
        image_generation_prompt="Cinematic EWS, 16mm lens, low angle, neon rain street",
    )
    mock_dop_resp.text = '{"shot_type": "Extreme Wide Shot (EWS)"}'
    mock_dop_resp.usage_metadata = MagicMock()
    mock_dop_resp.usage_metadata.prompt_token_count = 145
    mock_dop_resp.usage_metadata.candidates_token_count = 78

    # 2. Setup mock image response (Gemini native image generation format)
    mock_img_part = MagicMock()
    mock_img_part.inline_data = MagicMock()
    mock_img_part.inline_data.mime_type = "image/png"
    # 1x1 transparent PNG bytes
    mock_img_part.inline_data.data = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
        b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00'
        b'\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00'
        b'\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    mock_img_resp = MagicMock()
    mock_img_resp.candidates = [MagicMock()]
    mock_img_resp.candidates[0].content.parts = [mock_img_part]

    mock_gen_content.side_effect = [mock_dop_resp, mock_img_resp]

    # 3. Setup mock agento11y generation recorders
    dop_rec = MagicMock()
    dop_rec.generation_id = "gen_dop_987"
    dop_rec.err.return_value = None
    dop_rec.__enter__.return_value = dop_rec

    img_rec = MagicMock()
    img_rec.generation_id = "gen_img_654"
    img_rec.err.return_value = None
    img_rec.__enter__.return_value = img_rec

    mock_agento11y.start_generation.side_effect = [dop_rec, img_rec]

    # 4. Invoke the pipeline
    shot_data, img = generate_cinematic_package("A weary detective in neon rain")

    # 5. Assertions on Generations
    assert mock_agento11y.start_generation.call_count == 2
    calls = mock_agento11y.start_generation.call_args_list

    # Check DOP generation call
    dop_start_arg = calls[0].args[0]
    assert dop_start_arg.agent_name == "cinematographer-dop-reasoner"
    assert dop_start_arg.agent_version == "1.0.0"
    assert dop_start_arg.model.name == "gemini-2.5-flash"
    assert dop_start_arg.tags["role"] == "dop_reasoner"
    assert dop_rec.set_result.called
    dop_result_kwargs = dop_rec.set_result.call_args.kwargs
    assert dop_result_kwargs["response_model"] == "gemini-2.5-flash"
    assert dop_result_kwargs["stop_reason"] == "stop"

    # Check Storyboard render generation call & parent linkage
    img_start_arg = calls[1].args[0]
    assert img_start_arg.agent_name == "storyboard-image-renderer"
    assert img_start_arg.agent_version == "1.0.0"
    assert img_start_arg.model.name == "gemini-2.5-flash-image"
    assert img_start_arg.parent_generation_ids == ["gen_dop_987"]
    assert img_rec.set_result.called
    img_result_kwargs = img_rec.set_result.call_args.kwargs
    assert img_result_kwargs["response_model"] == "gemini-2.5-flash-image"
    assert img_result_kwargs["stop_reason"] == "stop"


@patch("agent.client.models.generate_content")
@patch("agent.agento11y_client")
def test_generation_error_captures_exception_object(mock_agento11y, mock_gen_content):
    """Verifies that API errors during text generation are correctly propagated
    to the agento11y SDK via set_call_error."""
    mock_gen_content.side_effect = RuntimeError("Quota exceeded")

    dop_rec = MagicMock()
    dop_rec.generation_id = "gen_fail"
    dop_rec.__enter__.return_value = dop_rec
    mock_agento11y.start_generation.return_value = dop_rec

    with pytest.raises(RuntimeError):
        generate_cinematic_package("Failing scene")

    # Verify set_call_error was passed the actual exception object
    assert dop_rec.set_call_error.called
    err_arg = dop_rec.set_call_error.call_args.args[0]
    assert isinstance(err_arg, Exception)
    assert str(err_arg) == "Quota exceeded"
