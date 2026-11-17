import sys
import os

with open('main.py', 'r', encoding='utf-8') as f:
    text = f.read()

start_marker = '    def show_aseprite_tools(self):'
end_marker = 'if __name__ == "__main__":'

idx_start = text.find(start_marker)
idx_end = text.rfind(end_marker)

if idx_start != -1 and idx_end != -1:
    new_text = '''    def show_aseprite_tools(self):
        ase_win = tk.Toplevel(self.root)
        ase_win.title("Aseprite 연동 도구")
        ase_win.geometry("1200x800")
        ase_win.minsize(1000, 750)
        if self.is_always_on_top.get():
            ase_win.attributes('-topmost', True)
            
        c = self.get_colors()
        ase_win.configure(bg=c["BG_COLOR"])

        self.auto_detect_aseprite_path()

        path_frame = ttk.LabelFrame(ase_win, text=" 1. Aseprite 실행 파일 경로 설정 ")
        path_frame.pack(fill="x", padx=15, pady=10)
        
        ttk.Entry(path_frame, textvariable=self.aseprite_path, state="readonly").pack(side="left", fill="x", expand=True, padx=(10, 5), pady=10)
        ttk.Button(path_frame, text="경로 찾기", command=self.find_aseprite_exe).pack(side="left", padx=(0, 10), pady=10)
        
        status_text = "자동 탐색 완료" if self.aseprite_path.get() else "경로를 찾을 수 없습니다"
        ttk.Label(path_frame, text=f"({status_text})", foreground=c["TEXT_MUTED"]).pack(side="left", padx=5)

        main_split = ttk.PanedWindow(ase_win, orient=tk.HORIZONTAL)
        main_split.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        left_frame = ttk.Frame(main_split, style="Panel.TFrame")
        main_split.add(left_frame, weight=1)

        ttk.Label(left_frame, text="작업 대상 파일 (.ase, .aseprite)").pack(anchor="w", padx=10, pady=(10, 0))
        ttk.Label(left_frame, text="* 파일 및 폴더 드래그 앤 드롭 지원", style="Muted.TLabel").pack(anchor="w", padx=10)
        
        list_frame = ttk.Frame(left_frame, style="Panel.TFrame")
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        list_scroll = ttk.Scrollbar(list_frame)
        list_scroll.pack(side="right", fill="y")
        
        ase_listbox = tk.Listbox(list_frame, bg=c["BG_COLOR"], fg=c["TEXT_COLOR"], relief="flat", borderwidth=1, highlightthickness=1, highlightbackground=c["BORDER_COLOR"], yscrollcommand=list_scroll.set, selectmode="extended")
        ase_listbox.pack(side="left", fill="both", expand=True)
        list_scroll.config(command=ase_listbox.yview)
        
        self.ase_metadata = {}
        self.current_preview_temp = None

        def update_inspector(event=None):
            sel = ase_listbox.curselection()
            if not sel: return
            idx = sel[0]
            path = self.aseprite_files[idx]
            
            meta = self.inspect_aseprite_file(path)
            if meta:
                self.ase_metadata[path] = meta
                
                info_lbl.config(text=f"파일명: {os.path.basename(path)}\\n크기: {meta['width']}x{meta['height']} px\\n프레임 수: {meta['frames']}개\\n레이어 수: {len(meta['layers'])}개\\n태그 수: {len(meta['tags'])}개")
                
                for item in layer_tree.get_children(): layer_tree.delete(item)
                for l in meta['layers']:
                    vis = "보기" if l['isVisible'] else "숨김"
                    layer_tree.insert("", tk.END, values=("☑", l['path'], vis))
                    
                for item in tag_tree.get_children(): tag_tree.delete(item)
                if not meta['tags']:
                    tag_tree.insert("", tk.END, values=("", "태그 없음", ""))
                else:
                    for t in meta['tags']:
                        tag_tree.insert("", tk.END, values=("☐", t['name'], f"{t['fromFrame']} ~ {t['toFrame']}"))
                
                ase_win.after(100, lambda: update_preview_image(path, 1))
            else:
                print(f"인스펙터 메타데이터 로드 실패: {path}")

        def update_preview_image(path, frame=1):
            if self.current_preview_temp and os.path.exists(self.current_preview_temp):
                try: os.remove(self.current_preview_temp)
                except: pass
                
            tmp_png = self.export_aseprite_preview_png(path, frame)
            if tmp_png:
                self.current_preview_temp = tmp_png
                try:
                    img = Image.open(tmp_png)
                    
                    c_w = preview_canvas.winfo_width()
                    c_h = preview_canvas.winfo_height()
                    if c_w < 10: c_w = 200
                    if c_h < 10: c_h = 150
                    
                    ratio = min((c_w-20)/img.width, (c_h-20)/img.height)
                    if ratio >= 1: ratio = int(ratio)
                    new_w = max(1, int(img.width * ratio))
                    new_h = max(1, int(img.height * ratio))
                    
                    img = img.resize((new_w, new_h), Image.Resampling.NEAREST)
                    self.ase_tk_preview = ImageTk.PhotoImage(img)
                    
                    preview_canvas.delete("all")
                    size=10
                    color1 = "#ffffff" if not self.is_dark_mode.get() else "#2A2A2A"
                    color2 = "#f1f5f9" if not self.is_dark_mode.get() else "#202020"
                    for y in range(0, c_h, size):
                        for x in range(0, c_w, size):
                            color = color1 if ((x//size) + (y//size)) % 2 == 0 else color2
                            preview_canvas.create_rectangle(x, y, x+size, y+size, fill=color, outline="")
                    
                    preview_canvas.create_image(c_w//2, c_h//2, image=self.ase_tk_preview, anchor="center")
                except Exception as e:
                    print(f"미리보기 로드 실패: {e}")
            else:
                print(f"미리보기 PNG 생성 실패 (path: {path}, frame: {frame})")

        ase_listbox.bind('<<ListboxSelect>>', lambda e: [update_inspector(), update_expected_label()], add="+")

        def add_file_or_folder(p_norm):
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

        ase_win.drop_target_register(DND_FILES)
        ase_win.dnd_bind('<<Drop>>', on_ase_drop)
        ase_listbox.drop_target_register(DND_FILES)
        ase_listbox.dnd_bind('<<Drop>>', on_ase_drop)

        btn_frame = ttk.Frame(left_frame, style="Panel.TFrame")
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        btn_frame.columnconfigure((0,1,2,3), weight=1)
        
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
            ase_listbox.delete(0, "end")
            info_lbl.config(text="파일을 선택하세요")
            layer_tree.delete(*layer_tree.get_children())
            tag_tree.delete(*tag_tree.get_children())
            preview_canvas.delete("all")
            update_expected_label()

        ttk.Button(btn_frame, text="파일 추가", command=add_ase_files).grid(row=0, column=0, sticky="ew", padx=1)
        ttk.Button(btn_frame, text="폴더 추가", command=add_ase_folder).grid(row=0, column=1, sticky="ew", padx=1)
        ttk.Button(btn_frame, text="선택 제거", command=remove_ase_files).grid(row=0, column=2, sticky="ew", padx=1)
        ttk.Button(btn_frame, text="전체 비우기", command=clear_ase_files).grid(row=0, column=3, sticky="ew", padx=1)

        right_frame = ttk.Frame(main_split, style="TFrame")
        main_split.add(right_frame, weight=3)

        info_frame = ttk.LabelFrame(right_frame, text=" 선택 파일 정보 및 미리보기 ")
        info_frame.pack(fill="x", pady=(0, 10))
        
        info_split = ttk.Frame(info_frame, style="Panel.TFrame")
        info_split.pack(fill="x", padx=10, pady=10)
        
        info_lbl = ttk.Label(info_split, text="파일을 선택하세요", justify="left")
        info_lbl.pack(side="left", fill="both", expand=True)
        
        preview_canvas = tk.Canvas(info_split, width=200, height=150, bg=c["BG_COLOR"], highlightbackground=c["BORDER_COLOR"])
        preview_canvas.pack(side="right", padx=10)

        notebook = ttk.Notebook(right_frame)
        notebook.pack(fill="both", expand=True)

        tab_move = ttk.Frame(notebook, style="Panel.TFrame")
        notebook.add(tab_move, text=" 레이어 이동 ")
        
        move_trees = ttk.Frame(tab_move, style="Panel.TFrame")
        move_trees.pack(fill="both", expand=True, padx=10, pady=10)
        
        move_split = ttk.PanedWindow(move_trees, orient=tk.HORIZONTAL)
        move_split.pack(fill="both", expand=True)
        
        layer_frame = ttk.LabelFrame(move_split, text=" 대상 레이어 선택 ")
        move_split.add(layer_frame, weight=1)
        
        l_scroll = ttk.Scrollbar(layer_frame)
        l_scroll.pack(side="right", fill="y", pady=(5, 5))
        
        layer_tree = ttk.Treeview(layer_frame, columns=("check", "path", "vis"), show="headings", yscrollcommand=l_scroll.set, selectmode="none")
        layer_tree.heading("check", text="체크")
        layer_tree.column("check", width=40, anchor="center", stretch=False)
        layer_tree.heading("path", text="레이어 경로", anchor="w")
        layer_tree.column("path", width=150, anchor="w", stretch=True)
        layer_tree.heading("vis", text="상태", anchor="center")
        layer_tree.column("vis", width=50, anchor="center", stretch=False)
        layer_tree.pack(side="top", expand=True, fill="both", padx=(5, 0), pady=(5, 5))
        l_scroll.config(command=layer_tree.yview)
        
        def toggle_check(event, tree):
            region = tree.identify_region(event.x, event.y)
            column = tree.identify_column(event.x)
            if region == "cell" and column == "#1":
                item = tree.identify_row(event.y)
                if item:
                    val = tree.item(item, "values")
                    if val[0] == "☑": new_val = ("☐", val[1], val[2])
                    elif val[0] == "☐": new_val = ("☑", val[1], val[2])
                    else: return
                    tree.item(item, values=new_val)

        layer_tree.bind('<ButtonRelease-1>', lambda e: toggle_check(e, layer_tree))
        
        l_btn_f = ttk.Frame(layer_frame, style="Panel.TFrame")
        l_btn_f.pack(fill="x", padx=5, pady=(0, 5))
        ttk.Button(l_btn_f, text="모두 체크", command=lambda: [layer_tree.item(i, values=("☑", layer_tree.item(i,"values")[1], layer_tree.item(i,"values")[2])) for i in layer_tree.get_children()]).pack(side="left", expand=True, fill="x")
        ttk.Button(l_btn_f, text="모두 해제", command=lambda: [layer_tree.item(i, values=("☐", layer_tree.item(i,"values")[1], layer_tree.item(i,"values")[2])) for i in layer_tree.get_children()]).pack(side="left", expand=True, fill="x")

        tag_frame = ttk.LabelFrame(move_split, text=" 적용 범위 (태그 선택) ")
        move_split.add(tag_frame, weight=1)
        
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
        
        target_frame_mode = tk.StringVar(value="tags")
        ttk.Radiobutton(t_btn_f, text="모든 프레임", variable=target_frame_mode, value="all").pack(side="left", padx=5)
        ttk.Radiobutton(t_btn_f, text="체크된 태그만", variable=target_frame_mode, value="tags").pack(side="left", padx=5)

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
                    
                    if val[1] != "태그 없음":
                        try:
                            rng = val[2].split("~")
                            f_start = int(rng[0].strip())
                            sel = ase_listbox.curselection()
                            if sel: 
                                ase_win.after(50, lambda: update_preview_image(self.aseprite_files[sel[0]], f_start))
                        except: pass

        tag_tree.bind('<ButtonRelease-1>', on_tag_click)
        ttk.Label(tag_frame, text="* 태그 선택/체크 시 해당 태그 첫 프레임 미리보기", style="Muted.TLabel").pack(pady=2)

        exec_frame = ttk.LabelFrame(tab_move, text=" 실행 옵션 ")
        exec_frame.pack(side="bottom", fill="x", padx=10, pady=(0, 10))
        
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

        dx_var.trace_add("write", update_expected_label)
        dy_var.trace_add("write", update_expected_label)
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
                ans = messagebox.askyesno("경고", "원본 파일에 덮어씁니다.\\n(진행 전 _aseprite_backup 폴더에 자동 백업됩니다.)\\n정말 진행하시겠습니까?")
                if not ans: return

            checked_layers = [layer_tree.item(i, "values")[1] for i in layer_tree.get_children() if layer_tree.item(i, "values")[0] == "☑"]
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

        ttk.Button(exec_frame, text="▶ 선택한 레이어 이동 실행", style="Success.TButton", command=on_execute_move).grid(row=0, column=4, rowspan=2, sticky="nsew", padx=10, pady=5)

        tab_pivot = ttk.Frame(notebook, style="Panel.TFrame")
        notebook.add(tab_pivot, text=" 피봇 보정 (준비중) ")
        
        piv_info = ttk.Frame(tab_pivot, style="Panel.TFrame")
        piv_info.pack(expand=True, fill="both", padx=20, pady=20)
        
        ttk.Label(piv_info, text="[ Aseprite 피봇 보정 안내 ]", font=("Malgun Gothic", 11, "bold")).pack(pady=(0, 10))
        ttk.Label(piv_info, text="현재 메인 화면의 '보정 및 변환 설정'을 참고하여 Aseprite 캔버스와 레이어를 조정합니다.", justify="center").pack(pady=5)
        ttk.Label(piv_info, text="- 결과물: 원본 보존 / _pivotfix.aseprite 복사본 생성 예정\\n- 피봇 로직: 모든 프레임 병합 박스 기준 재배치 (예정)\\n- 현재 Aseprite CLI 연동 기반 구조만 반영되었습니다.", justify="center", foreground=c["TEXT_MUTED"]).pack(pady=5)
        
        ttk.Button(piv_info, text="▶ Aseprite 피봇 보정 실행 (준비중)", style="Primary.TButton", command=self.run_aseprite_pivot_fix).pack(pady=20)

        def on_close():
            if self.current_preview_temp and os.path.exists(self.current_preview_temp):
                try: os.remove(self.current_preview_temp)
                except: pass
            ase_win.destroy()
            
        ase_win.protocol("WM_DELETE_WINDOW", on_close)
        update_expected_label()
'''
    with open('C:/Users/SOUTHPAW GAMES/Desktop/Pivot Fixer/main.py', 'w', encoding='utf-8') as f:
        f.write(text[:idx_start] + new_text + '\n\n' + text[idx_end:])
