import argparse
import gc
import json
import os
import subprocess
import sys
from PIL import Image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


POSITION_ALIASES = {
    "top-left": "Top-Left",
    "좌상단": "Top-Left",
    "top-center": "Top-Center",
    "중앙상단": "Top-Center",
    "상단중앙": "Top-Center",
    "top-right": "Top-Right",
    "우상단": "Top-Right",
    "middle-left": "Middle-Left",
    "좌측중앙": "Middle-Left",
    "좌중앙": "Middle-Left",
    "center": "Center",
    "정중앙": "Center",
    "중앙": "Center",
    "middle-right": "Middle-Right",
    "우측중앙": "Middle-Right",
    "우중앙": "Middle-Right",
    "bottom-left": "Bottom-Left",
    "좌하단": "Bottom-Left",
    "bottom-center": "Bottom-Center",
    "중앙하단": "Bottom-Center",
    "하단중앙": "Bottom-Center",
    "bottom-right": "Bottom-Right",
    "우하단": "Bottom-Right",
    "custom": "Custom",
    "직접지정": "Custom",
    "사용자지정": "Custom",
}

SUPPORTED_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")


def get_resample():
    try:
        return Image.Resampling.LANCZOS
    except AttributeError:
        return Image.LANCZOS


def normalize_position(pos_str):
    key = pos_str.strip().lower()
    if key in POSITION_ALIASES:
        return POSITION_ALIASES[key]
    for canonical in set(POSITION_ALIASES.values()):
        if canonical.lower() == key:
            return canonical
    raise ValueError(
        f"지원하지 않는 위치값입니다: '{pos_str}'. "
        f"사용 가능: Top-Left(좌상단), Top-Center(중앙상단), Top-Right(우상단), "
        f"Middle-Left(좌측중앙), Center(정중앙), Middle-Right(우측중앙), "
        f"Bottom-Left(좌하단), Bottom-Center(중앙하단), Bottom-Right(우하단), Custom(직접지정)"
    )


def collect_images(target_path, recursive=True):
    if os.path.isfile(target_path):
        if target_path.lower().endswith(SUPPORTED_EXTS):
            return [os.path.abspath(target_path)]
        return []

    collected = []
    if recursive:
        for root, dirs, files in os.walk(target_path):
            dirs[:] = [d for d in dirs if d.lower() != "processed"]
            for f in sorted(files):
                if f.lower().endswith(SUPPORTED_EXTS):
                    collected.append(os.path.join(root, f))
    else:
        for f in sorted(os.listdir(target_path)):
            full = os.path.join(target_path, f)
            if os.path.isfile(full) and f.lower().endswith(SUPPORTED_EXTS):
                collected.append(full)
    return collected


