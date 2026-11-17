import sys
import os
import re

with open('main.py', 'r', encoding='utf-8') as f:
    text = f.read()

start_marker = '    def export_aseprite_preview_png('
end_marker = '    def run_aseprite_layer_move('

idx_start = text.find(start_marker)
idx_end = text.find(end_marker)

if idx_start != -1 and idx_end != -1:
    new_export = '''    def export_aseprite_preview_png(self, path, frame=1):
        if not self.validate_aseprite_path(self.aseprite_path.get()): return None
        import tempfile, glob
        from PIL import Image
        
        tmp_dir = tempfile.mkdtemp(prefix="pivot_ase_preview_")
        out_path = os.path.join(tmp_dir, "preview.png")

        candidates = []
        candidates.append(max(0, int(frame) - 1))
        candidates.append(max(0, int(frame)))

        for idx in candidates:
            # 이전 시도 파일 정리
            for old in glob.glob(os.path.join(tmp_dir, "*.png")):
                try:
                    os.remove(old)
                except:
                    pass

            args = [path, "--frame-range", f"{idx},{idx}", "--save-as", out_path]
            ok, log = self.run_aseprite_cli(args)

            pngs = glob.glob(os.path.join(tmp_dir, "*.png"))
            valid_pngs = []
            for p in pngs:
                try:
                    if os.path.exists(p) and os.path.getsize(p) > 0:
                        with Image.open(p) as tmp_img:
                            tmp_img.verify()
                        valid_pngs.append(p)
                except Exception as e:
                    print(f"미리보기 PNG 검증 실패: {p} / {e}")

            if valid_pngs:
                return valid_pngs[0]

            print("[Aseprite Preview Export Failed]")
            print(f"source: {path}")
            print(f"requested frame: {frame}")
            print(f"tried cli frame index: {idx}")
            print(f"args: {args}")
            print(f"ok: {ok}")
            print(f"log: {log}")
            print(f"tmp_dir files: {[(p, os.path.getsize(p) if os.path.exists(p) else -1) for p in pngs]}")

        return None

'''
    with open('main.py', 'w', encoding='utf-8') as f:
        f.write(text[:idx_start] + new_export + text[idx_end:])
    print('export_aseprite_preview_png successfully replaced.')
else:
    print('Failed to locate target markers.')
