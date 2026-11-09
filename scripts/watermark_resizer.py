import gc
import os
import queue
import random
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from PIL import Image, ImageTk


def get_resample():
    try:
        return Image.Resampling.LANCZOS
    except AttributeError:
        return Image.LANCZOS


class WatermarkResizerApp:
    PREVIEW_FALLBACK_W = 760
    PREVIEW_FALLBACK_H = 520
    HANDLE_SIZE = 10
    MIN_WM_W = 48
    MIN_WM_H = 32
    HANDLE_CURSOR_MAP = {
        "nw": "size_nw_se",
        "n": "sb_v_double_arrow",
        "ne": "size_ne_sw",
        "e": "sb_h_double_arrow",
        "se": "size_nw_se",
        "s": "sb_v_double_arrow",
        "sw": "size_ne_sw",
        "w": "sb_h_double_arrow",
    }
    HANDLE_ORDER = ("nw", "n", "ne", "e", "se", "s", "sw", "w")
    THEMES = {
        "화이트": {
            "bg": "#f6f8fb",
            "card": "#ffffff",
            "text": "#0f172a",
            "muted": "#475569",
            "border": "#cbd5e1",
            "button": "#e2e8f0",
            "button_active": "#cbd5e1",
            "button_disabled": "#f1f5f9",
            "accent": "#0f766e",
            "accent_hover": "#115e59",
            "accent_disabled": "#99f6e4",
            "header_bg": "#0f766e",
            "header_fg": "#ffffff",
            "header_muted": "#d1fae5",
            "canvas_bg": "#eef2f7",
            "canvas_border": "#cbd5e1",
            "preview_outline": "#2563eb",
            "preview_fill": "#dbeafe",
            "preview_text": "#1e40af",
            "handle_fill": "#ffffff",
            "log_bg": "#f8fafc",
            "log_fg": "#0f172a",
        },
        "블랙": {
            "bg": "#111827",
            "card": "#1f2937",
            "text": "#f9fafb",
            "muted": "#d1d5db",
            "border": "#374151",
            "button": "#374151",
            "button_active": "#4b5563",
            "button_disabled": "#1f2937",
            "accent": "#14b8a6",
            "accent_hover": "#0d9488",
            "accent_disabled": "#155e75",
            "header_bg": "#0b1220",
            "header_fg": "#f9fafb",
            "header_muted": "#99f6e4",
            "canvas_bg": "#0f172a",
            "canvas_border": "#475569",
            "preview_outline": "#5eead4",
            "preview_fill": "#164e63",
            "preview_text": "#ccfbf1",
            "handle_fill": "#111827",
            "log_bg": "#0f172a",
            "log_fg": "#e5e7eb",
        },
    }

    def __init__(self, root):
        self.root = root
        self.root.title("Watermark Resizer")
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width = min(1360, max(1120, screen_w - 80))
        height = min(860, max(760, screen_h - 120))
        self.root.geometry(f"{width}x{height}")
        self.root.minsize(min(1120, screen_w - 40), min(760, screen_h - 40))

        self.queue = queue.Queue()

        self.target_dir = tk.StringVar()
        self.watermark_path = tk.StringVar()
        self.enable_resize = tk.BooleanVar(value=True)
        self.width_val = tk.StringVar(value="800")
        self.height_val = tk.StringVar(value="600")
        self.keep_ratio = tk.BooleanVar(value=True)

        self.opacity_val = tk.DoubleVar(value=80.0)
        self.size_val = tk.DoubleVar(value=20.0)
        self.margin_val = tk.DoubleVar(value=3.0)
        self.position_val = tk.StringVar(value="Bottom-Right")
        self.custom_x_val = tk.DoubleVar(value=95.0)
        self.custom_y_val = tk.DoubleVar(value=95.0)
        self.theme_val = tk.StringVar(value="화이트")
        self.watermark_aspect_ratio = 1.0

        self.preview_bg_pil = None
        self.loaded_watermark_pil = None
        self.preview_composite_tk = None
        self.preview_bg_tk = None
        self.preview_wm_tk = None

        self.is_dragging = False
        self.is_resizing = False
        self.active_handle = None
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        self.resize_anchor_x = 0
        self.resize_anchor_y = 0
        self.resize_start_w = 0
        self.resize_start_h = 0
        self.resize_aspect = 1.0

        self.is_processing = False
        self.cancel_requested = False
        self.total_files = 0
        self.header = None
        self.header_inner = None
        self.header_title_area = None
        self.header_theme_area = None
        self.header_title = None
        self.header_subtitle = None
        self.header_theme_label = None
        self.theme_combo = None

        self.apply_theme_styles()
        self.create_widgets()

        self.position_val.trace_add("write", self.on_position_change)

        self.update_resize_fields_state()
        self.update_custom_fields_state()
        self.draw_preview()
        self.root.after(100, self.poll_queue)

    def apply_theme_styles(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")

        colors = self.THEMES.get(self.theme_val.get(), self.THEMES["화이트"])
        self.theme_colors = colors
        bg = colors["bg"]
        card = colors["card"]
        text = colors["text"]
        muted = colors["muted"]
        border = colors["border"]
        accent = colors["accent"]
        accent_hover = colors["accent_hover"]

        self.root.configure(bg=bg)
        self.style.configure(".", background=bg, foreground=text, font=("Malgun Gothic", 10))
        self.style.configure("TFrame", background=bg)
        self.style.configure("TLabelframe", background=bg, foreground=text, bordercolor=border, borderwidth=1, relief="solid")
        self.style.configure("TLabelframe.Label", background=bg, foreground=text, font=("Malgun Gothic", 10, "bold"))
        self.style.configure("TLabel", background=bg, foreground=muted)
        self.style.configure("Heading.TLabel", background=bg, foreground=text, font=("Malgun Gothic", 17, "bold"))
        self.style.configure("Subheading.TLabel", background=bg, foreground=muted, font=("Malgun Gothic", 10))
        self.style.configure("TButton", background=colors["button"], foreground=text, font=("Malgun Gothic", 10, "bold"), padding=(10, 6))
        self.style.map("TButton", background=[("active", colors["button_active"]), ("disabled", colors["button_disabled"])])
        self.style.configure("Accent.TButton", background=accent, foreground="#ffffff", font=("Malgun Gothic", 10, "bold"), padding=(14, 7))
        self.style.map("Accent.TButton", background=[("active", accent_hover), ("disabled", colors["accent_disabled"])])
        self.style.configure("TCheckbutton", background=bg, foreground=muted)
        self.style.map("TCheckbutton", background=[("active", bg)])
        self.style.configure("TRadiobutton", background=bg, foreground=muted)
        self.style.map("TRadiobutton", background=[("active", bg)])
        self.style.configure("TEntry", fieldbackground=card, foreground=text, bordercolor=border, insertcolor=text)
        self.style.configure("TCombobox", fieldbackground=card, foreground=text, bordercolor=border, arrowsize=12)
        self.style.configure("TScale", background=bg)
        self.style.configure("Horizontal.TProgressbar", background=accent, troughcolor=card, bordercolor=border)

        if self.header is not None:
            self.header.configure(bg=colors["header_bg"])
            self.header_inner.configure(bg=colors["header_bg"])
            self.header_title_area.configure(bg=colors["header_bg"])
            self.header_theme_area.configure(bg=colors["header_bg"])
            self.header_title.configure(bg=colors["header_bg"], fg=colors["header_fg"])
            self.header_subtitle.configure(bg=colors["header_bg"], fg=colors["header_muted"])
            self.header_theme_label.configure(bg=colors["header_bg"], fg=colors["header_muted"])
        if hasattr(self, "preview_canvas"):
            self.preview_canvas.configure(bg=colors["canvas_bg"], highlightbackground=colors["canvas_border"])
        if hasattr(self, "log_text"):
            self.log_text.configure(bg=colors["log_bg"], fg=colors["log_fg"], insertbackground=colors["log_fg"])

    def change_theme(self, *args):
        self.apply_theme_styles()
        self.draw_preview()

    def create_widgets(self):
        colors = self.theme_colors
        self.header = tk.Frame(self.root, bg=colors["header_bg"], height=88)
        self.header.pack(fill=tk.X, padx=14, pady=(14, 0))
        self.header.pack_propagate(False)
        self.header_inner = tk.Frame(self.header, bg=colors["header_bg"])
        self.header_inner.pack(fill=tk.BOTH, expand=True, padx=18, pady=12)

        self.header_title_area = tk.Frame(self.header_inner, bg=colors["header_bg"])
        self.header_title_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.header_title = tk.Label(
            self.header_title_area,
            text="Watermark Resizer",
            bg=colors["header_bg"],
            fg=colors["header_fg"],
            font=("Malgun Gothic", 18, "bold"),
        )
        self.header_title.pack(anchor=tk.W)
        self.header_subtitle = tk.Label(
            self.header_title_area,
            text="변환 전에 미리보기에서 워터마크를 직접 이동하고 크기를 조절하세요.",
            bg=colors["header_bg"],
            fg=colors["header_muted"],
            font=("Malgun Gothic", 10),
        )
        self.header_subtitle.pack(anchor=tk.W, pady=(2, 0))

        self.header_theme_area = tk.Frame(self.header_inner, bg=colors["header_bg"])
        self.header_theme_area.pack(side=tk.RIGHT, padx=(12, 0))
        self.header_theme_label = tk.Label(
            self.header_theme_area,
            text="테마",
            bg=colors["header_bg"],
            fg=colors["header_muted"],
            font=("Malgun Gothic", 9, "bold"),
        )
        self.header_theme_label.pack(anchor=tk.E)
        self.theme_combo = ttk.Combobox(
            self.header_theme_area,
            values=("화이트", "블랙"),
            textvariable=self.theme_val,
            state="readonly",
            width=8,
        )
        self.theme_combo.pack(anchor=tk.E, pady=(4, 0))
        self.theme_combo.bind("<<ComboboxSelected>>", self.change_theme)

        main = ttk.Frame(self.root, padding="14 14 14 16")
        main.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(main)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        right = ttk.Frame(main)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))

        path_frame = ttk.LabelFrame(left, text="입력 폴더 / 워터마크", padding="10")
        path_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(path_frame, text="대상 폴더").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.dir_entry = ttk.Entry(path_frame, textvariable=self.target_dir)
        self.dir_entry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=5)
        ttk.Button(path_frame, text="폴더 선택", command=self.browse_directory).grid(row=0, column=2, padx=5, pady=5)
        ttk.Label(path_frame, text="워터마크 PNG").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.wm_entry = ttk.Entry(path_frame, textvariable=self.watermark_path)
        self.wm_entry.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=5)
        ttk.Button(path_frame, text="파일 선택", command=self.browse_watermark).grid(row=1, column=2, padx=5, pady=5)
        path_frame.columnconfigure(1, weight=1)

        resize_frame = ttk.LabelFrame(left, text="1. 이미지 크기 조절", padding="10")
        resize_frame.pack(fill=tk.X, pady=(0, 10))
        self.resize_check = ttk.Checkbutton(
            resize_frame,
            text="크기 조절 사용",
            variable=self.enable_resize,
            command=self.on_resize_toggle,
        )
        self.resize_check.grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 8))
        ttk.Label(resize_frame, text="가로 (Width)").grid(row=1, column=0, sticky=tk.W, pady=4)
        self.w_entry = ttk.Entry(resize_frame, textvariable=self.width_val, width=10)
        self.w_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=4)
        ttk.Label(resize_frame, text="px").grid(row=1, column=2, sticky=tk.W)
        ttk.Label(resize_frame, text="세로 (Height)").grid(row=2, column=0, sticky=tk.W, pady=4)
        self.h_entry = ttk.Entry(resize_frame, textvariable=self.height_val, width=10)
        self.h_entry.grid(row=2, column=1, sticky=tk.W, padx=5, pady=4)
        ttk.Label(resize_frame, text="px").grid(row=2, column=2, sticky=tk.W)
        self.ratio_check = ttk.Checkbutton(resize_frame, text="가로세로 비율 유지", variable=self.keep_ratio)
        self.ratio_check.grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=(8, 0))

        wm_frame = ttk.LabelFrame(left, text="2. 워터마크 설정", padding="10")
        wm_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(wm_frame, text="투명도").grid(row=0, column=0, sticky=tk.W, pady=4)
        self.opacity_slider = ttk.Scale(wm_frame, from_=10, to=100, variable=self.opacity_val, command=self.update_sliders_lbl)
        self.opacity_slider.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=4)
        self.opacity_lbl = ttk.Label(wm_frame, text="80%")
        self.opacity_lbl.grid(row=0, column=2, sticky=tk.W, pady=4)

        ttk.Label(wm_frame, text="크기 (%)").grid(row=1, column=0, sticky=tk.W, pady=4)
        self.size_slider = ttk.Scale(wm_frame, from_=1, to=100, variable=self.size_val, command=self.update_sliders_lbl)
        self.size_slider.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=4)
        self.size_lbl = ttk.Label(wm_frame, text="20%")
        self.size_lbl.grid(row=1, column=2, sticky=tk.W, pady=4)

        ttk.Label(wm_frame, text="여백 (%)").grid(row=2, column=0, sticky=tk.W, pady=4)
        self.margin_slider = ttk.Scale(wm_frame, from_=1, to=10, variable=self.margin_val, command=self.update_sliders_lbl)
        self.margin_slider.grid(row=2, column=1, sticky=tk.EW, padx=5, pady=4)
        self.margin_lbl = ttk.Label(wm_frame, text="3%")
        self.margin_lbl.grid(row=2, column=2, sticky=tk.W, pady=4)

        ttk.Label(wm_frame, text="위치").grid(row=3, column=0, sticky=tk.W, pady=(8, 4))
        positions = [
            "Bottom-Right",
            "Center",
            "Bottom-Left",
            "Top-Right",
            "Top-Left",
            "Bottom-Center",
            "Top-Center",
            "Middle-Left",
            "Middle-Right",
            "Custom",
        ]
        self.pos_combo = ttk.Combobox(wm_frame, values=positions, textvariable=self.position_val, state="readonly", width=22)
        self.pos_combo.grid(row=3, column=1, columnspan=2, sticky=tk.W, padx=5, pady=(8, 4))

        self.custom_x_lbl_title = ttk.Label(wm_frame, text="X 위치 (%)")
        self.custom_x_lbl_title.grid(row=4, column=0, sticky=tk.W, pady=4)
        self.custom_x_slider = ttk.Scale(wm_frame, from_=0, to=100, variable=self.custom_x_val, command=self.update_custom_x_slider)
        self.custom_x_slider.grid(row=4, column=1, sticky=tk.EW, padx=5, pady=4)
        self.custom_x_lbl = ttk.Label(wm_frame, text="95%")
        self.custom_x_lbl.grid(row=4, column=2, sticky=tk.W, pady=4)

        self.custom_y_lbl_title = ttk.Label(wm_frame, text="Y 위치 (%)")
        self.custom_y_lbl_title.grid(row=5, column=0, sticky=tk.W, pady=4)
        self.custom_y_slider = ttk.Scale(wm_frame, from_=0, to=100, variable=self.custom_y_val, command=self.update_custom_y_slider)
        self.custom_y_slider.grid(row=5, column=1, sticky=tk.EW, padx=5, pady=4)
        self.custom_y_lbl = ttk.Label(wm_frame, text="95%")
        self.custom_y_lbl.grid(row=5, column=2, sticky=tk.W, pady=4)
        wm_frame.columnconfigure(1, weight=1)

        button_frame = ttk.Frame(left, padding="5")
        button_frame.pack(fill=tk.X, pady=(5, 0))
        self.start_btn = ttk.Button(button_frame, text="변환 시작", style="Accent.TButton", command=self.start_processing)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10), ipadx=20, ipady=5)
        self.cancel_btn = ttk.Button(button_frame, text="취소", command=self.cancel_processing, state=tk.DISABLED)
        self.cancel_btn.pack(side=tk.LEFT, padx=5, ipadx=15, ipady=5)

        preview_frame = ttk.LabelFrame(right, text="미리보기 - 드래그로 이동, 모서리로 크기 조절", padding="10")
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.preview_canvas = tk.Canvas(
            preview_frame,
            width=self.PREVIEW_FALLBACK_W,
            height=self.PREVIEW_FALLBACK_H,
            bg=colors["canvas_bg"],
            highlightthickness=1,
            highlightbackground=colors["canvas_border"],
        )
        self.preview_canvas.pack(fill=tk.BOTH, expand=True)
        self.preview_canvas.bind("<Button-1>", self.on_canvas_click)
        self.preview_canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.preview_canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.preview_canvas.bind("<Motion>", self.on_canvas_motion)
        self.preview_canvas.bind("<Configure>", lambda event: self.draw_preview())

        progress_frame = ttk.LabelFrame(right, text="진행 상황 / 로그", padding="10")
        progress_frame.pack(fill=tk.BOTH, expand=False)
        self.progressbar = ttk.Progressbar(progress_frame, orient="horizontal", mode="determinate")
        self.progressbar.pack(fill=tk.X, pady=(0, 8))
        self.log_text = ScrolledText(
            progress_frame,
            height=9,
            state=tk.DISABLED,
            font=("Consolas", 9),
            bg=colors["log_bg"],
            fg=colors["log_fg"],
            insertbackground=colors["log_fg"],
            relief=tk.SOLID,
            bd=1,
            highlightthickness=0,
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _get_canvas_size(self):
        self.root.update_idletasks()
        w = self.preview_canvas.winfo_width()
        h = self.preview_canvas.winfo_height()
        if w < 50 or h < 50:
            return self.PREVIEW_FALLBACK_W, self.PREVIEW_FALLBACK_H
        return w, h

    def _get_display_box(self, canvas_w, canvas_h):
        aspect = self.watermark_aspect_ratio if self.watermark_aspect_ratio > 0 else 1.0
        wm_w = max(self.MIN_WM_W, int(canvas_w * (self.size_val.get() / 100.0)))
        wm_h = max(self.MIN_WM_H, int(wm_w / aspect))

        max_w = max(self.MIN_WM_W, int(canvas_w * 0.95))
        max_h = max(self.MIN_WM_H, int(canvas_h * 0.95))

        if wm_w > max_w:
            wm_w = max_w
            wm_h = max(self.MIN_WM_H, int(wm_w / aspect))
        if wm_h > max_h:
            wm_h = max_h
            wm_w = max(self.MIN_WM_W, int(wm_h * aspect))

        pos = self.position_val.get()
        margin_x = int(canvas_w * (self.margin_val.get() / 100.0))
        margin_y = int(canvas_h * (self.margin_val.get() / 100.0))

        if pos == "Custom":
            x = int((canvas_w - wm_w) * (self.custom_x_val.get() / 100.0))
            y = int((canvas_h - wm_h) * (self.custom_y_val.get() / 100.0))
        elif pos == "Top-Left":
            x, y = margin_x, margin_y
        elif pos == "Top-Center":
            x, y = (canvas_w - wm_w) // 2, margin_y
        elif pos == "Top-Right":
            x, y = canvas_w - wm_w - margin_x, margin_y
        elif pos == "Middle-Left":
            x, y = margin_x, (canvas_h - wm_h) // 2
        elif pos == "Center":
            x, y = (canvas_w - wm_w) // 2, (canvas_h - wm_h) // 2
        elif pos == "Middle-Right":
            x, y = canvas_w - wm_w - margin_x, (canvas_h - wm_h) // 2
        elif pos == "Bottom-Left":
            x, y = margin_x, canvas_h - wm_h - margin_y
        elif pos == "Bottom-Center":
            x, y = (canvas_w - wm_w) // 2, canvas_h - wm_h - margin_y
        else:
            x, y = canvas_w - wm_w - margin_x, canvas_h - wm_h - margin_y

        if pos != "Custom":
            x = max(0, min(x, max(0, canvas_w - wm_w)))
            y = max(0, min(y, max(0, canvas_h - wm_h)))

        return {"x": x, "y": y, "w": wm_w, "h": wm_h, "aspect": aspect}

    def _sync_custom_from_box(self, box, canvas_w, canvas_h):
        max_x = canvas_w - box["w"]
        max_y = canvas_h - box["h"]
        px = (box["x"] / max_x) * 100 if max_x > 0 else 0
        py = (box["y"] / max_y) * 100 if max_y > 0 else 0
        self.custom_x_val.set(round(max(0.0, min(100.0, px)), 1))
        self.custom_y_val.set(round(max(0.0, min(100.0, py)), 1))
        self.custom_x_lbl.config(text=f"{int(self.custom_x_val.get())}%")
        self.custom_y_lbl.config(text=f"{int(self.custom_y_val.get())}%")

    def update_custom_fields_state(self):
        custom = self.position_val.get() == "Custom"
        state = tk.NORMAL if custom else tk.DISABLED
        self.custom_x_slider.config(state=state)
        self.custom_y_slider.config(state=state)

    def update_resize_fields_state(self):
        state = tk.NORMAL if self.enable_resize.get() else tk.DISABLED
        self.w_entry.config(state=state)
        self.h_entry.config(state=state)
        self.ratio_check.config(state=state)

    def _collect_image_files(self, folder):
        supported = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
        collected = []
        for root_dir, dirnames, filenames in os.walk(folder):
            dirnames[:] = [name for name in dirnames if name.lower() != "processed"]
            for name in filenames:
                if name.lower().endswith(supported):
                    full_path = os.path.join(root_dir, name)
                    if os.path.isfile(full_path):
                        collected.append(full_path)
        return collected

    def _get_output_dimensions(self, orig_w, orig_h):
        if not self.enable_resize.get():
            return max(1, orig_w), max(1, orig_h)

        try:
            width = int(self.width_val.get().strip()) if self.width_val.get().strip() else 0
        except ValueError:
            width = 0
        try:
            height = int(self.height_val.get().strip()) if self.height_val.get().strip() else 0
        except ValueError:
            height = 0

        new_w, new_h = orig_w, orig_h
        if self.keep_ratio.get():
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
        return max(1, new_w), max(1, new_h)

    def _get_preview_geometry(self, canvas_w, canvas_h):
        if not self.preview_bg_pil:
            return None

        base_w, base_h = self._get_output_dimensions(self.preview_bg_pil.width, self.preview_bg_pil.height)
        scale = min(canvas_w / base_w, canvas_h / base_h)
        scale = max(scale, 0.01)
        disp_w = max(1, int(base_w * scale))
        disp_h = max(1, int(base_h * scale))
        disp_x = (canvas_w - disp_w) // 2
        disp_y = (canvas_h - disp_h) // 2

        logical_box = self._get_display_box(base_w, base_h)
        box = {
            "x": disp_x + int(logical_box["x"] * scale),
            "y": disp_y + int(logical_box["y"] * scale),
            "w": max(1, int(logical_box["w"] * scale)),
            "h": max(1, int(logical_box["h"] * scale)),
            "aspect": logical_box["aspect"],
        }
        return {
            "base_w": base_w,
            "base_h": base_h,
            "scale": scale,
            "display_x": disp_x,
            "display_y": disp_y,
            "display_w": disp_w,
            "display_h": disp_h,
            "box": box,
            "logical_box": logical_box,
        }

    def _get_handle_positions(self, box):
        x1 = box["x"]
        y1 = box["y"]
        x2 = x1 + box["w"]
        y2 = y1 + box["h"]
        xm = x1 + box["w"] / 2
        ym = y1 + box["h"] / 2
        return {
            "nw": (x1, y1),
            "n": (xm, y1),
            "ne": (x2, y1),
            "e": (x2, ym),
            "se": (x2, y2),
            "s": (xm, y2),
            "sw": (x1, y2),
            "w": (x1, ym),
        }

    def _get_handle_rect(self, cx, cy):
        half = self.HANDLE_SIZE // 2
        return (int(cx - half), int(cy - half), int(cx + half), int(cy + half))

    def _hit_test_handle(self, event, box):
        for handle, (cx, cy) in self._get_handle_positions(box).items():
            x1, y1, x2, y2 = self._get_handle_rect(cx, cy)
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                return handle
        return None

    def _resize_box_from_handle(self, box, handle, mx, my, canvas_w, canvas_h):
        aspect = box["aspect"] if box["aspect"] > 0 else 1.0
        x1 = box["x"]
        y1 = box["y"]
        x2 = x1 + box["w"]
        y2 = y1 + box["h"]

        if handle in ("nw", "ne", "se", "sw"):
            if handle == "nw":
                anchor_x, anchor_y = x2, y2
                dx, dy = anchor_x - mx, anchor_y - my
                new_w = max(self.MIN_WM_W, int(max(dx, dy * aspect)))
                new_h = max(self.MIN_WM_H, int(new_w / aspect))
                new_x = anchor_x - new_w
                new_y = anchor_y - new_h
            elif handle == "ne":
                anchor_x, anchor_y = x1, y2
                dx, dy = mx - anchor_x, anchor_y - my
                new_w = max(self.MIN_WM_W, int(max(dx, dy * aspect)))
                new_h = max(self.MIN_WM_H, int(new_w / aspect))
                new_x = anchor_x
                new_y = anchor_y - new_h
            elif handle == "se":
                anchor_x, anchor_y = x1, y1
                dx, dy = mx - anchor_x, my - anchor_y
                new_w = max(self.MIN_WM_W, int(max(dx, dy * aspect)))
                new_h = max(self.MIN_WM_H, int(new_w / aspect))
                new_x = anchor_x
                new_y = anchor_y
            else:  # sw
                anchor_x, anchor_y = x2, y1
                dx, dy = anchor_x - mx, my - anchor_y
                new_w = max(self.MIN_WM_W, int(max(dx, dy * aspect)))
                new_h = max(self.MIN_WM_H, int(new_w / aspect))
                new_x = anchor_x - new_w
                new_y = anchor_y
        elif handle in ("e", "w"):
            center_y = y1 + box["h"] / 2
            if handle == "e":
                new_w = max(self.MIN_WM_W, int(mx - x1))
                new_x = x1
            else:
                new_w = max(self.MIN_WM_W, int(x2 - mx))
                new_x = x2 - new_w
            new_h = max(self.MIN_WM_H, int(new_w / aspect))
            new_y = int(center_y - new_h / 2)
        else:  # n, s
            center_x = x1 + box["w"] / 2
            if handle == "s":
                new_h = max(self.MIN_WM_H, int(my - y1))
                new_y = y1
            else:
                new_h = max(self.MIN_WM_H, int(y2 - my))
                new_y = y2 - new_h
            new_w = max(self.MIN_WM_W, int(new_h * aspect))
            new_x = int(center_x - new_w / 2)

        return {"x": new_x, "y": new_y, "w": new_w, "h": new_h, "aspect": aspect}

    def browse_directory(self):
        selected = filedialog.askdirectory(title="변환할 이미지가 들어있는 폴더 선택")
        if selected:
            self.target_dir.set(os.path.normpath(selected))
            self.load_background_image_recursive(selected)

    def load_background_image(self, folder):
        supported = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
        try:
            files = [
                name
                for name in os.listdir(folder)
                if name.lower().endswith(supported) and os.path.isfile(os.path.join(folder, name))
            ]
            if not files:
                self.preview_bg_pil = None
                self.append_log("미리보기용 배경 이미지를 찾지 못했습니다.")
                self.draw_preview()
                return

            sample_name = random.choice(files)
            sample_path = os.path.join(folder, sample_name)
            with Image.open(sample_path) as img:
                self.preview_bg_pil = img.convert("RGB").copy()
            self.append_log(f"미리보기 배경으로 무작위 샘플 '{sample_name}'을 표시합니다.")
        except Exception as exc:
            self.preview_bg_pil = None
            self.append_log(f"미리보기 배경 로드 실패: {exc}")
        self.draw_preview()

    def load_background_image_recursive(self, folder):
        try:
            files = self._collect_image_files(folder)
            if not files:
                self.preview_bg_pil = None
                self.append_log("미리보기용 배경 이미지를 찾지 못했습니다.")
                self.draw_preview()
                return

            sample_path = random.choice(files)
            with Image.open(sample_path) as img:
                self.preview_bg_pil = img.convert("RGB").copy()
            rel_name = os.path.relpath(sample_path, folder)
            self.append_log(f"미리보기 배경으로 무작위 샘플 '{rel_name}'을 표시합니다.")
        except Exception as exc:
            self.preview_bg_pil = None
            self.append_log(f"미리보기 배경 로드 실패: {exc}")
        self.draw_preview()

    def browse_watermark(self):
        selected = filedialog.askopenfilename(
            title="워터마크 PNG 선택",
            filetypes=[("PNG Files", "*.png"), ("All Files", "*.*")],
        )
        if selected:
            self.watermark_path.set(os.path.normpath(selected))
            try:
                with Image.open(selected) as img:
                    self.loaded_watermark_pil = img.convert("RGBA").copy()
                    self.watermark_aspect_ratio = self.loaded_watermark_pil.width / self.loaded_watermark_pil.height
                self.append_log("워터마크 이미지를 불러왔습니다.")
            except Exception as exc:
                self.loaded_watermark_pil = None
                self.watermark_aspect_ratio = 1.0
                messagebox.showerror("오류", f"워터마크 이미지를 열 수 없습니다.\n{exc}")
        self.draw_preview()

    def update_sliders_lbl(self, *args):
        self.opacity_lbl.config(text=f"{int(self.opacity_val.get())}%")
        self.size_lbl.config(text=f"{int(self.size_val.get())}%")
        self.margin_lbl.config(text=f"{int(self.margin_val.get())}%")
        if self.position_val.get() != "Custom":
            self.update_custom_coords_from_standard()
        self.draw_preview()

    def on_position_change(self, *args):
        self.update_custom_fields_state()
        if self.position_val.get() != "Custom":
            self.update_custom_coords_from_standard()
        self.draw_preview()

    def update_custom_coords_from_standard(self):
        if self.position_val.get() == "Custom":
            return
        if not self.preview_bg_pil:
            return
        base_w, base_h = self._get_output_dimensions(self.preview_bg_pil.width, self.preview_bg_pil.height)
        box = self._get_display_box(base_w, base_h)
        self._sync_custom_from_box(box, base_w, base_h)

    def update_custom_x_slider(self, *args):
        self.custom_x_lbl.config(text=f"{int(self.custom_x_val.get())}%")
        if self.position_val.get() != "Custom":
            self.position_val.set("Custom")
        self.draw_preview()

    def update_custom_y_slider(self, *args):
        self.custom_y_lbl.config(text=f"{int(self.custom_y_val.get())}%")
        if self.position_val.get() != "Custom":
            self.position_val.set("Custom")
        self.draw_preview()

    def on_canvas_click(self, event):
        if self.is_processing:
            return
        canvas_w, canvas_h = self._get_canvas_size()
        geom = self._get_preview_geometry(canvas_w, canvas_h)
        if not geom:
            return
        box = geom["box"]
        handle = self._hit_test_handle(event, box)
        inside_box = box["x"] <= event.x <= box["x"] + box["w"] and box["y"] <= event.y <= box["y"] + box["h"]

        if handle:
            self.is_resizing = True
            self.is_dragging = False
            self.active_handle = handle
        elif inside_box:
            self.is_dragging = True
            self.is_resizing = False
            self.active_handle = None
            self.drag_offset_x = event.x - box["x"]
            self.drag_offset_y = event.y - box["y"]
        else:
            self.is_dragging = False
            self.is_resizing = False
            self.active_handle = None
            self.move_watermark_to(event.x, event.y)

    def on_canvas_drag(self, event):
        if self.is_processing:
            return
        canvas_w, canvas_h = self._get_canvas_size()
        geom = self._get_preview_geometry(canvas_w, canvas_h)
        if not geom:
            return
        box = geom["box"]

        if self.is_resizing:
            resized = self._resize_box_from_handle(box, self.active_handle or "se", event.x, event.y, canvas_w, canvas_h)
            size_pct = (resized["w"] / geom["display_w"]) * 100 if geom["display_w"] > 0 else 20.0
            self.size_val.set(round(max(1.0, min(100.0, size_pct)), 1))
            self.size_lbl.config(text=f"{int(self.size_val.get())}%")
            if self.position_val.get() != "Custom":
                self.position_val.set("Custom")
            max_x = max(1, geom["display_w"] - resized["w"])
            max_y = max(1, geom["display_h"] - resized["h"])
            rel_x = resized["x"] - geom["display_x"]
            rel_y = resized["y"] - geom["display_y"]
            self.custom_x_val.set(round((rel_x / max_x) * 100, 1))
            self.custom_y_val.set(round((rel_y / max_y) * 100, 1))
            self.custom_x_lbl.config(text=f"{int(self.custom_x_val.get())}%")
            self.custom_y_lbl.config(text=f"{int(self.custom_y_val.get())}%")
            self.draw_preview()
        elif self.is_dragging:
            new_x = event.x - self.drag_offset_x
            new_y = event.y - self.drag_offset_y
            self.position_val.set("Custom")
            max_x = max(1, geom["display_w"] - box["w"])
            max_y = max(1, geom["display_h"] - box["h"])
            rel_x = new_x - geom["display_x"]
            rel_y = new_y - geom["display_y"]
            self.custom_x_val.set(round((rel_x / max_x) * 100, 1))
            self.custom_y_val.set(round((rel_y / max_y) * 100, 1))
            self.custom_x_lbl.config(text=f"{int(self.custom_x_val.get())}%")
            self.custom_y_lbl.config(text=f"{int(self.custom_y_val.get())}%")
            self.draw_preview()

    def on_canvas_release(self, event):
        self.is_dragging = False
        self.is_resizing = False
        self.active_handle = None

    def on_canvas_motion(self, event):
        if self.is_processing:
            return
        canvas_w, canvas_h = self._get_canvas_size()
        geom = self._get_preview_geometry(canvas_w, canvas_h)
        if not geom:
            return
        box = geom["box"]
        handle = self._hit_test_handle(event, box)
        inside_box = box["x"] <= event.x <= box["x"] + box["w"] and box["y"] <= event.y <= box["y"] + box["h"]
        if handle:
            self.preview_canvas.config(cursor=self.HANDLE_CURSOR_MAP.get(handle, "size_nw_se"))
        elif inside_box:
            self.preview_canvas.config(cursor="fleur")
        else:
            self.preview_canvas.config(cursor="")

    def move_watermark_to(self, mx, my):
        canvas_w, canvas_h = self._get_canvas_size()
        geom = self._get_preview_geometry(canvas_w, canvas_h)
        if not geom:
            return
        box = geom["box"]
        x = int(mx - box["w"] / 2)
        y = int(my - box["h"] / 2)
        self.position_val.set("Custom")
        max_x = max(1, geom["display_w"] - box["w"])
        max_y = max(1, geom["display_h"] - box["h"])
        rel_x = x - geom["display_x"]
        rel_y = y - geom["display_y"]
        self.custom_x_val.set(round((rel_x / max_x) * 100, 1))
        self.custom_y_val.set(round((rel_y / max_y) * 100, 1))
        self.custom_x_lbl.config(text=f"{int(self.custom_x_val.get())}%")
        self.custom_y_lbl.config(text=f"{int(self.custom_y_val.get())}%")
        self.draw_preview()

    def _draw_preview_scaled(self):
        canvas_w, canvas_h = self._get_canvas_size()
        self.preview_canvas.delete("all")
        colors = self.theme_colors

        base = Image.new("RGBA", (canvas_w, canvas_h), colors["canvas_bg"])
        geom = self._get_preview_geometry(canvas_w, canvas_h)
        if geom and self.preview_bg_pil:
            bg = self.preview_bg_pil.convert("RGBA")
            bg_resized = bg.resize((geom["display_w"], geom["display_h"]), resample=get_resample())
            base.alpha_composite(bg_resized, dest=(geom["display_x"], geom["display_y"]))
            bg_resized.close()

        box = geom["box"] if geom else {"x": 0, "y": 0, "w": 0, "h": 0}
        if self.loaded_watermark_pil and geom:
            wm = self.loaded_watermark_pil.convert("RGBA").resize((box["w"], box["h"]), resample=get_resample())
            if self.opacity_val.get() < 100:
                alpha = wm.getchannel("A")
                alpha = alpha.point(lambda p: int(p * (self.opacity_val.get() / 100.0)))
                wm.putalpha(alpha)
            base.alpha_composite(wm, dest=(box["x"], box["y"]))
            wm.close()

        self.preview_composite_tk = ImageTk.PhotoImage(base.convert("RGB"))
        self.preview_canvas.create_image(0, 0, anchor=tk.NW, image=self.preview_composite_tk)
        base.close()

        if geom:
            outline = colors["preview_outline"]
            fill = colors["preview_fill"] if not self.loaded_watermark_pil else ""
            self.preview_canvas.create_rectangle(
                box["x"], box["y"], box["x"] + box["w"], box["y"] + box["h"],
                outline=outline, width=2, fill=fill
            )

            if not self.loaded_watermark_pil:
                self.preview_canvas.create_text(
                    box["x"] + box["w"] / 2,
                    box["y"] + box["h"] / 2,
                    text="워터마크를 선택하세요.",
                    fill=colors["preview_text"],
                    font=("Malgun Gothic", 11, "bold"),
                    justify=tk.CENTER,
                )

            for handle, (cx, cy) in self._get_handle_positions(box).items():
                x1, y1, x2, y2 = self._get_handle_rect(cx, cy)
                fill_color = colors["accent"] if handle == "se" else colors["handle_fill"]
                outline_color = colors["accent"]
                self.preview_canvas.create_rectangle(
                    x1, y1, x2, y2,
                    fill=fill_color,
                    outline=outline_color,
                    width=2,
                )

    def draw_preview(self):
        return self._draw_preview_scaled()
        canvas_w, canvas_h = self._get_canvas_size()
        self.preview_canvas.delete("all")

        base = Image.new("RGBA", (canvas_w, canvas_h), "#eef2f7")
        if self.preview_bg_pil:
            bg = self.preview_bg_pil.convert("RGBA")
            ratio = min(canvas_w / bg.width, canvas_h / bg.height)
            ratio = max(ratio, 0.01)
            new_size = (max(1, int(bg.width * ratio)), max(1, int(bg.height * ratio)))
            resample = get_resample()
            bg_resized = bg.resize(new_size, resample=resample)
            base.alpha_composite(bg_resized, dest=((canvas_w - new_size[0]) // 2, (canvas_h - new_size[1]) // 2))

        box = self._get_display_box(canvas_w, canvas_h)
        if self.loaded_watermark_pil:
            wm = self.loaded_watermark_pil.convert("RGBA").resize((box["w"], box["h"]), resample=get_resample())
            if self.opacity_val.get() < 100:
                alpha = wm.getchannel("A")
                alpha = alpha.point(lambda p: int(p * (self.opacity_val.get() / 100.0)))
                wm.putalpha(alpha)
            base.alpha_composite(wm, dest=(box["x"], box["y"]))

        self.preview_composite_tk = ImageTk.PhotoImage(base.convert("RGB"))
        self.preview_canvas.create_image(0, 0, anchor=tk.NW, image=self.preview_composite_tk)

        outline = "#2563eb"
        fill = "#dbeafe" if not self.loaded_watermark_pil else ""
        self.preview_canvas.create_rectangle(
            box["x"], box["y"], box["x"] + box["w"], box["y"] + box["h"],
            outline=outline, width=2, fill=fill
        )

        if not self.loaded_watermark_pil:
            self.preview_canvas.create_text(
                box["x"] + box["w"] / 2,
                box["y"] + box["h"] / 2,
                text="워터마크를 선택하세요.",
                fill="#1e40af",
                font=("Malgun Gothic", 11, "bold"),
                justify=tk.CENTER,
            )

        for handle, (cx, cy) in self._get_handle_positions(box).items():
            x1, y1, x2, y2 = self._get_handle_rect(cx, cy)
            fill_color = "#0f766e" if handle == "se" else "#ffffff"
            outline_color = "#0f766e"
            self.preview_canvas.create_rectangle(
                x1, y1, x2, y2,
                fill=fill_color,
                outline=outline_color,
                width=2,
            )

    def on_resize_toggle(self):
        self.update_resize_fields_state()
        self.draw_preview()

    def append_log(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def toggle_inputs(self, enable):
        state = tk.NORMAL if enable else tk.DISABLED
        self.dir_entry.config(state=state)
        self.wm_entry.config(state=state)
        self.opacity_slider.config(state=state)
        self.size_slider.config(state=state)
        self.margin_slider.config(state=state)
        self.pos_combo.config(state=state)
        self.resize_check.config(state=state)
        if enable:
            self.update_resize_fields_state()
            self.update_custom_fields_state()
        else:
            self.w_entry.config(state=tk.DISABLED)
            self.h_entry.config(state=tk.DISABLED)
            self.ratio_check.config(state=tk.DISABLED)
            self.custom_x_slider.config(state=tk.DISABLED)
            self.custom_y_slider.config(state=tk.DISABLED)
        self.start_btn.config(state=state)
        self.cancel_btn.config(state=tk.NORMAL if not enable else tk.DISABLED)

    def start_processing(self):
        target = self.target_dir.get().strip()
        watermark = self.watermark_path.get().strip()
        enable_resize = self.enable_resize.get()
        keep_ratio = self.keep_ratio.get()
        width_str = self.width_val.get().strip()
        height_str = self.height_val.get().strip()

        if not target:
            messagebox.showerror("오류", "대상 폴더를 선택해 주세요.")
            return
        if not os.path.isdir(target):
            messagebox.showerror("오류", "대상 폴더 경로가 올바르지 않습니다.")
            return
        if enable_resize:
            if keep_ratio:
                if not width_str and not height_str:
                    messagebox.showerror("오류", "가로 또는 세로 중 하나 이상 입력해 주세요.")
                    return
                if width_str and not width_str.isdigit():
                    messagebox.showerror("오류", "가로(Width) 값은 숫자만 입력해 주세요.")
                    return
                if height_str and not height_str.isdigit():
                    messagebox.showerror("오류", "세로(Height) 값은 숫자만 입력해 주세요.")
                    return
            else:
                if not width_str or not height_str:
                    messagebox.showerror("오류", "비율 유지를 끄면 가로와 세로를 모두 입력해야 합니다.")
                    return
                if not width_str.isdigit() or not height_str.isdigit():
                    messagebox.showerror("오류", "가로와 세로는 숫자만 입력해 주세요.")
                    return
        if watermark and not os.path.isfile(watermark):
            messagebox.showerror("오류", "워터마크 파일 경로가 올바르지 않습니다.")
            return

        self.is_processing = True
        self.cancel_requested = False
        self.toggle_inputs(False)
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.progressbar["value"] = 0
        self.progressbar["maximum"] = 1

        self.append_log("작업을 시작합니다.")
        if not watermark:
            self.append_log("워터마크 없이 크기 조절만 진행합니다.")

        worker = threading.Thread(
            target=self.process_images_thread_recursive,
            args=(
                target,
                watermark,
                enable_resize,
                int(width_str) if width_str.isdigit() and enable_resize else 0,
                int(height_str) if height_str.isdigit() and enable_resize else 0,
                keep_ratio,
                float(self.opacity_val.get()),
                float(self.size_val.get()),
                float(self.margin_val.get()),
                self.position_val.get(),
                float(self.custom_x_val.get()),
                float(self.custom_y_val.get()),
            ),
            daemon=True,
        )
        worker.start()

    def cancel_processing(self):
        if self.is_processing:
            self.cancel_requested = True
            self.append_log("취소 요청을 받았습니다. 현재 파일 처리 후 종료합니다.")
            self.cancel_btn.config(state=tk.DISABLED)

    def process_images_thread(self, target_dir, watermark_path, enable_resize, width, height, keep_ratio, opacity, size, margin, position, custom_x, custom_y):
        supported = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
        try:
            files = [
                name
                for name in os.listdir(target_dir)
                if name.lower().endswith(supported) and os.path.isfile(os.path.join(target_dir, name))
            ]
        except Exception as exc:
            self.queue.put(("error", f"폴더를 읽는 데 실패했습니다: {exc}"))
            return

        if not files:
            self.queue.put(("error", "처리할 이미지 파일이 없습니다."))
            return

        self.queue.put(("count", len(files)))

        watermark = None
        try:
            if watermark_path:
                watermark = Image.open(watermark_path)
                watermark.load()
        except Exception as exc:
            self.queue.put(("error", f"워터마크 이미지를 읽는 데 실패했습니다: {exc}"))
            return

        try:
            os.makedirs(target_dir, exist_ok=True)
        except Exception as exc:
            if watermark:
                watermark.close()
            self.queue.put(("error", f"결과 폴더를 만들 수 없습니다: {exc}"))
            return

        try:
            resample = get_resample()
            done = 0
            for idx, filename in enumerate(files, start=1):
                if self.cancel_requested:
                    break

                file_path = os.path.join(target_dir, filename)
                self.queue.put(("log", f"[{idx}/{len(files)}] {filename} 처리 중..."))

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

                        processed = img.resize((new_w, new_h), resample=resample) if (new_w, new_h) != (orig_w, orig_h) else img.copy()

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
                            if position == "Top-Left":
                                x, y = margin_px, margin_px
                            elif position == "Top-Center":
                                x, y = (new_w - wm_scaled_w) // 2, margin_px
                            elif position == "Top-Right":
                                x, y = new_w - wm_scaled_w - margin_px, margin_px
                            elif position == "Middle-Left":
                                x, y = margin_px, (new_h - wm_scaled_h) // 2
                            elif position == "Center":
                                x, y = (new_w - wm_scaled_w) // 2, (new_h - wm_scaled_h) // 2
                            elif position == "Middle-Right":
                                x, y = new_w - wm_scaled_w - margin_px, (new_h - wm_scaled_h) // 2
                            elif position == "Bottom-Left":
                                x, y = margin_px, new_h - wm_scaled_h - margin_px
                            elif position == "Bottom-Center":
                                x, y = (new_w - wm_scaled_w) // 2, new_h - wm_scaled_h - margin_px
                            elif position == "Custom":
                                x = int((new_w - wm_scaled_w) * (custom_x / 100.0))
                                y = int((new_h - wm_scaled_h) * (custom_y / 100.0))
                            else:
                                x, y = new_w - wm_scaled_w - margin_px, new_h - wm_scaled_h - margin_px

                            if position != "Custom":
                                x = max(0, min(x, max(0, new_w - wm_scaled_w)))
                                y = max(0, min(y, max(0, new_h - wm_scaled_h)))

                            if processed.mode not in ("RGB", "RGBA"):
                                processed = processed.convert("RGB")

                            if scaled_wm.mode == "RGBA":
                                processed.paste(scaled_wm, (x, y), scaled_wm)
                            else:
                                processed.paste(scaled_wm, (x, y))
                            scaled_wm.close()

                        out_dir = os.path.join(target_dir, "processed")
                        os.makedirs(out_dir, exist_ok=True)
                        out_path = os.path.join(out_dir, filename)
                        ext = filename.lower().split(".")[-1]
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

                    done += 1
                    self.queue.put(("progress", done))
                except Exception as exc:
                    self.queue.put(("log", f"오류: {filename} 처리 실패 - {exc}"))
        finally:
            if watermark:
                watermark.close()
            gc.collect()
            self.queue.put(("finish", done))

    def process_images_thread_recursive(self, target_dir, watermark_path, enable_resize, width, height, keep_ratio, opacity, size, margin, position, custom_x, custom_y):
        try:
            files = self._collect_image_files(target_dir)
        except Exception as exc:
            self.queue.put(("error", f"대상을 읽는 데 실패했습니다: {exc}"))
            return

        if not files:
            self.queue.put(("error", "처리할 이미지 파일이 없습니다."))
            return

        self.queue.put(("count", len(files)))

        watermark = None
        try:
            if watermark_path:
                watermark = Image.open(watermark_path)
                watermark.load()
        except Exception as exc:
            self.queue.put(("error", f"워터마크 이미지를 여는 데 실패했습니다: {exc}"))
            return

        done = 0
        try:
            resample = get_resample()
            for idx, file_path in enumerate(files, start=1):
                if self.cancel_requested:
                    break

                rel_path = os.path.relpath(file_path, target_dir)
                self.queue.put(("log", f"[{idx}/{len(files)}] {rel_path} 처리 중..."))

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

                        processed = img.resize((new_w, new_h), resample=resample) if (new_w, new_h) != (orig_w, orig_h) else img.copy()

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
                            if position == "Top-Left":
                                x, y = margin_px, margin_px
                            elif position == "Top-Center":
                                x, y = (new_w - wm_scaled_w) // 2, margin_px
                            elif position == "Top-Right":
                                x, y = new_w - wm_scaled_w - margin_px, margin_px
                            elif position == "Middle-Left":
                                x, y = margin_px, (new_h - wm_scaled_h) // 2
                            elif position == "Center":
                                x, y = (new_w - wm_scaled_w) // 2, (new_h - wm_scaled_h) // 2
                            elif position == "Middle-Right":
                                x, y = new_w - wm_scaled_w - margin_px, (new_h - wm_scaled_h) // 2
                            elif position == "Bottom-Left":
                                x, y = margin_px, new_h - wm_scaled_h - margin_px
                            elif position == "Bottom-Center":
                                x, y = (new_w - wm_scaled_w) // 2, new_h - wm_scaled_h - margin_px
                            elif position == "Custom":
                                x = int((new_w - wm_scaled_w) * (custom_x / 100.0))
                                y = int((new_h - wm_scaled_h) * (custom_y / 100.0))
                            else:
                                x, y = new_w - wm_scaled_w - margin_px, new_h - wm_scaled_h - margin_px

                            if position != "Custom":
                                x = max(0, min(x, max(0, new_w - wm_scaled_w)))
                                y = max(0, min(y, max(0, new_h - wm_scaled_h)))

                            if processed.mode not in ("RGB", "RGBA"):
                                processed = processed.convert("RGB")

                            if scaled_wm.mode == "RGBA":
                                processed.paste(scaled_wm, (x, y), scaled_wm)
                            else:
                                processed.paste(scaled_wm, (x, y))
                            scaled_wm.close()

                        out_dir = os.path.join(os.path.dirname(file_path), "processed")
                        os.makedirs(out_dir, exist_ok=True)
                        out_path = os.path.join(out_dir, os.path.basename(file_path))
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

                    done += 1
                    self.queue.put(("progress", done))
                except Exception as exc:
                    self.queue.put(("log", f"오류: {rel_path} 처리 실패 - {exc}"))
        finally:
            if watermark:
                watermark.close()
            gc.collect()
            self.queue.put(("finish", done))

    def poll_queue(self):
        try:
            while True:
                msg_type, value = self.queue.get_nowait()
                if msg_type == "log":
                    self.append_log(value)
                elif msg_type == "count":
                    self.total_files = value
                    self.progressbar["maximum"] = value
                    self.append_log(f"총 {value}개의 이미지가 발견되었습니다.")
                elif msg_type == "progress":
                    self.progressbar["value"] = value
                elif msg_type == "finish":
                    self.is_processing = False
                    self.toggle_inputs(True)
                    if self.cancel_requested:
                        self.append_log("작업이 취소되었습니다.")
                        messagebox.showinfo("취소", f"처리가 중단되었습니다. 완료한 파일: {value}개")
                    else:
                        self.append_log("모든 작업이 완료되었습니다.")
                        self.append_log("결과 폴더: 각 원본 폴더의 processed")
                        messagebox.showinfo("완료", f"변환이 완료되었습니다.\n성공: {value}/{self.total_files}")
                elif msg_type == "error":
                    self.is_processing = False
                    self.toggle_inputs(True)
                    self.append_log(f"오류: {value}")
                    messagebox.showerror("오류", value)
                self.queue.task_done()
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.poll_queue)

if __name__ == "__main__":
    root = tk.Tk()
    app = WatermarkResizerApp(root)
    root.mainloop()