def process_batch(
    input_path,
    watermark_path=None,
    output_dir=None,
    enable_resize=True,
    width=800,
    height=600,
    keep_ratio=True,
    opacity=80.0,
    size=20.0,
    margin=3.0,
    position="Bottom-Right",
    custom_x=95.0,
    custom_y=95.0,
    recursive=True,
):
    pos = normalize_position(position)
    files = collect_images(input_path, recursive=recursive)
    if not files:
        return {"status": "error", "message": f"처리할 이미지 파일이 없습니다: {input_path}", "processed": 0, "total": 0}

    watermark = None
    if watermark_path:
        if not os.path.isfile(watermark_path):
            return {"status": "error", "message": f"워터마크 파일을 찾을 수 없습니다: {watermark_path}", "processed": 0, "total": len(files)}
        watermark = Image.open(watermark_path)
        watermark.load()

    resample = get_resample()
    success_count = 0
    errors = []
    output_paths = []

    try:
        for idx, file_path in enumerate(files, start=1):
            try:
                with Image.open(file_path) as img:
                    orig_w, orig_h = img.size
                    new_w, new_h = orig_w, orig_h

                    if enable_resize:
                        if keep_ratio:
                            if width > 0 and height > 0:
                                scale = min(width / orig_w, height / orig_h)
                                new_w = max(1, int(orig_w * scale))
                                new_h = max(1, int(orig_h * scale))
                            elif width > 0:
                                new_w = width
                                new_h = max(1, int(orig_h * (width / orig_w)))
                            elif height > 0:
                                new_h = height
                                new_w = max(1, int(orig_w * (height / orig_h)))
                        elif width > 0 and height > 0:
                            new_w, new_h = width, height

                    if (new_w, new_h) != (orig_w, orig_h):
                        processed = img.resize((new_w, new_h), resample=resample)
                    else:
                        processed = img.copy()

                    if watermark:
                        wm_w, wm_h = watermark.size
                        wm_scaled_w = max(1, int(new_w * (size / 100.0)))
                        wm_scaled_h = max(1, int(wm_scaled_w * (wm_h / wm_w)))
                        scaled_wm = watermark.resize((wm_scaled_w, wm_scaled_h), resample=resample).convert("RGBA")

                        if opacity < 100:
                            alpha = scaled_wm.getchannel("A")
                            alpha = alpha.point(lambda p: int(p * (opacity / 100.0)))
                            scaled_wm.putalpha(alpha)

                        margin_px = int(min(new_w, new_h) * (margin / 100.0))
                        if pos == "Top-Left":
                            x, y = margin_px, margin_px
                        elif pos == "Top-Center":
                            x, y = (new_w - wm_scaled_w) // 2, margin_px
                        elif pos == "Top-Right":
                            x, y = new_w - wm_scaled_w - margin_px, margin_px
                        elif pos == "Middle-Left":
                            x, y = margin_px, (new_h - wm_scaled_h) // 2
                        elif pos == "Center":
                            x, y = (new_w - wm_scaled_w) // 2, (new_h - wm_scaled_h) // 2
                        elif pos == "Middle-Right":
                            x, y = new_w - wm_scaled_w - margin_px, (new_h - wm_scaled_h) // 2
                        elif pos == "Bottom-Left":
                            x, y = margin_px, new_h - wm_scaled_h - margin_px
                        elif pos == "Bottom-Center":
                            x, y = (new_w - wm_scaled_w) // 2, new_h - wm_scaled_h - margin_px
                        elif pos == "Custom":
                            x = int((new_w - wm_scaled_w) * (custom_x / 100.0))
                            y = int((new_h - wm_scaled_h) * (custom_y / 100.0))
                        else:
                            x, y = new_w - wm_scaled_w - margin_px, new_h - wm_scaled_h - margin_px

                        if pos != "Custom":
                            x = max(0, min(x, max(0, new_w - wm_scaled_w)))
                            y = max(0, min(y, max(0, new_h - wm_scaled_h)))

                        if processed.mode not in ("RGB", "RGBA"):
                            processed = processed.convert("RGB")

                        processed.paste(scaled_wm, (x, y), scaled_wm)
                        scaled_wm.close()

                    target_out_dir = output_dir if output_dir else os.path.join(os.path.dirname(file_path), "processed")
                    os.makedirs(target_out_dir, exist_ok=True)
                    out_path = os.path.join(target_out_dir, os.path.basename(file_path))
                    ext = file_path.lower().split(".")[-1]

                    save_img = processed
                    if ext in ("jpg", "jpeg") and processed.mode == "RGBA":
                        save_img = processed.convert("RGB")

                    if ext in ("jpg", "jpeg"):
                        save_img.save(out_path, quality=90, subsampling=1)
                    elif ext == "png":
                        save_img.save(out_path, optimize=False)
                    elif ext == "webp":
                        save_img.save(out_path, quality=88, method=2)
                    else:
                        save_img.save(out_path)

                    if save_img is not processed:
                        save_img.close()
                    processed.close()

                    success_count += 1
                    output_paths.append(out_path)
                    print(f"[{idx}/{len(files)}] 완료: {out_path}")
            except Exception as exc:
                err_msg = f"{file_path}: {exc}"
                errors.append(err_msg)
                print(f"[{idx}/{len(files)}] 오류: {err_msg}", file=sys.stderr)
    finally:
        if watermark:
            watermark.close()
        gc.collect()

    return {
        "status": "success" if success_count > 0 else "error",
        "processed": success_count,
        "total": len(files),
        "output_sample": output_paths[:5],
        "errors": errors,
    }


