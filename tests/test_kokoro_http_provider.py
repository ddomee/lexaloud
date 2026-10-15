"""Unit tests for the OpenAI-compatible local Kokoro provider."""

from __future__ import annotations

import io
import json
import wave

import httpx
import numpy as np
import pytest

from lexaloud.providers.kokoro_http import KokoroHttpProvider


def _wav_bytes(samples: np.ndarray, sample_rate: int = 24000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(samples.astype("<i2").tobytes())
    return buf.getvalue()


async def test_synthesize_posts_openai_compatible_wav_request():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update({"url": str(request.url), "json": json.loads(request.content)})
        return httpx.Response(200, content=_wav_bytes(np.array([0, 16384, -16384])))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = KokoroHttpProvider(
        "http://127.0.0.1:8880/v1/audio/speech",
        voice="af_bella",
        speed=1.15,
        client=client,
    )
    chunk = await provider.synthesize("Hello.", 4, lambda job_id: job_id == 4)

    assert chunk is not None
    assert chunk.sample_rate == 24000
    assert np.allclose(chunk.samples, [0.0, 0.5, -0.5])
    assert seen["url"] == "http://127.0.0.1:8880/v1/audio/speech"
    assert seen["json"] == {
        "model": "kokoro",
        "input": "Hello.",
        "voice": "af_bella",
        "response_format": "wav",
        "speed": 1.15,
    }
    await provider.aclose()


async def test_synthesize_returns_none_for_invalid_server_response():
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"not wav"))
    )
    provider = KokoroHttpProvider("http://127.0.0.1:8880/v1/audio/speech", client=client)
    assert await provider.synthesize("Hello.", 1, lambda _: True) is None
    await provider.aclose()


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://127.0.0.1:8880/v1/audio/speech",
        "http://localhost:8880/v1/audio/speech",
        "http://192.168.1.10:8880/v1/audio/speech",
        "http://127.0.0.1:8880/v1/audio/speech?forward=true",
    ],
)
def test_provider_rejects_non_literal_loopback_endpoint(endpoint: str):
    with pytest.raises(ValueError, match="literal loopback"):
        KokoroHttpProvider(endpoint)
