import os
import sys
import glob
import shutil
import subprocess
import tempfile
import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog

# PyInstaller 환경에서 tkinterdnd2 라이브러리 경로 설정
if getattr(sys, 'frozen', False):
    os.environ['TKDND_LIBRARY'] = os.path.join(sys._MEIPASS, 'tkinterdnd2')

from tkinterdnd2 import TkinterDnD, DND_FILES
from PIL import Image, ImageTk, ImageChops

class PivotFixerApp:
    def __init__(self, root):
        self.root = root
        self.version = "v0.3.1"
        self.root.title(f"PNG 피봇 보정 툴 (Pixel Art Optimizer) - {self.version}")

        self.root.geometry("1400x850")
        self.root.minsize(1200, 750)
        self.root.resizable(True, True)

        # 시스템 변수들 (윈도우/테마 설정)
        self.is_dark_mode = tk.BooleanVar(value=False)
        self.is_always_on_top = tk.BooleanVar(value=False)
        self.window_alpha = tk.DoubleVar(value=1.0)

        # 파일 데이터 구조: {"id": id, "path": path, "name": name, "checked": bool, "settings": dict}
        self.file_data = []
        self.preview_path = None
        self.output_dir = ""
        self.last_generated_files = [] 

        # UI 컨트롤 설정 변수들 (Spinbox 타이핑 즉시 감지를 위해 StringVar로 변경)
        self.offset_y = tk.StringVar(value="0")
        self.offset_x = tk.StringVar(value="0")
        self.h_align = tk.BooleanVar(value=True)
        self.trim_margin_x = tk.BooleanVar(value=False)
        
        self.overwrite = tk.BooleanVar(value=False)
        self.save_mode = tk.StringVar(value="original") 

        self.flip_h = tk.BooleanVar(value=False)
        self.flip_v = tk.BooleanVar(value=False)
        self.rotate_angle = tk.StringVar(value="0도 (회전 없음)")
        self.transform_order = tk.StringVar(value="before")

        self.tk_orig = None
        self.tk_res = None
        self._resize_timer = None
        self._offset_timer = None
        self._is_updating_ui = False
        self._current_selected_items = ()
        
        self.aseprite_path = tk.StringVar(value="")
        self.aseprite_files = []
        self.ase_selection_state = {}
        
        # 변수 변경 시 자동 저장 트리거 연결
        self.offset_y.trace_add("write", self._on_offset_change)
        self.offset_x.trace_add("write", self._on_offset_change)
        self.h_align.trace_add("write", self._on_var_change)
        self.trim_margin_x.trace_add("write", self._on_var_change)
        self.flip_h.trace_add("write", self._on_var_change)
        self.flip_v.trace_add("write", self._on_var_change)
        self.rotate_angle.trace_add("write", self._on_var_change)
        self.transform_order.trace_add("write", self._on_var_change)

        # UI 생성 사이클
        self.setup_menu()
        self.setup_ui()
        self.apply_theme() # 테마 초기화 적용
        
    def _on_var_change(self, *args):
        """UI에 연결된 변수값이 변경될 때마다 자동으로 호출됩니다."""
        if self._is_updating_ui: return
        self.on_ui_change()
        
    def _on_offset_change(self, *args):
        """오프셋 Spinbox 타이핑 시 너무 잦은 업데이트를 방지하기 위한 디바운싱 처리"""
        if self._is_updating_ui: return
        if self._offset_timer:
            self.root.after_cancel(self._offset_timer)
        self._offset_timer = self.root.after(80, self._apply_offset_change)
        
    def _apply_offset_change(self):
        self.on_ui_change()

    def get_colors(self):
        """다크모드 여부에 따라 동적으로 컬러 팔레트를 반환합니다."""
        if self.is_dark_mode.get():
            return {
                "BG_COLOR": "#1E1E1E",
                "PANEL_BG": "#252526",
                "PRIMARY_COLOR": "#6366F1",
                "PRIMARY_HOVER": "#4F46E5",
                "SUCCESS_COLOR": "#10B981",
                "SUCCESS_HOVER": "#059669",
                "DANGER_COLOR": "#F87171",
                "TEXT_COLOR": "#E5E7EB",
                "TEXT_MUTED": "#9CA3AF",
                "BORDER_COLOR": "#3E3E42"
            }
        else:
            return {
                "BG_COLOR": "#F0F2F5",
                "PANEL_BG": "#FFFFFF",
                "PRIMARY_COLOR": "#4F46E5",
                "PRIMARY_HOVER": "#4338CA",
                "SUCCESS_COLOR": "#10B981",
                "SUCCESS_HOVER": "#059669",
                "DANGER_COLOR": "#EF4444",
                "TEXT_COLOR": "#1E293B",
                "TEXT_MUTED": "#64748B",
                "BORDER_COLOR": "#E2E8F0"
            }

    def _update_tree_item(self, f):
        """파일 정보 딕셔너리 f를 바탕으로 Treeview의 행(체크여부, 이름, 요약텍스트, 색상)을 일괄 갱신합니다."""
        check_str = "☑" if f["checked"] else "☐"
        summary = self.format_settings_summary(f["settings"])
        tag = "modified" if summary != "━ [ 기본값 ]" else "default"
        self.tree.item(f["id"], values=(check_str, f["name"], summary), tags=(tag,))

    def apply_theme(self):
        """가져온 컬러 팔레트를 모든 ttk 위젯과 tkinter 캔버스 등에 덮어씌웁니다."""
        c = self.get_colors()
        self.root.configure(bg=c["BG_COLOR"])
        
        style = ttk.Style(self.root)
        style.theme_use("clam")

        default_font = ("Malgun Gothic", 10)
        bold_font = ("Malgun Gothic", 10, "bold")
        title_font = ("Malgun Gothic", 11, "bold")

        style.configure(".", font=default_font, background=c["BG_COLOR"], foreground=c["TEXT_COLOR"])

        style.configure("TFrame", background=c["BG_COLOR"])
        style.configure("Panel.TFrame", background=c["PANEL_BG"])

        style.configure("TLabelframe", background=c["PANEL_BG"], borderwidth=1, bordercolor=c["BORDER_COLOR"], relief="flat")
        style.configure("TLabelframe.Label", background=c["PANEL_BG"], foreground=c["PRIMARY_COLOR"], font=title_font, padding=(10, 5))

        style.configure("TLabel", background=c["PANEL_BG"], foreground=c["TEXT_COLOR"], font=default_font)
        style.configure("Muted.TLabel", background=c["PANEL_BG"], foreground=c["TEXT_MUTED"], font=("Malgun Gothic", 9))
        style.configure("Danger.TLabel", background=c["PANEL_BG"], foreground=c["DANGER_COLOR"], font=bold_font)
        style.configure("Success.TLabel", background=c["PANEL_BG"], foreground=c["SUCCESS_COLOR"], font=bold_font)

        style.configure("TCheckbutton", background=c["PANEL_BG"], foreground=c["TEXT_COLOR"], font=default_font, indicatorsize=16)
        style.map("TCheckbutton", background=[("active", c["PANEL_BG"])])

        style.configure("TRadiobutton", background=c["PANEL_BG"], foreground=c["TEXT_COLOR"], font=default_font, indicatorsize=16)
        style.map("TRadiobutton", background=[("active", c["PANEL_BG"])])

        style.configure("TCombobox", padding=5, font=default_font, bordercolor=c["BORDER_COLOR"], fieldbackground=c["PANEL_BG"], background=c["PANEL_BG"], foreground=c["TEXT_COLOR"])
        style.configure("TSpinbox", padding=5, font=default_font, bordercolor=c["BORDER_COLOR"], fieldbackground=c["PANEL_BG"], background=c["PANEL_BG"], foreground=c["TEXT_COLOR"], arrowcolor=c["TEXT_COLOR"])

        btn_bg = "#333333" if self.is_dark_mode.get() else "#F8FAFC"
        btn_active = "#444444" if self.is_dark_mode.get() else "#E2E8F0"
        style.configure("TButton", font=default_font, padding=(10, 5), background=btn_bg, borderwidth=1, bordercolor=c["BORDER_COLOR"], relief="flat", foreground=c["TEXT_COLOR"])
        style.map("TButton", background=[("active", btn_active)])

        style.configure("Primary.TButton", font=bold_font, padding=(10, 5), background=c["PRIMARY_COLOR"], foreground="white", borderwidth=0, relief="flat")
        style.map("Primary.TButton", background=[("active", c["PRIMARY_HOVER"])], foreground=[("active", "white")])

        style.configure("Success.TButton", font=("Malgun Gothic", 12, "bold"), padding=(10, 8), background=c["SUCCESS_COLOR"], foreground="white", borderwidth=0, relief="flat")
        style.map("Success.TButton", background=[("active", c["SUCCESS_HOVER"])], foreground=[("active", "white")])

        tree_bg = "#1E1E1E" if self.is_dark_mode.get() else "#FFFFFF"
        tree_head_bg = "#2D2D30" if self.is_dark_mode.get() else "#F8FAFC"
        tree_sel_bg = "#37373D" if self.is_dark_mode.get() else "#EEF2FF"
        tree_sel_fg = "#A5B4FC" if self.is_dark_mode.get() else c["PRIMARY_COLOR"]
        
        style.configure("Treeview", font=default_font, rowheight=30, background=tree_bg, fieldbackground=tree_bg, foreground=c["TEXT_COLOR"], borderwidth=0)
        style.configure("Treeview.Heading", font=bold_font, background=tree_head_bg, foreground=c["TEXT_COLOR"], borderwidth=1, bordercolor=c["BORDER_COLOR"], padding=5)
        style.map("Treeview", background=[('selected', tree_sel_bg)], foreground=[('selected', tree_sel_fg)])
        
        # 트리 폰트 태그 재설정
        self.tree.tag_configure("modified", foreground=c["DANGER_COLOR"], font=("Malgun Gothic", 10, "bold"))
        self.tree.tag_configure("default", foreground=c["TEXT_COLOR"], font=("Malgun Gothic", 10))

        scroll_bg = "#444" if self.is_dark_mode.get() else "#CBD5E1"
        scroll_trough = tree_head_bg
        style.configure("TScrollbar", background=scroll_bg, troughcolor=scroll_trough, borderwidth=0, arrowsize=12, relief="flat")
        style.map("TScrollbar", background=[("active", "#666" if self.is_dark_mode.get() else "#94A3B8")])

        # Canvas 및 하위 위젯 갱신
        if hasattr(self, 'canvas_orig') and self.canvas_orig:
            self.canvas_orig.configure(bg=c["PANEL_BG"], highlightbackground=c["BORDER_COLOR"])
            self.canvas_res.configure(bg=c["PANEL_BG"], highlightbackground=c["BORDER_COLOR"])
            self.update_preview()

        if hasattr(self, 'lbl_input_info') and self.lbl_input_info:
            self.lbl_input_info.configure(foreground=c["PRIMARY_COLOR"])

    def setup_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # 설정 메뉴
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="⚙️ 설정", menu=settings_menu)
        
        settings_menu.add_checkbutton(label="다크 모드 적용", variable=self.is_dark_mode, command=self.apply_theme)
        settings_menu.add_checkbutton(label="항상 맨 위에 띄우기", variable=self.is_always_on_top, command=self.toggle_always_on_top)
        settings_menu.add_separator()
        settings_menu.add_command(label="창 투명도 조절...", command=self.show_transparency_dialog)

        # Aseprite 메뉴
        aseprite_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="🎨 Aseprite", menu=aseprite_menu)
        aseprite_menu.add_command(label="Aseprite 연동 도구 열기...", command=self.show_aseprite_tools)

        # 도움말 메뉴
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="❓ 도움말", menu=help_menu)
        help_menu.add_command(label="사용 설명서 (매뉴얼)", command=self.show_manual)
        
    def toggle_always_on_top(self):
        """선택 시 창이 항상 최상단에 고정되도록 합니다."""
        self.root.attributes('-topmost', self.is_always_on_top.get())

    def show_transparency_dialog(self):
        """슬라이더(Scale)를 이용해 창 투명도를 직관적이고 실시간으로 조절합니다."""
        trans_win = tk.Toplevel(self.root)
        trans_win.title("투명도 조절")
        trans_win.geometry("300x120")
        trans_win.resizable(False, False)
        if self.is_always_on_top.get():
            trans_win.attributes('-topmost', True)
        
        c = self.get_colors()
        trans_win.configure(bg=c["PANEL_BG"])
        
        lbl = ttk.Label(trans_win, text="슬라이더를 움직여 투명도를 조절하세요\n(0.1 ~ 1.0)", justify="center", font=("Malgun Gothic", 10))
        lbl.pack(pady=(15, 5))
        
        def on_slider_change(val):
            alpha = float(val)
            self.window_alpha.set(alpha)
            self.root.attributes('-alpha', alpha)
            
        slider = ttk.Scale(trans_win, from_=0.1, to=1.0, orient="horizontal", command=on_slider_change)
        slider.set(self.window_alpha.get())
        slider.pack(fill="x", padx=30, pady=10)

    def show_manual(self):
        """사용 설명서를 팝업 창에 띄워줍니다."""
        manual_win = tk.Toplevel(self.root)
        manual_win.title("Pivot Fixer 사용 설명서")
        manual_win.geometry("750x650")
        manual_win.minsize(500, 400)
        # 매뉴얼 창도 메인 윈도우와 동일한 최상단 속성 부여
        if self.is_always_on_top.get():
            manual_win.attributes('-topmost', True)
        
        c = self.get_colors()
        manual_win.configure(bg=c["BG_COLOR"])
        
        txt = tk.Text(manual_win, font=("Malgun Gothic", 10), wrap="word", bg=c["PANEL_BG"], fg=c["TEXT_COLOR"], padx=20, pady=20, borderwidth=0)
        txt.pack(expand=True, fill="both", padx=10, pady=10)
        
        manual_text = """[ 🎨 PNG 피봇 보정 툴 (Pivot Fixer) 사용 설명서 ]

1. 개요
게임 개발, 스프라이트 애니메이션 프레임 작업 시 캐릭터나 오브젝트의 
'피봇(발밑 기준점)'을 캔버스 정중앙에 정확하게 맞춰주는 전문 최적화 툴입니다.

2. 작업 파일 목록 (다중 파일 제어)
- 윈도우 탐색기나 바탕화면에서 이미지를 리스트 창으로 '드래그 앤 드롭' 하세요.
- 일반 폴더처럼 Ctrl이나 Shift를 누른 채 클릭하여 여러 파일을 [다중 선택(파란색)] 할 수 있습니다.
- 목록에서 파일 이름을 더블클릭하면 툴 내부에서 즉시 새 이름으로 변경 예약이 가능합니다.

3. ⚡ 실시간 자동 설정 연동 (가장 중요)
- 목록에서 파일(들)을 파란색으로 선택해둔 상태로 상단의 '보정 및 변환 설정'을 만져보세요.
- '적용' 버튼을 누를 필요 없이 선택된 파일들의 설정값이 변경된 값으로 즉각 자동 저장됩니다.
- 각 파일마다 완전히 다른 오프셋이나 회전값을 개별적으로 줄 수 있습니다.

4. 캔버스 자동 확장 및 방어 시스템
- 처리된 이미지가 엔진에서 잘리지 않도록, 결과물은 기본적으로 원본의 2배 크기(정사각형)로 안전하게 확장됩니다.
- 피봇값을 엄청 크게(+100) 밀어서 이미지가 화면 밖으로 나가려 할 경우, 툴이 이를 감지하고 스스로 캔버스 크기를 3배, 4배로 넓혀 픽셀 손실을 방지합니다.

5. 메인 작업 실행 및 저장 옵션
- [원본 파일 덮어쓰기]: 대량의 프레임을 작업할 때 매우 추천합니다. 빠른 덮어쓰기 후 기존 이름을 유지합니다.
- [단일 폴더 취합]: 여러 폴더에 흩어져 있던 이미지들을 한 폴더에 쫙 모아서 이름 뒤에 '_pivotfix'를 붙여 뽑아줍니다.
- [마지막 작업 되돌리기]: 방금 생성된 새 파일들을 즉시 삭제(복구)해 줍니다. 단, 원본 덮어쓰기 모드에서는 사용할 수 없습니다.

* 문의나 버그 제보는 개발팀으로 언제든지 전달해 주세요!"""
        
        txt.insert("1.0", manual_text)
        txt.config(state="disabled")
    def get_current_ui_settings(self):
        """현재 UI에 입력된 설정값을 딕셔너리로 반환합니다 (문자열 값은 정수로 안전하게 캐스팅)"""
        try:
            oy = int(self.offset_y.get() or 0)
        except (ValueError, TypeError):
            oy = 0

        try:
            ox = int(self.offset_x.get() or 0)
        except (ValueError, TypeError):
            ox = 0

        return {
            "offset_y": oy,
            "offset_x": ox,
            "h_align": self.h_align.get(),
            "trim_margin_x": self.trim_margin_x.get(),
            "flip_h": self.flip_h.get(),
            "flip_v": self.flip_v.get(),
            "rotate_angle": self.rotate_angle.get(),
            "transform_order": self.transform_order.get()
        }

    def format_settings_summary(self, s):
        parts = []
        if s["offset_y"] != 0 or s["offset_x"] != 0:
            parts.append(f"Y:{s['offset_y']} X:{s['offset_x']}")
        if not s["h_align"]: parts.append("정렬OFF")
        if s["trim_margin_x"]: parts.append("여백X")
        if s["flip_h"]: parts.append("가로반전")
        if s["flip_v"]: parts.append("세로반전")
        if "0도" not in s["rotate_angle"]: parts.append(s["rotate_angle"].split()[0])
        
        if not parts: return "━ [ 기본값 ]"
        return f"━ [ {' | '.join(parts)} ]"

    def setup_ui(self):
        main_container = ttk.Frame(self.root, style="TFrame")
        main_container.pack(fill="both", expand=True, padx=20, pady=20)

        # ==========================================
        # 1. 상단 패널: 보정 및 변환 설정
        # ==========================================
        frame_top = ttk.LabelFrame(main_container, text=" ⚙️ 보정 및 변환 설정 (현재 UI 설정값) ")
        frame_top.pack(side="top", fill="x", pady=(0, 15))

        frame_top_inner = ttk.Frame(frame_top, style="Panel.TFrame")
        frame_top_inner.pack(fill="x", padx=10, pady=10)

        # [1-1] 이미지 변환 구역
        frame_transform = ttk.Frame(frame_top_inner, style="Panel.TFrame")
        frame_transform.pack(side="left", fill="y", padx=(0, 20))

        ttk.Label(frame_transform, text="[ 변환 적용 시점 ]", font=("Malgun Gothic", 9, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))
        ttk.Radiobutton(frame_transform, text="변환 후 피봇 보정 (추천)", variable=self.transform_order, value="before").grid(row=1, column=0, sticky="w", padx=(0, 15))
        ttk.Radiobutton(frame_transform, text="피봇 보정 후 캔버스 회전", variable=self.transform_order, value="after").grid(row=1, column=1, sticky="w")

        ttk.Label(frame_transform, text="[ 반전 및 회전 ]", font=("Malgun Gothic", 9, "bold")).grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 5))
        
        frame_flip_rot = ttk.Frame(frame_transform, style="Panel.TFrame")
        frame_flip_rot.grid(row=3, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(frame_flip_rot, text="가로 뒤집기", variable=self.flip_h).pack(side="left", padx=(0, 15))
        ttk.Checkbutton(frame_flip_rot, text="세로 뒤집기", variable=self.flip_v).pack(side="left", padx=(0, 15))
        
        ttk.Label(frame_flip_rot, text="회전 각도:").pack(side="left")
        rot_values = ["0도 (회전 없음)", "90도 (시계방향)", "180도", "270도 (시계방향)"]
        cb_rot = ttk.Combobox(frame_flip_rot, textvariable=self.rotate_angle, values=rot_values, state="readonly", width=16)
        cb_rot.pack(side="left", padx=5)

        ttk.Separator(frame_top_inner, orient="vertical").pack(side="left", fill="y", padx=20)

        # [1-2] 피봇 조절 구역
        frame_pivot = ttk.Frame(frame_top_inner, style="Panel.TFrame")
        frame_pivot.pack(side="left", fill="y")

        ttk.Label(frame_pivot, text="[ 피봇 위치 조절 ]", font=("Malgun Gothic", 9, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 5))
        
        ttk.Label(frame_pivot, text="세로 오프셋:").grid(row=1, column=0, sticky="w", pady=2)
        sb_y = ttk.Spinbox(frame_pivot, from_=-9999, to=9999, textvariable=self.offset_y, width=8)
        sb_y.grid(row=1, column=1, sticky="w", padx=10, pady=2)

        ttk.Label(frame_pivot, text="가로 오프셋:").grid(row=2, column=0, sticky="w", pady=2)
        sb_x = ttk.Spinbox(frame_pivot, from_=-9999, to=9999, textvariable=self.offset_x, width=8)
        sb_x.grid(row=2, column=1, sticky="w", padx=10, pady=2)

        ttk.Checkbutton(frame_pivot, text="좌우 알파 Bbox 중앙 자동 맞춤", variable=self.h_align).grid(row=1, column=2, sticky="w", padx=(20, 0))
        ttk.Checkbutton(frame_pivot, text="최종 캔버스 좌우 여백 최소화", variable=self.trim_margin_x).grid(row=2, column=2, sticky="w", padx=(20, 0))

        # [1-3] 메인 실행 버튼 구역
        frame_actions = ttk.Frame(frame_top_inner, style="Panel.TFrame")
        frame_actions.pack(side="right", fill="y", padx=(10, 0))
        
        ttk.Label(frame_actions, text="[ 메인 작업 실행 ]", font=("Malgun Gothic", 9, "bold")).pack(side="top", fill="x", pady=(0, 5))
        
        ttk.Button(frame_actions, text="▶ 체크된 파일 일괄 처리 시작", style="Success.TButton", command=self.run_batch).pack(side="top", fill="x", pady=(0, 2))
        
        btn_sub_frame = ttk.Frame(frame_actions, style="Panel.TFrame")
        btn_sub_frame.pack(side="top", fill="x", pady=(0, 2))
        ttk.Button(btn_sub_frame, text="🌐 모든 파일에 현재설정 덮어쓰기", style="Primary.TButton", command=self.apply_settings_to_all).pack(side="left", fill="x", expand=True, padx=(0, 2))
        ttk.Button(btn_sub_frame, text="🎨 Aseprite 도구 열기", command=self.show_aseprite_tools).pack(side="left", fill="x", expand=True, padx=(2, 0))
        
        self.btn_undo = ttk.Button(frame_actions, text="↩ 마지막 작업 되돌리기", command=self.undo_batch)
        self.btn_undo.pack(side="top", fill="x")

        # ==========================================
        # 2. 하단 패널: PanedWindow
        # ==========================================
        self.paned_main = ttk.PanedWindow(main_container, orient=tk.HORIZONTAL)
        self.paned_main.pack(fill="both", expand=True)

        frame_left = ttk.Frame(self.paned_main, style="TFrame")
        self.paned_main.add(frame_left, weight=1)

        # 2-1: 저장 옵션
        lf_save = ttk.LabelFrame(frame_left, text=" 💾 저장 옵션 ")
        lf_save.pack(fill="x", pady=(0, 10))

        ttk.Checkbutton(lf_save, text="원본 파일에 덮어쓰기 (!주의)", variable=self.overwrite, command=self.toggle_overwrite).pack(anchor="w", padx=10, pady=(10, 5))
        
        frame_save_mode = ttk.Frame(lf_save, style="Panel.TFrame")
        frame_save_mode.pack(fill="x", padx=10, pady=5)
        self.rb_orig = ttk.Radiobutton(frame_save_mode, text="각 원본 폴더 저장", variable=self.save_mode, value="original", command=self.toggle_save_mode)
        self.rb_orig.pack(side="left", padx=(0, 10))
        self.rb_single = ttk.Radiobutton(frame_save_mode, text="단일 폴더 취합", variable=self.save_mode, value="single", command=self.toggle_save_mode)
        self.rb_single.pack(side="left")

        frame_dir = ttk.Frame(lf_save, style="Panel.TFrame")
        frame_dir.pack(fill="x", padx=10, pady=5)
        self.btn_out_dir = ttk.Button(frame_dir, text="📁 폴더 선택", command=self.select_output_dir)
        self.btn_out_dir.pack(side="left")
        self.lbl_out_dir = ttk.Label(frame_dir, text="[미지정]", style="Muted.TLabel")
        self.lbl_out_dir.pack(side="left", padx=10, fill="x", expand=True)
        
        self.toggle_save_mode() 

        # 2-2: 작업 파일 목록
        lf_list = ttk.LabelFrame(frame_left, text=" 📂 작업 파일 목록 (Ctrl/Shift 다중 선택 지원) ")
        lf_list.pack(fill="both", expand=True, pady=(0, 10))

        self.lbl_input_info = ttk.Label(lf_list, text="체크됨: 0개 / 전체: 0개", font=("Malgun Gothic", 10, "bold"))
        self.lbl_input_info.pack(side="bottom", pady=(5, 10))

        frame_btns = ttk.Frame(lf_list, style="Panel.TFrame")
        frame_btns.pack(side="top", fill="x", padx=10, pady=(10, 5))
        ttk.Button(frame_btns, text="파일/폴더 열기", command=self.load_files_dialog, style="Primary.TButton").pack(side="left", expand=True, fill="x", padx=(0, 5))
        ttk.Button(frame_btns, text="선택 항목 비우기", command=self.clear_list).pack(side="right", fill="x")

        frame_check_btns = ttk.Frame(lf_list, style="Panel.TFrame")
        frame_check_btns.pack(side="top", fill="x", padx=10, pady=(0, 5))
        ttk.Button(frame_check_btns, text="☑ 전체 체크", command=self.check_all).pack(side="left", expand=True, fill="x", padx=(0, 2))
        ttk.Button(frame_check_btns, text="☐ 체크 해제", command=self.uncheck_all).pack(side="right", expand=True, fill="x", padx=(2, 0))

        ttk.Label(lf_list, text="* 더블클릭: 이름 변경 / 클릭: 설정 불러오기", style="Muted.TLabel").pack(side="top", pady=(0, 5))

        frame_list_inner = ttk.Frame(lf_list, style="Panel.TFrame")
        frame_list_inner.pack(side="top", expand=True, fill="both", padx=10, pady=(0, 5))
        
        scrollbar = ttk.Scrollbar(frame_list_inner)
        scrollbar.pack(side="right", fill="y")
        
        self.tree = ttk.Treeview(frame_list_inner, columns=("check", "name", "settings"), show="headings", yscrollcommand=scrollbar.set, selectmode="extended")
        self.tree.heading("check", text="처리")
        self.tree.column("check", width=40, anchor="center", stretch=False)
        self.tree.heading("name", text="파일 이름", anchor="w")
        self.tree.column("name", width=150, anchor="w", stretch=True)
        self.tree.heading("settings", text="적용된 설정", anchor="w")
        self.tree.column("settings", width=180, anchor="w", stretch=True)
        self.tree.pack(side="left", expand=True, fill="both")
        scrollbar.config(command=self.tree.yview)

        self.tree.bind('<ButtonRelease-1>', self.on_tree_click)
        self.tree.bind('<<TreeviewSelect>>', self.on_tree_select)
        self.tree.bind('<Double-Button-1>', self.on_tree_double_click) 

        # 드래그 앤 드롭 인식률 강화를 위해 개별 위젯에도 직접 바인딩
        self.tree.drop_target_register(DND_FILES)
        self.tree.dnd_bind('<<Drop>>', self.on_drop)
        self.paned_main.drop_target_register(DND_FILES)
        self.paned_main.dnd_bind('<<Drop>>', self.on_drop)

        # --- 하단 우측 (실시간 미리보기) ---
        frame_right = ttk.LabelFrame(self.paned_main, text=" 👁️ 실시간 미리보기 (현재 설정 반영) ")
        self.paned_main.add(frame_right, weight=3) 

        frame_right_lbls = ttk.Frame(frame_right, style="Panel.TFrame")
        frame_right_lbls.pack(fill="x", padx=10, pady=(10, 5))
        
        frame_orig_title = ttk.Frame(frame_right_lbls, style="Panel.TFrame")
        frame_orig_title.pack(side="left", expand=True)
        ttk.Label(frame_orig_title, text="[ 원본 캔버스 ]", font=("Malgun Gothic", 10, "bold")).pack(side="top")
        self.lbl_orig_dim = ttk.Label(frame_orig_title, text="(0 x 0 px)", style="Muted.TLabel")
        self.lbl_orig_dim.pack(side="top")

        frame_res_title = ttk.Frame(frame_right_lbls, style="Panel.TFrame")
        frame_res_title.pack(side="left", expand=True)
        ttk.Label(frame_res_title, text="[ 변환 및 보정 완료 ]", font=("Malgun Gothic", 10, "bold")).pack(side="top")
        self.lbl_res_dim = ttk.Label(frame_res_title, text="(0 x 0 px)", style="Muted.TLabel")
        self.lbl_res_dim.pack(side="top")

        self.frame_canvases = ttk.Frame(frame_right, style="Panel.TFrame")
        self.frame_canvases.pack(expand=True, fill="both", padx=10, pady=(0, 10))
        
        # 캔버스는 초기화 시 빈 객체로 생성, 나중에 apply_theme에서 색상 부여
        self.canvas_orig = tk.Canvas(self.frame_canvases, bd=0, highlightthickness=1, relief="flat")
        self.canvas_orig.pack(side="left", expand=True, fill="both", padx=(0, 5))

        self.canvas_res = tk.Canvas(self.frame_canvases, bd=0, highlightthickness=1, relief="flat")
        self.canvas_res.pack(side="left", expand=True, fill="both", padx=(5, 0))

        self.frame_canvases.bind("<Configure>", self.on_canvas_resize)

    # ------------------ 기능 메서드 ------------------

    def apply_settings_to_all(self):
        if not self.file_data:
            messagebox.showwarning("안내", "목록에 파일이 없습니다.")
            return

        ans = messagebox.askyesno("확인", "현재 설정되어 있는 옵션들을 목록에 있는 모든 파일에 일괄 적용하시겠습니까?\n(각 파일들의 기존 설정값은 덮어씌워집니다)")
        if not ans: return

        current_settings = self.get_current_ui_settings()
        
        for f in self.file_data:
            f["settings"] = current_settings.copy()
            self._update_tree_item(f)
            
        self.update_preview()
        messagebox.showinfo("완료", "모든 파일에 설정이 일괄 덮어씌워졌습니다.")

    def on_ui_change(self, event=None):
        if not self._is_updating_ui:
            selected_items = self.tree.selection()
            if selected_items:
                current_settings = self.get_current_ui_settings()
                
                for item_id in selected_items:
                    for f in self.file_data:
                        if f["id"] == item_id:
                            f["settings"] = current_settings.copy()
                            self._update_tree_item(f)
                            break
                            
            self.update_preview()

    def on_canvas_resize(self, event):
        if str(event.widget) == str(self.frame_canvases):
            if self._resize_timer:
                self.root.after_cancel(self._resize_timer)
            self._resize_timer = self.root.after(200, self.update_preview)

    def draw_checkerboard(self, canvas, width, height, size=10):
        canvas.delete("checkerboard")
        is_dark = self.is_dark_mode.get()
        color1 = "#ffffff" if not is_dark else "#2A2A2A"
        color2 = "#f1f5f9" if not is_dark else "#202020"
        
        for y in range(0, height, size):
            for x in range(0, width, size):
                color = color1 if ((x//size) + (y//size)) % 2 == 0 else color2
                canvas.create_rectangle(x, y, x+size, y+size, fill=color, outline="", tags="checkerboard")
        canvas.tag_lower("checkerboard")

    def toggle_overwrite(self):
        if self.overwrite.get():
            self.rb_orig.state(['disabled'])
            self.rb_single.state(['disabled'])
            self.btn_out_dir.state(['disabled'])
            self.btn_undo.state(['disabled'])
            self.lbl_out_dir.config(text="원본 파일에 덮어씁니다.\n되돌릴 수 없으니 주의하세요!")
        else:
            self.rb_orig.state(['!disabled'])
            self.rb_single.state(['!disabled'])
            self.btn_undo.state(['!disabled'])
            self.toggle_save_mode()

    def toggle_save_mode(self):
        if not self.overwrite.get():
            if self.save_mode.get() == "single":
                self.btn_out_dir.state(['!disabled'])
                if self.output_dir:
                    self.lbl_out_dir.config(text=self.output_dir)
                else:
                    self.lbl_out_dir.config(text="[폴더 미지정]")
            else:
                self.btn_out_dir.state(['disabled'])
                self.lbl_out_dir.config(text="기본값: 원본 폴더에 '_pivotfix' 추가")

    def update_selection_info(self):
        checked_count = sum(1 for f in self.file_data if f["checked"])
        total_count = len(self.file_data)
        self.lbl_input_info.config(text=f"체크됨: {checked_count}개 / 전체: {total_count}개")

    def load_files_dialog(self):
        paths = filedialog.askopenfilenames(filetypes=[("PNG Files", "*.png")])
        if paths:
            self.add_paths_to_list(paths)

    def on_drop(self, event):
        paths = self.root.tk.splitlist(event.data)
        if not paths: return
        
        png_files = []
        for p in paths:
            if os.path.isdir(p):
                png_files.extend(glob.glob(os.path.join(p, "*.png")))
            elif p.lower().endswith(".png"):
                png_files.append(p)
                
        if png_files:
            self.add_paths_to_list(png_files)
        else:
            messagebox.showwarning("안내", "PNG 파일이 발견되지 않았습니다.")

    def add_paths_to_list(self, new_paths):
        first_new_id = None
        current_settings = self.get_current_ui_settings()

        for p in new_paths:
            p_norm = os.path.normpath(p)
            if not any(f["path"] == p_norm for f in self.file_data):
                name = os.path.basename(p_norm)
                item_id = self.tree.insert("", tk.END, values=("☑", name, ""))
                
                f_data = {
                    "id": item_id, 
                    "path": p_norm, 
                    "name": name, 
                    "checked": True,
                    "settings": current_settings.copy()
                }
                self.file_data.append(f_data)
                self._update_tree_item(f_data)
                
                if first_new_id is None:
                    first_new_id = item_id
                
        self.update_selection_info()
        
        if first_new_id and not self.preview_path:
            self.tree.selection_set(first_new_id)
            self.tree.focus(first_new_id)

    def on_tree_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        column = self.tree.identify_column(event.x)
        
        if region == "cell" and column == "#1":
            item_id = self.tree.identify_row(event.y)
            if item_id:
                for f in self.file_data:
                    if f["id"] == item_id:
                        f["checked"] = not f["checked"]
                        self._update_tree_item(f)
                        self.update_selection_info()
                        break

    def on_tree_select(self, event):
        selection = self.tree.selection()
        if len(selection) == 1:
            item_id = selection[0]
            for f in self.file_data:
                if f["id"] == item_id:
                    self._is_updating_ui = True 
                    try:
                        s = f["settings"]
                        
                        self.offset_y.set(str(s["offset_y"]))
                        self.offset_x.set(str(s["offset_x"]))
                        self.h_align.set(s["h_align"])
                        self.trim_margin_x.set(s["trim_margin_x"])
                        self.flip_h.set(s["flip_h"])
                        self.flip_v.set(s["flip_v"])
                        self.rotate_angle.set(s["rotate_angle"])
                        self.transform_order.set(s["transform_order"])
                        
                        self.preview_path = f["path"]
                    finally:
                        self._is_updating_ui = False
                    
                    self.update_preview()
                    break

    def on_tree_double_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        column = self.tree.identify_column(event.x)
        
        if region == "cell" and column == "#2":
            item_id = self.tree.identify_row(event.y)
            if not item_id: return
            
            target_f = None
            for f in self.file_data:
                if f["id"] == item_id:
                    target_f = f
                    break
                    
            if not target_f: return
            
            old_name = target_f["name"]
            
            new_name = simpledialog.askstring("이름 변경", "저장될 새 파일 이름을 입력하세요:", initialvalue=old_name, parent=self.root)
            
            if new_name and new_name != old_name:
                if not new_name.lower().endswith(".png"):
                    new_name += ".png"
                    
                target_f["name"] = new_name
                self._update_tree_item(target_f)

    def check_all(self):
        for f in self.file_data:
            if not f["checked"]:
                f["checked"] = True
                self._update_tree_item(f)
        self.update_selection_info()

    def uncheck_all(self):
        for f in self.file_data:
            if f["checked"]:
                f["checked"] = False
                self._update_tree_item(f)
        self.update_selection_info()

    def clear_list(self):
        checked_files = [f for f in self.file_data if f["checked"]]
        
        if checked_files:
            for f in checked_files:
                self.tree.delete(f["id"])
                
            self.file_data = [f for f in self.file_data if not f["checked"]]
            
            if not any(f["path"] == self.preview_path for f in self.file_data):
                self.preview_path = None
                self.canvas_orig.delete("all")
                self.canvas_res.delete("all")
                self.lbl_orig_dim.config(text="(0 x 0 px)")
                self.lbl_res_dim.config(text="(0 x 0 px)")
            
            self.update_selection_info()
            return
            
        ans = messagebox.askyesno("안내", "체크된(☑) 파일이 없습니다.\n목록 전체를 비우시겠습니까?")
        if ans:
            self.file_data.clear()
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.preview_path = None
            self.update_selection_info()
            self.canvas_orig.delete("all")
            self.canvas_res.delete("all")
            self.lbl_orig_dim.config(text="(0 x 0 px)")
            self.lbl_res_dim.config(text="(0 x 0 px)")

    def select_output_dir(self):
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.output_dir = folder_path
            self.save_mode.set("single")
            self.toggle_save_mode()

    def get_alpha_bbox(self, img):
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        return img.split()[-1].getbbox()

    def apply_transformations(self, img, flip_h, flip_v, rot_val):
        if flip_h:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        if flip_v:
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
            
        if "90도" in rot_val:
            img = img.transpose(Image.ROTATE_270)
        elif "180도" in rot_val:
            img = img.transpose(Image.ROTATE_180)
        elif "270도" in rot_val:
            img = img.transpose(Image.ROTATE_90)
            
        return img

    def process_image(self, img, s):
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        if s["transform_order"] == "before":
            img = self.apply_transformations(img, s["flip_h"], s["flip_v"], s["rotate_angle"])
            
        W, H = img.size
        bbox = self.get_alpha_bbox(img)
        
        if bbox is None:
            left, upper, right, lower = 0, 0, W, H
            crop_img = img.copy()
        else:
            left, upper, right, lower = bbox
            crop_img = img.crop(bbox)

        cW, cH = crop_img.size

        if s["h_align"]:
            rel_x = -(cW // 2) + s["offset_x"]
        else:
            rel_x = left - (W // 2) + s["offset_x"]

        rel_y = -cH - s["offset_y"]

        need_left = max(0, -rel_x)
        need_right = max(0, rel_x + cW)
        need_top = max(0, -rel_y)
        need_bottom = max(0, rel_y + cH)

        if not s.get("trim_margin_x", False):
            # 기본 모드: 정사각형 캔버스 강제
            half_size = max(need_left, need_right, need_top, need_bottom)
            nW = half_size * 2
            nH = half_size * 2
        else:
            # 여백 최소화 모드: 세로는 안정 높이 유지, 가로는 필요한 만큼만 할당 (직사각형 가능)
            half_h = max(need_left, need_right, need_top, need_bottom)
            half_w = max(need_left, need_right)
            nW = half_w * 2
            nH = half_h * 2

        nW = max(nW, 2)
        nH = max(nH, 2)

        if nW % 2 != 0:
            nW += 1
        if nH % 2 != 0:
            nH += 1

        pivot_x = nW // 2
        pivot_y = nH // 2

        paste_x = pivot_x + rel_x
        paste_y = pivot_y + rel_y

        new_img = Image.new("RGBA", (nW, nH), (0, 0, 0, 0))
        new_img.paste(crop_img, (paste_x, paste_y))

        if s["transform_order"] == "after":
            new_img = self.apply_transformations(new_img, s["flip_h"], s["flip_v"], s["rotate_angle"])

        return new_img

    def resize_for_preview(self, img, max_w, max_h):
        w, h = img.size
        ratio = min(max_w / w, max_h / h)
        if ratio >= 1: ratio = int(ratio)
        new_w = max(1, int(w * ratio))
        new_h = max(1, int(h * ratio))
        return img.resize((new_w, new_h), Image.Resampling.NEAREST)

    def update_preview(self):
        self.canvas_orig.delete("all")
        self.canvas_res.delete("all")
        
        c_w = self.canvas_orig.winfo_width()
        c_h = self.canvas_orig.winfo_height()
        
        if c_w <= 1 or c_h <= 1: return

        self.draw_checkerboard(self.canvas_orig, c_w, c_h)
        self.draw_checkerboard(self.canvas_res, c_w, c_h)

        if not self.preview_path or not os.path.exists(self.preview_path):
            return

        try:
            img = Image.open(self.preview_path).convert("RGBA")
            
            current_settings = self.get_current_ui_settings()
            res_img = self.process_image(img, current_settings)

            self.lbl_orig_dim.config(text=f"({img.width} x {img.height} px)")
            self.lbl_res_dim.config(text=f"({res_img.width} x {res_img.height} px)")

            safe_w = c_w - 40
            safe_h = c_h - 40
            if safe_w < 10 or safe_h < 10: return
            
            cx = c_w // 2
            cy = c_h // 2

            img_preview = self.resize_for_preview(img, safe_w, safe_h)
            self.tk_orig = ImageTk.PhotoImage(img_preview)
            self.canvas_orig.create_image(cx, cy, image=self.tk_orig, anchor="center", tags="preview_image")

            orig_w, orig_h = img_preview.width, img_preview.height
            orig_x1 = cx - (orig_w // 2)
            orig_y1 = cy - (orig_h // 2)
            orig_x2 = orig_x1 + orig_w
            orig_y2 = orig_y1 + orig_h
            outline_color = "#ef4444" if not self.is_dark_mode.get() else "#F87171"
            self.canvas_orig.create_rectangle(orig_x1, orig_y1, orig_x2, orig_y2, outline=outline_color, dash=(2, 2), tags="preview_image")

            res_preview = self.resize_for_preview(res_img, safe_w, safe_h)
            self.tk_res = ImageTk.PhotoImage(res_preview)
            self.canvas_res.create_image(cx, cy, image=self.tk_res, anchor="center", tags="preview_image")

            res_w, res_h = res_preview.width, res_preview.height
            res_x1 = cx - (res_w // 2)
            res_y1 = cy - (res_h // 2)
            res_x2 = res_x1 + res_w
            res_y2 = res_y1 + res_h
            self.canvas_res.create_rectangle(res_x1, res_y1, res_x2, res_y2, outline=outline_color, dash=(2, 2), tags="preview_image")

            cross_color = "#06b6d4" if not self.is_dark_mode.get() else "#22D3EE"
            self.canvas_res.create_line(0, cy, c_w, cy, fill=cross_color, width=1, tags="crosshair")
            self.canvas_res.create_line(cx, 0, cx, c_h, fill=cross_color, width=1, tags="crosshair")
            
        except Exception as e:
            print(f"미리보기 업데이트 실패: {e}")

    def images_are_identical(self, img_a, img_b):
        if img_a.size != img_b.size:
            return False
        if img_a.mode != "RGBA":
            img_a = img_a.convert("RGBA")
        if img_b.mode != "RGBA":
            img_b = img_b.convert("RGBA")
            
        diff = ImageChops.difference(img_a, img_b)
        return diff.getbbox() is None

    def get_unique_backup_path(self, backup_dir, filename):
        name, ext = os.path.splitext(filename)
        base_path = os.path.join(backup_dir, filename)
        if not os.path.exists(base_path):
            return base_path
        
        counter = 1
        while True:
            new_name = f"{name}_{counter:03d}{ext}"
            new_path = os.path.join(backup_dir, new_name)
            if not os.path.exists(new_path):
                return new_path
            counter += 1

    def backup_original_file(self, orig_path):
        backup_dir = os.path.join(os.path.dirname(orig_path), "_pivotfix_backup")
        os.makedirs(backup_dir, exist_ok=True)
        filename = os.path.basename(orig_path)
        backup_path = self.get_unique_backup_path(backup_dir, filename)
        shutil.copy2(orig_path, backup_path)
        return backup_path

    def open_folder(self, path):
        try:
            os.startfile(path)
        except Exception as e:
            messagebox.showerror("오류", f"폴더 열기 실패:\n{e}")

    def show_batch_result_log(self, total_count, success_count, skipped_count, failure_logs, skipped_logs, output_dirs, mode_text):
        log_win = tk.Toplevel(self.root)
        log_win.title("처리 결과 보고서")
        log_win.geometry("560x520")
        log_win.minsize(520, 460)
        if self.is_always_on_top.get():
            log_win.attributes('-topmost', True)
        
        c = self.get_colors()
        log_win.configure(bg=c["BG_COLOR"])
        
        main_frame = ttk.Frame(log_win, style="TFrame")
        main_frame.pack(fill="both", expand=True, padx=20, pady=15)
        
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(2, weight=1)
        
        lbl_title = ttk.Label(main_frame, text="[ 작업 처리 완료 ]", font=("Malgun Gothic", 11, "bold"), foreground=c["PRIMARY_COLOR"])
        lbl_title.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        
        fail_count = len(failure_logs)
        
        summary_frame = ttk.Frame(main_frame, style="Panel.TFrame")
        summary_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        
        ttk.Label(summary_frame, text=f"• 전체 대상 파일: {total_count}개").pack(anchor="w", padx=10, pady=2)
        ttk.Label(summary_frame, text=f"• 성공: {success_count}개", foreground=c["SUCCESS_COLOR"], font=("Malgun Gothic", 10, "bold")).pack(anchor="w", padx=10, pady=2)
        ttk.Label(summary_frame, text=f"• 변경 없음 / 건너뜀: {skipped_count}개").pack(anchor="w", padx=10, pady=2)
        ttk.Label(summary_frame, text=f"• 실패: {fail_count}개", foreground=c["DANGER_COLOR"] if fail_count > 0 else c["TEXT_COLOR"]).pack(anchor="w", padx=10, pady=2)
        ttk.Label(summary_frame, text=f"• 저장 방식: {mode_text}").pack(anchor="w", padx=10, pady=2)

        if failure_logs or skipped_logs:
            detail_frame = ttk.LabelFrame(main_frame, text=" ⚠️ 세부 내역 ")
            detail_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
            
            scrollbar = ttk.Scrollbar(detail_frame)
            scrollbar.pack(side="right", fill="y")
            
            txt = tk.Text(detail_frame, font=("Malgun Gothic", 9), bg=c["PANEL_BG"], fg=c["TEXT_COLOR"], wrap="word", borderwidth=0, yscrollcommand=scrollbar.set)
            txt.pack(side="left", expand=True, fill="both", padx=10, pady=10)
            scrollbar.config(command=txt.yview)
            
            if failure_logs:
                txt.insert("end", "[ 실패 목록 ]\n")
                for i, log in enumerate(failure_logs):
                    if i >= 10:
                        txt.insert("end", f"... 외 {fail_count - 10}개 실패\n")
                        break
                    txt.insert("end", f"- {os.path.basename(log['file'])}: {log['reason']}\n")
                txt.insert("end", "\n")
                
            if skipped_logs:
                txt.insert("end", "[ 변경 없음 / 건너뜀 목록 ]\n")
                for i, log in enumerate(skipped_logs):
                    if i >= 10:
                        txt.insert("end", f"... 외 {skipped_count - 10}개 건너뜀\n")
                        break
                    txt.insert("end", f"- {os.path.basename(log)}\n")
                    
            txt.config(state="disabled")
        else:
            empty_frame = ttk.Frame(main_frame, style="TFrame")
            empty_frame.grid(row=2, column=0, sticky="nsew")

        btn_frame = ttk.Frame(main_frame, style="TFrame")
        btn_frame.grid(row=3, column=0, sticky="ew")
        
        btn_frame.columnconfigure(0, weight=1)
        
        if output_dirs:
            if len(output_dirs) > 1:
                ttk.Label(btn_frame, text=f"(*저장 폴더 {len(output_dirs)}곳)").grid(row=0, column=0, sticky="w")
            target_dir = list(output_dirs)[0]
            btn_open = ttk.Button(btn_frame, text="결과 폴더 열기", command=lambda d=target_dir: self.open_folder(d), style="Primary.TButton")
            btn_open.grid(row=0, column=1, sticky="e", padx=(0, 5))
            
        btn_close = ttk.Button(btn_frame, text="닫기", command=log_win.destroy)
        btn_close.grid(row=0, column=2, sticky="e")

    def run_batch(self):
        target_files = [f for f in self.file_data if f["checked"]]
        
        if not target_files:
            messagebox.showwarning("안내", "체크된(☑) 파일이 없습니다.\n처리할 파일을 목록에서 체크해주세요.")
            return

        is_overwrite = self.overwrite.get()
        save_mode_val = self.save_mode.get()
        
        if is_overwrite:
            ans = messagebox.askyesno("경고", f"체크된 {len(target_files)}개 원본 파일 자체를 덮어씁니다.\n이 작업은 되돌리기로 복구할 수 없습니다.\n(진행 전 _pivotfix_backup 폴더에 자동 백업됩니다.)\n\n정말로 진행하시겠습니까?")
            if not ans: return
        elif save_mode_val == "single" and not self.output_dir:
            messagebox.showwarning("안내", "단일 폴더 저장 모드가 선택되었지만, 저장할 폴더가 지정되지 않았습니다.\n폴더를 먼저 선택해주세요.")
            return

        success_count = 0
        skipped_count = 0
        failure_logs = []
        skipped_logs = []
        output_dirs = set()
        
        if is_overwrite:
            mode_text = "원본 파일 덮어쓰기 (자동 백업 완료)"
        elif save_mode_val == "single":
            mode_text = "단일 폴더 취합"
        else:
            mode_text = "각 원본 폴더 저장"

        self.last_generated_files.clear()

        for idx, file_info in enumerate(target_files):
            orig_path = file_info["path"]
            target_name = file_info["name"]
            orig_name = os.path.basename(orig_path)
            
            s = file_info["settings"]

            try:
                img = Image.open(orig_path)
                res_img = self.process_image(img, s)
                
                if self.images_are_identical(img, res_img) and target_name == orig_name:
                    skipped_count += 1
                    skipped_logs.append(orig_path)
                    img.close()
                    continue

                if is_overwrite:
                    try:
                        self.backup_original_file(orig_path)
                    except Exception as e:
                        img.close()
                        raise Exception(f"백업 실패: {e}")

                img.close() 
                
                if is_overwrite:
                    save_dir = os.path.dirname(orig_path)
                    save_path = os.path.join(save_dir, target_name)
                    res_img.save(save_path, "PNG")
                    
                    if target_name != orig_name and orig_path != save_path:
                        if os.path.exists(orig_path):
                            try:
                                os.remove(orig_path)
                            except Exception as e:
                                print(f"이전 원본 파일 삭제 실패: {e}")
                    
                    file_info["path"] = save_path
                    if self.preview_path == orig_path:
                        self.preview_path = save_path
                    output_dirs.add(save_dir)
                else:
                    if save_mode_val == "single":
                        save_dir = self.output_dir
                    else: 
                        save_dir = os.path.dirname(orig_path)
                    
                    if target_name == orig_name:
                        name, ext = os.path.splitext(target_name)
                        final_filename = f"{name}_pivotfix.png"
                    else:
                        final_filename = target_name
                        
                    save_path = os.path.join(save_dir, final_filename)
                    self.last_generated_files.append(save_path) 
                    res_img.save(save_path, "PNG")
                    output_dirs.add(save_dir)
                
                success_count += 1
            except Exception as e:
                failure_logs.append({"file": orig_path, "reason": str(e)})
                print(f"파일 처리 실패 ({orig_path}): {e}")
                
            if idx % 10 == 0:
                self.root.update()

        self.show_batch_result_log(len(target_files), success_count, skipped_count, failure_logs, skipped_logs, output_dirs, mode_text)

    def undo_batch(self):
        if self.overwrite.get():
            messagebox.showwarning("경고", "덮어쓰기 모드에서는 파일 삭제(되돌리기) 기능을 사용할 수 없습니다.")
            return
            
        if not self.last_generated_files:
            messagebox.showinfo("안내", "되돌릴 작업 내역이 없습니다.")
            return
            
        confirm = messagebox.askyesno("되돌리기 확인", f"방금 생성된 {len(self.last_generated_files)}개의 _pivotfix.png 파일을 삭제하시겠습니까?")
        if not confirm: return
        
        count = 0
        for path in self.last_generated_files:
            if os.path.exists(path):
                try:
                    os.remove(path)
                    count += 1
                except Exception as e:
                    print(f"삭제 실패 ({path}): {e}")
                    
        self.last_generated_files.clear()
        messagebox.showinfo("되돌리기 완료", f"{count}개의 파일이 안전하게 삭제되었습니다. 🗑️")

    # ------------------ Aseprite 연동 기능 ------------------

    def get_settings_path(self):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "pivot_fixer_settings.json")

    def load_app_settings(self):
        path = self.get_settings_path()
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: pass
        return {}

    def save_app_settings(self, settings):
        path = self.get_settings_path()
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4)
        except: pass

    def validate_aseprite_path(self, path):
        if not path or not os.path.exists(path) or not path.lower().endswith('.exe'):
            return False
        return True

    def auto_detect_aseprite_path(self):
        settings = self.load_app_settings()
        if "aseprite_path" in settings and self.validate_aseprite_path(settings["aseprite_path"]):
            self.aseprite_path.set(settings["aseprite_path"])
            return

        candidates = [
            shutil.which("aseprite"),
            shutil.which("aseprite.exe"),
            "C:/Program Files/Aseprite/Aseprite.exe",
            "C:/Program Files (x86)/Aseprite/Aseprite.exe",
            "C:/Program Files (x86)/Steam/steamapps/common/Aseprite/Aseprite.exe",
            "C:/Program Files/Steam/steamapps/common/Aseprite/Aseprite.exe"
        ]
        for c in candidates:
            if c and self.validate_aseprite_path(c):
                self.aseprite_path.set(c)
                settings["aseprite_path"] = c
                self.save_app_settings(settings)
                return

    def find_aseprite_exe(self):
        path = filedialog.askopenfilename(title="Aseprite.exe 실행 파일 선택", filetypes=[("Executable", "*.exe")])
        if path:
            self.aseprite_path.set(path)
            settings = self.load_app_settings()
            settings["aseprite_path"] = path
            self.save_app_settings(settings)

    def run_aseprite_cli(self, args):
        exe_path = self.aseprite_path.get()
        if not self.validate_aseprite_path(exe_path):
            messagebox.showerror("오류", "유효한 Aseprite.exe 경로가 설정되지 않았습니다.")
            return False, "Invalid Aseprite path"
        
        cmd = [exe_path, "-b"] + args
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
            result = subprocess.run(cmd, capture_output=True, text=True, startupinfo=startupinfo)
            if result.returncode != 0:
                print(f"Aseprite CLI Error: {result.stderr}")
                return False, result.stderr
            return True, result.stdout
        except Exception as e:
            print(f"Aseprite CLI Exception: {e}")
            return False, str(e)

    def create_temp_lua_script(self, content):
        fd, path = tempfile.mkstemp(suffix=".lua", text=True)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(content)
        return path

    def create_aseprite_inspect_lua(self):
        content = """
local app = app
local sprite = app.activeSprite
if not sprite then return end

local function get_layers(layer, prefix, result)
    for _, l in ipairs(layer.layers) do
        local path = prefix .. l.name
        table.insert(result, {name=l.name, path=path, isGroup=l.isGroup, isVisible=l.isVisible})
        if l.isGroup then
            get_layers(l, path .. "/", result)
        end
    end
end

local layers = {}
for _, l in ipairs(sprite.layers) do
    local path = l.name
    table.insert(layers, {name=l.name, path=path, isGroup=l.isGroup, isVisible=l.isVisible})
    if l.isGroup then
        get_layers(l, path .. "/", layers)
    end
end

local tags = {}
for _, t in ipairs(sprite.tags) do
    table.insert(tags, {name=t.name, fromFrame=t.fromFrame.frameNumber, toFrame=t.toFrame.frameNumber})
end

local data = {
    width = sprite.width,
    height = sprite.height,
    frames = #sprite.frames,
    layers = layers,
    tags = tags
}

local function to_json(val)
    local t = type(val)
    if t == "number" or t == "boolean" then
        return tostring(val)
    elseif t == "string" then
        return '"' .. val:gsub('"', '\\"') .. '"'
    elseif t == "table" then
        local is_dict = false
        for k, v in pairs(val) do
            if type(k) == "string" then is_dict = true break end
        end
        if is_dict then
            local items = {}
            for k, v in pairs(val) do
                table.insert(items, '"' .. k .. '":' .. to_json(v))
            end
            return "{" .. table.concat(items, ",") .. "}"
        else
            local items = {}
            for _, v in ipairs(val) do
                table.insert(items, to_json(v))
            end
            return "[" .. table.concat(items, ",") .. "]"
        end
    else
        return "null"
    end
end

local out_path = app.params["output_path"]
if out_path then
    local f = io.open(out_path, "w")
    f:write(to_json(data))
    f:close()
end
"""
        return self.create_temp_lua_script(content)

    def inspect_aseprite_file(self, path):
        if not self.validate_aseprite_path(self.aseprite_path.get()): return None
        script = self.create_aseprite_inspect_lua()
        fd, out_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            args = [path, "--script-param", f"output_path={out_path}", "--script", script]
            ok, _ = self.run_aseprite_cli(args)
            if ok and os.path.exists(out_path):
                with open(out_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return None
        except:
            return None
        finally:
            if os.path.exists(script): os.remove(script)
            if os.path.exists(out_path): os.remove(out_path)

    def export_aseprite_preview_png(self, path, frame=1):
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

    def export_aseprite_preview_png_with_visible_layers(self, path, frame=1, visible_layer_paths=None):
        if visible_layer_paths is None:
            return self.export_aseprite_preview_png(path, frame)
        if not visible_layer_paths:
            print("[Aseprite Layer Preview Export Skipped] visible layer list is empty")
            return None
        if not self.validate_aseprite_path(self.aseprite_path.get()): return None

        import tempfile, glob
        from PIL import Image

        tmp_dir = tempfile.mkdtemp(prefix="pivot_ase_preview_layers_")
        out_path = os.path.join(tmp_dir, "preview.png")

        candidates = []
        candidates.append(max(0, int(frame) - 1))
        candidates.append(max(0, int(frame)))

        for idx in candidates:
            for old in glob.glob(os.path.join(tmp_dir, "*.png")):
                try:
                    os.remove(old)
                except:
                    pass

            args = [path]
            for layer_path in visible_layer_paths:
                args += ["--layer", layer_path]
            args += ["--frame-range", f"{idx},{idx}", "--save-as", out_path]
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
                    print(f"레이어 미리보기 PNG 검증 실패: {p} / {e}")

            if valid_pngs:
                return valid_pngs[0]

            print("[Aseprite Layer Preview Export Failed]")
            print(f"source: {path}")
            print(f"visible layers: {list(visible_layer_paths)}")
            print(f"requested frame: {frame}")
            print(f"tried cli frame index: {idx}")
            print(f"args: {args}")
            print(f"ok: {ok}")
            print(f"log: {log}")
            print(f"tmp_dir files: {[(p, os.path.getsize(p) if os.path.exists(p) else -1) for p in pngs]}")

        return None

    def create_aseprite_pivot_analyze_lua(self):
        content = r'''
local sprite = app.activeSprite
if not sprite then return end

local function read_lines(path)
    local result = {}
    if not path or path == "" then return result end
    local file = io.open(path, "r")
    if not file then return result end
    for line in file:lines() do
        if line ~= "" then
            table.insert(result, line)
        end
    end
    file:close()
    return result
end

local function read_layer_set(path)
    local result = {}
    for _, line in ipairs(read_lines(path)) do
        result[line] = true
    end
    return result
end

local function read_frame_ranges(path)
    local result = {}
    for _, line in ipairs(read_lines(path)) do
        local start_text, finish_text = string.match(line, "^(-?%d+),(-?%d+)$")
        if start_text and finish_text then
            table.insert(result, {
                start = tonumber(start_text),
                finish = tonumber(finish_text)
            })
        end
    end
    return result
end

local function json_escape(value)
    return value
        :gsub("\\", "\\\\")
        :gsub('"', '\\"')
        :gsub("\b", "\\b")
        :gsub("\f", "\\f")
        :gsub("\n", "\\n")
        :gsub("\r", "\\r")
        :gsub("\t", "\\t")
end

local function to_json(value)
    local value_type = type(value)
    if value_type == "nil" then
        return "null"
    elseif value_type == "boolean" or value_type == "number" then
        return tostring(value)
    elseif value_type == "string" then
        return '"' .. json_escape(value) .. '"'
    elseif value_type == "table" then
        local is_array = true
        local max_index = 0
        for key, _ in pairs(value) do
            if type(key) ~= "number" or key < 1 or math.floor(key) ~= key then
                is_array = false
                break
            end
            if key > max_index then max_index = key end
        end

        local items = {}
        if is_array then
            for index = 1, max_index do
                table.insert(items, to_json(value[index]))
            end
            return "[" .. table.concat(items, ",") .. "]"
        end

        for key, item in pairs(value) do
            table.insert(items, to_json(tostring(key)) .. ":" .. to_json(item))
        end
        return "{" .. table.concat(items, ",") .. "}"
    end
    return "null"
end

local function get_layer_path(layer)
    local path = layer.name
    local parent = layer.parent
    while parent and parent ~= sprite do
        path = parent.name .. "/" .. path
        parent = parent.parent
    end
    return path
end

local target_layers = read_layer_set(app.params["layers_path"])
local frame_ranges = read_frame_ranges(app.params["ranges_path"])
local target_frame_mode = app.params["target_frame_mode"] or "all"
local offset_x = tonumber(app.params["offset_x"]) or 0
local offset_y = tonumber(app.params["offset_y"]) or 0

local function frame_is_target(frame_number)
    if target_frame_mode == "all" then return true end
    for _, range in ipairs(frame_ranges) do
        if frame_number >= range.start and frame_number <= range.finish then
            return true
        end
    end
    return false
end

local target_leaf_layers = {}
local function collect_target_layers(layer)
    if layer.isGroup then
        for _, child in ipairs(layer.layers) do
            collect_target_layers(child)
        end
    else
        local path = get_layer_path(layer)
        if target_layers[path] then
            table.insert(target_leaf_layers, layer)
        end
    end
end

for _, layer in ipairs(sprite.layers) do
    collect_target_layers(layer)
end

local result = {
    ok = true,
    width = sprite.width,
    height = sprite.height,
    pivot_x = math.floor(sprite.width / 2) + offset_x,
    pivot_y = math.floor(sprite.height / 2) - offset_y,
    total_frames = #sprite.frames,
    selected_frames = 0,
    analyzed_frames = 0,
    skipped_frames = {},
    per_frame = {},
    warnings = {}
}

if #target_leaf_layers == 0 then
    result.ok = false
    result.error = "대상 레이어 경로와 일치하는 drawable 레이어가 없습니다."
end

if result.ok then
    for _, frame in ipairs(sprite.frames) do
        local frame_number = frame.frameNumber
        if frame_is_target(frame_number) then
            result.selected_frames = result.selected_frames + 1
            local left = nil
            local top = nil
            local right = nil
            local bottom = nil

            for _, layer in ipairs(target_leaf_layers) do
                local cel = layer:cel(frame_number)
                if cel and cel.image and not cel.image:isEmpty() then
                    local local_bounds = cel.image:shrinkBounds()
                    if local_bounds and local_bounds.width > 0 and local_bounds.height > 0 then
                        local cel_left = cel.position.x + local_bounds.x
                        local cel_top = cel.position.y + local_bounds.y
                        local cel_right = cel_left + local_bounds.width
                        local cel_bottom = cel_top + local_bounds.height

                        left = left and math.min(left, cel_left) or cel_left
                        top = top and math.min(top, cel_top) or cel_top
                        right = right and math.max(right, cel_right) or cel_right
                        bottom = bottom and math.max(bottom, cel_bottom) or cel_bottom
                    end
                end
            end

            if left == nil then
                table.insert(result.skipped_frames, {
                    frame = frame_number,
                    reason = "대상 레이어에 표시 가능한 픽셀이 없습니다."
                })
            else
                local bbox_width = right - left
                local bbox_height = bottom - top
                local bbox_center_x = left + math.floor(bbox_width / 2)
                local bbox_bottom_y = bottom
                local dx = result.pivot_x - bbox_center_x
                local dy = result.pivot_y - bbox_bottom_y
                local moved_left = left + dx
                local moved_top = top + dy
                local moved_right = right + dx
                local moved_bottom = bottom + dy
                local clipped = (
                    moved_left < 0 or
                    moved_top < 0 or
                    moved_right > sprite.width or
                    moved_bottom > sprite.height
                )
                local frame_warnings = {}
                if clipped then
                    table.insert(frame_warnings, "이동 후 bbox가 캔버스 밖으로 나갑니다.")
                end

                table.insert(result.per_frame, {
                    frame = frame_number,
                    bbox = {
                        left = left,
                        top = top,
                        right = right,
                        bottom = bottom,
                        width = bbox_width,
                        height = bbox_height
                    },
                    bbox_center_x = bbox_center_x,
                    bbox_bottom_y = bbox_bottom_y,
                    dx = dx,
                    dy = dy,
                    moved_bbox = {
                        left = moved_left,
                        top = moved_top,
                        right = moved_right,
                        bottom = moved_bottom,
                        width = bbox_width,
                        height = bbox_height
                    },
                    clipped = clipped,
                    warnings = frame_warnings
                })
                result.analyzed_frames = result.analyzed_frames + 1
            end
        end
    end
end

if result.ok and result.selected_frames == 0 then
    result.ok = false
    result.error = "분석 대상 프레임이 없습니다."
elseif result.ok and result.analyzed_frames == 0 then
    result.ok = false
    result.error = "분석 가능한 bbox가 없습니다."
end

local output_path = app.params["output_path"]
if output_path and output_path ~= "" then
    local output = io.open(output_path, "w")
    if output then
        output:write(to_json(result))
        output:close()
    end
end
'''
        return self.create_temp_lua_script(content)

    def analyze_aseprite_pivot(self, path, target_layer_paths, target_frame_mode, checked_tags, offset_x=0, offset_y=0):
        if not self.validate_aseprite_path(self.aseprite_path.get()):
            return {"ok": False, "error": "유효한 Aseprite 실행 파일 경로가 아닙니다."}
        if not path or not os.path.exists(path):
            return {"ok": False, "error": "분석할 Aseprite 파일을 찾을 수 없습니다."}
        if not target_layer_paths:
            return {"ok": False, "error": "수정 대상으로 체크된 레이어가 없습니다."}
        if target_frame_mode == "tags" and not checked_tags:
            return {"ok": False, "error": "체크된 태그 프레임 범위가 없습니다."}

        script_path = None
        output_path = None
        layers_path = None
        ranges_path = None
        try:
            script_path = self.create_aseprite_pivot_analyze_lua()

            fd, output_path = tempfile.mkstemp(suffix=".json")
            os.close(fd)
            fd, layers_path = tempfile.mkstemp(suffix=".txt", text=True)
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as file:
                for layer_path in target_layer_paths:
                    file.write(f"{layer_path}\n")
            fd, ranges_path = tempfile.mkstemp(suffix=".txt", text=True)
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as file:
                for start, finish in checked_tags:
                    file.write(f"{int(start)},{int(finish)}\n")

            args = [
                path,
                "--script-param", f"output_path={output_path}",
                "--script-param", f"layers_path={layers_path}",
                "--script-param", f"ranges_path={ranges_path}",
                "--script-param", f"target_frame_mode={target_frame_mode}",
                "--script-param", f"offset_x={int(offset_x)}",
                "--script-param", f"offset_y={int(offset_y)}",
                "--script", script_path
            ]
            ok, log = self.run_aseprite_cli(args)
            if not ok:
                return {"ok": False, "error": f"Aseprite 분석 Lua 실행 실패: {log}"}
            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                return {"ok": False, "error": "Aseprite 분석 결과 JSON이 생성되지 않았습니다."}

            try:
                with open(output_path, "r", encoding="utf-8") as file:
                    return json.load(file)
            except Exception as e:
                return {"ok": False, "error": f"분석 결과 JSON 해석 실패: {e}"}
        except Exception as e:
            return {"ok": False, "error": f"피봇 분석 중 오류가 발생했습니다: {e}"}
        finally:
            for temp_path in (script_path, output_path, layers_path, ranges_path):
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass

    def create_aseprite_pivot_apply_lua(self):
        content = r'''
local sprite = app.activeSprite
if not sprite then return end

local function read_lines(path)
    local result = {}
    if not path or path == "" then return result end
    local file = io.open(path, "r")
    if not file then return result end
    for line in file:lines() do
        if line ~= "" then
            table.insert(result, line)
        end
    end
    file:close()
    return result
end

local function read_layer_set(path)
    local result = {}
    for _, line in ipairs(read_lines(path)) do
        result[line] = true
    end
    return result
end

local function read_frame_ranges(path)
    local result = {}
    for _, line in ipairs(read_lines(path)) do
        local start_text, finish_text = string.match(line, "^(-?%d+),(-?%d+)$")
        if start_text and finish_text then
            table.insert(result, {
                start = tonumber(start_text),
                finish = tonumber(finish_text)
            })
        end
    end
    return result
end

local function json_escape(value)
    return value
        :gsub("\\", "\\\\")
        :gsub('"', '\\"')
        :gsub("\b", "\\b")
        :gsub("\f", "\\f")
        :gsub("\n", "\\n")
        :gsub("\r", "\\r")
        :gsub("\t", "\\t")
end

local function to_json(value)
    local value_type = type(value)
    if value_type == "nil" then
        return "null"
    elseif value_type == "boolean" or value_type == "number" then
        return tostring(value)
    elseif value_type == "string" then
        return '"' .. json_escape(value) .. '"'
    elseif value_type == "table" then
        local is_array = true
        local max_index = 0
        for key, _ in pairs(value) do
            if type(key) ~= "number" or key < 1 or math.floor(key) ~= key then
                is_array = false
                break
            end
            if key > max_index then max_index = key end
        end

        local items = {}
        if is_array then
            for index = 1, max_index do
                table.insert(items, to_json(value[index]))
            end
            return "[" .. table.concat(items, ",") .. "]"
        end

        for key, item in pairs(value) do
            table.insert(items, to_json(tostring(key)) .. ":" .. to_json(item))
        end
        return "{" .. table.concat(items, ",") .. "}"
    end
    return "null"
end

local function get_layer_path(layer)
    local path = layer.name
    local parent = layer.parent
    while parent and parent ~= sprite do
        path = parent.name .. "/" .. path
        parent = parent.parent
    end
    return path
end

local target_layers = read_layer_set(app.params["layers_path"])
local frame_ranges = read_frame_ranges(app.params["ranges_path"])
local target_frame_mode = app.params["target_frame_mode"] or "all"
local offset_x = tonumber(app.params["offset_x"]) or 0
local offset_y = tonumber(app.params["offset_y"]) or 0
local output_path = app.params["output_path"]

local function frame_is_target(frame_number)
    if target_frame_mode == "all" then return true end
    for _, range in ipairs(frame_ranges) do
        if frame_number >= range.start and frame_number <= range.finish then
            return true
        end
    end
    return false
end

local target_leaf_layers = {}
local function collect_target_layers(layer)
    if layer.isGroup then
        for _, child in ipairs(layer.layers) do
            collect_target_layers(child)
        end
    else
        local path = get_layer_path(layer)
        if target_layers[path] then
            table.insert(target_leaf_layers, layer)
        end
    end
end

local function write_result(result)
    local out_json = app.params["result_path"]
    if out_json and out_json ~= "" then
        local output = io.open(out_json, "w")
        if output then
            output:write(to_json(result))
            output:close()
        end
    end
end

for _, layer in ipairs(sprite.layers) do
    collect_target_layers(layer)
end

local result = {
    ok = true,
    width = sprite.width,
    height = sprite.height,
    pivot_x = math.floor(sprite.width / 2) + offset_x,
    pivot_y = math.floor(sprite.height / 2) - offset_y,
    total_frames = #sprite.frames,
    selected_frames = 0,
    processed_frames = 0,
    skipped_frames = {},
    clipped_frames = {},
    moved_cels = 0,
    per_frame = {},
    output_path = output_path
}

if not output_path or output_path == "" then
    result.ok = false
    result.error = "출력 파일 경로가 없습니다."
elseif #target_leaf_layers == 0 then
    result.ok = false
    result.error = "대상 레이어 경로와 일치하는 drawable 레이어가 없습니다."
end

local frame_moves = {}
if result.ok then
    for _, frame in ipairs(sprite.frames) do
        local frame_number = frame.frameNumber
        if frame_is_target(frame_number) then
            result.selected_frames = result.selected_frames + 1
            local left = nil
            local top = nil
            local right = nil
            local bottom = nil

            for _, layer in ipairs(target_leaf_layers) do
                local cel = layer:cel(frame_number)
                if cel and cel.image and not cel.image:isEmpty() then
                    local local_bounds = cel.image:shrinkBounds()
                    if local_bounds and local_bounds.width > 0 and local_bounds.height > 0 then
                        local cel_left = cel.position.x + local_bounds.x
                        local cel_top = cel.position.y + local_bounds.y
                        local cel_right = cel_left + local_bounds.width
                        local cel_bottom = cel_top + local_bounds.height

                        left = left and math.min(left, cel_left) or cel_left
                        top = top and math.min(top, cel_top) or cel_top
                        right = right and math.max(right, cel_right) or cel_right
                        bottom = bottom and math.max(bottom, cel_bottom) or cel_bottom
                    end
                end
            end

            if left == nil then
                table.insert(result.skipped_frames, {
                    frame = frame_number,
                    reason = "대상 레이어에 표시 가능한 픽셀이 없습니다."
                })
            else
                local bbox_width = right - left
                local bbox_height = bottom - top
                local bbox_center_x = left + math.floor(bbox_width / 2)
                local bbox_bottom_y = bottom
                local dx = result.pivot_x - bbox_center_x
                local dy = result.pivot_y - bbox_bottom_y
                local moved_left = left + dx
                local moved_top = top + dy
                local moved_right = right + dx
                local moved_bottom = bottom + dy
                local clipped = (
                    moved_left < 0 or
                    moved_top < 0 or
                    moved_right > sprite.width or
                    moved_bottom > sprite.height
                )
                local frame_result = {
                    frame = frame_number,
                    bbox = {
                        left = left,
                        top = top,
                        right = right,
                        bottom = bottom,
                        width = bbox_width,
                        height = bbox_height
                    },
                    bbox_center_x = bbox_center_x,
                    bbox_bottom_y = bbox_bottom_y,
                    dx = dx,
                    dy = dy,
                    moved_bbox = {
                        left = moved_left,
                        top = moved_top,
                        right = moved_right,
                        bottom = moved_bottom,
                        width = bbox_width,
                        height = bbox_height
                    },
                    clipped = clipped,
                    warnings = {}
                }
                if clipped then
                    table.insert(frame_result.warnings, "이동 후 bbox가 캔버스 밖으로 나갑니다.")
                    table.insert(result.clipped_frames, frame_number)
                end
                table.insert(result.per_frame, frame_result)
                table.insert(frame_moves, {frame = frame_number, dx = dx, dy = dy})
            end
        end
    end

    if result.selected_frames == 0 then
        result.ok = false
        result.error = "적용 대상 프레임이 없습니다."
    elseif #frame_moves == 0 then
        result.ok = false
        result.error = "적용 가능한 bbox가 없습니다."
    elseif #result.clipped_frames > 0 then
        result.ok = false
        result.clipped_blocked = true
        result.error = "클리핑이 예상되어 복사본 저장을 중단했습니다."
    end
end

if result.ok then
    local move_by_frame = {}
    for _, item in ipairs(frame_moves) do
        move_by_frame[item.frame] = item
    end

    app.transaction(function()
        for _, layer in ipairs(target_leaf_layers) do
            for _, frame in ipairs(sprite.frames) do
                local frame_number = frame.frameNumber
                local move = move_by_frame[frame_number]
                if move then
                    local cel = layer:cel(frame_number)
                    if cel then
                        cel.position = Point(cel.position.x + move.dx, cel.position.y + move.dy)
                        result.moved_cels = result.moved_cels + 1
                    end
                end
            end
        end
    end)

    result.processed_frames = #frame_moves
    sprite:saveCopyAs(output_path)
end

write_result(result)
'''
        return self.create_temp_lua_script(content)

    def run_aseprite_pivot_apply_copy(self, path, target_layer_paths, target_frame_mode, checked_tags, offset_x=0, offset_y=0, suffix="_pivot"):
        if not self.validate_aseprite_path(self.aseprite_path.get()):
            return {"ok": False, "error": "유효한 Aseprite 실행 파일 경로가 아닙니다."}
        if not path or not os.path.exists(path):
            return {"ok": False, "error": "처리할 Aseprite 파일을 찾을 수 없습니다."}
        if not target_layer_paths:
            return {"ok": False, "error": "수정 대상으로 체크된 레이어가 없습니다."}
        if target_frame_mode == "tags" and not checked_tags:
            return {"ok": False, "error": "체크된 태그 프레임 범위가 없습니다."}

        directory = os.path.dirname(path)
        base_name, ext = os.path.splitext(os.path.basename(path))
        suffix = suffix.strip() or "_pivot"
        output_path = os.path.join(directory, f"{base_name}{suffix}{ext}")
        counter = 1
        while os.path.exists(output_path):
            output_path = os.path.join(directory, f"{base_name}{suffix}_{counter:03d}{ext}")
            counter += 1

        if os.path.abspath(output_path) == os.path.abspath(path):
            return {"ok": False, "error": "출력 경로가 원본과 같습니다. 작업을 중단합니다."}

        script_path = None
        result_path = None
        layers_path = None
        ranges_path = None
        try:
            script_path = self.create_aseprite_pivot_apply_lua()
            fd, result_path = tempfile.mkstemp(suffix=".json")
            os.close(fd)
            fd, layers_path = tempfile.mkstemp(suffix=".txt", text=True)
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as file:
                for layer_path in target_layer_paths:
                    file.write(f"{layer_path}\n")
            fd, ranges_path = tempfile.mkstemp(suffix=".txt", text=True)
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as file:
                for start, finish in checked_tags:
                    file.write(f"{int(start)},{int(finish)}\n")

            args = [
                path,
                "--script-param", f"result_path={result_path}",
                "--script-param", f"output_path={output_path}",
                "--script-param", f"layers_path={layers_path}",
                "--script-param", f"ranges_path={ranges_path}",
                "--script-param", f"target_frame_mode={target_frame_mode}",
                "--script-param", f"offset_x={int(offset_x)}",
                "--script-param", f"offset_y={int(offset_y)}",
                "--script", script_path
            ]
            ok, log = self.run_aseprite_cli(args)
            if not ok:
                return {"ok": False, "error": f"Aseprite 피봇 보정 Lua 실행 실패: {log}", "output_path": output_path}
            if not os.path.exists(result_path) or os.path.getsize(result_path) == 0:
                return {"ok": False, "error": "Aseprite 피봇 보정 결과 JSON이 생성되지 않았습니다.", "output_path": output_path}

            try:
                with open(result_path, "r", encoding="utf-8") as file:
                    result = json.load(file)
            except Exception as e:
                return {"ok": False, "error": f"피봇 보정 결과 JSON 해석 실패: {e}", "output_path": output_path}

            result["output_path"] = output_path
            if result.get("ok"):
                if not os.path.exists(output_path) or os.path.getsize(output_path) <= 0:
                    result["ok"] = False
                    result["error"] = "복사본 파일이 생성되지 않았거나 비어 있습니다."
                elif self.inspect_aseprite_file(output_path) is None:
                    result["ok"] = False
                    result["error"] = "복사본 파일 검증에 실패했습니다."
            return result
        except Exception as e:
            return {"ok": False, "error": f"피봇 보정 복사본 생성 중 오류가 발생했습니다: {e}", "output_path": output_path}
        finally:
            for temp_path in (script_path, result_path, layers_path, ranges_path):
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass

    def run_aseprite_layer_move(self, files, dx, dy, target_layers_list, target_frames_mode, tag_ranges, save_mode, suffix):
        if not self.validate_aseprite_path(self.aseprite_path.get()):
            messagebox.showwarning("경고", "Aseprite 경로를 먼저 설정해주세요.")
            return

        if not files:
            messagebox.showwarning("경고", "처리할 Aseprite 파일(.ase, .aseprite)을 추가해주세요.")
            return

        if not target_layers_list:
            messagebox.showwarning("경고", "선택된 대상 레이어가 없습니다.")
            return

        success = 0
        
        # Serialize python lists to Lua code
        layers_str = "{" + ",".join(f'["{l}"]=true' for l in target_layers_list) + "}"
        frames_str = "{"
        for f_start, f_end in tag_ranges:
            frames_str += f"{{start={f_start}, finish={f_end}}},"
        frames_str += "}"

        lua_content = f"""
local app = app
local sprite = app.activeSprite
if not sprite then return end

local dx = {dx}
local dy = {dy}
local target_frames_mode = "{target_frames_mode}"

local layer_names = {layers_str}
local tag_ranges = {frames_str}

local function is_frame_in_range(frame_num)
    if #tag_ranges == 0 then return false end
    for _, r in ipairs(tag_ranges) do
        if frame_num >= r.start and frame_num <= r.finish then
            return true
        end
    end
    return false
end

local function get_layer_path(layer)
    local path = layer.name
    local p = layer.parent
    while p and p ~= sprite do
        path = p.name .. "/" .. path
        p = p.parent
    end
    return path
end

local target_layers_mode = "selected"

local function process_layer(layer)
    if layer.isGroup then
        for _, sublayer in ipairs(layer.layers) do
            process_layer(sublayer)
        end
    else
        local path = get_layer_path(layer)
        if target_layers_mode == "all" or layer_names[path] then
            if target_frames_mode == "all" then
                for _, frame in ipairs(sprite.frames) do
                    local cel = layer:cel(frame.frameNumber)
                    if cel then
                        cel.position = Point(cel.position.x + dx, cel.position.y + dy)
                    end
                end
            elseif target_frames_mode == "tags" then
                for _, frame in ipairs(sprite.frames) do
                    if is_frame_in_range(frame.frameNumber) then
                        local cel = layer:cel(frame.frameNumber)
                        if cel then
                            cel.position = Point(cel.position.x + dx, cel.position.y + dy)
                        end
                    end
                end
            end
        end
    end
end

for _, layer in ipairs(sprite.layers) do
    process_layer(layer)
end

local out_path = app.params["output_path"]
if out_path then
    sprite:saveCopyAs(out_path)
end
"""
        script_path = self.create_temp_lua_script(lua_content)

        try:
            for p in files:
                name, ext = os.path.splitext(p)
                
                if save_mode == "copy":
                    out_p = f"{name}{suffix}{ext}"
                    counter = 1
                    while os.path.exists(out_p) and out_p != p:
                        out_p = f"{name}{suffix}_{counter:03d}{ext}"
                        counter += 1
                else: # overwrite
                    try:
                        backup_dir = os.path.join(os.path.dirname(p), "_aseprite_backup")
                        os.makedirs(backup_dir, exist_ok=True)
                        filename = os.path.basename(p)
                        backup_path = self.get_unique_backup_path(backup_dir, filename)
                        shutil.copy2(p, backup_path)
                    except Exception as e:
                        messagebox.showerror("백업 실패", f"파일: {os.path.basename(p)}\n백업 실패로 인해 덮어쓰기를 취소합니다.\n오류: {e}")
                        continue
                    
                    # Aseprite CLI가 원본을 열고 바로 덮어쓰면 충돌이 날 수 있으므로 임시 파일에 저장 후 교체
                    fd, temp_out = tempfile.mkstemp(suffix=ext)
                    os.close(fd)
                    out_p = temp_out

                args = [p, "--script-param", f"output_path={out_p}", "--script", script_path]
                ok, log = self.run_aseprite_cli(args)
                
                if ok:
                    if save_mode == "overwrite":
                        try:
                            shutil.move(out_p, p)
                            success += 1
                        except Exception as e:
                            messagebox.showerror("덮어쓰기 오류", f"원본 파일을 교체하는 중 오류가 발생했습니다.\n오류: {e}")
                    else:
                        success += 1
                else:
                    messagebox.showerror("Aseprite 실행 오류", f"파일: {os.path.basename(p)}\n오류: {log}")
                    if save_mode == "overwrite" and os.path.exists(out_p):
                        try: os.remove(out_p)
                        except: pass
                    
        finally:
            if os.path.exists(script_path):
                os.remove(script_path)

        messagebox.showinfo("처리 완료", f"총 {success}개의 Aseprite 레이어 이동 작업이 완료되었습니다.")

    def run_aseprite_pivot_fix(self):
        if not self.validate_aseprite_path(self.aseprite_path.get()):
            messagebox.showwarning("경고", "Aseprite 경로를 먼저 설정해주세요.")
            return
        messagebox.showinfo("안내", "Aseprite 피봇 보정 기능은 현재 기초 구조 및 CLI 연결이 준비되었습니다.\n(곧 업데이트됩니다!)")

    def show_aseprite_tools(self):
        ase_win = tk.Toplevel(self.root)
        ase_win.title("Aseprite 연동 도구")
        ase_win.geometry("1200x820")
        ase_win.minsize(1000, 720)
        if self.is_always_on_top.get():
            ase_win.attributes('-topmost', True)
            
        c = self.get_colors()
        ase_win.configure(bg=c["BG_COLOR"])

        self.auto_detect_aseprite_path()

        # ================= 상단: 경로 상태 및 설정 =================
        header_frame = ttk.Frame(ase_win, style="TFrame")
        header_frame.pack(fill="x", padx=15, pady=10)
        
        status_text = "연결됨" if self.aseprite_path.get() else "경로 미설정"
        lbl_status = ttk.Label(header_frame, text=f"Aseprite: {status_text}", font=("Malgun Gothic", 10, "bold"), foreground=c["PRIMARY_COLOR"] if self.aseprite_path.get() else c["DANGER_COLOR"])
        lbl_status.pack(side="left")
        
        def open_path_settings():
            pop = tk.Toplevel(ase_win)
            pop.title("Aseprite 경로 설정")
            pop.geometry("600x150")
            if self.is_always_on_top.get(): pop.attributes('-topmost', True)
            pop.configure(bg=c["BG_COLOR"])
            
            f = ttk.Frame(pop, style="TFrame")
            f.pack(fill="both", expand=True, padx=20, pady=20)
            ttk.Label(f, text="Aseprite 실행 파일 경로:").pack(anchor="w", pady=(0, 5))
            
            ent_frame = ttk.Frame(f, style="TFrame")
            ent_frame.pack(fill="x")
            
            ttk.Entry(ent_frame, textvariable=self.aseprite_path, state="readonly").pack(side="left", fill="x", expand=True, padx=(0, 10))
            def do_find():
                self.find_aseprite_exe()
                st = "연결됨" if self.aseprite_path.get() else "경로 미설정"
                lbl_status.config(text=f"Aseprite: {st}", foreground=c["PRIMARY_COLOR"] if self.aseprite_path.get() else c["DANGER_COLOR"])
            ttk.Button(ent_frame, text="경로 찾기", command=do_find).pack(side="left")
            ttk.Button(ent_frame, text="닫기", command=pop.destroy).pack(side="left", padx=(10, 0))

        ttk.Button(header_frame, text="⚙ 설정", command=open_path_settings).pack(side="left", padx=10)

        # ================= 중앙/하단 분할 패널 =================
        main_split = ttk.PanedWindow(ase_win, orient=tk.HORIZONTAL)
        main_split.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        # ==================== 좌측: 파일 리스트 ====================
        left_frame = ttk.Frame(main_split, style="Panel.TFrame")
        main_split.add(left_frame, weight=0) # weight 0 to restrict width

        ttk.Label(left_frame, text="작업 대상 파일 (.ase, .aseprite)").pack(anchor="w", padx=10, pady=(10, 0))
        ttk.Label(left_frame, text="* 파일 및 폴더 드래그 앤 드롭 지원", style="Muted.TLabel").pack(anchor="w", padx=10)
        
        list_frame = ttk.Frame(left_frame, style="Panel.TFrame")
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        list_scroll = ttk.Scrollbar(list_frame)
        list_scroll.pack(side="right", fill="y")
        
        ase_listbox = tk.Listbox(list_frame, bg=c["BG_COLOR"], fg=c["TEXT_COLOR"], relief="flat", borderwidth=1, highlightthickness=1, highlightbackground=c["BORDER_COLOR"], yscrollcommand=list_scroll.set, selectmode="extended", width=35)
        ase_listbox.pack(side="left", fill="both", expand=True)
        list_scroll.config(command=ase_listbox.yview)
        
        self.ase_metadata = {}
        self.current_preview_temp = None
        current_ase_path = {"path": None}
        current_preview_frame = {"frame": 1}
        preview_after_id = {"id": None}
        preview_resize_after_id = {"id": None}
        preview_move_after_id = {"id": None}
        preview_zoom = {"mode": "fit", "scale": 1.0}
        current_preview_source = {"path": None, "frame": None, "image": None}

        # Initialize listbox with existing files if they exist (Restoring state)
        for f in self.aseprite_files:
            ase_listbox.insert("end", os.path.basename(f))

        target_frame_mode = tk.StringVar(value="tags")

        def save_current_ase_ui_state(path):
            if not path: return
            state = {
                "preview_visible_layers": set(),
                "edit_target_layers": set(),
                "checked_tags": set(),
                "target_frame_mode": target_frame_mode.get()
            }
            for item in layer_tree.get_children():
                val = layer_tree.item(item, "values")
                if val[0] == "☑":
                    state["preview_visible_layers"].add(val[2])
                if val[1] == "☑":
                    state["edit_target_layers"].add(val[2])
            for item in tag_tree.get_children():
                val = tag_tree.item(item, "values")
                if val[0] == "☑" and val[1] != "태그 없음": state["checked_tags"].add(val[1])
            self.ase_selection_state[path] = state

        def restore_ase_ui_state(path):
            if path in self.ase_selection_state:
                state = self.ase_selection_state[path]
                edit_target_layers = set(state.get("edit_target_layers", state.get("checked_layers", set())))
                preview_visible_layers = state.get("preview_visible_layers")
                if preview_visible_layers is None:
                    preview_visible_layers = {
                        layer_tree.item(item, "values")[2]
                        for item in layer_tree.get_children()
                        if layer_tree.item(item, "values")[3] == "보기"
                    }
                else:
                    preview_visible_layers = set(preview_visible_layers)

                state["edit_target_layers"] = edit_target_layers
                state["preview_visible_layers"] = preview_visible_layers
                for item in layer_tree.get_children():
                    val = layer_tree.item(item, "values")
                    preview_check = "☑" if val[2] in preview_visible_layers else "☐"
                    edit_check = "☑" if val[2] in edit_target_layers else "☐"
                    layer_tree.item(item, values=(preview_check, edit_check, val[2], val[3]))
                for item in tag_tree.get_children():
                    val = tag_tree.item(item, "values")
                    if val[1] != "태그 없음":
                        check = "☑" if val[1] in state.get("checked_tags", set()) else "☐"
                        tag_tree.item(item, values=(check, val[1], val[2]))
                target_frame_mode.set(state.get("target_frame_mode", "tags"))
            else:
                target_frame_mode.set("tags")

        def get_preview_visible_layers():
            return [
                layer_tree.item(item, "values")[2]
                for item in layer_tree.get_children()
                if layer_tree.item(item, "values")[0] == "☑"
            ]

        def invalidate_ase_preview_source():
            old_source = current_preview_source["image"]
            if old_source is not None:
                try:
                    old_source.close()
                except:
                    pass
            current_preview_source["path"] = None
            current_preview_source["frame"] = None
            current_preview_source["image"] = None

        def refresh_ase_preview(delay=50):
            sel = ase_listbox.curselection()
            if not sel:
                return

            idx = sel[0]
            if idx < 0 or idx >= len(self.aseprite_files):
                return

            path = self.aseprite_files[idx]
            frame = current_preview_frame["frame"]
            visible_layer_paths = tuple(get_preview_visible_layers())

            if preview_after_id["id"] is not None:
                try:
                    ase_win.after_cancel(preview_after_id["id"])
                except tk.TclError:
                    pass
                preview_after_id["id"] = None

            def run_refresh(p=path, f=frame, layers=visible_layer_paths):
                preview_after_id["id"] = None
                update_preview_image(p, f, layers)

            preview_after_id["id"] = ase_win.after(delay, run_refresh)

        def set_preview_zoom(mode, scale=None):
            preview_zoom["mode"] = mode
            if scale is not None:
                preview_zoom["scale"] = max(0.25, min(8.0, float(scale)))
            if current_preview_source["image"] is not None:
                render_ase_preview_canvas()
            else:
                refresh_ase_preview()

        def step_preview_zoom(direction):
            current_scale = preview_zoom["scale"]
            factor = 2.0 if direction > 0 else 0.5
            set_preview_zoom("manual", current_scale * factor)

        def on_preview_mousewheel(event):
            if not (event.state & 0x0004):
                return
            step_preview_zoom(1 if event.delta > 0 else -1)
            return "break"

        def on_preview_canvas_resize(event=None):
            if preview_zoom["mode"] != "fit":
                return
            if preview_resize_after_id["id"] is not None:
                try:
                    ase_win.after_cancel(preview_resize_after_id["id"])
                except tk.TclError:
                    pass

            def refresh_after_resize():
                preview_resize_after_id["id"] = None
                if current_preview_source["image"] is not None:
                    render_ase_preview_canvas()

            preview_resize_after_id["id"] = ase_win.after(200, refresh_after_resize)

        def update_inspector(event=None):
            sel = ase_listbox.curselection()
            if not sel: return
            idx = sel[0]
            path = self.aseprite_files[idx]
            
            if current_ase_path["path"] and current_ase_path["path"] != path:
                save_current_ase_ui_state(current_ase_path["path"])
                
            current_ase_path["path"] = path
            
            meta = self.inspect_aseprite_file(path)
            if meta:
                self.ase_metadata[path] = meta
                
                info_text = f"[{os.path.basename(path)}]\n원본 캔버스: {meta['width']}x{meta['height']}px | {meta['frames']}프레임 | 태그 {len(meta['tags'])}개"
                info_lbl.config(text=info_text)
                
                for item in layer_tree.get_children(): layer_tree.delete(item)
                for l in meta['layers']:
                    vis = "보기" if l['isVisible'] else "숨김"
                    preview_check = "☑" if l['isVisible'] else "☐"
                    layer_tree.insert("", tk.END, values=(preview_check, "☑", l['path'], vis))
                    
                for item in tag_tree.get_children(): tag_tree.delete(item)
                if not meta['tags']:
                    tag_tree.insert("", tk.END, values=("", "태그 없음", ""))
                else:
                    for t in meta['tags']:
                        tag_tree.insert("", tk.END, values=("☐", t['name'], f"{t['fromFrame']} ~ {t['toFrame']}"))
                
                restore_ase_ui_state(path)
                
                preview_frame = 1
                for item in tag_tree.get_children():
                    val = tag_tree.item(item, "values")
                    if val[0] == "☑" and val[1] != "태그 없음":
                        try:
                            rng = val[2].split("~")
                            preview_frame = int(rng[0].strip())
                            break
                        except: pass
                 
                current_preview_frame["frame"] = preview_frame
                refresh_ase_preview(delay=100)
            else:
                print(f"인스펙터 메타데이터 로드 실패: {path}")

        def render_ase_preview_canvas():
            source_img = current_preview_source["image"]
            path = current_preview_source["path"]
            frame = current_preview_source["frame"]
            if source_img is None or not path or frame is None:
                return

            try:
                import PIL.Image
                import PIL.ImageTk

                try:
                    dx = int(dx_var.get() or 0)
                except (ValueError, TypeError):
                    dx = 0
                try:
                    dy = int(dy_var.get() or 0)
                except (ValueError, TypeError):
                    dy = 0

                # Preview-only fallback: move the composited frame without saving the Aseprite file.
                moved_img = PIL.Image.new("RGBA", source_img.size, (0, 0, 0, 0))
                moved_img.paste(source_img, (dx, dy), source_img)

                c_w = preview_canvas.winfo_width()
                c_h = preview_canvas.winfo_height()
                if c_w < 10: c_w = 420
                if c_h < 10: c_h = 420

                if preview_zoom["mode"] == "fit":
                    ratio = min((c_w-20)/moved_img.width, (c_h-20)/moved_img.height)
                    if ratio >= 1:
                        ratio = max(1, int(ratio))
                    ratio = max(0.25, min(8.0, ratio))
                    preview_zoom["scale"] = ratio
                    zoom_text = f"맞춤 ({ratio:g}x)"
                else:
                    ratio = max(0.25, min(8.0, preview_zoom["scale"]))
                    preview_zoom["scale"] = ratio
                    zoom_text = f"{ratio:g}x"

                new_w = max(1, int(moved_img.width * ratio))
                new_h = max(1, int(moved_img.height * ratio))
                img_resized = moved_img.resize((new_w, new_h), PIL.Image.Resampling.NEAREST)
                self.ase_tk_preview = PIL.ImageTk.PhotoImage(img_resized)

                preview_canvas.delete("all")
                size = 10
                color1 = "#ffffff" if not self.is_dark_mode.get() else "#2A2A2A"
                color2 = "#f1f5f9" if not self.is_dark_mode.get() else "#202020"
                for y in range(0, c_h, size):
                    for x in range(0, c_w, size):
                        color = color1 if ((x//size) + (y//size)) % 2 == 0 else color2
                        preview_canvas.create_rectangle(x, y, x+size, y+size, fill=color, outline="")

                cx, cy = c_w // 2, c_h // 2
                preview_canvas.create_image(cx, cy, image=self.ase_tk_preview, anchor="center")

                cross_color = "#06b6d4" if not self.is_dark_mode.get() else "#22D3EE"
                preview_canvas.create_line(0, cy, c_w, cy, fill=cross_color, width=1, tags="crosshair")
                preview_canvas.create_line(cx, 0, cx, c_h, fill=cross_color, width=1, tags="crosshair")

                orig_x1 = cx - (new_w // 2)
                orig_y1 = cy - (new_h // 2)
                orig_x2 = orig_x1 + new_w
                orig_y2 = orig_y1 + new_h
                outline_color = "#ef4444" if not self.is_dark_mode.get() else "#F87171"
                preview_canvas.create_rectangle(orig_x1, orig_y1, orig_x2, orig_y2, outline=outline_color, dash=(2, 2))

                tag_name = ""
                for item in tag_tree.get_children():
                    val = tag_tree.item(item, "values")
                    if val[0] == "☑" and val[1] != "태그 없음":
                        try:
                            rng = val[2].split("~")
                            if int(rng[0].strip()) == frame:
                                tag_name = f" [{val[1]}]"
                                break
                        except: pass

                info_lbl.config(
                    text=(
                        f"파일명: {os.path.basename(path)}\n"
                        f"표시 프레임: {frame}{tag_name}\n"
                        f"원본 캔버스: {source_img.width}x{source_img.height} px\n"
                        f"표시 크기: {new_w}x{new_h} px\n"
                        f"미리보기 전용 전체 이미지 가상 이동: X {dx}, Y {dy}"
                    )
                )
                zoom_lbl.config(text=f"배율: {zoom_text}")
            except Exception as e:
                print(f"미리보기 렌더링 실패: {e}")
                info_lbl.config(text=f"미리보기 렌더링 실패\n프레임: {frame}\n에러: {e}")

        def update_preview_image(path, frame=1, visible_layer_paths=None):
            if self.current_preview_temp and os.path.exists(self.current_preview_temp):
                try: os.remove(self.current_preview_temp)
                except: pass

            if visible_layer_paths is None:
                visible_layer_paths = get_preview_visible_layers()
            else:
                visible_layer_paths = list(visible_layer_paths)

            if not visible_layer_paths:
                invalidate_ase_preview_source()
                preview_canvas.delete("all")
                c_w = max(1, preview_canvas.winfo_width())
                c_h = max(1, preview_canvas.winfo_height())
                self.draw_checkerboard(preview_canvas, c_w, c_h)
                info_lbl.config(
                    text=(
                        f"파일명: {os.path.basename(path)}\n"
                        f"표시 프레임: {frame}\n"
                        "보기 레이어 없음\n"
                        "레이어 트리에서 보기 항목을 체크하세요."
                    )
                )
                zoom_lbl.config(text="배율: -")
                return

            tmp_png = self.export_aseprite_preview_png_with_visible_layers(
                path,
                frame,
                visible_layer_paths
            )
            if tmp_png:
                self.current_preview_temp = tmp_png
                try:
                    import PIL.Image
                    with PIL.Image.open(tmp_png) as img:
                        source_img = img.convert("RGBA")
                        source_img.load()

                    old_source = current_preview_source["image"]
                    if old_source is not None:
                        try: old_source.close()
                        except: pass

                    current_preview_source["path"] = path
                    current_preview_source["frame"] = frame
                    current_preview_source["image"] = source_img
                    render_ase_preview_canvas()
                except Exception as e:
                    print(f"미리보기 로드 실패 (Image.open): {e}")
                    info_lbl.config(text=f"미리보기 이미지 열기 실패\n프레임: {frame}\n에러: {e}")
            else:
                print(f"미리보기 PNG 생성 실패 연동 로직 (path: {path}, frame: {frame})")
                info_lbl.config(text=f"미리보기 PNG 생성 실패\n프레임: {frame}\n콘솔 로그를 확인하세요.")

        ase_listbox.bind('<<ListboxSelect>>', lambda e: [update_inspector(), update_expected_label()], add="+")

        def add_file_or_folder(p_norm):
            import glob
            if os.path.isdir(p_norm):
                added = False
                for f in glob.glob(os.path.join(p_norm, "*.*")):
                    if f.lower().endswith((".ase", ".aseprite")) and f not in self.aseprite_files:
                        self.aseprite_files.append(f)
                        ase_listbox.insert("end", os.path.basename(f))
                        added = True
                return added
            elif p_norm.lower().endswith((".ase", ".aseprite")) and p_norm not in self.aseprite_files:
                self.aseprite_files.append(p_norm)
                ase_listbox.insert("end", os.path.basename(p_norm))
                return True
            return False

        def on_ase_drop(event):
            paths = ase_win.tk.splitlist(event.data)
            if not paths: return
            
            added = False
            for p in paths:
                if add_file_or_folder(os.path.normpath(p)):
                    added = True
                    
            if added and ase_listbox.size() > 0:
                ase_listbox.selection_clear(0, "end")
                ase_listbox.selection_set(0)
                update_inspector()
                update_expected_label()

        # DND
        from tkinterdnd2 import DND_FILES
        ase_win.drop_target_register(DND_FILES)
        ase_win.dnd_bind('<<Drop>>', on_ase_drop)
        ase_listbox.drop_target_register(DND_FILES)
        ase_listbox.dnd_bind('<<Drop>>', on_ase_drop)

        btn_frame = ttk.Frame(left_frame, style="Panel.TFrame")
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        btn_frame.columnconfigure((0,1), weight=1)
        btn_frame2 = ttk.Frame(left_frame, style="Panel.TFrame")
        btn_frame2.pack(fill="x", padx=10, pady=(0, 10))
        btn_frame2.columnconfigure((0,1), weight=1)
        
        def add_ase_files():
            paths = filedialog.askopenfilenames(filetypes=[("Aseprite", "*.ase *.aseprite")])
            added = False
            for p in paths:
                if add_file_or_folder(os.path.normpath(p)): added = True
            if added:
                ase_listbox.selection_clear(0, "end")
                ase_listbox.selection_set(ase_listbox.size()-1)
                update_inspector()
                update_expected_label()
                
        def add_ase_folder():
            folder = filedialog.askdirectory()
            if folder:
                if add_file_or_folder(os.path.normpath(folder)):
                    ase_listbox.selection_clear(0, "end")
                    ase_listbox.selection_set(ase_listbox.size()-1)
                    update_inspector()
                    update_expected_label()
                    
        def remove_ase_files():
            sel = ase_listbox.curselection()
            if not sel: return
            for idx in reversed(sel):
                p = self.aseprite_files[idx]
                if p in self.ase_metadata: del self.ase_metadata[p]
                if p in self.ase_selection_state: del self.ase_selection_state[p]
                if current_ase_path["path"] == p: current_ase_path["path"] = None
                del self.aseprite_files[idx]
                ase_listbox.delete(idx)
            if ase_listbox.size() > 0:
                ase_listbox.selection_set(0)
                update_inspector()
                update_expected_label()
            else:
                info_lbl.config(text="파일을 선택하세요")
                layer_tree.delete(*layer_tree.get_children())
                tag_tree.delete(*tag_tree.get_children())
                preview_canvas.delete("all")
                update_expected_label()
                
        def clear_ase_files():
            self.aseprite_files.clear()
            self.ase_metadata.clear()
            self.ase_selection_state.clear()
            current_ase_path["path"] = None
            ase_listbox.delete(0, "end")
            info_lbl.config(text="파일을 선택하세요")
            layer_tree.delete(*layer_tree.get_children())
            tag_tree.delete(*tag_tree.get_children())
            preview_canvas.delete("all")
            update_expected_label()

        ttk.Button(btn_frame, text="파일 추가", command=add_ase_files).grid(row=0, column=0, sticky="ew", padx=(0, 2))
        ttk.Button(btn_frame, text="폴더 추가", command=add_ase_folder).grid(row=0, column=1, sticky="ew", padx=(2, 0))
        ttk.Button(btn_frame2, text="선택 제거", command=remove_ase_files).grid(row=0, column=0, sticky="ew", padx=(0, 2))
        ttk.Button(btn_frame2, text="전체 비우기", command=clear_ase_files).grid(row=0, column=1, sticky="ew", padx=(2, 0))

        # ==================== 우측: 옵션 및 미리보기 ====================
        right_frame = ttk.Frame(main_split, style="TFrame")
        main_split.add(right_frame, weight=3)
        
        # Set sash position initially
        ase_win.after(100, lambda: main_split.sashpos(0, 280))

        # 우측 상단: 실행 옵션 (고정 영역)
        exec_frame = ttk.LabelFrame(right_frame, text=" 실행 옵션 ")
        exec_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        exec_frame.columnconfigure(1, weight=1)
        
        ttk.Label(exec_frame, text="가로 이동(px):").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        dx_var = tk.StringVar(value="0")
        ttk.Spinbox(exec_frame, from_=-9999, to=9999, textvariable=dx_var, width=8).grid(row=0, column=1, sticky="w", pady=5)

        ttk.Label(exec_frame, text="세로 이동(px):").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        dy_var = tk.StringVar(value="0")
        ttk.Spinbox(exec_frame, from_=-9999, to=9999, textvariable=dy_var, width=8).grid(row=1, column=1, sticky="w", pady=5)

        ttk.Label(exec_frame, text="저장 방식:").grid(row=0, column=2, sticky="w", padx=10, pady=5)
        save_mode_var = tk.StringVar(value="copy")
        save_mode_frame = ttk.Frame(exec_frame, style="Panel.TFrame")
        save_mode_frame.grid(row=0, column=3, sticky="w", pady=5)
        ttk.Radiobutton(save_mode_frame, text="새 파일로 저장", variable=save_mode_var, value="copy").pack(side="left", padx=(0, 10))
        ttk.Radiobutton(save_mode_frame, text="원본 덮어쓰기", variable=save_mode_var, value="overwrite").pack(side="left")

        ttk.Label(exec_frame, text="새 파일 접미사:").grid(row=1, column=2, sticky="w", padx=10, pady=5)
        suffix_var = tk.StringVar(value="_move_x{dx}_y{dy}")
        ttk.Entry(exec_frame, textvariable=suffix_var, width=20).grid(row=1, column=3, sticky="w", pady=5)

        lbl_expected = ttk.Label(exec_frame, text="예상 저장 결과: ", style="Muted.TLabel")
        lbl_expected.grid(row=2, column=0, columnspan=4, sticky="w", padx=10, pady=(5, 10))

        def update_expected_label(*args):
            sel = ase_listbox.curselection()
            if not sel and not self.aseprite_files:
                lbl_expected.config(text="예상 저장 결과: 대상 파일 없음")
                return
                
            path = self.aseprite_files[sel[0]] if sel else self.aseprite_files[0]
            name, ext = os.path.splitext(os.path.basename(path))
            
            mode = save_mode_var.get()
            total = len(ase_listbox.curselection()) if ase_listbox.curselection() else len(self.aseprite_files)
            
            if mode == "overwrite":
                extra = f" 외 {total-1}개" if total > 1 else ""
                lbl_expected.config(text=f"예상 저장 결과: {name}{ext} → 원본 파일 덮어쓰기{extra} (백업: _aseprite_backup 폴더 생성 예정)")
            else:
                try: dx = int(dx_var.get())
                except: dx = 0
                try: dy = int(dy_var.get())
                except: dy = 0
                
                suf = suffix_var.get().replace("{dx}", str(dx)).replace("{dy}", str(dy))
                extra = f" 외 {total-1}개" if total > 1 else ""
                lbl_expected.config(text=f"예상 저장 결과: {name}{ext} → {name}{suf}{ext}{extra}")

        def on_move_preview_option_change(*args):
            update_expected_label()
            if preview_move_after_id["id"] is not None:
                try:
                    ase_win.after_cancel(preview_move_after_id["id"])
                except tk.TclError:
                    pass

            def render_after_move_change():
                preview_move_after_id["id"] = None
                if current_preview_source["image"] is not None:
                    render_ase_preview_canvas()

            preview_move_after_id["id"] = ase_win.after(80, render_after_move_change)

        dx_var.trace_add("write", on_move_preview_option_change)
        dy_var.trace_add("write", on_move_preview_option_change)
        save_mode_var.trace_add("write", update_expected_label)
        suffix_var.trace_add("write", update_expected_label)

        def on_execute_move():
            try: dx = int(dx_var.get())
            except: dx = 0
            try: dy = int(dy_var.get())
            except: dy = 0
            
            sel = ase_listbox.curselection()
            files_to_process = [self.aseprite_files[i] for i in sel] if sel else self.aseprite_files
            
            if not files_to_process:
                messagebox.showwarning("경고", "처리할 파일이 없습니다.")
                return

            if save_mode_var.get() == "overwrite":
                ans = messagebox.askyesno("경고", "원본 파일에 덮어씁니다.\n(진행 전 _aseprite_backup 폴더에 자동 백업됩니다.)\n정말 진행하시겠습니까?")
                if not ans: return
            
            if current_ase_path["path"]:
                save_current_ase_ui_state(current_ase_path["path"])

            checked_layers = [
                layer_tree.item(i, "values")[2]
                for i in layer_tree.get_children()
                if layer_tree.item(i, "values")[1] == "☑"
            ]
            if not checked_layers:
                messagebox.showwarning("안내", "선택된 대상 레이어가 없습니다.")
                return

            checked_tags = []
            if target_frame_mode.get() == "tags":
                for i in tag_tree.get_children():
                    val = tag_tree.item(i, "values")
                    if val[0] == "☑" and val[1] != "태그 없음":
                        rng = val[2].split("~")
                        checked_tags.append((int(rng[0].strip()), int(rng[1].strip())))
                
                if not checked_tags:
                    messagebox.showwarning("안내", "'체크된 태그만' 모드이지만 선택된 태그가 없습니다.")
                    return
            
            raw_suffix = suffix_var.get().strip() or "_move_x{dx}_y{dy}"
            suf = raw_suffix.replace("{dx}", str(dx)).replace("{dy}", str(dy))
            
            self.run_aseprite_layer_move(
                files_to_process, 
                dx, 
                dy, 
                checked_layers, 
                target_frame_mode.get(), 
                checked_tags, 
                save_mode_var.get(), 
                suf
            )

        def show_pivot_analysis_result(path, result, offset_x, offset_y):
            result_win = tk.Toplevel(ase_win)
            result_win.title("Aseprite 피봇 분석 결과")
            result_win.geometry("760x620")
            result_win.minsize(640, 480)
            if self.is_always_on_top.get():
                result_win.attributes("-topmost", True)

            result_frame = ttk.Frame(result_win, padding=12)
            result_frame.pack(fill="both", expand=True)

            clipped_count = sum(1 for item in result.get("per_frame", []) if item.get("clipped"))
            summary = (
                f"파일: {os.path.basename(path)}\n"
                f"캔버스: {result.get('width', 0)}x{result.get('height', 0)} px | "
                f"목표 피봇: ({result.get('pivot_x', 0)}, {result.get('pivot_y', 0)})\n"
                f"피봇 오프셋: X {offset_x}, Y {offset_y}\n"
                f"대상 프레임: {result.get('selected_frames', 0)} | "
                f"분석 완료: {result.get('analyzed_frames', 0)} | "
                f"건너뜀: {len(result.get('skipped_frames', []))} | "
                f"클리핑 예상: {clipped_count}\n"
                "분석 전용 결과이며 실제 .ase/.aseprite 파일은 수정하지 않았습니다."
            )
            ttk.Label(result_frame, text=summary, justify="left").pack(fill="x", pady=(0, 10))

            text_frame = ttk.Frame(result_frame)
            text_frame.pack(fill="both", expand=True)
            scrollbar = ttk.Scrollbar(text_frame)
            scrollbar.pack(side="right", fill="y")
            result_text = tk.Text(
                text_frame,
                wrap="none",
                font=("Consolas", 10),
                yscrollcommand=scrollbar.set
            )
            result_text.pack(side="left", fill="both", expand=True)
            scrollbar.config(command=result_text.yview)

            result_text.insert("end", "[프레임별 분석]\n")
            for item in result.get("per_frame", []):
                bbox = item.get("bbox", {})
                moved = item.get("moved_bbox", {})
                result_text.insert(
                    "end",
                    (
                        f"Frame {item.get('frame')}: "
                        f"bbox=({bbox.get('left')}, {bbox.get('top')}, "
                        f"{bbox.get('right')}, {bbox.get('bottom')}) "
                        f"size={bbox.get('width')}x{bbox.get('height')} | "
                        f"centerX={item.get('bbox_center_x')} bottomY={item.get('bbox_bottom_y')} | "
                        f"move=({item.get('dx')}, {item.get('dy')}) | "
                        f"moved=({moved.get('left')}, {moved.get('top')}, "
                        f"{moved.get('right')}, {moved.get('bottom')}) | "
                        f"clipped={item.get('clipped')}\n"
                    )
                )
                for warning in item.get("warnings", []):
                    result_text.insert("end", f"  warning: {warning}\n")

            skipped_frames = result.get("skipped_frames", [])
            if skipped_frames:
                result_text.insert("end", "\n[건너뜬 프레임]\n")
                for skipped in skipped_frames:
                    result_text.insert(
                        "end",
                        f"Frame {skipped.get('frame')}: {skipped.get('reason', '이유 없음')}\n"
                    )

            result_text.config(state="disabled")
            ttk.Button(result_frame, text="닫기", command=result_win.destroy).pack(anchor="e", pady=(10, 0))

        def on_analyze_pivot():
            sel = ase_listbox.curselection()
            if not sel:
                messagebox.showwarning("피봇 분석", "분석할 Aseprite 파일을 하나 선택해주세요.")
                return
            path = self.aseprite_files[sel[0]]

            target_layers = [
                layer_tree.item(item, "values")[2]
                for item in layer_tree.get_children()
                if layer_tree.item(item, "values")[1] == "☑"
            ]
            if not target_layers:
                messagebox.showwarning("피봇 분석", "수정 대상으로 체크된 레이어가 없습니다.")
                return

            checked_tags = []
            if target_frame_mode.get() == "tags":
                for item in tag_tree.get_children():
                    values = tag_tree.item(item, "values")
                    if values[0] == "☑" and values[1] != "태그 없음":
                        try:
                            start_text, finish_text = values[2].split("~")
                            checked_tags.append((int(start_text.strip()), int(finish_text.strip())))
                        except Exception:
                            messagebox.showerror("피봇 분석", f"태그 프레임 범위를 읽을 수 없습니다: {values[1]}")
                            return
                if not checked_tags:
                    messagebox.showwarning("피봇 분석", "체크된 태그 프레임 범위가 없습니다.")
                    return

            try:
                offset_x = int(dx_var.get() or 0)
            except (ValueError, TypeError):
                offset_x = 0
            try:
                offset_y = int(dy_var.get() or 0)
            except (ValueError, TypeError):
                offset_y = 0

            result = self.analyze_aseprite_pivot(
                path,
                target_layers,
                target_frame_mode.get(),
                checked_tags,
                offset_x,
                offset_y
            )
            if not result.get("ok"):
                messagebox.showerror("피봇 분석 실패", result.get("error", "알 수 없는 분석 오류입니다."))
                return

            clipped_count = sum(1 for item in result.get("per_frame", []) if item.get("clipped"))
            messagebox.showinfo(
                "피봇 분석 완료",
                (
                    f"분석 완료: {result.get('analyzed_frames', 0)}프레임\n"
                    f"건너뜀: {len(result.get('skipped_frames', []))}프레임\n"
                    f"클리핑 예상: {clipped_count}프레임\n\n"
                    "분석만 수행했으며 실제 파일은 수정하지 않았습니다."
                )
            )
            show_pivot_analysis_result(path, result, offset_x, offset_y)

        def get_pivot_ui_inputs():
            sel = ase_listbox.curselection()
            if not sel:
                return None, "처리할 Aseprite 파일을 하나 선택해주세요."
            path = self.aseprite_files[sel[0]]
            target_layers = [
                layer_tree.item(item, "values")[2]
                for item in layer_tree.get_children()
                if layer_tree.item(item, "values")[1] == "☑"
            ]
            if not target_layers:
                return None, "수정 대상으로 체크된 레이어가 없습니다."

            checked_tags = []
            if target_frame_mode.get() == "tags":
                for item in tag_tree.get_children():
                    values = tag_tree.item(item, "values")
                    if values[0] == "☑" and values[1] != "태그 없음":
                        try:
                            start_text, finish_text = values[2].split("~")
                            checked_tags.append((int(start_text.strip()), int(finish_text.strip())))
                        except Exception:
                            return None, f"태그 프레임 범위를 읽을 수 없습니다: {values[1]}"
                if not checked_tags:
                    return None, "체크된 태그 프레임 범위가 없습니다."

            try:
                offset_x = int(dx_var.get() or 0)
            except (ValueError, TypeError):
                offset_x = 0
            try:
                offset_y = int(dy_var.get() or 0)
            except (ValueError, TypeError):
                offset_y = 0

            return {
                "path": path,
                "target_layers": target_layers,
                "target_frame_mode": target_frame_mode.get(),
                "checked_tags": checked_tags,
                "offset_x": offset_x,
                "offset_y": offset_y
            }, None

        def on_apply_pivot_copy():
            inputs, error = get_pivot_ui_inputs()
            if error:
                messagebox.showwarning("피봇 보정 복사본", error)
                return

            answer = messagebox.askyesno(
                "피봇 보정 복사본 생성",
                (
                    "원본 파일은 수정하지 않고 _pivot 복사본으로 저장합니다.\n"
                    "클리핑이 예상되면 저장하지 않습니다.\n\n"
                    "진행하시겠습니까?"
                )
            )
            if not answer:
                return

            result = self.run_aseprite_pivot_apply_copy(
                inputs["path"],
                inputs["target_layers"],
                inputs["target_frame_mode"],
                inputs["checked_tags"],
                inputs["offset_x"],
                inputs["offset_y"]
            )

            if not result.get("ok"):
                detail = result.get("error", "알 수 없는 오류입니다.")
                if result.get("clipped_blocked"):
                    clipped_frames = result.get("clipped_frames", [])
                    sample = ", ".join(str(frame) for frame in clipped_frames[:10])
                    if len(clipped_frames) > 10:
                        sample += f" ... 외 {len(clipped_frames) - 10}개"
                    detail += f"\n\n클리핑 예상 프레임: {sample}"
                    detail += "\n복사본은 저장되지 않았습니다."
                messagebox.showerror("피봇 보정 복사본 실패", detail)
                return

            messagebox.showinfo(
                "피봇 보정 복사본 완료",
                (
                    f"저장된 파일:\n{result.get('output_path')}\n\n"
                    f"처리 프레임: {result.get('processed_frames', 0)}\n"
                    f"건너뜀: {len(result.get('skipped_frames', []))}\n"
                    f"이동한 cel: {result.get('moved_cels', 0)}\n\n"
                    "원본 파일은 수정하지 않았습니다."
                )
            )

        ttk.Button(exec_frame, text="▶ 선택한 레이어 이동 실행", style="Success.TButton", command=on_execute_move).grid(row=0, column=4, rowspan=2, sticky="nsew", padx=10, pady=5)
        ttk.Button(exec_frame, text="피봇 분석만 실행", command=on_analyze_pivot).grid(row=2, column=4, sticky="nsew", padx=10, pady=(0, 5))
        ttk.Button(exec_frame, text="피봇 보정 복사본 생성", command=on_apply_pivot_copy).grid(row=3, column=4, sticky="nsew", padx=10, pady=(0, 5))
        ttk.Label(
            exec_frame,
            text="피봇 기능에서는 가로/세로 이동값을 자동 정렬 기준의 X/Y 오프셋으로 해석합니다. 복사본 생성은 원본을 수정하지 않고 _pivot 파일로 저장합니다.",
            style="Muted.TLabel"
        ).grid(row=4, column=0, columnspan=5, sticky="w", padx=10, pady=(0, 8))

        # 우측 본문: 레이어/태그 & 미리보기 (좌우 분할)
        body_split = ttk.PanedWindow(right_frame, orient=tk.HORIZONTAL)
        body_split.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        move_trees = ttk.Frame(body_split, style="Panel.TFrame")
        body_split.add(move_trees, weight=1)
        
        tree_split = ttk.PanedWindow(move_trees, orient=tk.VERTICAL)
        tree_split.pack(fill="both", expand=True)
        
        # 레이어 선택 트리
        layer_frame = ttk.LabelFrame(tree_split, text=" 대상 레이어 선택 ")
        tree_split.add(layer_frame, weight=1)
        
        l_scroll = ttk.Scrollbar(layer_frame)
        l_scroll.pack(side="right", fill="y", pady=(5, 5))
        
        layer_tree = ttk.Treeview(layer_frame, columns=("preview", "edit", "path", "vis"), show="headings", yscrollcommand=l_scroll.set, selectmode="none")
        layer_tree.heading("preview", text="보기")
        layer_tree.column("preview", width=42, anchor="center", stretch=False)
        layer_tree.heading("edit", text="수정")
        layer_tree.column("edit", width=42, anchor="center", stretch=False)
        layer_tree.heading("path", text="레이어 경로", anchor="w")
        layer_tree.column("path", width=150, anchor="w", stretch=True)
        layer_tree.heading("vis", text="상태", anchor="center")
        layer_tree.column("vis", width=50, anchor="center", stretch=False)
        layer_tree.pack(side="top", expand=True, fill="both", padx=(5, 0), pady=(5, 5))
        l_scroll.config(command=layer_tree.yview)
        
        def on_layer_click(event):
            if layer_tree.identify_region(event.x, event.y) != "cell":
                return
            column = layer_tree.identify_column(event.x)
            if column not in ("#1", "#2"):
                return
            item = layer_tree.identify_row(event.y)
            if not item:
                return

            val = list(layer_tree.item(item, "values"))
            check_index = 0 if column == "#1" else 1
            if val[check_index] == "☑":
                val[check_index] = "☐"
            elif val[check_index] == "☐":
                val[check_index] = "☑"
            else:
                return
            layer_tree.item(item, values=tuple(val))
            if current_ase_path["path"]:
                save_current_ase_ui_state(current_ase_path["path"])
            if check_index == 0:
                invalidate_ase_preview_source()
                refresh_ase_preview(delay=150)

        layer_tree.bind('<ButtonRelease-1>', on_layer_click)
        
        l_btn_f = ttk.Frame(layer_frame, style="Panel.TFrame")
        l_btn_f.pack(fill="x", padx=5, pady=(0, 5))

        def set_all_layer_checks(check_index, checked):
            check_value = "☑" if checked else "☐"
            for item in layer_tree.get_children():
                val = list(layer_tree.item(item, "values"))
                val[check_index] = check_value
                layer_tree.item(item, values=tuple(val))
            if current_ase_path["path"]:
                save_current_ase_ui_state(current_ase_path["path"])
            if check_index == 0:
                invalidate_ase_preview_source()
                refresh_ase_preview(delay=150)

        l_btn_f.columnconfigure(0, weight=1)
        l_btn_f.columnconfigure(1, weight=1)
        ttk.Button(l_btn_f, text="보기 전체 체크", command=lambda: set_all_layer_checks(0, True)).grid(row=0, column=0, sticky="ew", padx=(0, 2), pady=(0, 2))
        ttk.Button(l_btn_f, text="보기 전체 해제", command=lambda: set_all_layer_checks(0, False)).grid(row=0, column=1, sticky="ew", padx=(2, 0), pady=(0, 2))
        ttk.Button(l_btn_f, text="수정 전체 체크", command=lambda: set_all_layer_checks(1, True)).grid(row=1, column=0, sticky="ew", padx=(0, 2))
        ttk.Button(l_btn_f, text="수정 전체 해제", command=lambda: set_all_layer_checks(1, False)).grid(row=1, column=1, sticky="ew", padx=(2, 0))
        ttk.Label(
            layer_frame,
            text="보기 체크는 미리보기 export에만 반영되며 실제 수정 대상과는 독립적입니다.",
            style="Muted.TLabel",
            wraplength=320,
            justify="left"
        ).pack(fill="x", padx=7, pady=(0, 5))

        # 태그 선택 트리
        tag_frame = ttk.LabelFrame(tree_split, text=" 적용 범위 (태그 선택) ")
        tree_split.add(tag_frame, weight=1)
        
        t_scroll = ttk.Scrollbar(tag_frame)
        t_scroll.pack(side="right", fill="y", pady=(5, 5))
        
        tag_tree = ttk.Treeview(tag_frame, columns=("check", "name", "range"), show="headings", yscrollcommand=t_scroll.set, selectmode="none")
        tag_tree.heading("check", text="체크")
        tag_tree.column("check", width=40, anchor="center", stretch=False)
        tag_tree.heading("name", text="태그 이름", anchor="w")
        tag_tree.column("name", width=100, anchor="w", stretch=True)
        tag_tree.heading("range", text="프레임 범위", anchor="w")
        tag_tree.column("range", width=100, anchor="w", stretch=True)
        tag_tree.pack(side="top", expand=True, fill="both", padx=(5, 0), pady=(5, 5))
        t_scroll.config(command=tag_tree.yview)
        
        t_btn_f = ttk.Frame(tag_frame, style="Panel.TFrame")
        t_btn_f.pack(fill="x", padx=5, pady=(0, 5))
        
        def tag_check_all():
            for i in tag_tree.get_children():
                val = tag_tree.item(i, "values")
                if val[1] != "태그 없음":
                    tag_tree.item(i, values=("☑", val[1], val[2]))
            if current_ase_path["path"]: save_current_ase_ui_state(current_ase_path["path"])
            
            # Update preview to first tag's first frame
            for i in tag_tree.get_children():
                val = tag_tree.item(i, "values")
                if val[1] != "태그 없음":
                    try:
                        rng = val[2].split("~")
                        f_start = int(rng[0].strip())
                        current_preview_frame["frame"] = f_start
                        refresh_ase_preview()
                    except: pass
                    break

        def tag_uncheck_all():
            for i in tag_tree.get_children():
                val = tag_tree.item(i, "values")
                if val[1] != "태그 없음":
                    tag_tree.item(i, values=("☐", val[1], val[2]))
            if current_ase_path["path"]: save_current_ase_ui_state(current_ase_path["path"])

        ttk.Button(t_btn_f, text="모두 체크", command=tag_check_all).pack(side="left", expand=True, fill="x")
        ttk.Button(t_btn_f, text="모두 해제", command=tag_uncheck_all).pack(side="left", expand=True, fill="x")
        
        t_mode_f = ttk.Frame(tag_frame, style="Panel.TFrame")
        t_mode_f.pack(fill="x", padx=5, pady=(0, 5))
        ttk.Radiobutton(t_mode_f, text="모든 프레임", variable=target_frame_mode, value="all").pack(side="left", padx=5)
        ttk.Radiobutton(t_mode_f, text="체크된 태그만", variable=target_frame_mode, value="tags").pack(side="left", padx=5)

        def on_tag_click(event):
            region = tag_tree.identify_region(event.x, event.y)
            if region == "cell":
                item = tag_tree.identify_row(event.y)
                if item:
                    val = tag_tree.item(item, "values")
                    column = tag_tree.identify_column(event.x)
                    if column == "#1":
                        if val[0] == "☑": new_val = ("☐", val[1], val[2])
                        elif val[0] == "☐": new_val = ("☑", val[1], val[2])
                        else: return
                        tag_tree.item(item, values=new_val)
                        if current_ase_path["path"]: save_current_ase_ui_state(current_ase_path["path"])
                    
                    if val[1] != "태그 없음":
                        try:
                            rng = val[2].split("~")
                            f_start = int(rng[0].strip())
                            current_preview_frame["frame"] = f_start
                            refresh_ase_preview()
                        except: pass

        tag_tree.bind('<ButtonRelease-1>', on_tag_click)
        ttk.Label(tag_frame, text="* 태그 선택/체크 시 해당 태그 첫 프레임 미리보기", style="Muted.TLabel").pack(pady=2)

        # 우측: 큰 미리보기 영역
        info_frame = ttk.LabelFrame(body_split, text=" 미리보기 ")
        body_split.add(info_frame, weight=3)
        
        info_split = ttk.Frame(info_frame, style="Panel.TFrame")
        info_split.pack(fill="both", expand=True, padx=10, pady=10)
        
        preview_header = ttk.Frame(info_split, style="Panel.TFrame")
        preview_header.pack(side="top", fill="x", pady=(0, 10))

        info_lbl = ttk.Label(preview_header, text="파일을 선택하세요", justify="left")
        info_lbl.pack(side="left", fill="x", expand=True, padx=(0, 10))

        zoom_controls = ttk.Frame(preview_header, style="Panel.TFrame")
        zoom_controls.pack(side="right")

        ttk.Button(zoom_controls, text="맞춤", command=lambda: set_preview_zoom("fit")).pack(side="left", padx=1)
        ttk.Button(zoom_controls, text="1x", command=lambda: set_preview_zoom("manual", 1.0)).pack(side="left", padx=1)
        ttk.Button(zoom_controls, text="2x", command=lambda: set_preview_zoom("manual", 2.0)).pack(side="left", padx=1)
        ttk.Button(zoom_controls, text="-", width=3, command=lambda: step_preview_zoom(-1)).pack(side="left", padx=1)
        ttk.Button(zoom_controls, text="+", width=3, command=lambda: step_preview_zoom(1)).pack(side="left", padx=1)

        zoom_lbl = ttk.Label(zoom_controls, text="배율: 맞춤", style="Muted.TLabel")
        zoom_lbl.pack(side="left", padx=(8, 0))
        
        preview_canvas = tk.Canvas(info_split, bg=c["BG_COLOR"], highlightbackground=c["BORDER_COLOR"])
        preview_canvas.pack(side="top", fill="both", expand=True)
        preview_canvas.bind("<Control-MouseWheel>", on_preview_mousewheel)
        preview_canvas.bind("<Configure>", on_preview_canvas_resize)

        # 초기 파일이 있다면 1번 선택 
        if self.aseprite_files:
            ase_listbox.selection_set(0)
            update_inspector()
            update_expected_label()

        # cleanup temps on close
        def on_close():
            if preview_after_id["id"] is not None:
                try:
                    ase_win.after_cancel(preview_after_id["id"])
                except tk.TclError:
                    pass
                preview_after_id["id"] = None
            if preview_resize_after_id["id"] is not None:
                try:
                    ase_win.after_cancel(preview_resize_after_id["id"])
                except tk.TclError:
                    pass
                preview_resize_after_id["id"] = None
            if preview_move_after_id["id"] is not None:
                try:
                    ase_win.after_cancel(preview_move_after_id["id"])
                except tk.TclError:
                    pass
                preview_move_after_id["id"] = None
            if current_preview_source["image"] is not None:
                try:
                    current_preview_source["image"].close()
                except: pass
                current_preview_source["image"] = None
            if self.current_preview_temp and os.path.exists(self.current_preview_temp):
                try:
                    tmp_dir = os.path.dirname(self.current_preview_temp)
                    import shutil
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                except: pass
            ase_win.destroy()
            
        ase_win.protocol("WM_DELETE_WINDOW", on_close)
        update_expected_label()



if __name__ == "__main__":
    try:
        from tkinterdnd2 import TkinterDnD
        root = TkinterDnD.Tk()
    except Exception as e:
        print("tkinterdnd2 초기화 오류:", e)
        import tkinter as tk
        root = tk.Tk()
        
    app = PivotFixerApp(root)
    root.mainloop()
