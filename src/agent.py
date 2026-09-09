# pyrefly: ignore [missing-import]
import uuid
from google import genai
from google.genai import types
from PIL.Image import Image
from config import Config
from schemas import ShotSetup, DOP_SYSTEM_PROMPT
from telemetry import tracer, agento11y_client
from opentelemetry.trace.status import Status, StatusCode

try:
    from agento11y import (
        GenerationStart,
        ModelRef,
        TokenUsage,
        user_text_message,
        assistant_text_message,
    )
except ImportError:
    # Dummy fallbacks if agento11y isn't imported directly
    class GenerationStart:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    class ModelRef:
        def __init__(self, provider, name):
            self.provider = provider
            self.name = name
    class TokenUsage:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    def user_text_message(text):
        return {"role": "user", "content": text}
    def assistant_text_message(text):
        return {"role": "assistant", "content": text}

if Config.USE_VERTEXAI:
    # Authenticates automatically via Application Default Credentials (ADC)
    client = genai.Client(
        vertexai=True,
        project=Config.GOOGLE_CLOUD_PROJECT,
        location=Config.GOOGLE_CLOUD_LOCATION
    )
else:
    client = genai.Client(api_key=Config.GEMINI_API_KEY)


def generate_cinematic_package(scene_description: str) -> tuple[ShotSetup, Image]:
    """Generates the shot metadata and storyboard image."""
    conversation_id = f"scene_{uuid.uuid4().hex[:12]}"
    dop_generation_id = f"gen_{uuid.uuid4().hex}"

    with tracer.start_as_current_span("generate_cinematic_package") as parent_span:
        parent_span.set_attribute("app.scene_input_length", len(scene_description))
        parent_span.set_attribute("gen_ai.conversation.id", conversation_id)

        # 1. Text Generation (DOP Reasoning)
        with tracer.start_as_current_span("llm_reasoning_gemini_flash") as text_span:
            with agento11y_client.start_generation(
                GenerationStart(
                    id=dop_generation_id,
                    conversation_id=conversation_id,
                    agent_name="cinematographer-dop-reasoner",
                    agent_version="1.0.0",
                    model=ModelRef(provider="google", name="gemini-2.5-flash"),
                    system_prompt=DOP_SYSTEM_PROMPT,
                    tags={"pipeline": "pre-production", "role": "dop_reasoner"},
                )
            ) as dop_rec:
                try:
                    text_response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=scene_description,
                        config=types.GenerateContentConfig(
                            system_instruction=DOP_SYSTEM_PROMPT,
                            response_mime_type="application/json",
                            response_schema=ShotSetup,
                            temperature=0.7,
                        ),
                    )
                    shot_data = text_response.parsed
                    text_span.set_attribute("llm.focal_length_chosen", shot_data.focal_length)
                    text_span.set_status(Status(StatusCode.OK))

                    usage_meta = getattr(text_response, "usage_metadata", None)
                    dop_rec.set_result(
                        input=[user_text_message(scene_description)],
                        output=[assistant_text_message(text_response.text or "")],
                        response_model="gemini-2.5-flash",
                        stop_reason="stop",
                        usage=TokenUsage(
                            input_tokens=usage_meta.prompt_token_count if usage_meta else 0,
                            output_tokens=usage_meta.candidates_token_count if usage_meta else 0,
                        ),
                    )
                except Exception as e:
                    text_span.record_exception(e)
                    text_span.set_status(Status(StatusCode.ERROR, str(e)))
                    dop_rec.set_call_error(e)
                    raise RuntimeError(f"Text Generation Failed: {e}")
                finally:
                    if hasattr(dop_rec, "err") and dop_rec.err():
                        parent_span.set_attribute("agento11y.dop_rec.error", str(dop_rec.err()))

        # 2. Image Generation (Storyboard Render) — Gemini native "Nano Banana"
        with tracer.start_as_current_span("image_generation_nano_banana") as img_span:
            with agento11y_client.start_generation(
                GenerationStart(
                    conversation_id=conversation_id,
                    agent_name="storyboard-image-renderer",
                    agent_version="1.0.0",
                    model=ModelRef(provider="google", name="gemini-2.5-flash-image"),
                    parent_generation_ids=[dop_generation_id] if dop_generation_id else [],
                    tags={"pipeline": "pre-production", "role": "image_renderer"},
                )
            ) as img_rec:
                try:
                    # Generate storyboard image via Gemini native image generation
                    image_response = client.models.generate_content(
                        model='gemini-2.5-flash-image',
                        contents=shot_data.image_generation_prompt,
                        config=types.GenerateContentConfig(
                            response_modalities=["IMAGE", "TEXT"],
                        ),
                    )

                    # Extract the generated image from the response parts
                    from io import BytesIO
                    from PIL import Image as PILImage
                    generated_image = None
                    for part in image_response.candidates[0].content.parts:
                        if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                            generated_image = PILImage.open(BytesIO(part.inline_data.data))
                            break

                    if generated_image is None:
                        raise RuntimeError("No image was returned by the model.")

                    img_span.set_status(Status(StatusCode.OK))

                    img_rec.set_result(
                        input=[user_text_message(shot_data.image_generation_prompt)],
                        output=[assistant_text_message("[Image rendered successfully]")],
                        response_model="gemini-2.5-flash-image",
                        stop_reason="stop",
                    )
                except Exception as e:
                    img_span.record_exception(e)
                    img_span.set_status(Status(StatusCode.ERROR, str(e)))
                    img_rec.set_call_error(e)
                    raise RuntimeError(f"Image Generation Failed: {e}")
                finally:
                    if hasattr(img_rec, "err") and img_rec.err():
                        parent_span.set_attribute("agento11y.img_rec.error", str(img_rec.err()))

            return shot_data, generated_image



    

    