def launch_gui():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    local_py = os.path.join(script_dir, "watermark_resizer.py")
    project_dir = r"C:\Users\쭈니\Documents\photo resiging"
    exe_path = os.path.join(project_dir, "WatermarkResizer.exe")
    py_path = os.path.join(project_dir, "watermark_resizer.py")

    if os.path.isfile(exe_path):
        subprocess.Popen([exe_path], cwd=project_dir)
        print(f"GUI 실행 파일을 시작했습니다: {exe_path}")
    elif os.path.isfile(local_py):
        subprocess.Popen([sys.executable, local_py], cwd=script_dir)
        print(f"스킬 내장 GUI 스크립트를 시작했습니다: {local_py}")
    elif os.path.isfile(py_path):
        subprocess.Popen([sys.executable, py_path], cwd=project_dir)
        print(f"GUI 파이썬 스크립트를 시작했습니다: {py_path}")
    else:
        print("오류: GUI 프로그램 경로를 찾을 수 없습니다.", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="블로그 이미지 일괄 크기 조절 및 워터마크 합성 CLI 도구 (AI 에이전트 스킬용)"
    )
    parser.add_argument("-i", "--input", help="대상 폴더 경로 또는 단일 이미지 파일 경로")
    parser.add_argument("-w", "--watermark", help="합성할 워터마크 PNG 파일 경로 (생략 시 크기 조절만 수행)")
    parser.add_argument("-o", "--output", help="결과물 저장 폴더 경로 (생략 시 원본 폴더 내 processed/ 폴더에 저장)")
    parser.add_argument("--width", type=int, default=800, help="가로 픽셀 크기 (기본값: 800, 0 입력 시 미지정)")
    parser.add_argument("--height", type=int, default=600, help="세로 픽셀 크기 (기본값: 600, 0 입력 시 미지정)")
    parser.add_argument("--no-resize", action="store_true", help="크기 조절 비활성화 (원본 해상도 유지)")
    parser.add_argument("--stretch", action="store_true", help="가로세로 비율 유지 해제 (지정 크기로 강제 맞춤)")
    parser.add_argument("--opacity", type=float, default=80.0, help="워터마크 투명도 10~100%% (기본값: 80)")
    parser.add_argument("--size", type=float, default=20.0, help="이미지 가로 대비 워터마크 크기 비율 %% (기본값: 20)")
    parser.add_argument("--margin", type=float, default=3.0, help="모서리 여백 비율 %% (기본값: 3)")
    parser.add_argument(
        "--position",
        default="Bottom-Right",
        help="워터마크 위치: Top-Left(좌상단), Top-Center(중앙상단), Top-Right(우상단), Middle-Left(좌측중앙), Center(정중앙), Middle-Right(우측중앙), Bottom-Left(좌하단), Bottom-Center(중앙하단), Bottom-Right(우하단), Custom(직접지정)",
    )
    parser.add_argument("--custom-x", type=float, default=95.0, help="Custom 위치일 때 가로 상대 좌표 %% (기본값: 95)")
    parser.add_argument("--custom-y", type=float, default=95.0, help="Custom 위치일 때 세로 상대 좌표 %% (기본값: 95)")
    parser.add_argument("--no-recursive", action="store_true", help="하위 폴더 재귀 탐색 비활성화")
    parser.add_argument("--gui", action="store_true", help="직접 마우스로 배치할 수 있도록 데스크톱 GUI 창 실행")
    parser.add_argument("--json", action="store_true", help="결과 요약을 JSON 형식으로 출력")

    args = parser.parse_args()

    if args.gui:
        launch_gui()
        return

    if not args.input:
        parser.error("--input (-i) 대상 경로를 지정하거나 --gui 옵션을 사용하세요.")

    result = process_batch(
        input_path=args.input,
        watermark_path=args.watermark,
        output_dir=args.output,
        enable_resize=not args.no_resize,
        width=args.width,
        height=args.height,
        keep_ratio=not args.stretch,
        opacity=args.opacity,
        size=args.size,
        margin=args.margin,
        position=args.position,
        custom_x=args.custom_x,
        custom_y=args.custom_y,
        recursive=not args.no_recursive,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"\n[완료] 성공: {result['processed']}/{result['total']}장")
        if result.get("errors"):
            print(f"[오류 발생] {len(result['errors'])}건")

    if result["status"] != "success":
        sys.exit(1)


if __name__ == "__main__":
    main()
