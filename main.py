import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import io

try:
    from w32_drop import enable_drop
except ImportError:
    enable_drop = None

try:
    import operations
except ImportError:
    operations = None

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

APP_TITLE = "PDF助手"
APP_VERSION = "1.0"
WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 720


class PDFApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{APP_TITLE} v{APP_VERSION}")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(900, 600)

        self.files = []
        self.files_info = {}
        self.output_dir = tk.StringVar(value="")
        self._cancel_flag = False
        self._batch_log = []
        self._thumb_cache = {}
        self._thumb_page_cache = {}

        self._build_ui()
        self._setup_dnd()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _build_ui(self):
        self._build_topbar()
        self._build_main_area()
        self._build_statusbar()

    def _build_topbar(self):
        topbar = tk.Frame(self.root, bg="#f0f0f0", height=40)
        topbar.pack(fill=tk.X, side=tk.TOP)
        topbar.pack_propagate(False)

        title_label = tk.Label(topbar, text=f"{APP_TITLE} v{APP_VERSION}",
                               font=("Microsoft YaHei", 12, "bold"), bg="#f0f0f0")
        title_label.pack(side=tk.LEFT, padx=15, pady=5)

    def _build_main_area(self):
        pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        left_frame = tk.Frame(pane)
        pane.add(left_frame, weight=1)
        self._build_left_panel(left_frame)

        right_frame = tk.Frame(pane)
        pane.add(right_frame, weight=2)
        self._build_right_panel(right_frame)

    def _build_left_panel(self, parent):
        drop_frame = tk.LabelFrame(parent, text="PDF文件 (拖放到此处)", font=("Microsoft YaHei", 9))
        drop_frame.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)

        list_frame = tk.Frame(drop_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.file_listbox = tk.Listbox(list_frame, selectmode=tk.EXTENDED,
                                       yscrollcommand=scrollbar.set, font=("Microsoft YaHei", 9))
        self.file_listbox.pack(fill=tk.BOTH, expand=True)
        self.file_listbox.bind("<<ListboxSelect>>", self._on_file_select)
        scrollbar.config(command=self.file_listbox.yview)

        self.file_count_label = tk.Label(drop_frame, text="已添加 0 个文件",
                                         font=("Microsoft YaHei", 9), fg="gray")
        self.file_count_label.pack(anchor=tk.W, padx=5)

        btn_frame = tk.Frame(drop_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        tk.Button(btn_frame, text="添加文件", command=self._add_files,
                  font=("Microsoft YaHei", 9)).pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(btn_frame, text="移除选中", command=self._remove_selected,
                  font=("Microsoft YaHei", 9)).pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(btn_frame, text="清空", command=self._clear_files,
                  font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)

        out_frame = tk.LabelFrame(parent, text="输出目录", font=("Microsoft YaHei", 9))
        out_frame.pack(fill=tk.X, padx=3, pady=3)

        out_row = tk.Frame(out_frame)
        out_row.pack(fill=tk.X, padx=5, pady=5)
        self.out_entry = tk.Entry(out_row, textvariable=self.output_dir,
                                  font=("Microsoft YaHei", 9))
        self.out_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        tk.Button(out_row, text="浏览", command=self._choose_output_dir,
                  font=("Microsoft YaHei", 9)).pack(side=tk.RIGHT)

    def _build_right_panel(self, parent):
        info_frame = tk.LabelFrame(parent, text="文件信息", font=("Microsoft YaHei", 9))
        info_frame.pack(fill=tk.X, padx=3, pady=3)

        self.info_text = tk.Text(info_frame, height=1, font=("Consolas", 9), state=tk.DISABLED,
                                 bg="#fafafa")
        self.info_text.pack(fill=tk.X, padx=5, pady=2)

        preview_frame = tk.LabelFrame(parent, text="页面预览", font=("Microsoft YaHei", 9))
        preview_frame.pack(fill=tk.BOTH, expand=False, padx=3, pady=(0, 2))

        self.preview_canvas = tk.Canvas(preview_frame, height=100, bg="#e8e8e8",
                                        highlightthickness=0)
        self.preview_scroll = tk.Scrollbar(preview_frame, orient=tk.HORIZONTAL,
                                           command=self.preview_canvas.xview)
        self.preview_canvas.configure(xscrollcommand=self.preview_scroll.set)
        self.preview_canvas.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
        self.preview_scroll.pack(fill=tk.X, padx=3, pady=(0, 3))

        self.preview_inner = tk.Frame(self.preview_canvas, bg="#e8e8e8")
        self.preview_canvas.create_window((0, 0), window=self.preview_inner, anchor=tk.NW)
        self.preview_inner.bind("<Configure>",
                                lambda e: self.preview_canvas.configure(
                                    scrollregion=self.preview_canvas.bbox("all")))
        self.preview_canvas.bind("<MouseWheel>",
                                 lambda e: self.preview_canvas.xview_scroll(
                                     int(-e.delta / 60), "units"))
        self._preview_labels = []

        self.op_notebook = ttk.Notebook(parent)
        self.op_notebook.pack(fill=tk.BOTH, expand=True, padx=3, pady=(0, 3))

        self._build_merge_tab()
        self._build_split_tab()
        self._build_extract_tab()
        self._build_convert_tab()
        self._build_encrypt_tab()
        self._build_compress_tab()
        self._build_watermark_tab()
        self._build_img2pdf_tab()
        self._build_ocr_tab()

        name_frame = tk.Frame(parent)
        name_frame.pack(fill=tk.X, padx=3, pady=(0, 0))
        tk.Label(name_frame, text="文件名:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.output_name = tk.StringVar(value="output")
        tk.Entry(name_frame, textvariable=self.output_name,
                 font=("Microsoft YaHei", 9)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        action_frame = tk.Frame(parent)
        action_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=3, pady=(2, 3))
        action_frame.columnconfigure(0, weight=1)
        action_frame.columnconfigure(1, weight=1)
        action_frame.columnconfigure(2, weight=1)
        tk.Button(action_frame, text="预览效果", command=self._do_preview,
                  font=("Microsoft YaHei", 11), height=1).grid(row=0, column=0, padx=2, sticky="ew")
        tk.Button(action_frame, text="开始处理", command=self._start_batch,
                  font=("Microsoft YaHei", 11), bg="#2196F3", fg="white", height=1).grid(
            row=0, column=1, padx=2, sticky="ew")
        tk.Button(action_frame, text="取消", command=self._cancel_batch,
                  font=("Microsoft YaHei", 11), height=1).grid(row=0, column=2, padx=2, sticky="ew")

    def _build_merge_tab(self):
        tab = tk.Frame(self.op_notebook)
        self.op_notebook.add(tab, text="合并")
        tk.Label(tab, text="将所有PDF文件合并为一个PDF",
                 font=("Microsoft YaHei", 10)).pack(anchor=tk.W, padx=15, pady=(15, 5))
        tk.Label(tab, text="合并顺序与左侧文件列表顺序一致。可用右侧按钮调整顺序。",
                 font=("Microsoft YaHei", 8), fg="gray").pack(anchor=tk.W, padx=15)

        reorder_frame = tk.Frame(tab)
        reorder_frame.pack(fill=tk.X, padx=15, pady=10)
        self._build_reorder_buttons(reorder_frame)

        out_frame = tk.Frame(tab)
        out_frame.pack(fill=tk.X, padx=15, pady=5)
        tk.Label(out_frame, text="输出文件名:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.merge_out_name = tk.StringVar(value="合并输出")
        tk.Entry(out_frame, textvariable=self.merge_out_name,
                 font=("Microsoft YaHei", 9), width=20).pack(side=tk.LEFT, padx=5)

    def _build_reorder_buttons(self, parent):
        tk.Button(parent, text="↑ 上移", command=self._move_file_up,
                  font=("Microsoft YaHei", 9), width=8).pack(side=tk.LEFT, padx=3)
        tk.Button(parent, text="↓ 下移", command=self._move_file_down,
                  font=("Microsoft YaHei", 9), width=8).pack(side=tk.LEFT, padx=3)

    def _move_file_up(self):
        sel = self.file_listbox.curselection()
        if len(sel) == 1:
            idx = sel[0]
            if idx > 0:
                self.files[idx], self.files[idx - 1] = self.files[idx - 1], self.files[idx]
                self._refresh_file_list()
                self.file_listbox.selection_set(idx - 1)

    def _move_file_down(self):
        sel = self.file_listbox.curselection()
        if len(sel) == 1:
            idx = sel[0]
            if idx < len(self.files) - 1:
                self.files[idx], self.files[idx + 1] = self.files[idx + 1], self.files[idx]
                self._refresh_file_list()
                self.file_listbox.selection_set(idx + 1)

    def _build_split_tab(self):
        tab = tk.Frame(self.op_notebook)
        self.op_notebook.add(tab, text="拆分")

        self.split_mode = tk.StringVar(value="range")
        tk.Radiobutton(tab, text="按页码范围拆分", variable=self.split_mode,
                       value="range", font=("Microsoft YaHei", 10),
                       command=self._on_split_mode).pack(anchor=tk.W, padx=15, pady=(15, 5))

        self.split_range_frame = tk.Frame(tab)
        self.split_range_frame.pack(fill=tk.X, padx=30, pady=5)
        tk.Label(self.split_range_frame, text="页码范围:",
                 font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.split_range_entry = tk.Entry(self.split_range_frame, font=("Microsoft YaHei", 9), width=25)
        self.split_range_entry.pack(side=tk.LEFT, padx=5)
        self.split_range_entry.insert(0, "1-3,5,7-9")
        tk.Label(self.split_range_frame, text="例: 1-3,5,7-9",
                 font=("Microsoft YaHei", 8), fg="gray").pack(side=tk.LEFT)

        tk.Radiobutton(tab, text="每N页拆分为一个文件", variable=self.split_mode,
                       value="every_n", font=("Microsoft YaHei", 10),
                       command=self._on_split_mode).pack(anchor=tk.W, padx=15, pady=(10, 5))

        self.split_n_frame = tk.Frame(tab)
        self.split_n_frame.pack(fill=tk.X, padx=30, pady=5)
        tk.Label(self.split_n_frame, text="每",
                 font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.split_n_var = tk.IntVar(value=1)
        tk.Spinbox(self.split_n_frame, from_=1, to=999, textvariable=self.split_n_var,
                   font=("Microsoft YaHei", 9), width=5).pack(side=tk.LEFT, padx=5)
        tk.Label(self.split_n_frame, text="页一个文件",
                 font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)

        self._on_split_mode()

    def _on_split_mode(self):
        if self.split_mode.get() == "range":
            self.split_n_frame.pack_forget()
            self.split_range_frame.pack(fill=tk.X, padx=30, pady=5)
        else:
            self.split_range_frame.pack_forget()
            self.split_n_frame.pack(fill=tk.X, padx=30, pady=5)

    def _build_extract_tab(self):
        tab = tk.Frame(self.op_notebook)
        self.op_notebook.add(tab, text="提取")

        tk.Label(tab, text="提取指定页面为新的PDF",
                 font=("Microsoft YaHei", 10)).pack(anchor=tk.W, padx=15, pady=(15, 5))

        range_frame = tk.Frame(tab)
        range_frame.pack(fill=tk.X, padx=15, pady=5)
        tk.Label(range_frame, text="页码范围:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.extract_range = tk.Entry(range_frame, font=("Microsoft YaHei", 9), width=25)
        self.extract_range.pack(side=tk.LEFT, padx=5)
        self.extract_range.insert(0, "1-5,8,10-12")
        tk.Label(range_frame, text="例: 1-5,8,10-12",
                 font=("Microsoft YaHei", 8), fg="gray").pack(side=tk.LEFT)

        out_frame = tk.Frame(tab)
        out_frame.pack(fill=tk.X, padx=15, pady=5)
        tk.Label(out_frame, text="输出文件名:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.extract_out_name = tk.StringVar(value="提取页面")
        tk.Entry(out_frame, textvariable=self.extract_out_name,
                 font=("Microsoft YaHei", 9), width=20).pack(side=tk.LEFT, padx=5)

        thumb_frame = tk.LabelFrame(tab, text="页面缩略图 (点击切换选中)",
                                    font=("Microsoft YaHei", 9))
        thumb_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        self.thumb_canvas = tk.Canvas(thumb_frame, height=140, bg="#f5f5f5")
        self.thumb_scrollbar = tk.Scrollbar(thumb_frame, orient=tk.HORIZONTAL,
                                            command=self.thumb_canvas.xview)
        self.thumb_canvas.configure(xscrollcommand=self.thumb_scrollbar.set)
        self.thumb_canvas.pack(fill=tk.X, padx=5, pady=(5, 0))
        self.thumb_scrollbar.pack(fill=tk.X, padx=5)

        self.thumb_inner = tk.Frame(self.thumb_canvas, bg="#f5f5f5")
        self.thumb_canvas.create_window((0, 0), window=self.thumb_inner, anchor=tk.NW)
        self.thumb_inner.bind("<Configure>",
                              lambda e: self.thumb_canvas.configure(
                                  scrollregion=self.thumb_canvas.bbox("all")))
        self.thumb_selected = set()
        self.thumb_labels = []

    def _build_convert_tab(self):
        tab = tk.Frame(self.op_notebook)
        self.op_notebook.add(tab, text="转换")

        tk.Label(tab, text="PDF转换为图片或Word文档",
                 font=("Microsoft YaHei", 10)).pack(anchor=tk.W, padx=15, pady=(15, 5))

        fmt_frame = tk.Frame(tab)
        fmt_frame.pack(fill=tk.X, padx=15, pady=5)
        tk.Label(fmt_frame, text="输出格式:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.convert_fmt = tk.StringVar(value="PNG")
        ttk.Combobox(fmt_frame, textvariable=self.convert_fmt,
                     values=["PNG", "JPEG", "Word (.docx)"],
                     font=("Microsoft YaHei", 9), width=14, state="readonly").pack(
            side=tk.LEFT, padx=5)

        self._convert_img_opts = tk.Frame(tab)
        self._convert_img_opts.pack(fill=tk.X, padx=15, pady=5)
        dpi_frame = tk.Frame(self._convert_img_opts)
        dpi_frame.pack(fill=tk.X)
        tk.Label(dpi_frame, text="DPI:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.convert_dpi_var = tk.StringVar(value="150")
        ttk.Combobox(dpi_frame, textvariable=self.convert_dpi_var,
                     values=["72", "96", "150", "200", "300"],
                     font=("Microsoft YaHei", 9), width=6).pack(side=tk.LEFT, padx=5)

        q_frame = tk.Frame(self._convert_img_opts)
        q_frame.pack(fill=tk.X, pady=(3, 0))
        tk.Label(q_frame, text="JPEG质量:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.convert_quality = tk.IntVar(value=85)
        tk.Scale(q_frame, from_=10, to=100, orient=tk.HORIZONTAL, variable=self.convert_quality,
                 length=200).pack(side=tk.LEFT, padx=5)

    def _on_convert_fmt(self, event=None):
        if self.convert_fmt.get() == "Word (.docx)":
            self._convert_img_opts.pack_forget()
        else:
            self._convert_img_opts.pack(fill=tk.X, padx=15, pady=5)

    def _build_encrypt_tab(self):
        tab = tk.Frame(self.op_notebook)
        self.op_notebook.add(tab, text="加密")

        self.enc_sub_notebook = ttk.Notebook(tab)
        self.enc_sub_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        enc_tab = tk.Frame(self.enc_sub_notebook)
        self.enc_sub_notebook.add(enc_tab, text="加密")

        tk.Label(enc_tab, text="为PDF添加密码保护 (AES-256)",
                 font=("Microsoft YaHei", 10)).pack(anchor=tk.W, padx=15, pady=(15, 5))

        pwd_frame = tk.Frame(enc_tab)
        pwd_frame.pack(fill=tk.X, padx=15, pady=5)
        tk.Label(pwd_frame, text="用户密码:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.enc_user_pwd = tk.StringVar()
        tk.Entry(pwd_frame, textvariable=self.enc_user_pwd, show="*",
                 font=("Microsoft YaHei", 9), width=25).pack(side=tk.LEFT, padx=5)

        owner_frame = tk.Frame(enc_tab)
        owner_frame.pack(fill=tk.X, padx=15, pady=5)
        tk.Label(owner_frame, text="所有者密码:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.enc_owner_pwd = tk.StringVar()
        tk.Entry(owner_frame, textvariable=self.enc_owner_pwd, show="*",
                 font=("Microsoft YaHei", 9), width=25).pack(side=tk.LEFT, padx=5)
        tk.Label(owner_frame, text="(可选，留空=使用用户密码)",
                 font=("Microsoft YaHei", 7), fg="gray").pack(side=tk.LEFT)

        dec_tab = tk.Frame(self.enc_sub_notebook)
        self.enc_sub_notebook.add(dec_tab, text="解密")

        tk.Label(dec_tab, text="移除PDF密码保护",
                 font=("Microsoft YaHei", 10)).pack(anchor=tk.W, padx=15, pady=(15, 5))

        dpwd_frame = tk.Frame(dec_tab)
        dpwd_frame.pack(fill=tk.X, padx=15, pady=5)
        tk.Label(dpwd_frame, text="密码:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.dec_password = tk.StringVar()
        tk.Entry(dpwd_frame, textvariable=self.dec_password, show="*",
                 font=("Microsoft YaHei", 9), width=25).pack(side=tk.LEFT, padx=5)

    def _build_compress_tab(self):
        tab = tk.Frame(self.op_notebook)
        self.op_notebook.add(tab, text="压缩")

        tk.Label(tab, text="压缩PDF文件大小",
                 font=("Microsoft YaHei", 10)).pack(anchor=tk.W, padx=15, pady=(15, 5))

        self.compress_level = tk.StringVar(value="标准")
        for text, val in [("轻度压缩 (保持质量, 约减少10-20%)", "轻度"),
                          ("标准压缩 (平衡质量与体积, 约减少20-40%)", "标准"),
                          ("极限压缩 (最大压缩, 可能影响图片质量)", "极限")]:
            tk.Radiobutton(tab, text=text, variable=self.compress_level,
                           value=val, font=("Microsoft YaHei", 9)).pack(
                anchor=tk.W, padx=30, pady=3)

    def _build_watermark_tab(self):
        tab = tk.Frame(self.op_notebook)
        self.op_notebook.add(tab, text="水印")

        self.wm_sub_notebook = ttk.Notebook(tab)
        self.wm_sub_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        text_tab = tk.Frame(self.wm_sub_notebook)
        self.wm_sub_notebook.add(text_tab, text="文字水印")

        tk.Label(text_tab, text="文字水印", font=("Microsoft YaHei", 10)).pack(
            anchor=tk.W, padx=15, pady=(15, 5))
        row1 = tk.Frame(text_tab)
        row1.pack(fill=tk.X, padx=15, pady=3)
        tk.Label(row1, text="文字:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.wm_text = tk.StringVar(value="机密")
        tk.Entry(row1, textvariable=self.wm_text, font=("Microsoft YaHei", 9),
                 width=20).pack(side=tk.LEFT, padx=5)
        tk.Label(row1, text="字号:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT, padx=(10, 0))
        self.wm_font_size = tk.IntVar(value=36)
        tk.Spinbox(row1, from_=12, to=120, textvariable=self.wm_font_size,
                   font=("Microsoft YaHei", 9), width=5).pack(side=tk.LEFT, padx=5)

        row2 = tk.Frame(text_tab)
        row2.pack(fill=tk.X, padx=15, pady=3)
        tk.Label(row2, text="透明度:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.wm_opacity = tk.IntVar(value=128)
        tk.Scale(row2, from_=10, to=255, orient=tk.HORIZONTAL,
                 variable=self.wm_opacity, length=120).pack(side=tk.LEFT, padx=5)
        tk.Label(row2, text="位置:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT, padx=(10, 0))
        self.wm_text_pos = tk.StringVar(value="居中")
        ttk.Combobox(row2, textvariable=self.wm_text_pos,
                     values=["居中", "左上", "右上", "左下", "右下", "平铺"],
                     font=("Microsoft YaHei", 9), width=8, state="readonly").pack(
            side=tk.LEFT, padx=5)
        tk.Label(row2, text="颜色:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT, padx=(10, 0))
        COLOR_MAP = {
            "红色": "#FF0000", "黑色": "#000000", "蓝色": "#0000FF",
            "灰色": "#808080", "橙色": "#FF6600", "绿色": "#008000",
            "粉色": "#FF69B4", "紫色": "#800080", "棕色": "#8B4513",
            "白色": "#FFFFFF", "黄色": "#FFD700", "青色": "#00CED1",
        }
        self._color_map = COLOR_MAP
        self.wm_color = tk.StringVar(value="红色")
        ttk.Combobox(row2, textvariable=self.wm_color,
                     values=list(COLOR_MAP.keys()),
                     font=("Microsoft YaHei", 9), width=8, state="readonly").pack(side=tk.LEFT, padx=5)

        img_tab = tk.Frame(self.wm_sub_notebook)
        self.wm_sub_notebook.add(img_tab, text="图片水印")

        tk.Label(img_tab, text="图片水印", font=("Microsoft YaHei", 10)).pack(
            anchor=tk.W, padx=15, pady=(15, 5))
        img_row = tk.Frame(img_tab)
        img_row.pack(fill=tk.X, padx=15, pady=3)
        tk.Label(img_row, text="图片:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.wm_img_path = tk.StringVar()
        tk.Entry(img_row, textvariable=self.wm_img_path, font=("Microsoft YaHei", 9),
                 width=25).pack(side=tk.LEFT, padx=5)
        tk.Button(img_row, text="选择", command=self._choose_wm_image,
                  font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)

        img_row2 = tk.Frame(img_tab)
        img_row2.pack(fill=tk.X, padx=15, pady=3)
        tk.Label(img_row2, text="缩放:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.wm_img_scale = tk.IntVar(value=15)
        tk.Scale(img_row2, from_=5, to=100, orient=tk.HORIZONTAL,
                 variable=self.wm_img_scale, length=120).pack(side=tk.LEFT, padx=5)
        tk.Label(img_row2, text="位置:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT, padx=(10, 0))
        self.wm_img_pos = tk.StringVar(value="居中")
        ttk.Combobox(img_row2, textvariable=self.wm_img_pos,
                     values=["居中", "左上", "右上", "左下", "右下", "平铺"],
                     font=("Microsoft YaHei", 9), width=8, state="readonly").pack(
            side=tk.LEFT, padx=5)

    def _choose_wm_image(self):
        path = filedialog.askopenfilename(
            title="选择水印图片",
            filetypes=[("图片", "*.png;*.jpg;*.jpeg;*.bmp"), ("所有", "*.*")])
        if path:
            self.wm_img_path.set(path)

    def _build_ocr_tab(self):
        tab = tk.Frame(self.op_notebook)
        self.op_notebook.add(tab, text="OCR")

        tk.Label(tab, text="OCR 文字识别 (扫描件/图片PDF → 纯文本)",
                 font=("Microsoft YaHei", 10)).pack(anchor=tk.W, padx=15, pady=(15, 10))

        lang_frame = tk.Frame(tab)
        lang_frame.pack(fill=tk.X, padx=15, pady=5)
        tk.Label(lang_frame, text="识别语言:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.ocr_lang = tk.StringVar(value="chi_sim+eng")
        ttk.Combobox(lang_frame, textvariable=self.ocr_lang,
                     values=["chi_sim+eng", "chi_sim", "eng", "chi_tra+eng"],
                     font=("Microsoft YaHei", 9), width=14, state="readonly").pack(
            side=tk.LEFT, padx=5)

        tk.Label(tab, text="输出为 .txt 纯文本文件，逐页识别，保留换行格式",
                 font=("Microsoft YaHei", 9), fg="gray").pack(anchor=tk.W, padx=15, pady=10)

    def _build_img2pdf_tab(self):
        tab = tk.Frame(self.op_notebook)
        self.op_notebook.add(tab, text="图片转PDF")

        tk.Label(tab, text="将图片文件合并转换为PDF",
                 font=("Microsoft YaHei", 10)).pack(anchor=tk.W, padx=15, pady=(15, 10))

        tk.Label(tab, text="支持 PNG、JPG、JPEG、BMP 格式，每张图片一页",
                 font=("Microsoft YaHei", 8), fg="gray").pack(anchor=tk.W, padx=15)

        tk.Label(tab, text="图片顺序与左侧文件列表顺序一致",
                 font=("Microsoft YaHei", 8), fg="gray").pack(anchor=tk.W, padx=15, pady=(0, 10))

        self.img2pdf_fit = tk.StringVar(value="original")
        tk.Radiobutton(tab, text="保持原始尺寸（一页一张图）", variable=self.img2pdf_fit,
                       value="original", font=("Microsoft YaHei", 9)).pack(anchor=tk.W, padx=30, pady=3)
        tk.Radiobutton(tab, text="统一A4页面（图片自适应）", variable=self.img2pdf_fit,
                       value="a4", font=("Microsoft YaHei", 9)).pack(anchor=tk.W, padx=30, pady=3)

    def _build_statusbar(self):
        bar = tk.Frame(self.root, height=28, bg="#e0e0e0")
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        bar.pack_propagate(False)

        self.progress = ttk.Progressbar(bar, length=200, mode="determinate")
        self.progress.pack(side=tk.LEFT, padx=(10, 5), pady=3)

        self.status_label = tk.Label(bar, text="就绪", font=("Microsoft YaHei", 9),
                                     bg="#e0e0e0", anchor=tk.W)
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

    def _setup_dnd(self):
        if enable_drop is not None:
            self.root.after(200, lambda: enable_drop(self.root, self._on_drop))

    def _on_drop(self, files):
        pdfs = [f for f in files if f.lower().endswith(".pdf")]
        if pdfs:
            for f in pdfs:
                if f not in self.files:
                    self.files.append(f)
            self._refresh_file_list()
            self._set_status(f"已拖入 {len(pdfs)} 个PDF文件")
        else:
            self._set_status("未检测到PDF文件")

    def _add_files(self):
        files = filedialog.askopenfilenames(
            title="选择PDF文件",
            filetypes=[("支持的文件", "*.pdf;*.png;*.jpg;*.jpeg;*.bmp"), ("PDF", "*.pdf"), ("图片", "*.png;*.jpg;*.jpeg;*.bmp"), ("所有", "*.*")]
        )
        if files:
            for f in files:
                if f not in self.files:
                    self.files.append(f)
            self._refresh_file_list()
            self._set_status(f"已添加 {len(files)} 个文件")

    def _clear_files(self):
        self.files = []
        self.files_info = {}
        self._thumb_cache = {}
        self._thumb_page_cache = {}
        self._refresh_file_list()
        self._show_file_info(None)
        self._set_status("已清空文件列表")

    def _remove_selected(self):
        sel = self.file_listbox.curselection()
        if sel:
            for idx in sorted(sel, reverse=True):
                if idx < len(self.files):
                    path = self.files.pop(idx)
                    self.files_info.pop(path, None)
                    self._thumb_cache.pop(path, None)
                    self._thumb_page_cache.pop(path, None)
            self._refresh_file_list()
            self._set_status(f"已移除 {len(sel)} 个文件")

    def _refresh_file_list(self):
        self.file_listbox.delete(0, tk.END)
        for f in self.files:
            self.file_listbox.insert(tk.END, os.path.basename(f))
        self.file_count_label.config(text=f"已添加 {len(self.files)} 个文件")

    def _on_file_select(self, event):
        self.root.after(50, self._on_file_select_delayed)

    def _on_file_select_delayed(self):
        sel = self.file_listbox.curselection()
        if sel:
            path = self.files[sel[0]]
            self._show_file_info(path)
            self._show_page_preview(path)

    def _show_file_info(self, path):
        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete("1.0", tk.END)
        if path is None:
            self.info_text.insert("1.0", "未选择文件")
            self.info_text.config(state=tk.DISABLED)
            return

        if path in self.files_info:
            info = self.files_info[path]
        elif operations is not None:
            try:
                info = operations.get_pdf_info(path)
                self.files_info[path] = info
            except Exception as e:
                info = {"pages": "?", "size_mb": "?", "encrypted": False, "title": str(e)}
        else:
            info = {"pages": "?", "size_mb": "?", "encrypted": False, "title": "operations未加载"}

        lines = [
            f"{os.path.basename(path)}  |  {info.get('pages', '?')}页  |  {info.get('size_mb', '?')}MB  |  {'🔒' if info.get('encrypted') else '未加密'}",
        ]
        self.info_text.insert("1.0", "\n".join(lines))
        self.info_text.config(state=tk.DISABLED)

    def _load_thumbnails(self, path):
        if path in self._thumb_page_cache:
            return
        if operations is None or Image is None or ImageTk is None:
            return
        try:
            thumbs = operations.get_page_thumbnails(path, width=90)
            self._thumb_page_cache[path] = thumbs
        except Exception:
            self._thumb_page_cache[path] = []

    def _show_page_preview(self, path, label=None):
        for lbl in self._preview_labels:
            lbl.destroy()
        self._preview_labels = []
        self._preview_pdf_path = path

        if label:
            banner = tk.Frame(self.preview_inner, bg="#FF9800", height=22)
            banner.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 3), pady=5)
            banner.pack_propagate(False)
            tk.Label(banner, text=label,
                     font=("Microsoft YaHei", 9, "bold"), fg="white",
                     bg="#FF9800").pack(padx=6, pady=3)

        if operations is None or Image is None or ImageTk is None:
            tk.Label(self.preview_inner, text="预览不可用 (缺少依赖)",
                     font=("Microsoft YaHei", 9), fg="gray", bg="#e8e8e8").pack(side=tk.LEFT, padx=10)
            return

        try:
            thumbs = operations.get_page_thumbnails(path, width=90)
        except Exception as e:
            tk.Label(self.preview_inner, text=f"无法渲染预览: {e}",
                     font=("Microsoft YaHei", 9), fg="red", bg="#e8e8e8").pack(side=tk.LEFT, padx=10)
            return

        for i, data in enumerate(thumbs):
            img = Image.open(io.BytesIO(data))
            photo = ImageTk.PhotoImage(img)
            frame = tk.Frame(self.preview_inner, bg="white", bd=1, relief=tk.SOLID)
            lbl = tk.Label(frame, image=photo, bg="white", cursor="hand2")
            lbl.image = photo
            lbl.pack(padx=1, pady=(3, 1))
            tk.Label(frame, text=f"第 {i+1} 页", font=("Microsoft YaHei", 8),
                     bg="white", fg="gray").pack(pady=(0, 2))
            frame.pack(side=tk.LEFT, padx=3, pady=5)
            lbl.bind("<Button-1>", lambda e, pn=i: self._zoom_page(pn))
            frame.bind("<Button-1>", lambda e, pn=i: self._zoom_page(pn))
            for child in frame.winfo_children():
                child.bind("<Button-1>", lambda e, pn=i: self._zoom_page(pn))
            self._preview_labels.append(frame)

    def _show_image_preview(self, image_path, label=None):
        for lbl in self._preview_labels:
            lbl.destroy()
        self._preview_labels = []
        if label:
            banner = tk.Frame(self.preview_inner, bg="#FF9800", height=22)
            banner.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 3), pady=5)
            banner.pack_propagate(False)
            tk.Label(banner, text=label,
                     font=("Microsoft YaHei", 9, "bold"), fg="white",
                     bg="#FF9800").pack(padx=6, pady=3)
        if Image is None or ImageTk is None:
            return
        try:
            img = Image.open(image_path)
            w, h = img.size
            scale = 100 / max(w, h) * 2 if max(w, h) > 100 else 1
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            lbl = tk.Label(self.preview_inner, image=photo, bg="white", bd=1, relief=tk.SOLID)
            lbl.image = photo
            lbl.pack(side=tk.LEFT, padx=3, pady=5)
            self._preview_labels.append(lbl)
        except Exception:
            pass

    def _zoom_page(self, page_num):
        path = getattr(self, "_preview_pdf_path", None)
        if not path or operations is None or Image is None or ImageTk is None:
            return
        try:
            data = operations.get_thumbnail(path, page=page_num, width=600)
        except Exception as e:
            messagebox.showerror("放大失败", str(e))
            return
        img = Image.open(io.BytesIO(data))
        photo = ImageTk.PhotoImage(img)
        popup = tk.Toplevel(self.root)
        popup.title(f"第 {page_num + 1} 页 - 点击外部关闭")
        popup.geometry(f"{img.width + 40}x{img.height + 60}")
        popup.resizable(False, False)
        popup.transient(self.root)
        popup.focus_set()
        lbl = tk.Label(popup, image=photo, bg="white")
        lbl.image = photo
        lbl.pack(padx=10, pady=10)
        popup.bind("<Escape>", lambda e: popup.destroy())
        self.root.bind("<Button-1>", lambda e: popup.destroy(), add="+")

    def _choose_output_dir(self):
        d = filedialog.askdirectory(title="选择输出目录", initialdir=self.output_dir.get())
        if d:
            self.output_dir.set(d)

    def _get_active_tab_name(self):
        idx = self.op_notebook.index(self.op_notebook.select())
        return self.op_notebook.tab(idx, "text")

    def _do_preview(self):
        if not self.files:
            messagebox.showinfo("提示", "请先添加PDF文件")
            return
        sel = self.file_listbox.curselection()
        if not sel:
            messagebox.showinfo("提示", "请先在左侧文件列表中选择一个PDF文件")
            return
        path = self.files[sel[0]]
        tab = self._get_active_tab_name()

        if tab in ("水印", "压缩", "转换", "加密"):
            try:
                result = self._make_preview(path, tab)
                if result:
                    self._show_file_info(path)
                    if tab == "转换":
                        self._show_image_preview(result, label=f"  {tab}效果 ↓")
                    else:
                        self._show_page_preview(result, label=f"  {tab}效果 ↓   (对比上方原文件)")
                    self._set_status(f"预览已生成 — {tab}效果显示在下方预览区")
                    return
            except Exception as e:
                self._set_status(f"预览失败: {e}")
                return

        self._show_file_info(path)
        self._show_page_preview(path)

    def _make_preview(self, path, tab):
        import tempfile
        out_dir = tempfile.mkdtemp()
        out_path = os.path.join(out_dir, "preview_output.pdf")

        if tab == "水印":
            is_text = self.wm_sub_notebook.index(self.wm_sub_notebook.select()) == 0
            if is_text:
                color_hex = self._color_map.get(self.wm_color.get(), "#FF0000")
                operations.add_text_watermark_pdf(
                    path, out_path, self.wm_text.get(),
                    position=self.wm_text_pos.get(), font_size=self.wm_font_size.get(),
                    opacity=self.wm_opacity.get(), color=color_hex)
            else:
                if not self.wm_img_path.get():
                    return None
                operations.add_image_watermark_pdf(
                    path, out_path, self.wm_img_path.get(),
                    position=self.wm_img_pos.get(),
                    scale=self.wm_img_scale.get() / 100.0)
        elif tab == "压缩":
            operations.compress_pdf(path, out_path, self.compress_level.get())
        elif tab == "转换":
            fmt = self.convert_fmt.get()
            if fmt == "Word (.docx)":
                return None
            dpi = int(self.convert_dpi_var.get())
            quality = self.convert_quality.get()
            imgs = operations.pdf_to_images(path, out_dir, fmt=fmt, dpi=dpi, quality=quality)
            if imgs:
                return imgs[0]
            return None
        elif tab == "加密":
            pwd = self.enc_user_pwd.get() or "preview123"
            sub_idx = self.enc_sub_notebook.index(self.enc_sub_notebook.select())
            if sub_idx == 0:
                operations.encrypt_pdf(path, out_path, pwd)
            else:
                dpwd = self.dec_password.get()
                if not dpwd:
                    return None
                operations.decrypt_pdf(path, out_path, dpwd)
        else:
            return None
        return out_path if os.path.exists(out_path) else None

    def _refresh_thumbnail_strip(self):
        for lbl in self.thumb_labels:
            lbl.destroy()
        self.thumb_labels = []
        self.thumb_selected = set()

        sel = self.file_listbox.curselection()
        if not sel:
            return
        path = self.files[sel[0]]
        if path not in self._thumb_page_cache:
            return

        thumbs = self._thumb_page_cache[path]
        for i, data in enumerate(thumbs):
            img = Image.open(io.BytesIO(data))
            photo = ImageTk.PhotoImage(img)
            frame = tk.Frame(self.thumb_inner, bd=2, relief=tk.FLAT, bg="#f5f5f5")
            lbl = tk.Label(frame, image=photo, bg="#f5f5f5", cursor="hand2")
            lbl.image = photo
            lbl.pack()
            tk.Label(frame, text=str(i + 1), font=("Microsoft YaHei", 8),
                     bg="#f5f5f5", fg="gray").pack()
            frame.pack(side=tk.LEFT, padx=3, pady=5)
            frame.bind("<Button-1>", lambda e, n=i, f=frame: self._toggle_thumb(n, f))
            lbl.bind("<Button-1>", lambda e, n=i, f=frame: self._toggle_thumb(n, f))
            self.thumb_labels.append(frame)

    def _toggle_thumb(self, page_idx, frame):
        if page_idx in self.thumb_selected:
            self.thumb_selected.discard(page_idx)
            frame.config(relief=tk.FLAT, bg="#f5f5f5")
            for child in frame.winfo_children():
                child.config(bg="#f5f5f5")
        else:
            self.thumb_selected.add(page_idx)
            frame.config(relief=tk.SOLID, bg="#90CAF9")
            for child in frame.winfo_children():
                child.config(bg="#90CAF9")
        pages = sorted(self.thumb_selected)
        self.extract_range.delete(0, tk.END)
        self.extract_range.insert(0, ",".join(str(p + 1) for p in pages))

    def _parse_page_range(self, text):
        result = []
        for part in text.replace("，", ",").split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                a, b = part.split("-", 1)
                result.append((int(a.strip()) - 1, int(b.strip()) - 1))
            else:
                p = int(part) - 1
                result.append((p, p))
        return result

    def _parse_page_list(self, text):
        pages = []
        for part in text.replace("，", ",").split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                a, b = part.split("-", 1)
                pages.extend(range(int(a.strip()) - 1, int(b.strip())))
            else:
                pages.append(int(part) - 1)
        return sorted(set(pages))

    def _get_out_dir(self, pdf_path):
        d = self.output_dir.get()
        return d if d else os.path.dirname(pdf_path)

    def _get_out_name(self, default_name):
        name = self.output_name.get().strip()
        return name if name else default_name

    def _apply_operation(self, pdf_path):
        tab = self._get_active_tab_name()
        out_dir = self._get_out_dir(pdf_path)
        os.makedirs(out_dir, exist_ok=True)

        if tab == "合并":
            out_path = os.path.join(out_dir, f"{self._get_out_name('merged')}.pdf")
            result = operations.merge_pdfs(self.files, out_path)
            return f"合并完成: {result['page_count']} 页, {result['file_count']} 个文件 → {out_path}"

        elif tab == "拆分":
            if self.split_mode.get() == "range":
                ranges = self._parse_page_range(self.split_range_entry.get())
                files = operations.split_pdf_by_range(pdf_path, ranges, out_dir)
                return f"拆分完成: {len(files)} 个文件 → {out_dir}"
            else:
                n = self.split_n_var.get()
                files = operations.split_pdf_every_n(pdf_path, n, out_dir)
                return f"拆分完成: {len(files)} 个文件 → {out_dir}"

        elif tab == "提取":
            pages = self._parse_page_list(self.extract_range.get())
            out_path = os.path.join(out_dir, f"{self._get_out_name('extracted')}.pdf")
            result = operations.extract_pages(pdf_path, pages, out_path)
            return f"提取完成: {result['extracted_pages']} 页 → {out_path}"

        elif tab == "转换":
            fmt = self.convert_fmt.get()
            if fmt == "Word (.docx)":
                out_path = os.path.join(out_dir, f"{self._get_out_name('converted')}.docx")
                result = operations.pdf_to_word(pdf_path, out_path)
                return f"转换完成 → {out_path}"
            else:
                dpi = int(self.convert_dpi_var.get())
                quality = self.convert_quality.get()
                files = operations.pdf_to_images(pdf_path, out_dir, fmt=fmt, dpi=dpi, quality=quality)
                return f"转换完成: {len(files)} 张图片 → {out_dir}"

        elif tab == "加密":
            user_pwd = self.enc_user_pwd.get()
            owner_pwd = self.enc_owner_pwd.get() or None
            if not user_pwd:
                return "错误: 请输入用户密码"
            sub_idx = self.enc_sub_notebook.index(self.enc_sub_notebook.select())
            suffix = "encrypted" if sub_idx == 0 else "decrypted"
            out_path = os.path.join(out_dir, f"{self._get_out_name(suffix)}.pdf")
            if sub_idx == 0:
                result = operations.encrypt_pdf(pdf_path, out_path, user_pwd, owner_pwd)
                return f"加密完成 → {out_path}"
            else:
                password = self.dec_password.get()
                if not password:
                    return "错误: 请输入密码"
                result = operations.decrypt_pdf(pdf_path, out_path, password)
                return f"解密完成 → {out_path}"

        elif tab == "压缩":
            level = self.compress_level.get()
            out_path = os.path.join(out_dir, f"{self._get_out_name('compressed')}.pdf")
            result = operations.compress_pdf(pdf_path, out_path, level)
            return (f"压缩完成: {result['original_size_mb']}MB → {result['compressed_size_mb']}MB "
                    f"({result['ratio']}%) → {out_path}")

        elif tab == "水印":
            is_text = self.wm_sub_notebook.index(self.wm_sub_notebook.select()) == 0
            suffix = "watermark_text" if is_text else "watermark_img"
            out_path = os.path.join(out_dir, f"{self._get_out_name(suffix)}.pdf")
            if is_text:
                color_hex = self._color_map.get(self.wm_color.get(), "#FF0000")
                result = operations.add_text_watermark_pdf(
                    pdf_path, out_path, self.wm_text.get(),
                    position=self.wm_text_pos.get(),
                    font_size=self.wm_font_size.get(),
                    opacity=self.wm_opacity.get(),
                    color=color_hex)
                return f"文字水印完成 → {out_path}"
            else:
                if not self.wm_img_path.get():
                    return "错误: 请选择水印图片"
                result = operations.add_image_watermark_pdf(
                    pdf_path, out_path, self.wm_img_path.get(),
                    position=self.wm_img_pos.get(),
                    scale=self.wm_img_scale.get() / 100.0)
                return f"图片水印完成 → {out_path}"

        elif tab == "图片转PDF":
            out_path = os.path.join(out_dir, f"{self._get_out_name('images')}.pdf")
            result = operations.images_to_pdf(self.files, out_path)
            return f"图片转PDF完成: {result['pages']} 页 → {out_path}"

        elif tab == "OCR":
            out_path = os.path.join(out_dir, f"{self._get_out_name('ocr')}.txt")
            result = operations.ocr_pdf_to_text(
                pdf_path, out_path, lang=self.ocr_lang.get())
            return f"OCR完成: {result['pages']}页 → {out_path}"

        return "未知操作"

    def _start_batch(self):
        tab = self._get_active_tab_name()
        if tab in ("合并", "图片转PDF"):
            if not self.files:
                messagebox.showinfo("提示", "请先添加文件")
                return
            if tab == "合并":
                files_to_process = [self.files[0]]
                total_pages = 0
                for f in self.files:
                    try:
                        total_pages += operations.get_page_count(f)
                    except Exception:
                        pass
            else:
                files_to_process = [self.files[0]]
                total_pages = 0
        else:
            sel = self.file_listbox.curselection()
            if not sel:
                messagebox.showinfo("提示", "请先选择要处理的PDF文件")
                return
            files_to_process = [self.files[idx] for idx in sel]
            total_pages = 0
            for f in files_to_process:
                try:
                    total_pages += operations.get_page_count(f)
                except Exception:
                    pass

        out_dir = self.output_dir.get()
        if not out_dir and files_to_process:
            out_dir = os.path.dirname(files_to_process[0])
        if not out_dir:
            messagebox.showerror("错误", "无法确定输出目录，请手动选择")
            return
        try:
            os.makedirs(out_dir, exist_ok=True)
        except Exception as e:
            messagebox.showerror("错误", f"无法创建输出目录: {str(e)}")
            return

        if tab == "加密":
            sub_idx = self.enc_sub_notebook.index(self.enc_sub_notebook.select())
            if sub_idx == 0 and not self.enc_user_pwd.get():
                messagebox.showinfo("提示", "请输入密码")
                return
            if sub_idx == 1 and not self.dec_password.get():
                messagebox.showinfo("提示", "请输入密码")
                return

        self._cancel_flag = False
        self._batch_log = []
        self._set_status("处理中...")
        self.status_label.config(fg="red", font=("Microsoft YaHei", 10, "bold"))
        self.progress.config(mode="indeterminate")
        self.progress.start()
        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete("1.0", tk.END)
        self.info_text.insert("1.0", "处理中，请稍候...\n")
        self.info_text.config(state=tk.DISABLED)

        thread = threading.Thread(target=self._process_batch,
                                  args=(files_to_process, tab),
                                  daemon=True)
        thread.start()

    def _process_batch(self, files, tab):
        total = len(files)
        try:
            for i, path in enumerate(files):
                if self._cancel_flag:
                    self.root.after(0, lambda: self._batch_done("已取消"))
                    return
                try:
                    msg = self._apply_operation(path)
                    self._batch_log.append(msg)
                    print(msg)
                except Exception as e:
                    err = f"处理失败: {os.path.basename(path)} - {str(e)}"
                    self._batch_log.append(err)
                    print(err)

                pct = int((i + 1) / total * 100)
                self.root.after(0, lambda p=pct, m=f"处理中... ({i + 1}/{total})": (
                    self._update_progress(p, m)
                ))
        except Exception as e:
            self.root.after(0, lambda: self._batch_done(f"处理异常: {str(e)}"))
            return

        self.root.after(0, lambda: self._batch_done("处理完成"))

    def _update_progress(self, pct, msg):
        self.progress.config(mode="determinate")
        self.progress.stop()
        self.progress.config(value=pct)
        self._set_status(msg)
        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete("1.0", tk.END)
        self.info_text.insert("1.0", f"{msg}\n")
        self.info_text.config(state=tk.DISABLED)

    def _cancel_batch(self):
        self._cancel_flag = True
        self._set_status("正在取消...")

    def _batch_done(self, msg):
        self.progress.config(mode="determinate")
        self.progress.stop()
        self.progress.config(value=100 if "完成" in msg else 0)
        self._set_status(msg)
        self.status_label.config(fg="black", font=("Microsoft YaHei", 9))

        if self._batch_log:
            summary = "\n".join(self._batch_log[:20])
            if len(self._batch_log) > 20:
                summary += f"\n... 还有 {len(self._batch_log) - 20} 条"
            messagebox.showinfo("处理结果", summary)
        elif "完成" not in msg:
            messagebox.showinfo("提示", msg)

    def _set_status(self, text):
        self.status_label.config(text=text)

    def _on_close(self):
        self.root.destroy()


if __name__ == "__main__":
    app = PDFApp()
    app.run()
