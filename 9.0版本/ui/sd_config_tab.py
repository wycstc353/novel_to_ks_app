# ui/sd_config_tab.py
import customtkinter as ctk
from tkinter import StringVar, IntVar, DoubleVar, BooleanVar, filedialog
import traceback

class SDConfigTab(ctk.CTkFrame):
    """SD WebUI API 设置的 UI 标签页"""
    def __init__(self, master, config_manager, app_instance):
        super().__init__(master, fg_color="transparent")
        self.config_manager = config_manager
        self.app = app_instance
        self.sd_samplers = [
            "Euler a", "Euler", "LMS", "Heun", "DPM2", "DPM2 a", "DPM++ 2S a", "DPM++ 2M",
            "DPM++ SDE", "DPM++ 2M SDE", "DPM fast", "DPM adaptive", "LMS Karras",
            "DPM2 Karras", "DPM2 a Karras", "DPM++ 2S a Karras", "DPM++ 2M Karras",
            "DPM++ SDE Karras", "DPM++ 2M SDE Karras", "DDIM", "PLMS", "UniPC"
        ]

        # --- 创建主滚动框架 ---
        self.scrollable_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scrollable_frame.pack(expand=True, fill="both")

        # --- 将所有 UI 元素放入滚动框架内 ---
        self.build_ui_within_scrollable_frame(self.scrollable_frame)
        self.load_initial_config()

    def build_ui_within_scrollable_frame(self, master_frame):
        """在指定的父框架（滚动框架）内构建 UI 元素"""
        # 配置滚动框架内部网格列权重
        master_frame.grid_columnconfigure(1, weight=1) # 输入框列扩展
        row = 0

        # --- SD WebUI URL & 保存目录 ---
        url_label = ctk.CTkLabel(master_frame, text="WebUI API 地址:")
        url_label.grid(row=row, column=0, padx=10, pady=5, sticky="w")
        self.url_var = StringVar()
        url_entry = ctk.CTkEntry(master_frame, textvariable=self.url_var, placeholder_text="例如: http://127.0.0.1:7860")
        url_entry.grid(row=row, column=1, padx=10, pady=5, sticky="ew")
        url_entry.bind("<FocusOut>", self.trigger_workflow_button_update)
        row += 1
        save_dir_label = ctk.CTkLabel(master_frame, text="图片保存目录:")
        save_dir_label.grid(row=row, column=0, padx=10, pady=5, sticky="w")
        self.save_dir_var = StringVar()
        dir_entry = ctk.CTkEntry(master_frame, textvariable=self.save_dir_var, placeholder_text="应用可访问的完整目录路径")
        dir_entry.grid(row=row, column=1, padx=(10, 0), pady=5, sticky="ew")
        dir_entry.bind("<FocusOut>", self.trigger_workflow_button_update)
        browse_button = ctk.CTkButton(master_frame, text="浏览...", width=60, command=self.browse_save_directory)
        browse_button.grid(row=row, column=2, padx=(5, 10), pady=5, sticky="w")

        # --- SD 生成参数 ---
        row += 1
        param_frame = ctk.CTkFrame(master_frame, fg_color="transparent")
        param_frame.grid(row=row, column=0, columnspan=3, sticky="ew", padx=5, pady=(15, 5))
        param_frame.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="group_sd") # 均匀分布列
        col = 0; row_param = 0
        # 采样器
        sampler_label = ctk.CTkLabel(param_frame, text="采样器:")
        sampler_label.grid(row=row_param, column=col, padx=5, pady=5, sticky="w")
        self.sampler_var = StringVar(value="Euler a")
        sampler_combo = ctk.CTkComboBox(param_frame, values=self.sd_samplers, variable=self.sampler_var)
        sampler_combo.grid(row=row_param+1, column=col, padx=5, pady=5, sticky="ew")
        col += 1
        # 步数
        steps_label = ctk.CTkLabel(param_frame, text="步数:")
        steps_label.grid(row=row_param, column=col, padx=5, pady=5, sticky="w")
        self.steps_var = IntVar(value=20)
        steps_entry = ctk.CTkEntry(param_frame, textvariable=self.steps_var)
        steps_entry.grid(row=row_param+1, column=col, padx=5, pady=5, sticky="ew")
        col += 1
        # CFG Scale
        cfg_label = ctk.CTkLabel(param_frame, text="CFG Scale:")
        cfg_label.grid(row=row_param, column=col, padx=5, pady=5, sticky="w")
        self.cfg_scale_var = DoubleVar(value=7.0)
        cfg_entry = ctk.CTkEntry(param_frame, textvariable=self.cfg_scale_var)
        cfg_entry.grid(row=row_param+1, column=col, padx=5, pady=5, sticky="ew")
        # 换行
        col = 0; row_param += 2
        # 宽度
        width_label = ctk.CTkLabel(param_frame, text="宽度:")
        width_label.grid(row=row_param, column=col, padx=5, pady=5, sticky="w")
        self.width_var = IntVar(value=512)
        width_entry = ctk.CTkEntry(param_frame, textvariable=self.width_var)
        width_entry.grid(row=row_param+1, column=col, padx=5, pady=5, sticky="ew")
        col += 1
        # 高度
        height_label = ctk.CTkLabel(param_frame, text="高度:")
        height_label.grid(row=row_param, column=col, padx=5, pady=5, sticky="w")
        self.height_var = IntVar(value=512)
        height_entry = ctk.CTkEntry(param_frame, textvariable=self.height_var)
        height_entry.grid(row=row_param+1, column=col, padx=5, pady=5, sticky="ew")
        col += 1
        # 种子
        seed_label = ctk.CTkLabel(param_frame, text="种子 (-1随机):")
        seed_label.grid(row=row_param, column=col, padx=5, pady=5, sticky="w")
        self.seed_var = IntVar(value=-1)
        seed_entry = ctk.CTkEntry(param_frame, textvariable=self.seed_var)
        seed_entry.grid(row=row_param+1, column=col, padx=5, pady=5, sticky="ew")
        # 换行
        col = 0; row_param += 2
        # 面部修复
        self.restore_faces_var = BooleanVar(value=False)
        restore_check = ctk.CTkCheckBox(param_frame, text="面部修复", variable=self.restore_faces_var)
        restore_check.grid(row=row_param, column=col, padx=5, pady=10, sticky="w")
        col += 1
        # 平铺/无缝
        self.tiling_var = BooleanVar(value=False)
        tiling_check = ctk.CTkCheckBox(param_frame, text="平铺/无缝", variable=self.tiling_var)
        tiling_check.grid(row=row_param, column=col, padx=5, pady=10, sticky="w")

        # --- 全局附加提示词 ---
        row += 1
        add_pos_label = ctk.CTkLabel(master_frame, text="全局附加正向提示:")
        add_pos_label.grid(row=row, column=0, padx=10, pady=(15, 5), sticky="nw")
        self.add_pos_textbox = ctk.CTkTextbox(master_frame, height=60, wrap="word")
        self.add_pos_textbox.grid(row=row, column=1, columnspan=2, padx=10, pady=(15, 5), sticky="ew")
        row += 1
        add_neg_label = ctk.CTkLabel(master_frame, text="全局附加负向提示:")
        add_neg_label.grid(row=row, column=0, padx=10, pady=5, sticky="nw")
        self.add_neg_textbox = ctk.CTkTextbox(master_frame, height=60, wrap="word")
        self.add_neg_textbox.grid(row=row, column=1, columnspan=2, padx=10, pady=5, sticky="ew")

    def browse_save_directory(self):
        """打开目录选择对话框"""
        directory = filedialog.askdirectory(title="选择 SD 图片保存目录", parent=self)
        if directory: self.save_dir_var.set(directory); print(f"SD 图片保存目录已设置为: {directory}"); self.trigger_workflow_button_update()
        else: print("用户取消选择目录。")

    def load_initial_config(self):
        """加载初始 SD 配置"""
        print("正在加载 SD 配置到 UI...")
        config = self.config_manager.load_config("sd")
        self.url_var.set(config.get("sdWebUiUrl", ""))
        self.save_dir_var.set(config.get("sdImageSaveDir", ""))
        self.sampler_var.set(config.get("sdSampler", "Euler a"))
        self.steps_var.set(int(config.get("sdSteps", 20)))
        self.cfg_scale_var.set(float(config.get("sdCfgScale", 7.0)))
        self.width_var.set(int(config.get("sdWidth", 512)))
        self.height_var.set(int(config.get("sdHeight", 512)))
        self.seed_var.set(int(config.get("sdSeed", -1)))
        self.restore_faces_var.set(bool(config.get("sdRestoreFaces", False)))
        self.tiling_var.set(bool(config.get("sdTiling", False)))
        # 加载附加提示词
        if hasattr(self, 'add_pos_textbox') and self.add_pos_textbox.winfo_exists():
            self.add_pos_textbox.delete("1.0", "end")
            self.add_pos_textbox.insert("1.0", config.get("sdAdditionalPositivePrompt", ""))
        if hasattr(self, 'add_neg_textbox') and self.add_neg_textbox.winfo_exists():
            self.add_neg_textbox.delete("1.0", "end")
            self.add_neg_textbox.insert("1.0", config.get("sdAdditionalNegativePrompt", ""))
        print("SD 配置加载完成。")

    def get_config_data(self):
        """收集当前的 SD 配置数据"""
        print("正在从 UI 收集 SD 配置数据...")
        # 输入校验
        try: steps = int(self.steps_var.get()); assert steps > 0
        except: print(f"警告: 无效的步数输入 '{self.steps_var.get()}'，将使用默认值 20。"); steps = 20; self.steps_var.set(steps)
        try: cfg = float(self.cfg_scale_var.get())
        except: print(f"警告: 无效的 CFG Scale 输入 '{self.cfg_scale_var.get()}'，将使用默认值 7.0。"); cfg = 7.0; self.cfg_scale_var.set(cfg)
        try: width = int(self.width_var.get()); assert width > 0 and width % 8 == 0
        except: print(f"警告: 无效的宽度输入 '{self.width_var.get()}' (必须是8的倍数)，将使用默认值 512。"); width = 512; self.width_var.set(width)
        try: height = int(self.height_var.get()); assert height > 0 and height % 8 == 0
        except: print(f"警告: 无效的高度输入 '{self.height_var.get()}' (必须是8的倍数)，将使用默认值 512。"); height = 512; self.height_var.set(height)
        try: seed = int(self.seed_var.get())
        except: print(f"警告: 无效的种子输入 '{self.seed_var.get()}'，将使用默认值 -1。"); seed = -1; self.seed_var.set(seed)
        # 获取附加提示词
        add_pos = ""; add_neg = ""
        if hasattr(self, 'add_pos_textbox') and self.add_pos_textbox.winfo_exists(): add_pos = self.add_pos_textbox.get("1.0", "end-1c").strip()
        if hasattr(self, 'add_neg_textbox') and self.add_neg_textbox.winfo_exists(): add_neg = self.add_neg_textbox.get("1.0", "end-1c").strip()
        # 组合配置字典
        config_data = {
            "sdWebUiUrl": self.url_var.get().rstrip('/'), "sdImageSaveDir": self.save_dir_var.get(),
            "sdSampler": self.sampler_var.get(), "sdSteps": steps, "sdCfgScale": cfg,
            "sdWidth": width, "sdHeight": height, "sdSeed": seed,
            "sdRestoreFaces": self.restore_faces_var.get(), "sdTiling": self.tiling_var.get(),
            "sdAdditionalPositivePrompt": add_pos, "sdAdditionalNegativePrompt": add_neg
        }
        print("SD 配置数据收集完成。")
        return config_data

    def trigger_workflow_button_update(self, event=None):
        """通知 WorkflowTab 更新按钮状态"""
        try:
            if hasattr(self.app, 'workflow_tab') and self.app.workflow_tab and self.app.workflow_tab.winfo_exists():
                print(f"[{type(self).__name__}] 触发 WorkflowTab 按钮状态更新...")
                self.app.workflow_tab.update_button_states()
            else: print(f"[{type(self).__name__}] 无法触发更新：WorkflowTab 不可用。")
        except Exception as e: print(f"错误: 在 trigger_workflow_button_update ({type(self).__name__}) 中发生异常: {e}"); traceback.print_exc()