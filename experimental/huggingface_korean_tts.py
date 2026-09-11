"""명예회장봇에 연결하기 전 단독으로 시험하는 Hugging Face 한국어 TTS."""

from __future__ import annotations

import asyncio
import os
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path
from threading import Lock


VOICE_OPTIONS = {
    "fast_korean": "빠르고 자연스러운 한국 여성 목소리 (기본·추천)",
    "sohee": "고품질 한국 여성 목소리 (느림)",
    "vivian": "밝고 선명한 젊은 여성 목소리",
    "serena": "따뜻하고 부드러운 젊은 여성 목소리",
    "uncle_fu": "낮고 차분한 중년 남성 목소리",
    "dylan": "맑고 자연스러운 젊은 남성 목소리",
    "eric": "활기차고 약간 허스키한 남성 목소리",
    "ryan": "리듬감 있고 역동적인 남성 목소리",
    "aiden": "밝고 또렷한 남성 목소리",
    "ono_anna": "가볍고 장난스러운 여성 목소리",
}

QWEN_SPEAKERS = {
    "sohee": "Sohee", "vivian": "Vivian", "serena": "Serena",
    "uncle_fu": "Uncle_Fu", "dylan": "Dylan", "eric": "Eric",
    "ryan": "Ryan", "aiden": "Aiden", "ono_anna": "Ono_Anna",
}


@dataclass(frozen=True)
class TTSConfig:
    default_voice: str = "fast_korean"
    qwen_model_id: str = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
    mms_model_id: str = "facebook/mms-tts-kor"
    uroman_path: str | None = os.getenv("UROMAN_PATH")
    max_text_length: int = 500
    device: str = "auto"
    fast_model_dir: str = "models/vits-mimic3-ko_KO-kss_low"


