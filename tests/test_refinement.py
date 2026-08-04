from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import httpx
import pytest
from PIL import Image, ImageDraw

from eikon_core.brand_library import BrandLibrary
from eikon_core.refinement import (
    RefinementError,
    build_refinement_prompt,
    evaluate_quality,
    gpt_edit_size,
    refine_asset,
)
from eikon_core.refinement_providers import (
    LocalPreviewProvider,
    OpenAIImageEditProvider,
)


@pytest.fixture
def brand_spec():
    return BrandLibrary.from_sources().get("pinakotheke-kosmos")


def _mockup(path: Path, *, color: str = "#0b1417") -> Path:
    image = Image.new("RGB", (1024, 1024), color)
    draw = ImageDraw.Draw(image)
    draw.rectangle((64, 64, 960, 280), fill="#43b5a6")
    draw.rectangle((64, 780, 960, 940), fill="#8d7cc0")
    image.save(path)
    return path


def _png_bytes(color: str = "#43b5a6") -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (1024, 1024), color).save(output, format="PNG")
    return output.getvalue()


def test_prompt_carries_exact_content_and_invariants(brand_spec) -> None:
    prompt = build_refinement_prompt(brand_spec, "ig_post")
    assert "Preserve all readable text verbatim" in prompt
    assert '"titulo": "Caos que se organiza"' in prompt
    assert brand_spec.name in prompt
    assert "Do not add new logos" in prompt


@pytest.mark.parametrize(
    ("width", "height", "expected"),
    [(1024, 1024, "1024x1024"), (1200, 628, "1200x624"), (1080, 1920, "1088x1920")],
)
def test_gpt_edit_size_is_valid(width: int, height: int, expected: str) -> None:
    size = gpt_edit_size(width, height)
    assert size == expected
    result_width, result_height = (int(part) for part in size.split("x"))
    assert result_width % 16 == result_height % 16 == 0
    assert 655_360 <= result_width * result_height <= 8_294_400


def test_gpt_edit_size_rejects_unsupported_ratio() -> None:
    with pytest.raises(ValueError, match="aspect ratios"):
        gpt_edit_size(4000, 500)


def test_local_pipeline_writes_png_and_traceable_metadata(tmp_path, brand_spec) -> None:
    source = _mockup(tmp_path / "before.png")
    output = tmp_path / "after.png"
    result = refine_asset(
        source_path=source,
        output_path=output,
        spec=brand_spec,
        asset_type="ig_post",
        provider=LocalPreviewProvider(),
    )
    assert output.is_file()
    assert Image.open(output).size == (1024, 1024)
    assert result.provider == "local-preview"
    assert result.output_sha256 != result.source_sha256
    assert result.gate.passed

    metadata = json.loads(Path(result.metadata_path).read_text(encoding="utf-8"))
    assert metadata["brand_spec_digest"] == brand_spec.digest
    assert metadata["asset_type"] == "ig_post"
    assert "api_key" not in json.dumps(metadata).lower()
    with pytest.raises(RefinementError, match="destino ya existe"):
        refine_asset(
            source_path=source,
            output_path=output,
            spec=brand_spec,
            asset_type="ig_post",
            provider=LocalPreviewProvider(),
        )


def test_quality_gate_rejects_redesign(brand_spec) -> None:
    source = Image.new("RGB", (512, 512), "#0b1417")
    candidate = Image.new("RGB", (512, 512), "#ffffff")
    gate = evaluate_quality(source, candidate, brand_spec)
    assert not gate.passed
    assert gate.reasons


def test_openai_provider_sends_edit_and_decodes_base64() -> None:
    response_png = _png_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/images/edits"
        assert request.headers["authorization"] == "Bearer test-secret"
        assert "multipart/form-data" in request.headers["content-type"]
        body = request.read()
        assert b'gpt-image-2' in body
        assert b'quality prompt' in body
        return httpx.Response(
            200,
            headers={"x-request-id": "req_123"},
            json={"data": [{"b64_json": base64.b64encode(response_png).decode()}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAIImageEditProvider(api_key="test-secret", client=client)
    result = provider.refine(
        _png_bytes("#0b1417"), "quality prompt", size="1024x1024", quality="high"
    )
    assert result.image_bytes == response_png
    assert result.request_id == "req_123"
    client.close()


def test_openai_provider_error_does_not_echo_secret() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            401,
            json={"error": {"type": "invalid_request_error", "code": "invalid_api_key"}},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAIImageEditProvider(api_key="never-echo-me", client=client)
    with pytest.raises(Exception) as captured:
        provider.refine(_png_bytes(), "prompt", size="1024x1024", quality="high")
    assert "never-echo-me" not in str(captured.value)
    assert "invalid_api_key" in str(captured.value)
    client.close()
