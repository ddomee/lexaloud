"""Kokoro provider backed by an OpenAI-compatible local HTTP server."""

from __future__ import annotations

import asyncio
import io
import logging
import wave
from collections.abc import Callable

import httpx
import numpy as np

from .._privacy import sentence_token
from ..config import validate_local_tts_endpoint
from .base import AudioChunk

log = logging.getLogger(__name__)


class KokoroHttpProvider:
    """Request WAV audio from a local ``/v1/audio/speech`` endpoint.

    The server owns the model, voices, and hardware.  Lexaloud deliberately
    requests WAV so it can pass decoded float samples directly to its existing
    audio pipeline without adding a codec dependency.
    """

    name = "kokoro-http"

    def __init__(
        self,
        endpoint: str,
        *,
        model: str = "kokoro",
        voice: str = "af_heart",
        speed: float = 1.0,
        timeout_s: float = 60.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.endpoint = validate_local_tts_endpoint(endpoint)
        self.model = model
        self.voice = voice
        self.speed = speed
        self.timeout_s = timeout_s
        self._client = client
        self._synth_lock = asyncio.Lock()

    @property
    def session_providers(self) -> list[str]:
        return [self.endpoint]

    async def warmup(self) -> None:
        """The server manages its own warmup; don't synthesize unwanted audio."""

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()

    @staticmethod
    def _decode_wav(audio: bytes) -> tuple[np.ndarray, int]:
        try:
            with wave.open(io.BytesIO(audio), "rb") as wav:
                channels = wav.getnchannels()
                sample_width = wav.getsampwidth()
                sample_rate = wav.getframerate()
                frames = wav.readframes(wav.getnframes())
        except (wave.Error, EOFError) as e:
            raise ValueError("server did not return a valid WAV response") from e

        if channels < 1 or sample_rate < 1:
            raise ValueError("server returned WAV with invalid audio parameters")
        if sample_width == 1:
            samples = (
                np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128.0
            ) / 128.0
        elif sample_width == 2:
            samples = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
        elif sample_width == 3:
            raw = np.frombuffer(frames, dtype=np.uint8).reshape(-1, 3)
            values = (
                raw[:, 0].astype(np.int32)
                | (raw[:, 1].astype(np.int32) << 8)
                | (raw[:, 2].astype(np.int32) << 16)
            )
            values -= (values & 0x800000) << 1
            samples = values.astype(np.float32) / 8388608.0
        elif sample_width == 4:
            samples = np.frombuffer(frames, dtype="<i4").astype(np.float32) / 2147483648.0
        else:
            raise ValueError(f"unsupported WAV sample width: {sample_width} bytes")

        if samples.size % channels:
            raise ValueError("server returned a malformed WAV response")
        return (samples if channels == 1 else samples.reshape(-1, channels)), sample_rate

    async def synthesize(
        self,
        sentence: str,
        job_id: int,
        is_current_job: Callable[[int], bool],
    ) -> AudioChunk | None:
        if not is_current_job(job_id):
            return None

        payload = {
            "model": self.model,
            "input": sentence,
            "voice": self.voice,
            "response_format": "wav",
            "speed": self.speed,
        }
        async with self._synth_lock:
            if not is_current_job(job_id):
                return None
            try:
                if self._client is None:
                    async with httpx.AsyncClient(
                        timeout=self.timeout_s,
                        trust_env=False,
                    ) as client:
                        response = await client.post(self.endpoint, json=payload)
                else:
                    response = await self._client.post(self.endpoint, json=payload)
                response.raise_for_status()
                samples, sample_rate = self._decode_wav(response.content)
            except asyncio.CancelledError:
                raise
            except (httpx.HTTPError, ValueError) as e:
                log.error("Kokoro HTTP synthesis failed for %s: %s", sentence_token(sentence), e)
                return None

        if not is_current_job(job_id):
            return None
        return AudioChunk(
            samples=samples,
            sample_rate=sample_rate,
            metadata={"voice": self.voice, "endpoint": self.endpoint},
        )