class HuggingFaceKoreanTTS:
    """10개 음색 중 하나로 한국어 WAV를 생성한다."""

    def __init__(self, config: TTSConfig | None = None) -> None:
        self.config = config or TTSConfig()
        if self.config.default_voice not in VOICE_OPTIONS:
            raise ValueError(f"지원하지 않는 기본 목소리: {self.config.default_voice}")
        self._qwen_model = None
        self._fast_model = None
        self._mms_model = None
        self._mms_tokenizer = None
        self._torch = None
        self._lock = Lock()
        self._fast_lock = Lock()

    def warmup(self) -> None:
        """운영 요청 전에 모델과 첫 추론을 준비한다. 파일은 생성하지 않는다."""
        with self._fast_lock:
            self._load_fast()
            self._fast_model.generate("안녕하세요", sid=0, speed=1.0)

    @staticmethod
    def available_voices() -> dict[str, str]:
        return VOICE_OPTIONS.copy()

    def _load_qwen(self) -> None:
        if self._qwen_model is not None:
            return
        try:
            import torch
            from qwen_tts import Qwen3TTSModel
        except ImportError as exc:
            raise RuntimeError("requirements-tts.txt의 패키지를 설치하세요.") from exc
        self._torch = torch
        torch.set_num_threads(2)
        has_cuda = torch.cuda.is_available()
        requested_device = "cuda:0" if has_cuda else "cpu"
        self._qwen_model = Qwen3TTSModel.from_pretrained(
            self.config.qwen_model_id,
            device_map=requested_device if self.config.device == "auto" else self.config.device,
            dtype=torch.bfloat16 if has_cuda else torch.float32,
        )

    def _load_fast(self) -> None:
        if self._fast_model is not None:
            return
        try:
            import sherpa_onnx
        except ImportError as exc:
            raise RuntimeError("sherpa-onnx 패키지를 설치하세요.") from exc

        model_dir = Path(self.config.fast_model_dir).expanduser().resolve()
        config = sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(
                vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                    model=str(model_dir / "ko_KO-kss_low.onnx"),
                    tokens=str(model_dir / "tokens.txt"),
                    data_dir=str(model_dir / "espeak-ng-data"),
                ),
                num_threads=2,
            )
        )
        if not config.validate():
            raise RuntimeError(f"빠른 한국어 모델 파일을 확인하세요: {model_dir}")
        self._fast_model = sherpa_onnx.OfflineTts(config)

    def _load_mms(self) -> None:
        if self._mms_model is not None:
            return
        try:
            import torch
            from transformers import AutoTokenizer, VitsModel
        except ImportError as exc:
            raise RuntimeError("requirements-tts.txt의 패키지를 설치하세요.") from exc
        self._torch = torch
        self._mms_tokenizer = AutoTokenizer.from_pretrained(self.config.mms_model_id)
        self._mms_model = VitsModel.from_pretrained(self.config.mms_model_id)
        self._mms_model.eval()

    def _romanize(self, text: str) -> str:
        if not self.config.uroman_path:
            raise RuntimeError("mms_korean 사용에는 UROMAN_PATH 설정이 필요합니다.")
        script = Path(self.config.uroman_path).expanduser().resolve()
        if not script.is_file():
            raise RuntimeError(f"uroman 스크립트를 찾을 수 없습니다: {script}")
        result = subprocess.run(
            ["perl", str(script)], input=text, text=True, capture_output=True, check=False
        )
        if result.returncode != 0 or not result.stdout.strip():
            raise RuntimeError(result.stderr.strip() or "한국어 로마자 변환 실패")
        return result.stdout.strip()

    @staticmethod
    def _save_wav(destination: Path, waveform, sample_rate: int) -> None:
        import numpy as np
        audio = np.asarray(waveform, dtype=np.float32).squeeze()
        peak = float(np.abs(audio).max()) if audio.size else 0.0
        if peak > 1.0:
            audio = audio / peak
        pcm = (audio * 32767).astype("int16")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(destination), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(int(sample_rate))
            wav_file.writeframes(pcm.tobytes())

    def synthesize(
        self, text: str, output_path: str | Path, *, voice: str | None = None,
        style: str = "따뜻하고 자연스러운 말투로 말해 주세요.",
    ) -> Path:
        cleaned = " ".join(text.split())
        selected = (voice or self.config.default_voice).lower()
        if not cleaned:
            raise ValueError("읽을 문장을 입력하세요.")
        if len(cleaned) > self.config.max_text_length:
            raise ValueError(f"문장은 최대 {self.config.max_text_length}자까지 가능합니다.")
        if selected not in VOICE_OPTIONS:
            raise ValueError(f"지원하지 않는 목소리입니다: {selected}")

        destination = Path(output_path).expanduser().resolve()
        with (self._fast_lock if selected == "fast_korean" else self._lock):
            if selected == "fast_korean":
                self._load_fast()
                audio = self._fast_model.generate(cleaned, sid=0, speed=1.0)
                waveform = audio.samples
                sample_rate = audio.sample_rate
            elif selected == "mms_korean":
                self._load_mms()
                inputs = self._mms_tokenizer(self._romanize(cleaned), return_tensors="pt")
                with self._torch.inference_mode():
                    waveform = self._mms_model(**inputs).waveform.squeeze().cpu().numpy()
                sample_rate = self._mms_model.config.sampling_rate
            else:
                self._load_qwen()
                wavs, sample_rate = self._qwen_model.generate_custom_voice(
                    text=cleaned, language="Korean", speaker=QWEN_SPEAKERS[selected],
                    instruct=style,
                )
                waveform = wavs[0]
            self._save_wav(destination, waveform, sample_rate)
        return destination

    async def synthesize_async(self, *args, **kwargs) -> Path:
        return await asyncio.to_thread(self.synthesize, *args, **kwargs)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="한국어 TTS 10개 목소리 시험")
    parser.add_argument("text", nargs="?", default="안녕하세요, 명예회장봇입니다.")
    parser.add_argument("--voice", choices=VOICE_OPTIONS, default="fast_korean")
    parser.add_argument("--style", default="따뜻하고 자연스러운 말투로 말해 주세요.")
    parser.add_argument("--output", default="tts-output.wav")
    parser.add_argument("--list-voices", action="store_true")
    args = parser.parse_args()
    if args.list_voices:
        for key, description in VOICE_OPTIONS.items():
            print(f"{key:12} {description}")
    else:
        result = HuggingFaceKoreanTTS().synthesize(
            args.text, args.output, voice=args.voice, style=args.style
        )
        print(f"완료: {result}")
