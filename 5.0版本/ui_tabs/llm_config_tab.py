# ui_tabs/llm_config_tab.py
import customtkinter as ctk
from tkinter import BooleanVar, StringVar, messagebox # 使用标准库 messagebox

class LLMConfigTab(ctk.CTkFrame):
    """LLM 和全局设置（包括代理）的 UI 标签页"""
    def __init__(self, master, config_manager, app_instance):
        super().__init__(master, fg_color="transparent")
        self.config_manager = config_manager
        self.app = app_instance
        self.build_ui()
        self.load_initial_config()

    def build_ui(self):
        """构建此标签页的 UI 元素"""
        # 配置主框架网格，让第二列 (输入框) 可扩展
        self.grid_columnconfigure(1, weight=1)
        current_row = 0

        # --- LLM API 设置 ---
        # API Key
        api_key_label = ctk.CTkLabel(self, text="LLM API Key:")
        api_key_label.grid(row=current_row, column=0, padx=10, pady=5, sticky="w")
        self.api_key_var = StringVar()
        api_key_entry = ctk.CTkEntry(self, textvariable=self.api_key_var, show="*") # 隐藏输入
        api_key_entry.grid(row=current_row, column=1, columnspan=3, padx=10, pady=5, sticky="ew") # 跨3列

        current_row += 1
        # API Base URL / Endpoint
        api_endpoint_label = ctk.CTkLabel(self, text="LLM API Base URL:")
        api_endpoint_label.grid(row=current_row, column=0, padx=10, pady=5, sticky="w")
        self.api_endpoint_var = StringVar()
        api_endpoint_entry = ctk.CTkEntry(self, textvariable=self.api_endpoint_var, placeholder_text="例如: https://generativelanguage.googleapis.com")
        api_endpoint_entry.grid(row=current_row, column=1, columnspan=3, padx=10, pady=5, sticky="ew")

        current_row += 1
        # 模型名称
        model_name_label = ctk.CTkLabel(self, text="LLM 模型名称:")
        model_name_label.grid(row=current_row, column=0, padx=10, pady=5, sticky="w")
        self.model_name_var = StringVar()
        model_name_entry = ctk.CTkEntry(self, textvariable=self.model_name_var, placeholder_text="例如: gemini-1.5-flash-latest")
        model_name_entry.grid(row=current_row, column=1, columnspan=3, padx=10, pady=5, sticky="ew")

        # --- 生成参数 (Temperature, Max Tokens) ---
        current_row += 1
        gen_param_frame = ctk.CTkFrame(self, fg_color="transparent")
        gen_param_frame.grid(row=current_row, column=0, columnspan=4, pady=(10, 5), sticky="ew")
        # 配置参数框架内部列权重，让输入框均匀分布
        gen_param_frame.grid_columnconfigure((1, 3), weight=1)

        # Temperature
        temp_label = ctk.CTkLabel(gen_param_frame, text="Temperature:")
        temp_label.grid(row=0, column=0, padx=(10,5), pady=5, sticky="w")
        self.temperature_var = StringVar(value="0.2") # 默认值
        temp_entry = ctk.CTkEntry(gen_param_frame, textvariable=self.temperature_var, width=80) # 限制宽度
        temp_entry.grid(row=0, column=1, padx=(0,10), pady=5, sticky="w") # 左对齐

        # Max Tokens
        max_tokens_label = ctk.CTkLabel(gen_param_frame, text="Max Tokens:")
        max_tokens_label.grid(row=0, column=2, padx=(10,5), pady=5, sticky="w")
        self.max_tokens_var = StringVar(value="8192") # 默认值
        max_tokens_entry = ctk.CTkEntry(gen_param_frame, textvariable=self.max_tokens_var, width=80) # 限制宽度
        max_tokens_entry.grid(row=0, column=3, padx=(0,10), pady=5, sticky="w") # 左对齐

        # --- Google API 代理设置 ---
        current_row += 1
        proxy_frame = ctk.CTkFrame(self, fg_color="transparent")
        proxy_frame.grid(row=current_row, column=0, columnspan=4, padx=10, pady=10, sticky="ew")
        # 配置代理框架内部列权重，让地址输入框扩展
        proxy_frame.grid_columnconfigure(2, weight=1)

        # 启用代理复选框
        self.use_proxy_var = BooleanVar()
        proxy_checkbox = ctk.CTkCheckBox(proxy_frame, text="使用代理访问 Google API?",
                                         variable=self.use_proxy_var,
                                         command=self.toggle_proxy_entries) # 点击时切换输入框状态
        proxy_checkbox.grid(row=0, column=0, padx=(0, 20), pady=10, sticky="w")

        # 代理地址
        proxy_addr_label = ctk.CTkLabel(proxy_frame, text="地址:")
        proxy_addr_label.grid(row=0, column=1, padx=(0, 5), pady=10, sticky="w")
        self.proxy_address_var = StringVar()
        self.proxy_address_entry = ctk.CTkEntry(proxy_frame, textvariable=self.proxy_address_var, placeholder_text="例如: 127.0.0.1")
        self.proxy_address_entry.grid(row=0, column=2, padx=5, pady=10, sticky="ew")

        # 代理端口
        proxy_port_label = ctk.CTkLabel(proxy_frame, text="端口:")
        proxy_port_label.grid(row=0, column=3, padx=(10, 5), pady=10, sticky="w")
        self.proxy_port_var = StringVar()
        self.proxy_port_entry = ctk.CTkEntry(proxy_frame, textvariable=self.proxy_port_var, placeholder_text="例如: 7890", width=80) # 固定宽度
        self.proxy_port_entry.grid(row=0, column=4, padx=(0, 10), pady=10, sticky="w")

        # --- 全局指令 ---
        current_row += 1
        pre_instr_label = ctk.CTkLabel(self, text="全局前置指令:")
        pre_instr_label.grid(row=current_row, column=0, padx=10, pady=(10, 5), sticky="nw") # 西北对齐
        self.pre_instruction_textbox = ctk.CTkTextbox(self, height=60, wrap="word") # 自动换行
        self.pre_instruction_textbox.grid(row=current_row, column=1, columnspan=3, padx=10, pady=(10, 5), sticky="ew")

        current_row += 1
        post_instr_label = ctk.CTkLabel(self, text="全局后置指令:")
        post_instr_label.grid(row=current_row, column=0, padx=10, pady=5, sticky="nw")
        self.post_instruction_textbox = ctk.CTkTextbox(self, height=60, wrap="word")
        self.post_instruction_textbox.grid(row=current_row, column=1, columnspan=3, padx=10, pady=5, sticky="ew")

        # --- 提示音路径 ---
        current_row += 1
        sound_frame = ctk.CTkFrame(self, fg_color="transparent")
        sound_frame.grid(row=current_row, column=0, columnspan=4, pady=(10, 5), sticky="ew")
        # 配置声音框架内部列权重，让输入框扩展
        sound_frame.grid_columnconfigure((1, 3), weight=1)

        # 成功提示音
        success_sound_label = ctk.CTkLabel(sound_frame, text="成功提示音:")
        success_sound_label.grid(row=0, column=0, padx=(10,5), pady=5, sticky="w")
        self.success_sound_var = StringVar()
        success_sound_entry = ctk.CTkEntry(sound_frame, textvariable=self.success_sound_var, placeholder_text="例如: assets/success.wav")
        success_sound_entry.grid(row=0, column=1, padx=(0,10), pady=5, sticky="ew")
        # 可以在这里加一个浏览按钮

        # 失败提示音
        failure_sound_label = ctk.CTkLabel(sound_frame, text="失败提示音:")
        failure_sound_label.grid(row=0, column=2, padx=(10,5), pady=5, sticky="w")
        self.failure_sound_var = StringVar()
        failure_sound_entry = ctk.CTkEntry(sound_frame, textvariable=self.failure_sound_var, placeholder_text="例如: assets/failure.wav")
        failure_sound_entry.grid(row=0, column=3, padx=(0,10), pady=5, sticky="ew")
        # 可以在这里加一个浏览按钮

        # --- 其他开关 ---
        current_row += 1
        switch_frame = ctk.CTkFrame(self, fg_color="transparent")
        switch_frame.grid(row=current_row, column=0, columnspan=4, pady=10, sticky="w", padx=10)

        # 保存调试输入开关
        self.save_debug_var = BooleanVar()
        save_debug_check = ctk.CTkCheckBox(switch_frame, text="保存 LLM 调试输入?", variable=self.save_debug_var)
        save_debug_check.pack(side="left", padx=(0, 20))

        # 启用流式传输开关
        self.enable_streaming_var = BooleanVar(value=True) # 默认启用
        streaming_checkbox = ctk.CTkCheckBox(switch_frame, text="启用 LLM 流式传输?", variable=self.enable_streaming_var)
        streaming_checkbox.pack(side="left")

        # 初始化代理输入框状态
        self.toggle_proxy_entries()

    def toggle_proxy_entries(self):
        """根据 Google API 代理复选框的状态启用或禁用代理地址/端口输入框"""
        use_proxy = self.use_proxy_var.get()
        new_state = "normal" if use_proxy else "disabled"

        # 更新地址输入框状态
        if hasattr(self, 'proxy_address_entry') and self.proxy_address_entry.winfo_exists():
            self.proxy_address_entry.configure(state=new_state)
            if not use_proxy: self.proxy_address_var.set("") # 禁用时清空

        # 更新端口输入框状态
        if hasattr(self, 'proxy_port_entry') and self.proxy_port_entry.winfo_exists():
            self.proxy_port_entry.configure(state=new_state)
            if not use_proxy: self.proxy_port_var.set("") # 禁用时清空

    def load_initial_config(self):
        """从配置文件加载初始 LLM 和全局配置到 UI 元素"""
        print("正在加载 LLM 及全局配置到 UI...")
        config = self.config_manager.load_config("llm_global")

        # 打印加载的配置 (隐藏 API Key)
        config_to_print = {k: v for k, v in config.items() if k != 'apiKey'}
        print("[LLM Tab] 加载的配置:", config_to_print)

        # 设置 UI 变量
        self.api_key_var.set(config.get("apiKey", ""))
        self.api_endpoint_var.set(config.get("apiEndpoint", ""))
        self.model_name_var.set(config.get("modelName", ""))

        # 处理可能为 None 的数字类型
        temp = config.get("temperature")
        self.temperature_var.set(str(temp) if temp is not None else defaults.get("temperature", 0.2)) # 使用默认值处理 None
        max_tokens = config.get("maxOutputTokens")
        self.max_tokens_var.set(str(max_tokens) if max_tokens is not None else defaults.get("maxOutputTokens", 8192))

        # 加载指令到文本框 (检查控件是否存在)
        try:
            if hasattr(self, 'pre_instruction_textbox') and self.pre_instruction_textbox.winfo_exists():
                self.pre_instruction_textbox.delete("1.0", "end")
                self.pre_instruction_textbox.insert("1.0", config.get("preInstruction", ""))
            if hasattr(self, 'post_instruction_textbox') and self.post_instruction_textbox.winfo_exists():
                self.post_instruction_textbox.delete("1.0", "end")
                self.post_instruction_textbox.insert("1.0", config.get("postInstruction", ""))
        except Exception as e:
            print(f"[LLM Tab] 更新指令文本框时出错: {e}")

        # 加载提示音路径
        self.success_sound_var.set(config.get("successSoundPath", ""))
        self.failure_sound_var.set(config.get("failureSoundPath", ""))

        # 加载开关状态 (确保是布尔值)
        self.save_debug_var.set(bool(config.get("saveDebugInputs", False)))
        self.enable_streaming_var.set(bool(config.get("enableStreaming", True)))

        # 加载代理设置
        self.use_proxy_var.set(bool(config.get("use_proxy", False)))
        self.proxy_address_var.set(config.get("proxy_address", ""))
        self.proxy_port_var.set(str(config.get("proxy_port", ""))) # 端口加载为字符串

        # 根据加载的代理设置初始化输入框状态
        self.toggle_proxy_entries()
        print("[LLM Tab] 配置加载完成。")

    def get_config_data(self):
        """从 UI 元素收集当前的 LLM 和全局配置数据"""
        print("[LLM Tab] 正在从 UI 收集配置数据...")
        # 获取指令文本 (检查控件是否存在)
        pre_instruction = ""
        post_instruction = ""
        try:
            if hasattr(self, 'pre_instruction_textbox') and self.pre_instruction_textbox.winfo_exists():
                pre_instruction = self.pre_instruction_textbox.get("1.0", "end-1c").strip()
            if hasattr(self, 'post_instruction_textbox') and self.post_instruction_textbox.winfo_exists():
                post_instruction = self.post_instruction_textbox.get("1.0", "end-1c").strip()
        except Exception as e:
            print(f"[LLM Tab] 获取指令文本时出错: {e}")

        # --- 输入校验 ---
        # Temperature (float, 0-2)
        temperature = None # 初始化为 None
        temp_str = self.temperature_var.get().strip()
        if temp_str:
             try:
                 temperature = float(temp_str)
                 # Google API 允许 0-2，这里可以放宽或严格限制
                 if not (0.0 <= temperature <= 2.0):
                      print(f"警告: Temperature '{temperature}' 超出建议范围 [0.0, 2.0]。")
                      # 可以选择弹窗警告或自动修正，这里只打印警告
                      # messagebox.showwarning("输入警告", f"Temperature 值 '{temperature}' 超出建议范围 [0.0, 2.0]。", parent=self)
                      # temperature = max(0.0, min(temperature, 2.0)) # 强制修正到范围内
             except ValueError:
                  print(f"警告: 无效的 Temperature 值 '{temp_str}'，将使用 None (API 默认)。")
                  messagebox.showwarning("输入错误", f"Temperature 值 '{temp_str}' 不是有效的数字。\n将使用 API 的默认值。", parent=self)
                  temperature = None # 明确设为 None
                  # self.temperature_var.set("") # 清空无效输入

        # Max Tokens (int, >0)
        max_tokens = None # 初始化为 None
        max_tokens_str = self.max_tokens_var.get().strip()
        if max_tokens_str:
             try:
                 max_tokens = int(max_tokens_str)
                 if max_tokens < 1:
                      print(f"警告: Max Tokens '{max_tokens}' 必须大于 0。")
                      messagebox.showwarning("输入错误", f"Max Tokens 值 '{max_tokens}' 无效 (必须大于 0)。\n将使用 API 的默认值。", parent=self)
                      max_tokens = None # 设为 None
                      # self.max_tokens_var.set("") # 清空无效输入
             except ValueError:
                  print(f"警告: 无效的 Max Tokens 值 '{max_tokens_str}'，将使用 None (API 默认)。")
                  messagebox.showwarning("输入错误", f"Max Tokens 值 '{max_tokens_str}' 不是有效的整数。\n将使用 API 的默认值。", parent=self)
                  max_tokens = None # 明确设为 None
                  # self.max_tokens_var.set("") # 清空无效输入

        # Google API 代理端口校验
        proxy_port_validated = "" # 用于存储校验后的端口
        proxy_port_str = self.proxy_port_var.get().strip()
        if self.use_proxy_var.get() and proxy_port_str: # 仅在启用代理且端口非空时校验
             try:
                  port_num = int(proxy_port_str)
                  if 1 <= port_num <= 65535:
                       proxy_port_validated = proxy_port_str # 端口有效
                  else:
                       # 端口号无效
                       messagebox.showwarning("输入错误", f"Google API 代理端口号 '{proxy_port_str}' 无效。\n端口号必须在 1 到 65535 之间。", parent=self)
                       print(f"错误: 无效的 Google API 代理端口号 '{proxy_port_str}'。")
                       # self.proxy_port_var.set("") # 清空无效输入
             except ValueError:
                  # 输入不是数字
                  messagebox.showwarning("输入错误", f"Google API 代理端口 '{proxy_port_str}' 不是有效的数字。", parent=self)
                  print(f"错误: Google API 代理端口 '{proxy_port_str}' 不是数字。")
                  # self.proxy_port_var.set("") # 清空无效输入

        # 组合配置字典
        config_data = {
            "apiKey": self.api_key_var.get(),
            "apiEndpoint": self.api_endpoint_var.get().rstrip('/'), # 移除末尾斜杠
            "modelName": self.model_name_var.get(),
            "temperature": temperature, # 可能为 None
            "maxOutputTokens": max_tokens, # 可能为 None
            "preInstruction": pre_instruction,
            "postInstruction": post_instruction,
            "successSoundPath": self.success_sound_var.get(),
            "failureSoundPath": self.failure_sound_var.get(),
            "saveDebugInputs": self.save_debug_var.get(),
            "enableStreaming": self.enable_streaming_var.get(),
            "use_proxy": self.use_proxy_var.get(),
            "proxy_address": self.proxy_address_var.get().strip(),
            "proxy_port": proxy_port_validated # 返回校验后的端口 (可能为空字符串)
        }
        # 打印收集的配置 (隐藏 API Key)
        config_to_print = {k: v for k, v in config_data.items() if k != 'apiKey'}
        print("[LLM Tab] 配置数据收集完成:", config_to_print)
        return config_data