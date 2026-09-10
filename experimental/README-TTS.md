# 허깅페이스 한국어 TTS 준비 코드

이 폴더의 코드는 현재 명예회장봇과 연결되어 있지 않습니다. `bot.py`, 기존 Cog,
VPS 서비스에는 아무 변경도 하지 않고 단독 시험용으로만 둡니다.

## 목소리 선택

- 기본 모델: Sherpa-ONNX `vits-mimic3-ko_KO-kss_low`
- 기본 목소리: `fast_korean` (2 vCPU 실측 약 0.78초)
- 선택 가능: `fast_korean`, `sohee`, `vivian`, `serena`, `uncle_fu`,
  `dylan`, `eric`, `ryan`, `aiden`, `ono_anna`
- 실행 방식: VPS 또는 PC에서 모델을 직접 실행
- Qwen 모델은 Apache 2.0, 기존 `mms_korean`은 CC-BY-NC 4.0 라이선스입니다.
- 무료 호스팅 API가 아니라 첫 사용 시 모델을 내려받아 직접 실행합니다.

## 준비

1. 별도 가상환경에 `requirements-tts.txt`를 설치합니다.
2. `mms_korean` 사용 시에만 Perl과 [uroman](https://github.com/isi-nlp/uroman)을 준비합니다.
3. `mms_korean` 사용 시 환경변수 `UROMAN_PATH`에 `uroman.pl` 경로를 지정합니다.

예시:

```bash
python experimental/huggingface_korean_tts.py "안녕하세요, 명예회장봇입니다." --voice fast_korean --output test.wav
python experimental/huggingface_korean_tts.py "목소리 시험입니다." --voice ryan --style "차분하고 진중하게 말해 주세요."
```

나중에 Discord `/음성` 명령을 만들 때에는 다음처럼 비동기 메서드를 호출한 뒤,
생성된 WAV 파일을 FFmpeg로 음성 채널에 재생하면 됩니다.

```python
path = await tts.synthesize_async(message, "/tmp/honorary-tts.wav", voice="fast_korean")
```

동시에 여러 요청이 들어올 때 모델 실행은 내부 잠금으로 한 번씩 처리됩니다. 실제 봇에
연결할 때에는 요청 대기열, 글자 수 제한, 임시 파일 삭제, 음성 채널 권한 검사를 추가해야 합니다.
