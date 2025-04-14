# ui/llm_config_tab.py
import customtkinter as ctk
from tkinter import BooleanVar, StringVar, messagebox

class LLMConfigTab(ctk.CTkFrame):
    """LLM 和全局设置（包括代理）的 UI 标签页"""
    def __init__(self, master, config_manager, app_instance):
        super().__init__(master, fg_color="transparent")
        self.config_manager = config_manager
        self.app = app_instance

        # --- 创建主滚动框架 ---
        self.scrollable_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scrollable_frame.pack(expand=True, fill="both")

        # --- 将所有 UI 元素放入滚动框架内 ---
        self.build_ui_within_scrollable_frame(self.scrollable_frame)
        self.load_initial_config()

    def build_ui_within_scrollable_frame(self, master_frame):
        """在指定的父框架（滚动框架）内构建 UI 元素"""
        master_frame.grid_columnconfigure(1, weight=1)
        current_row = 0

        # --- LLM API 设置 ---
        api_key_label = ctk.CTkLabel(master_frame, text="LLM API Key:")
        api_key_label.grid(row=current_row, column=0, padx=10, pady=5, sticky="w")
        self.api_key_var = StringVar()
        api_key_entry = ctk.CTkEntry(master_frame, textvariable=self.api_key_var, show="*")
        api_key_entry.grid(row=current_row, column=1, columnspan=3, padx=10, pady=5, sticky="ew")
        current_row += 1
        api_endpoint_label = ctk.CTkLabel(master_frame, text="LLM API Base URL:")
        api_endpoint_label.grid(row=current_row, column=0, padx=10, pady=5, sticky="w")
        self.api_endpoint_var = StringVar()
        api_endpoint_entry = ctk.CTkEntry(master_frame, textvariable=self.api_endpoint_var, placeholder_text="例如: https://generativelanguage.googleapis.com")
        api_endpoint_entry.grid(row=current_row, column=1, columnspan=3, padx=10, pady=5, sticky="ew")
        current_row += 1
        model_name_label = ctk.CTkLabel(master_frame, text="LLM 模型名称:")
        model_name_label.grid(row=current_row, column=0, padx=10, pady=5, sticky="w")
        self.model_name_var = StringVar()
        model_name_entry = ctk.CTkEntry(master_frame, textvariable=self.model_name_var, placeholder_text="例如: gemini-1.5-flash-latest")
        model_name_entry.grid(row=current_row, column=1, columnspan=3, padx=10, pady=5, sticky="ew")

        # --- 生成参数 (包括新增的 Top P, Top K) ---
        current_row += 1
        gen_param_frame = ctk.CTkFrame(master_frame, fg_color="transparent")
        gen_param_frame.grid(row=current_row, column=0, columnspan=4, pady=(10, 5), sticky="ew")
        # 配置4列均匀分布
        gen_param_frame.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="llm_params")

        # Temperature
        temp_label = ctk.CTkLabel(gen_param_frame, text="Temperature:")
        temp_label.grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.temperature_var = StringVar(value="0.2")
        temp_entry = ctk.CTkEntry(gen_param_frame, textvariable=self.temperature_var)
        temp_entry.grid(row=1, column=0, padx=5, pady=5, sticky="ew")

        # Max Tokens
        max_tokens_label = ctk.CTkLabel(gen_param_frame, text="Max Tokens:")
        max_tokens_label.grid(row=0, column=1, padx=5, pady=2, sticky="w")
        self.max_tokens_var = StringVar(value="8192")
        max_tokens_entry = ctk.CTkEntry(gen_param_frame, textvariable=self.max_tokens_var)
        max_tokens_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        # --- 新增 Top P ---
        top_p_label = ctk.CTkLabel(gen_param_frame, text="Top P (可选):")
        top_p_label.grid(row=0, column=2, padx=5, pady=2, sticky="w")
        self.top_p_var = StringVar() # 默认空字符串，表示不设置
        top_p_entry = ctk.CTkEntry(gen_param_frame, textvariable=self.top_p_var, placeholder_text="0.0-1.0, 留空则不设置")
        top_p_entry.grid(row=1, column=2, padx=5, pady=5, sticky="ew")

        # --- 新增 Top K ---
        top_k_label = ctk.CTkLabel(gen_param_frame, text="Top K (可选):")
        top_k_label.grid(row=0, column=3, padx=5, pady=2, sticky="w")
        self.top_k_var = StringVar() # 默认空字符串，表示不设置
        top_k_entry = ctk.CTkEntry(gen_param_frame, textvariable=self.top_k_var, placeholder_text=">=1, 留空则不设置")
        top_k_entry.grid(row=1, column=3, padx=5, pady=5, sticky="ew")
        # --- 新增结束 ---

        # --- Google API 代理设置 ---
        current_row += 1
        proxy_frame = ctk.CTkFrame(master_frame, fg_color="transparent")
        proxy_frame.grid(row=current_row, column=0, columnspan=4, padx=10, pady=10, sticky="ew")
        proxy_frame.grid_columnconfigure(2, weight=1)
        self.use_proxy_var = BooleanVar()
        proxy_checkbox = ctk.CTkCheckBox(proxy_frame, text="使用代理访问 Google API?", variable=self.use_proxy_var, command=self.toggle_proxy_entries)
        proxy_checkbox.grid(row=0, column=0, padx=(0, 20), pady=10, sticky="w")
        proxy_addr_label = ctk.CTkLabel(proxy_frame, text="地址:")
        proxy_addr_label.grid(row=0, column=1, padx=(0, 5), pady=10, sticky="w")
        self.proxy_address_var = StringVar()
        self.proxy_address_entry = ctk.CTkEntry(proxy_frame, textvariable=self.proxy_address_var, placeholder_text="例如: 127.0.0.1")
        self.proxy_address_entry.grid(row=0, column=2, padx=5, pady=10, sticky="ew")
        proxy_port_label = ctk.CTkLabel(proxy_frame, text="端口:")
        proxy_port_label.grid(row=0, column=3, padx=(10, 5), pady=10, sticky="w")
        self.proxy_port_var = StringVar()
        self.proxy_port_entry = ctk.CTkEntry(proxy_frame, textvariable=self.proxy_port_var, placeholder_text="例如: 7890", width=80)
        self.proxy_port_entry.grid(row=0, column=4, padx=(0, 10), pady=10, sticky="w")

        # --- 全局指令 ---
        current_row += 1
        pre_instr_label = ctk.CTkLabel(master_frame, text="全局前置指令:")
        pre_instr_label.grid(row=current_row, column=0, padx=10, pady=(10, 5), sticky="nw")
        self.pre_instruction_textbox = ctk.CTkTextbox(master_frame, height=60, wrap="word")
        self.pre_instruction_textbox.grid(row=current_row, column=1, columnspan=3, padx=10, pady=(10, 5), sticky="ew")
        current_row += 1
        post_instr_label = ctk.CTkLabel(master_frame, text="全局后置指令:")
        post_instr_label.grid(row=current_row, column=0, padx=10, pady=5, sticky="nw")
        self.post_instruction_textbox = ctk.CTkTextbox(master_frame, height=60, wrap="word")
        self.post_instruction_textbox.grid(row=current_row, column=1, columnspan=3, padx=10, pady=5, sticky="ew")

        # --- 提示音路径 ---
        current_row += 1
        sound_frame = ctk.CTkFrame(master_frame, fg_color="transparent")
        sound_frame.grid(row=current_row, column=0, columnspan=4, pady=(10, 5), sticky="ew")
        sound_frame.grid_columnconfigure((1, 3), weight=1)
        success_sound_label = ctk.CTkLabel(sound_frame, text="成功提示音:")
        success_sound_label.grid(row=0, column=0, padx=(10,5), pady=5, sticky="w")
        self.success_sound_var = StringVar()
        success_sound_entry = ctk.CTkEntry(sound_frame, textvariable=self.success_sound_var, placeholder_text="例如: assets/success.wav")
        success_sound_entry.grid(row=0, column=1, padx=(0,10), pady=5, sticky="ew")
        failure_sound_label = ctk.CTkLabel(sound_frame, text="失败提示音:")
        failure_sound_label.grid(row=0, column=2, padx=(10,5), pady=5, sticky="w")
        self.failure_sound_var = StringVar()
        failure_sound_entry = ctk.CTkEntry(sound_frame, textvariable=self.failure_sound_var, placeholder_text="例如: assets/failure.wav")
        failure_sound_entry.grid(row=0, column=3, padx=(0,10), pady=5, sticky="ew")

        # --- 其他开关 ---
        current_row += 1
        switch_frame = ctk.CTkFrame(master_frame, fg_color="transparent")
        switch_frame.grid(row=current_row, column=0, columnspan=4, pady=10, sticky="w", padx=10)
        self.save_debug_var = BooleanVar()
        save_debug_check = ctk.CTkCheckBox(switch_frame, text="保存 LLM 调试输入?", variable=self.save_debug_var)
        save_debug_check.pack(side="left", padx=(0, 20))
        self.enable_streaming_var = BooleanVar(value=True)
        streaming_checkbox = ctk.CTkCheckBox(switch_frame, text="启用 LLM 流式传输?", variable=self.enable_streaming_var)
        streaming_checkbox.pack(side="left")

        # 初始化代理输入框状态
        self.toggle_proxy_entries()

    def toggle_proxy_entries(self):
        """切换代理输入框状态"""
        use_proxy = self.use_proxy_var.get()
        new_state = "normal" if use_proxy else "disabled"
        if hasattr(self, 'proxy_address_entry') and self.proxy_address_entry.winfo_exists():
            self.proxy_address_entry.configure(state=new_state)
            if not use_proxy: self.proxy_address_var.set("")
        if hasattr(self, 'proxy_port_entry') and self.proxy_port_entry.winfo_exists():
            self.proxy_port_entry.configure(state=new_state)
            if not use_proxy: self.proxy_port_var.set("")

    def load_initial_config(self):
        """加载初始 LLM 和全局配置"""
        print("正在加载 LLM 及全局配置到 UI...")
        config = self.config_manager.load_config("llm_global")
        config_to_print = {k: v for k, v in config.items() if k != 'apiKey'}
        print("[LLM Tab] 加载的配置:", config_to_print)

        self.api_key_var.set(config.get("apiKey", ""))
        self.api_endpoint_var.set(config.get("apiEndpoint", ""))
        self.model_name_var.set(config.get("modelName", ""))
        self.temperature_var.set(str(config.get("temperature", 0.2)))
        self.max_tokens_var.set(str(config.get("maxOutputTokens", 8192)))
        # 加载 Top P 和 Top K (如果值为 None 则设置为空字符串)
        self.top_p_var.set(str(config.get("topP")) if config.get("topP") is not None else "")
        self.top_k_var.set(str(config.get("topK")) if config.get("topK") is not None else "")

        try:
            if hasattr(self, 'pre_instruction_textbox') and self.pre_instruction_textbox.winfo_exists(): self.pre_instruction_textbox.delete("1.0", "end"); self.pre_instruction_textbox.insert("1.0", config.get("preInstruction", ""))
            if hasattr(self, 'post_instruction_textbox') and self.post_instruction_textbox.winfo_exists(): self.post_instruction_textbox.delete("1.0", "end"); self.post_instruction_textbox.insert("1.0", config.get("postInstruction", ""))
        except Exception as e: print(f"[LLM Tab] 更新指令文本框时出错: {e}")

        self.success_sound_var.set(config.get("successSoundPath", ""))
        self.failure_sound_var.set(config.get("failureSoundPath", ""))
        self.save_debug_var.set(bool(config.get("saveDebugInputs", False)))
        self.enable_streaming_var.set(bool(config.get("enableStreaming", True)))
        self.use_proxy_var.set(bool(config.get("use_proxy", False)))
        self.proxy_address_var.set(config.get("proxy_address", ""))
        self.proxy_port_var.set(str(config.get("proxy_port", "")))
        # 注意：通知开关的状态由 main_app 管理，这里不直接加载

        self.toggle_proxy_entries()
        print("[LLM Tab] 配置加载完成。")

    def get_config_data(self):
        """收集当前的 LLM 和全局配置数据"""
        print("[LLM Tab] 正在从 UI 收集配置数据...")
        pre_instruction = ""; post_instruction = ""
        try:
            if hasattr(self, 'pre_instruction_textbox') and self.pre_instruction_textbox.winfo_exists(): pre_instruction = self.pre_instruction_textbox.get("1.0", "end-1c").strip()
            if hasattr(self, 'post_instruction_textbox') and self.post_instruction_textbox.winfo_exists(): post_instruction = self.post_instruction_textbox.get("1.0", "end-1c").strip()
        except Exception as e: print(f"[LLM Tab] 获取指令文本时出错: {e}")

        # 输入校验
        temperature = None; temp_str = self.temperature_var.get().strip()
        if temp_str:
             try: temperature = float(temp_str); assert 0.0 <= temperature <= 2.0
             except: print(f"警告: 无效的 Temperature 值 '{temp_str}'，将使用 None。"); messagebox.showwarning("输入错误", f"Temperature 值 '{temp_str}' 不是 0.0 到 2.0 之间的有效数字。", parent=self); temperature = None
        max_tokens = None; max_tokens_str = self.max_tokens_var.get().strip()
        if max_tokens_str:
             try: max_tokens = int(max_tokens_str); assert max_tokens >= 1
             except: print(f"警告: 无效的 Max Tokens 值 '{max_tokens_str}'，将使用 None。"); messagebox.showwarning("输入错误", f"Max Tokens 值 '{max_tokens_str}' 不是有效的正整数。", parent=self); max_tokens = None
        # --- 新增 Top P / Top K 校验 ---
        top_p = None; top_p_str = self.top_p_var.get().strip()
        if top_p_str:
            try: top_p = float(top_p_str); assert 0.0 <= top_p <= 1.0
            except: print(f"警告: 无效的 Top P 值 '{top_p_str}'，将使用 None。"); messagebox.showwarning("输入错误", f"Top P 值 '{top_p_str}' 不是 0.0 到 1.0 之间的有效数字。", parent=self); top_p = None
        top_k = None; top_k_str = self.top_k_var.get().strip()
        if top_k_str:
            try: top_k = int(top_k_str); assert top_k >= 1
            except: print(f"警告: 无效的 Top K 值 '{top_k_str}'，将使用 None。"); messagebox.showwarning("输入错误", f"Top K 值 '{top_k_str}' 不是有效的正整数。", parent=self); top_k = None
        # --- 校验结束 ---
        proxy_port_validated = ""; proxy_port_str = self.proxy_port_var.get().strip()
        if self.use_proxy_var.get() and proxy_port_str:
             try: port_num = int(proxy_port_str); assert 1 <= port_num <= 65535; proxy_port_validated = proxy_port_str
             except: print(f"错误: 无效的 Google API 代理端口号 '{proxy_port_str}'。"); messagebox.showwarning("输入错误", f"Google API 代理端口号 '{proxy_port_str}' 无效 (必须是 1-65535)。", parent=self)

        # 组合配置字典
        config_data = {
            "apiKey": self.api_key_var.get(), "apiEndpoint": self.api_endpoint_var.get().rstrip('/'),
            "modelName": self.model_name_var.get(), "temperature": temperature, "maxOutputTokens": max_tokens,
            "topP": top_p, "topK": top_k, # 添加 Top P 和 Top K
            "preInstruction": pre_instruction, "postInstruction": post_instruction,
            "successSoundPath": self.success_sound_var.get(), "failureSoundPath": self.failure_sound_var.get(),
            "saveDebugInputs": self.save_debug_var.get(), "enableStreaming": self.enable_streaming_var.get(),
            "use_proxy": self.use_proxy_var.get(), "proxy_address": self.proxy_address_var.get().strip(), "proxy_port": proxy_port_validated,
            "enableSoundNotifications": self.app.enable_sound_var.get(), "enableWinNotifications": self.app.enable_win_notify_var.get(),
        }
        config_to_print = {k: v for k, v in config_data.items() if k != 'apiKey'}
        print("[LLM Tab] 配置数据收集完成:", config_to_print)
        return config_data