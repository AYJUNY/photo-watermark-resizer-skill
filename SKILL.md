---
name: photo-watermark-resizer
description: >-
  Batch resize images and apply transparent PNG watermarks for blog posts and photo folders.
  Use this skill whenever the user asks to resize photos, add a watermark/signature PNG to images,
  batch-process a directory of blog photos, or launch the Watermark Resizer GUI.
---

# Photo Watermark & Resizer Skill (`photo-watermark-resizer`)

이 스킬은 블로그 포스팅용 다량의 사진이나 이미지 폴더를 일괄 리사이즈(가로/세로 픽셀 조절)하고 투명 PNG 워터마크를 합성하는 도구입니다.
AI 에이전트는 사용자의 요청에 따라 **1) CLI 스크립트로 즉시 자동 변환**하거나, **2) 사용자가 직접 마우스로 미리보기를 보며 배치할 수 있도록 GUI 앱을 실행**할 수 있습니다.

---

## 실행 환경 및 경로

* **파이썬 실행기**: `C:\Users\쭈니\AppData\Local\Programs\Python\Python313\python.exe` (또는 시스템 `python`)
* **CLI 스크립트**: [cli_resizer.py](./scripts/cli_resizer.py)
* **GUI 원본 프로젝트**: `C:\Users\쭈니\Documents\photo resiging\watermark_resizer.py` (실행 파일: `WatermarkResizer.exe`)
* **기본 워터마크 에셋 참고 경로 (`C:\Users\쭈니\Pictures`)**:
  - `C:\Users\쭈니\Pictures\넥스가드서명.png`
  - `C:\Users\쭈니\Pictures\넥스가드서명화이트.png`
  - `C:\Users\쭈니\Pictures\서명화이트.png`
  - `C:\Users\쭈니\Pictures\안산수암점.png`

---

## 사용 방법 (Step-by-Step)

### 1. AI가 백그라운드에서 즉시 일괄 변환할 때 (CLI 모드)

사용자가 폴더 경로와 크기/워터마크 옵션을 말하면 `cli_resizer.py`를 실행하여 즉시 처리합니다.

```powershell
& "C:\Users\쭈니\AppData\Local\Programs\Python\Python313\python.exe" "C:\Users\쭈니\.gemini\config\skills\photo-watermark-resizer\scripts\cli_resizer.py" `
  --input "<대상_폴더_또는_파일_경로>" `
  --watermark "<워터마크_PNG_경로>" `
  --width 800 `
  --height 600 `
  --opacity 80 `
  --size 20 `
  --margin 3 `
  --position "우하단" `
  --json
```

#### 주요 옵션 설명
| 옵션 | 기본값 | 설명 |
| :--- | :--- | :--- |
| `-i`, `--input` | (필수) | 변환할 이미지들이 들어있는 폴더 경로 또는 단일 이미지 파일 경로 |
| `-w`, `--watermark` | 없음 | 합성할 워터마크 PNG 파일 경로 (생략하면 리사이즈만 수행) |
| `-o`, `--output` | `원본폴더/processed` | 결과물을 저장할 폴더 경로 (미지정 시 각 이미지 폴더 하위 `processed/`에 자동 저장) |
| `--width` | `800` | 목표 가로(Width) 픽셀 크기 (`0`으로 주면 세로 기준으로만 비율 조절) |
| `--height` | `600` | 목표 세로(Height) 픽셀 크기 (`0`으로 주면 가로 기준으로만 비율 조절) |
| `--no-resize` | `False` | 플래그 추가 시 원본 해상도를 그대로 유지하고 워터마크만 합성 |
| `--stretch` | `False` | 플래그 추가 시 가로세로 비율 유지를 끄고 지정한 `width` x `height`로 강제 맞춤 |
| `--opacity` | `80.0` | 워터마크 불투명도 (`10` ~ `100`%) |
| `--size` | `20.0` | 결과 이미지 가로 폭 대비 워터마크 가로 크기 비율 (`5` ~ `100`%) |
| `--margin` | `3.0` | 모서리 여백 비율 (`0` ~ `50`%) |
| `--position` | `Bottom-Right` | `좌상단`(`Top-Left`), `중앙상단`(`Top-Center`), `우상단`(`Top-Right`), `좌측중앙`(`Middle-Left`), `정중앙`(`Center`), `우측중앙`(`Middle-Right`), `좌하단`(`Bottom-Left`), `중앙하단`(`Bottom-Center`), `우하단`(`Bottom-Right`), `직접지정`(`Custom`) |
| `--custom-x`, `--custom-y` | `95.0` | `--position Custom`일 때 가로/세로 상대 위치 퍼센트 (`0` ~ `100`%) |
| `--no-recursive` | `False` | 하위 폴더 탐색을 끄고 최상위 폴더의 이미지만 변환 |
| `--json` | `False` | 처리 결과를 AI가 파싱하기 쉬운 JSON으로 출력 |

---

### 2. 사용자가 직접 미리보기로 워터마크를 드래그 배치하고 싶을 때 (GUI 모드)

사용자가 "창 띄워줘", "미리보기로 직접 위치 잡고 싶어"라고 요청하면 `--gui` 옵션으로 데스크톱 앱을 실행합니다:

```powershell
& "C:\Users\쭈니\AppData\Local\Programs\Python\Python313\python.exe" "C:\Users\쭈니\.gemini\config\skills\photo-watermark-resizer\scripts\cli_resizer.py" --gui
```

---

## 결과 검증 (Verification)

1. 명령어 실행 후 출력된 JSON의 `"status": "success"` 및 `"processed"` 건수를 확인합니다.
2. 지정된 대상 폴더 내부의 `processed/` 하위 폴더에 변환된 이미지들이 생성되었는지 확인하고 사용자에게 저장 경로와 처리 건수를 안내합니다.
