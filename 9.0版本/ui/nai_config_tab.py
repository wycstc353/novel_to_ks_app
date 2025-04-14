# ui/nai_config_tab.py
import customtkinter as ctk
from tkinter import StringVar, IntVar, DoubleVar, BooleanVar, messagebox, filedialog
import os
import traceback

class NAIConfigTab(ctk.CTkFrame):
    """NAI API 设置（包括代理）的 UI 标签页"""
    def __init__(self, master, config_manager, app_instance):
        super().__init__(master, fg_color="transparent")
        self.config_manager = config_manager
        self.app = app_instance
        self.nai_models = self.config_manager.load_nai_models()
        self._model_name_to_value = {m['name']: m['value'] for m in self.nai_models}
        self._model_value_to_name = {m['value']: m['name'] for m in self.nai_models}
        self._uc_preset_map = {0: "Heavy", 1: "Light", 2: "Human Focus", 3: "None"}
        self._uc_preset_name_to_value = {v: k for k, v in self._uc_preset_map.items()}

        # --- 创建主滚动框架 ---
        self.scrollable_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scrollable_frame.pack(expand=True, fill="both")

        # --- 将所有 UI 元素放入滚动框架内 ---
        self.build_ui_within_scrollable_frame(self.scrollable_frame)
        self.load_initial_config()

    def build_ui_within_scrollable_frame(self, master_frame):
        """在指定的父框架（滚动框架）内构建 UI 元素"""
        # 配置滚动框架内部网格，让第二列 (输入框) 可扩展
        master_frame.grid_columnconfigure(1, weight=1)
        row = 0

        # --- NAI API Key ---
        api_key_label = ctk.CTkLabel(master_frame, text="NAI API Key:")
        api_key_label.grid(row=row, column=0, padx=10, pady=5, sticky="w")
        self.api_key_var = StringVar()
        api_key_entry = ctk.CTkEntry(master_frame, textvariable=self.api_key_var, show="*")
        api_key_entry.grid(row=row, column=1, columnspan=2, padx=10, pady=5, sticky="ew")
        api_key_entry.bind("<FocusOut>", self.trigger_workflow_button_update)

        # --- 图片保存目录 ---
        row += 1
        save_dir_label = ctk.CTkLabel(master_frame, text="图片保存目录:")
        save_dir_label.grid(row=row, column=0, padx=10, pady=5, sticky="w")
        self.save_dir_var = StringVar()
        dir_entry = ctk.CTkEntry(master_frame, textvariable=self.save_dir_var, placeholder_text="应用可访问的完整目录路径")
        dir_entry.grid(row=row, column=1, padx=(10, 0), pady=5, sticky="ew")
        dir_entry.bind("<FocusOut>", self.trigger_workflow_button_update)
        browse_button = ctk.CTkButton(master_frame, text="浏览...", width=60, command=self.browse_save_directory)
        browse_button.grid(row=row, column=2, padx=(5, 10), pady=5, sticky="w")

        # --- NAI 代理设置 ---
        row += 1
        nai_proxy_frame = ctk.CTkFrame(master_frame, fg_color="transparent")
        nai_proxy_frame.grid(row=row, column=0, columnspan=3, padx=10, pady=(10, 0), sticky="ew")
        nai_proxy_frame.grid_columnconfigure(2, weight=1) # 地址输入框列扩展
        self.nai_use_proxy_var = BooleanVar()
        nai_proxy_checkbox = ctk.CTkCheckBox(nai_proxy_frame, text="使用代理访问 NAI API?", variable=self.nai_use_proxy_var, command=self.toggle_nai_proxy_entries)
        nai_proxy_checkbox.grid(row=0, column=0, padx=(0, 20), pady=10, sticky="w")
        nai_proxy_addr_label = ctk.CTkLabel(nai_proxy_frame, text="地址:")
        nai_proxy_addr_label.grid(row=0, column=1, padx=(0, 5), pady=10, sticky="w")
        self.nai_proxy_address_var = StringVar()
        self.nai_proxy_address_entry = ctk.CTkEntry(nai_proxy_frame, textvariable=self.nai_proxy_address_var, placeholder_text="例如: 127.0.0.1")
        self.nai_proxy_address_entry.grid(row=0, column=2, padx=5, pady=10, sticky="ew")
        nai_proxy_port_label = ctk.CTkLabel(nai_proxy_frame, text="端口:")
        nai_proxy_port_label.grid(row=0, column=3, padx=(10, 5), pady=10, sticky="w")
        self.nai_proxy_port_var = StringVar()
        self.nai_proxy_port_entry = ctk.CTkEntry(nai_proxy_frame, textvariable=self.nai_proxy_port_var, placeholder_text="例如: 7890", width=80)
        self.nai_proxy_port_entry.grid(row=0, column=4, padx=(0, 10), pady=10, sticky="w")

        # --- NAI 生成参数 ---
        row += 1
        param_frame = ctk.CTkFrame(master_frame, fg_color="transparent")
        param_frame.grid(row=row, column=0, columnspan=3, sticky="ew", padx=5, pady=(5, 5))
        param_frame.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="group_nai") # 均匀分布列
        col = 0; row_param = 0
        # 模型
        model_label = ctk.CTkLabel(param_frame, text="模型:")
        model_label.grid(row=row_param, column=col, padx=5, pady=5, sticky="w")
        model_options = [m['name'] for m in self.nai_models] if self.nai_models else ["未加载模型列表"]
        self.model_display_var = StringVar(value=model_options[0] if model_options else "")
        self.model_combobox = ctk.CTkComboBox(param_frame, values=model_options, variable=self.model_display_var)
        self.model_combobox.grid(row=row_param+1, column=col, padx=5, pady=5, sticky="ew")
        if not self.nai_models: self.model_combobox.configure(state="disabled")
        col += 1
        # 采样器
        sampler_label = ctk.CTkLabel(param_frame, text="采样器:")
        sampler_label.grid(row=row_param, column=col, padx=5, pady=5, sticky="w")
        self.sampler_var = StringVar(value="k_euler")
        sampler_options = ["k_euler", "k_euler_ancestral", "k_dpmpp_2s_ancestral", "k_dpmpp_2m", "k_dpmpp_sde", "ddim"]
        sampler_combo = ctk.CTkComboBox(param_frame, values=sampler_options, variable=self.sampler_var)
        sampler_combo.grid(row=row_param+1, column=col, padx=5, pady=5, sticky="ew")
        col += 1
        # 步数
        steps_label = ctk.CTkLabel(param_frame, text="步数:")
        steps_label.grid(row=row_param, column=col, padx=5, pady=5, sticky="w")
        self.steps_var = IntVar(value=28)
        steps_entry = ctk.CTkEntry(param_frame, textvariable=self.steps_var)
        steps_entry.grid(row=row_param+1, column=col, padx=5, pady=5, sticky="ew")
        col += 1
        # 引导强度
        scale_label = ctk.CTkLabel(param_frame, text="引导强度:")
        scale_label.grid(row=row_param, column=col, padx=5, pady=5, sticky="w")
        self.scale_var = DoubleVar(value=7.0)
        scale_entry = ctk.CTkEntry(param_frame, textvariable=self.scale_var)
        scale_entry.grid(row=row_param+1, column=col, padx=5, pady=5, sticky="ew")
        # 换行
        col = 0; row_param += 2
        # 种子
        seed_label = ctk.CTkLabel(param_frame, text="种子 (-1随机):")
        seed_label.grid(row=row_param, column=col, padx=5, pady=5, sticky="w")
        self.seed_var = IntVar(value=-1)
        seed_entry = ctk.CTkEntry(param_frame, textvariable=self.seed_var)
        seed_entry.grid(row=row_param+1, column=col, padx=5, pady=5, sticky="ew")
        col += 1
        # 负面预设
        uc_label = ctk.CTkLabel(param_frame, text="负面预设:")
        uc_label.grid(row=row_param, column=col, padx=5, pady=5, sticky="w")
        uc_preset_options = list(self._uc_preset_map.values())
        self.uc_preset_display_var = StringVar(value=uc_preset_options[0] if uc_preset_options else "")
        uc_combo = ctk.CTkComboBox(param_frame, values=uc_preset_options, variable=self.uc_preset_display_var)
        uc_combo.grid(row=row_param+1, column=col, padx=5, pady=5, sticky="ew")
        col += 1
        # 质量标签
        quality_label = ctk.CTkLabel(param_frame, text="质量标签:")
        quality_label.grid(row=row_param, column=col, padx=5, pady=5, sticky="w")
        self.quality_toggle_var = BooleanVar(value=True)
        quality_check = ctk.CTkCheckBox(param_frame, text="", variable=self.quality_toggle_var)
        quality_check.grid(row=row_param+1, column=col, padx=5, pady=5, sticky="w")

        # 初始化代理输入框状态
        self.toggle_nai_proxy_entries()

    def browse_save_directory(self):
        """打开目录选择对话框"""
        directory = filedialog.askdirectory(title="选择 NAI 图片保存目录", parent=self)
        if directory: self.save_dir_var.set(directory); print(f"NAI 图片保存目录已设置为: {directory}"); self.trigger_workflow_button_update()
        else: print("用户取消选择目录。")

    def toggle_nai_proxy_entries(self):
        """切换 NAI 代理输入框状态"""
        use_proxy = self.nai_use_proxy_var.get()
        new_state = "normal" if use_proxy else "disabled"
        if hasattr(self, 'nai_proxy_address_entry') and self.nai_proxy_address_entry.winfo_exists():
             self.nai_proxy_address_entry.configure(state=new_state)
             if not use_proxy: self.nai_proxy_address_var.set("")
        if hasattr(self, 'nai_proxy_port_entry') and self.nai_proxy_port_entry.winfo_exists():
             self.nai_proxy_port_entry.configure(state=new_state)
             if not use_proxy: self.nai_proxy_port_var.set("")

    def load_initial_config(self):
        """加载初始 NAI 配置"""
        print("正在加载 NAI 配置到 UI...")
        config = self.config_manager.load_config("nai")
        self.api_key_var.set(config.get("naiApiKey", ""))
        self.save_dir_var.set(config.get("naiImageSaveDir", ""))
        saved_model_value = config.get("naiModel", "")
        saved_model_name = self._model_value_to_name.get(saved_model_value)
        if saved_model_name and self.nai_models: self.model_display_var.set(saved_model_name)
        elif self.nai_models: self.model_display_var.set(self.nai_models[0]['name'])
        else: self.model_display_var.set("未加载模型列表"); self.model_combobox.configure(state="disabled")
        self.sampler_var.set(config.get("naiSampler", "k_euler"))
        self.steps_var.set(int(config.get("naiSteps", 28)))
        self.scale_var.set(float(config.get("naiScale", 7.0)))
        self.seed_var.set(int(config.get("naiSeed", -1)))
        uc_preset_value = config.get("naiUcPreset", 0)
        uc_preset_name = self._uc_preset_map.get(uc_preset_value, "Heavy")
        self.uc_preset_display_var.set(uc_preset_name)
        self.quality_toggle_var.set(bool(config.get("naiQualityToggle", True)))
        self.nai_use_proxy_var.set(bool(config.get("nai_use_proxy", False)))
        self.nai_proxy_address_var.set(config.get("nai_proxy_address", ""))
        self.nai_proxy_port_var.set(str(config.get("nai_proxy_port", "")))
        self.toggle_nai_proxy_entries()
        print("NAI 配置加载完成。")

    def get_config_data(self):
        """收集当前的 NAI 配置数据"""
        print("正在从 UI 收集 NAI 配置数据...")
        selected_model_name = self.model_display_var.get()
        model_value = self._model_name_to_value.get(selected_model_name, "")
        if not model_value and self.nai_models: print(f"警告: 未找到模型名称 '{selected_model_name}' 对应的值，将使用第一个模型的值。"); model_value = self.nai_models[0]['value']
        selected_uc_preset_name = self.uc_preset_display_var.get()
        uc_preset_value = self._uc_preset_name_to_value.get(selected_uc_preset_name, 0)
        # 输入校验
        try: steps = int(self.steps_var.get()); assert steps > 0
        except: print(f"警告: 无效的步数输入 '{self.steps_var.get()}'，将使用默认值 28。"); steps = 28; self.steps_var.set(steps)
        try: scale = float(self.scale_var.get())
        except: print(f"警告: 无效的引导强度输入 '{self.scale_var.get()}'，将使用默认值 7.0。"); scale = 7.0; self.scale_var.set(scale)
        try: seed = int(self.seed_var.get())
        except: print(f"警告: 无效的种子输入 '{self.seed_var.get()}'，将使用默认值 -1。"); seed = -1; self.seed_var.set(seed)
        nai_proxy_port_validated = ""; nai_proxy_port_str = self.nai_proxy_port_var.get().strip()
        if self.nai_use_proxy_var.get() and nai_proxy_port_str:
             try: port_num = int(nai_proxy_port_str); assert 1 <= port_num <= 65535; nai_proxy_port_validated = nai_proxy_port_str
             except: messagebox.showwarning("输入错误", f"NAI 代理端口号 '{nai_proxy_port_str}' 无效 (必须是 1-65535)。", parent=self); print(f"错误: 无效的 NAI 代理端口号 '{nai_proxy_port_str}'。")
        # 组合配置字典
        config_data = {
            "naiApiKey": self.api_key_var.get(), "naiImageSaveDir": self.save_dir_var.get(),
            "naiModel": model_value, "naiSampler": self.sampler_var.get(), "naiSteps": steps,
            "naiScale": scale, "naiSeed": seed, "naiUcPreset": uc_preset_value,
            "naiQualityToggle": self.quality_toggle_var.get(),
            "nai_use_proxy": self.nai_use_proxy_var.get(),
            "nai_proxy_address": self.nai_proxy_address_var.get().strip(),
            "nai_proxy_port": nai_proxy_port_validated
        }
        print("NAI 配置数据收集完成。")
        return config_data

    def trigger_workflow_button_update(self, event=None):
        """通知 WorkflowTab 更新按钮状态"""
        try:
            if hasattr(self.app, 'workflow_tab') and self.app.workflow_tab and self.app.workflow_tab.winfo_exists():
                print(f"[{type(self).__name__}] 触发 WorkflowTab 按钮状态更新...")
                self.app.workflow_tab.update_button_states()
            else: print(f"[{type(self).__name__}] 无法触发更新：WorkflowTab 不可用。")
        except Exception as e: print(f"错误: 在 trigger_workflow_button_update ({type(self).__name__}) 中发生异常: {e}"); traceback.print_exc()