# ui/llm_config_tab.py
import customtkinter as ctk
from tkinter import BooleanVar, StringVar, messagebox, Text
import json
import traceback # 保留用于错误处理
import threading
from queue import Queue, Empty
from customtkinter import CTkFont # 导入 CTkFont
import logging # 导入日志模块

# 导入 UI 辅助函数
from .ui_helpers import create_help_button

# 尝试从 api 模块导入默认 URL (如果存在)
try: from api.openai_api_helper import OPENAI_API_BASE
except ImportError: OPENAI_API_BASE = "https://api.openai.com/v1"
try: from api.google_api_helpers import GOOGLE_API_BASE
except ImportError: GOOGLE_API_BASE = "https://generativelanguage.googleapis.com"

# 获取当前模块的 logger 实例
logger = logging.getLogger(__name__)

class LLMConfigTab(ctk.CTkFrame):
    """统一的 LLM 设置 UI 标签页 (Google & OpenAI)"""
    def __init__(self, master, config_manager, app_instance):
        super().__init__(master, fg_color="transparent")
        self.config_manager = config_manager
        self.app = app_instance
        self.google_model_fetch_queue = Queue()
        self.openai_model_fetch_queue = Queue()
        self.is_fetching_google_models = False
        self.is_fetching_openai_models = False

        # --- 创建主滚动框架 ---
        self.scrollable_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scrollable_frame.pack(expand=True, fill="both")

        # --- 将所有 UI 元素放入滚动框架内 ---
        self.build_ui_within_scrollable_frame(self.scrollable_frame)
        self.load_initial_config()
        # 启动队列检查循环
        self.after(200, self._check_google_model_fetch_queue)
        self.after(210, self._check_openai_model_fetch_queue)

    def build_ui_within_scrollable_frame(self, master_frame):
        """在指定的父框架（滚动框架）内构建 UI 元素"""
        # 调整列配置以容纳帮助按钮
        master_frame.grid_columnconfigure(1, weight=1) # 输入框列
        master_frame.grid_columnconfigure(2, weight=0) # 帮助按钮列
        current_row = 0

        # --- 新增：顶部提示文字 ---
        warning_text = "每次修改后要点击保存所有设置，不然修改不起效。"
        warning_textbox = ctk.CTkTextbox(
            master_frame,
            wrap="word",
            height=25, # 调整高度以适应单行文本
            activate_scrollbars=False,
            border_width=1,
            border_color="orange", # 橙色边框以示提醒
            corner_radius=5,
            font=CTkFont(size=12),
            fg_color="transparent"
        )
        warning_textbox.grid(row=current_row, column=0, columnspan=3, padx=10, pady=(10, 5), sticky="ew")
        warning_textbox.insert("1.0", warning_text)
        warning_textbox.configure(state="disabled") # 设置为只读
        current_row += 1

        # --- Google 特定设置 Frame ---
        self.google_frame = ctk.CTkFrame(master_frame, fg_color="transparent")
        self.google_frame.grid(row=current_row, column=0, columnspan=3, padx=10, pady=5, sticky="ew") # columnspan=3
        self.google_frame.grid_columnconfigure(1, weight=1)
        self.google_frame.grid_columnconfigure(2, weight=0) # Help button column
        google_row = 0

        google_api_key_label = ctk.CTkLabel(self.google_frame, text="Google API Key:")
        google_api_key_label.grid(row=google_row, column=0, padx=0, pady=5, sticky="w")
        self.google_api_key_var = StringVar()
        google_api_key_entry = ctk.CTkEntry(self.google_frame, textvariable=self.google_api_key_var, show="*")
        google_api_key_entry.grid(row=google_row, column=1, padx=5, pady=5, sticky="ew")
        if help_btn := create_help_button(self.google_frame, "google", "apiKey"): help_btn.grid(row=google_row, column=2, padx=(0, 5), pady=5, sticky="w")
        google_row += 1

        google_endpoint_label = ctk.CTkLabel(self.google_frame, text="Google API Base URL:")
        google_endpoint_label.grid(row=google_row, column=0, padx=0, pady=5, sticky="w")
        self.google_api_endpoint_var = StringVar()
        google_endpoint_entry = ctk.CTkEntry(self.google_frame, textvariable=self.google_api_endpoint_var, placeholder_text="例如: https://generativelanguage.googleapis.com")
        google_endpoint_entry.grid(row=google_row, column=1, padx=5, pady=5, sticky="ew")
        if help_btn := create_help_button(self.google_frame, "google", "apiEndpoint"): help_btn.grid(row=google_row, column=2, padx=(0, 5), pady=5, sticky="w")
        google_row += 1

        # Google 模型选择区域
        google_model_frame = ctk.CTkFrame(self.google_frame, fg_color="transparent")
        google_model_frame.grid(row=google_row, column=0, columnspan=3, padx=0, pady=(10, 5), sticky="ew")
        google_model_frame.grid_columnconfigure(1, weight=1)
        google_model_label = ctk.CTkLabel(google_model_frame, text="Google 模型:")
        google_model_label.grid(row=0, column=0, padx=(0, 5), pady=2, sticky="w")
        google_model_list_label = ctk.CTkLabel(google_model_frame, text="从列表选择:", font=("", 11))
        google_model_list_label.grid(row=1, column=0, padx=(0, 5), pady=2, sticky="w")
        self.google_model_combobox = ctk.CTkComboBox(google_model_frame, values=["点击下方按钮获取"], state="readonly", command=self._on_google_combo_select)
        self.google_model_combobox.grid(row=1, column=1, padx=5, pady=2, sticky="ew")
        google_model_manual_label = ctk.CTkLabel(google_model_frame, text="或手动输入:", font=("", 11))
        google_model_manual_label.grid(row=2, column=0, padx=(0, 5), pady=2, sticky="w")
        self.google_model_manual_var = StringVar()
        self.google_model_manual_entry = ctk.CTkEntry(google_model_frame, textvariable=self.google_model_manual_var, placeholder_text="手动输入将覆盖上方选择")
        self.google_model_manual_entry.grid(row=2, column=1, padx=5, pady=2, sticky="ew")
        self.google_model_manual_entry.bind("<KeyRelease>", self._on_google_manual_input)
        if help_btn := create_help_button(google_model_frame, "google", "modelName"): help_btn.grid(row=2, column=2, padx=(0, 5), pady=2, sticky="w") # Help for manual entry
        google_fetch_frame = ctk.CTkFrame(google_model_frame, fg_color="transparent")
        google_fetch_frame.grid(row=1, column=3, rowspan=2, padx=(10, 0), pady=5, sticky="w") # Adjusted column
        self.google_fetch_models_button = ctk.CTkButton(google_fetch_frame, text="测试连接\n& 获取模型", command=self.fetch_google_models)
        self.google_fetch_models_button.pack(pady=(0, 3))
        self.google_fetch_status_label = ctk.CTkLabel(google_fetch_frame, text="", text_color="gray", font=("", 10))
        self.google_fetch_status_label.pack()
        current_row += 1 # Google Frame 占一行

        # --- OpenAI 特定设置 Frame ---
        self.openai_frame = ctk.CTkFrame(master_frame, fg_color="transparent")
        self.openai_frame.grid(row=current_row, column=0, columnspan=3, padx=10, pady=5, sticky="ew") # columnspan=3
        self.openai_frame.grid_columnconfigure(1, weight=1)
        self.openai_frame.grid_columnconfigure(2, weight=0) # Help button column
        openai_row = 0

        openai_api_key_label = ctk.CTkLabel(self.openai_frame, text="OpenAI API Key:")
        openai_api_key_label.grid(row=openai_row, column=0, padx=0, pady=5, sticky="w")
        self.openai_api_key_var = StringVar()
        openai_api_key_entry = ctk.CTkEntry(self.openai_frame, textvariable=self.openai_api_key_var, show="*")
        openai_api_key_entry.grid(row=openai_row, column=1, padx=5, pady=5, sticky="ew")
        if help_btn := create_help_button(self.openai_frame, "openai", "apiKey"): help_btn.grid(row=openai_row, column=2, padx=(0, 5), pady=5, sticky="w")
        openai_row += 1

        openai_base_url_label = ctk.CTkLabel(self.openai_frame, text="OpenAI API Base URL:")
        openai_base_url_label.grid(row=openai_row, column=0, padx=0, pady=5, sticky="w")
        self.openai_api_base_url_var = StringVar()
        openai_base_url_entry = ctk.CTkEntry(self.openai_frame, textvariable=self.openai_api_base_url_var, placeholder_text="例如: https://api.openai.com/v1 或反代地址")
        openai_base_url_entry.grid(row=openai_row, column=1, padx=5, pady=5, sticky="ew")
        if help_btn := create_help_button(self.openai_frame, "openai", "apiBaseUrl"): help_btn.grid(row=openai_row, column=2, padx=(0, 5), pady=5, sticky="w")
        openai_row += 1

        # OpenAI 模型选择区域
        openai_model_frame = ctk.CTkFrame(self.openai_frame, fg_color="transparent")
        openai_model_frame.grid(row=openai_row, column=0, columnspan=3, padx=0, pady=(10, 5), sticky="ew")
        openai_model_frame.grid_columnconfigure(1, weight=1)
        openai_model_label = ctk.CTkLabel(openai_model_frame, text="OpenAI 模型:")
        openai_model_label.grid(row=0, column=0, padx=(0, 5), pady=2, sticky="w")
        openai_model_list_label = ctk.CTkLabel(openai_model_frame, text="从列表选择:", font=("", 11))
        openai_model_list_label.grid(row=1, column=0, padx=(0, 5), pady=2, sticky="w")
        self.openai_model_combobox = ctk.CTkComboBox(openai_model_frame, values=["点击下方按钮获取"], state="readonly", command=self._on_openai_combo_select)
        self.openai_model_combobox.grid(row=1, column=1, padx=5, pady=2, sticky="ew")
        openai_model_manual_label = ctk.CTkLabel(openai_model_frame, text="或手动输入:", font=("", 11))
        openai_model_manual_label.grid(row=2, column=0, padx=(0, 5), pady=2, sticky="w")
        self.openai_model_manual_var = StringVar()
        self.openai_model_manual_entry = ctk.CTkEntry(openai_model_frame, textvariable=self.openai_model_manual_var, placeholder_text="手动输入将覆盖上方选择")
        self.openai_model_manual_entry.grid(row=2, column=1, padx=5, pady=2, sticky="ew")
        self.openai_model_manual_entry.bind("<KeyRelease>", self._on_openai_manual_input)
        if help_btn := create_help_button(openai_model_frame, "openai", "modelName"): help_btn.grid(row=2, column=2, padx=(0, 5), pady=2, sticky="w") # Help for manual entry
        openai_fetch_frame = ctk.CTkFrame(openai_model_frame, fg_color="transparent")
        openai_fetch_frame.grid(row=1, column=3, rowspan=2, padx=(10, 0), pady=5, sticky="w") # Adjusted column
        self.openai_fetch_models_button = ctk.CTkButton(openai_fetch_frame, text="测试连接\n& 获取模型", command=self.fetch_openai_models)
        self.openai_fetch_models_button.pack(pady=(0, 3))
        self.openai_fetch_status_label = ctk.CTkLabel(openai_fetch_frame, text="", text_color="gray", font=("", 10))
        self.openai_fetch_status_label.pack()
        openai_row += 1

        # OpenAI 自定义 Headers
        openai_headers_label = ctk.CTkLabel(self.openai_frame, text="自定义 Headers (JSON):")
        openai_headers_label.grid(row=openai_row, column=0, padx=0, pady=(10, 5), sticky="nw")
        self.openai_custom_headers_textbox = ctk.CTkTextbox(self.openai_frame, height=60, wrap="word")
        self.openai_custom_headers_textbox.grid(row=openai_row, column=1, padx=5, pady=(10, 5), sticky="ew")
        if help_btn := create_help_button(self.openai_frame, "openai", "customHeaders"): help_btn.grid(row=openai_row, column=2, padx=(0, 5), pady=(10, 5), sticky="nw")
        openai_headers_hint = ctk.CTkLabel(self.openai_frame, text='用于反代认证等, 例如: {"X-Api-Password": "pass"}', font=("", 10), text_color="gray")
        openai_headers_hint.grid(row=openai_row+1, column=1, padx=5, pady=(0, 5), sticky="w")
        current_row += 1 # OpenAI Frame 占一行

        # --- 共享参数区域 ---
        shared_params_frame = ctk.CTkFrame(master_frame) # 加个边框
        shared_params_frame.grid(row=current_row, column=0, columnspan=3, padx=10, pady=10, sticky="ew") # columnspan=3
        shared_params_frame.grid_columnconfigure(1, weight=1) # 让输入框列扩展
        shared_params_frame.grid_columnconfigure(2, weight=0) # 帮助按钮列
        shared_row = 0

        shared_label = ctk.CTkLabel(shared_params_frame, text="共享生成参数", font=ctk.CTkFont(weight="bold"))
        shared_label.grid(row=shared_row, column=0, columnspan=3, padx=10, pady=(5, 10), sticky="w") # columnspan=3
        shared_row += 1

        # Temperature, Max Tokens, Top P, Top K in a sub-frame for better layout
        gen_param_frame = ctk.CTkFrame(shared_params_frame, fg_color="transparent")
        gen_param_frame.grid(row=shared_row, column=0, columnspan=3, pady=(0, 5), sticky="ew") # columnspan=3
        gen_param_frame.grid_columnconfigure((0, 2, 4, 6), weight=1) # Input columns expand
        gen_param_frame.grid_columnconfigure((1, 3, 5, 7), weight=0) # Help button columns
        # Temp
        temp_label = ctk.CTkLabel(gen_param_frame, text="Temperature:")
        temp_label.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="w")
        self.temperature_var = StringVar(value="0.2")
        temp_entry = ctk.CTkEntry(gen_param_frame, textvariable=self.temperature_var, width=60)
        temp_entry.grid(row=0, column=1, padx=0, pady=5, sticky="w")
        if help_btn := create_help_button(gen_param_frame, "llm_global", "temperature"): help_btn.grid(row=0, column=2, padx=(2, 10), pady=5, sticky="w")
        # Max Tokens
        max_tokens_label = ctk.CTkLabel(gen_param_frame, text="Max Tokens:")
        max_tokens_label.grid(row=0, column=3, padx=(10, 5), pady=5, sticky="w")
        self.max_tokens_var = StringVar(value="8192")
        max_tokens_entry = ctk.CTkEntry(gen_param_frame, textvariable=self.max_tokens_var, width=70)
        max_tokens_entry.grid(row=0, column=4, padx=0, pady=5, sticky="w")
        if help_btn := create_help_button(gen_param_frame, "llm_global", "maxOutputTokens"): help_btn.grid(row=0, column=5, padx=(2, 10), pady=5, sticky="w")
        # Top P
        top_p_label = ctk.CTkLabel(gen_param_frame, text="Top P:")
        top_p_label.grid(row=1, column=0, padx=(0, 5), pady=5, sticky="w")
        self.top_p_var = StringVar()
        top_p_entry = ctk.CTkEntry(gen_param_frame, textvariable=self.top_p_var, placeholder_text="0.0-1.0, 留空", width=60)
        top_p_entry.grid(row=1, column=1, padx=0, pady=5, sticky="w")
        if help_btn := create_help_button(gen_param_frame, "llm_global", "topP"): help_btn.grid(row=1, column=2, padx=(2, 10), pady=5, sticky="w")
        # Top K
        top_k_label = ctk.CTkLabel(gen_param_frame, text="Top K:")
        top_k_label.grid(row=1, column=3, padx=(10, 5), pady=5, sticky="w")
        self.top_k_var = StringVar()
        top_k_entry = ctk.CTkEntry(gen_param_frame, textvariable=self.top_k_var, placeholder_text=">=1, 留空", width=70)
        top_k_entry.grid(row=1, column=4, padx=0, pady=5, sticky="w")
        if help_btn := create_help_button(gen_param_frame, "llm_global", "topK"): help_btn.grid(row=1, column=5, padx=(2, 10), pady=5, sticky="w")
        shared_row += 1

        # 代理设置
        proxy_frame = ctk.CTkFrame(shared_params_frame, fg_color="transparent")
        proxy_frame.grid(row=shared_row, column=0, columnspan=3, padx=0, pady=5, sticky="ew") # columnspan=3
        proxy_frame.grid_columnconfigure(3, weight=1) # Address entry expands
        proxy_frame.grid_columnconfigure(7, weight=0) # Help button column for port
        self.use_proxy_var = BooleanVar()
        proxy_checkbox = ctk.CTkCheckBox(proxy_frame, text="使用代理访问 LLM?", variable=self.use_proxy_var, command=self.toggle_proxy_entries)
        proxy_checkbox.grid(row=0, column=0, padx=(10, 5), pady=5, sticky="w")
        if help_btn := create_help_button(proxy_frame, "llm_global", "use_proxy"): help_btn.grid(row=0, column=1, padx=(0, 10), pady=5, sticky="w")
        proxy_addr_label = ctk.CTkLabel(proxy_frame, text="地址:")
        proxy_addr_label.grid(row=0, column=2, padx=(10, 5), pady=5, sticky="w")
        self.proxy_address_var = StringVar()
        self.proxy_address_entry = ctk.CTkEntry(proxy_frame, textvariable=self.proxy_address_var, placeholder_text="例如: 127.0.0.1")
        self.proxy_address_entry.grid(row=0, column=3, padx=5, pady=5, sticky="ew")
        if help_btn := create_help_button(proxy_frame, "llm_global", "proxy_address"): help_btn.grid(row=0, column=4, padx=(0, 5), pady=5, sticky="w")
        proxy_port_label = ctk.CTkLabel(proxy_frame, text="端口:")
        proxy_port_label.grid(row=0, column=5, padx=(10, 5), pady=5, sticky="w")
        self.proxy_port_var = StringVar()
        self.proxy_port_entry = ctk.CTkEntry(proxy_frame, textvariable=self.proxy_port_var, placeholder_text="例如: 7890", width=80)
        self.proxy_port_entry.grid(row=0, column=6, padx=(0, 5), pady=5, sticky="w")
        if help_btn := create_help_button(proxy_frame, "llm_global", "proxy_port"): help_btn.grid(row=0, column=7, padx=(0, 10), pady=5, sticky="w")
        shared_row += 1

        # 全局指令
        pre_instr_label = ctk.CTkLabel(shared_params_frame, text="全局前置指令:")
        pre_instr_label.grid(row=shared_row, column=0, padx=10, pady=(10, 5), sticky="nw")
        self.pre_instruction_textbox = ctk.CTkTextbox(shared_params_frame, height=60, wrap="word")
        self.pre_instruction_textbox.grid(row=shared_row, column=1, padx=10, pady=(10, 5), sticky="ew")
        if help_btn := create_help_button(shared_params_frame, "llm_global", "preInstruction"): help_btn.grid(row=shared_row, column=2, padx=(0, 10), pady=(10, 5), sticky="nw")
        shared_row += 1
        post_instr_label = ctk.CTkLabel(shared_params_frame, text="全局后置指令:")
        post_instr_label.grid(row=shared_row, column=0, padx=10, pady=5, sticky="nw")
        self.post_instruction_textbox = ctk.CTkTextbox(shared_params_frame, height=60, wrap="word")
        self.post_instruction_textbox.grid(row=shared_row, column=1, padx=10, pady=5, sticky="ew")
        if help_btn := create_help_button(shared_params_frame, "llm_global", "postInstruction"): help_btn.grid(row=shared_row, column=2, padx=(0, 10), pady=5, sticky="nw")
        shared_row += 1

        # 提示音路径
        sound_frame = ctk.CTkFrame(shared_params_frame, fg_color="transparent")
        sound_frame.grid(row=shared_row, column=0, columnspan=3, pady=(10, 5), sticky="ew") # columnspan=3
        sound_frame.grid_columnconfigure((1, 4), weight=1) # Input columns expand
        sound_frame.grid_columnconfigure((2, 5), weight=0) # Help button columns
        success_sound_label = ctk.CTkLabel(sound_frame, text="成功提示音:")
        success_sound_label.grid(row=0, column=0, padx=(10,5), pady=5, sticky="w")
        self.success_sound_var = StringVar()
        success_sound_entry = ctk.CTkEntry(sound_frame, textvariable=self.success_sound_var, placeholder_text="例如: assets/success.wav")
        success_sound_entry.grid(row=0, column=1, padx=(0,5), pady=5, sticky="ew")
        if help_btn := create_help_button(sound_frame, "llm_global", "successSoundPath"): help_btn.grid(row=0, column=2, padx=(0, 10), pady=5, sticky="w")
        failure_sound_label = ctk.CTkLabel(sound_frame, text="失败提示音:")
        failure_sound_label.grid(row=0, column=3, padx=(10,5), pady=5, sticky="w")
        self.failure_sound_var = StringVar()
        failure_sound_entry = ctk.CTkEntry(sound_frame, textvariable=self.failure_sound_var, placeholder_text="例如: assets/failure.wav")
        failure_sound_entry.grid(row=0, column=4, padx=(0,5), pady=5, sticky="ew")
        if help_btn := create_help_button(sound_frame, "llm_global", "failureSoundPath"): help_btn.grid(row=0, column=5, padx=(0, 10), pady=5, sticky="w")
        shared_row += 1

        # 其他开关
        switch_frame = ctk.CTkFrame(shared_params_frame, fg_color="transparent")
        switch_frame.grid(row=shared_row, column=0, columnspan=3, pady=10, sticky="w", padx=10) # columnspan=3
        self.save_debug_var = BooleanVar() # LLM 调试开关
        save_debug_check = ctk.CTkCheckBox(switch_frame, text="保存 LLM 调试输入?", variable=self.save_debug_var)
        save_debug_check.pack(side="left", padx=(0, 5))
        if help_btn := create_help_button(switch_frame, "llm_global", "saveDebugInputs"): help_btn.pack(side="left", padx=(0, 20))
        self.enable_streaming_var = BooleanVar(value=True)
        streaming_checkbox = ctk.CTkCheckBox(switch_frame, text="启用 LLM 流式传输?", variable=self.enable_streaming_var)
        streaming_checkbox.pack(side="left", padx=(0, 5))
        if help_btn := create_help_button(switch_frame, "llm_global", "enableStreaming"): help_btn.pack(side="left", padx=(0, 20))
        current_row += 1 # 共享 Frame 占一行

        # 初始化代理输入框状态
        self.toggle_proxy_entries()
        # 根据初始提供商显示/隐藏 Frame
        self.on_provider_change(self.app.selected_llm_provider_var.get())

    def on_provider_change(self, selected_provider):
        """根据选择的提供商显示/隐藏特定设置区域"""
        if selected_provider == "Google":
            self.google_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=10, pady=5) # 调整行号
            self.openai_frame.grid_remove() # 隐藏 OpenAI Frame
        elif selected_provider == "OpenAI":
            self.google_frame.grid_remove() # 隐藏 Google Frame
            self.openai_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=10, pady=5) # 调整行号
        else: # 默认或未知情况，都隐藏
            self.google_frame.grid_remove()
            self.openai_frame.grid_remove()

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

    # --- Google 模型获取 ---
    def fetch_google_models(self):
        """按钮回调：启动后台线程获取 Google 模型列表"""
        if self.is_fetching_google_models: return
        api_key = self.google_api_key_var.get().strip()
        base_url = self.google_api_endpoint_var.get().strip()
        if not api_key or not base_url: messagebox.showerror("缺少信息", "请输入 Google API Key 和 Base URL！", parent=self); return
        proxy_config = {"use_proxy": self.use_proxy_var.get(), "proxy_address": self.proxy_address_var.get().strip(), "proxy_port": self.proxy_port_var.get().strip()}
        logger.info(f"准备获取 Google 模型列表: URL='{base_url}', Key=HIDDEN, Proxy={proxy_config.get('use_proxy')}") # 使用 logging
        self.is_fetching_google_models = True
        self.google_fetch_models_button.configure(state="disabled", text="获取中...")
        self.google_fetch_status_label.configure(text="正在请求...", text_color="orange")
        thread = threading.Thread(target=self._fetch_google_models_thread_target, args=(api_key, base_url, proxy_config), daemon=True); thread.start()

    def _fetch_google_models_thread_target(self, api_key, base_url, proxy_config):
        """后台线程实际执行获取 Google 模型列表的函数"""
        try:
            save_debug = self.app.get_global_llm_config().get("saveDebugInputs", False)
            model_list, error_message = self.app.api_helpers.get_google_models(api_key, base_url, proxy_config, save_debug=save_debug)
            self.google_model_fetch_queue.put((model_list, error_message))
        except Exception as e:
            error_msg = f"获取 Google 模型线程内部错误: {e}"
            logger.exception(error_msg) # 使用 logging
            self.google_model_fetch_queue.put((None, error_msg))

    def _check_google_model_fetch_queue(self):
        """定时检查 Google 模型获取结果队列并更新 UI"""
        try:
            model_list, error_message = self.google_model_fetch_queue.get_nowait()
            self.is_fetching_google_models = False
            self.google_fetch_models_button.configure(state="normal", text="测试连接\n& 获取模型")
            if error_message:
                self.google_fetch_status_label.configure(text=f"失败: {error_message[:30]}...", text_color="red")
                messagebox.showerror("获取模型失败", f"无法获取 Google 模型列表:\n{error_message}", parent=self)
            elif model_list:
                self.google_fetch_status_label.configure(text="获取成功!", text_color="green")
                self.google_model_combobox.configure(values=model_list, state="normal")
                current_manual = self.google_model_manual_var.get()
                saved_config_model = self.app.google_config.get("modelName")
                if current_manual and current_manual in model_list: self.google_model_combobox.set(current_manual)
                elif saved_config_model and saved_config_model in model_list: self.google_model_combobox.set(saved_config_model); self.google_model_manual_var.set("")
                elif model_list: self.google_model_combobox.set(model_list[0])
                logger.info(f"Google 模型列表已更新: {len(model_list)} 个模型。") # 使用 logging
                self._on_google_manual_input() # 更新 ComboBox 状态
            else:
                self.google_fetch_status_label.configure(text="成功但列表为空", text_color="orange")
                self.google_model_combobox.configure(values=["列表为空"], state="readonly"); self.google_model_combobox.set("列表为空")
            self.after(5000, lambda: self.google_fetch_status_label.configure(text=""))
        except Empty: pass
        except Exception as e:
            logger.exception(f"检查 Google 模型队列或更新 UI 时出错: {e}") # 使用 logging
            self.is_fetching_google_models = False; self.google_fetch_models_button.configure(state="normal", text="测试连接\n& 获取模型"); self.google_fetch_status_label.configure(text="UI 更新错误", text_color="red")
        finally: self.after(200, self._check_google_model_fetch_queue)

    def _on_google_manual_input(self, event=None):
        """当 Google 手动输入框内容改变时调用"""
        if self.google_model_manual_var.get().strip():
            self.google_model_combobox.configure(state="disabled", text_color="gray")
        else:
            if self.google_model_combobox.cget("values") and self.google_model_combobox.cget("values")[0] not in ["点击下方按钮获取", "获取失败", "列表为空"]:
                self.google_model_combobox.configure(state="normal", text_color=ctk.ThemeManager.theme["CTkLabel"]["text_color"])
            else:
                 self.google_model_combobox.configure(state="readonly", text_color=ctk.ThemeManager.theme["CTkLabel"]["text_color"])

    def _on_google_combo_select(self, choice):
        """当 Google ComboBox 被选择时调用"""
        self.google_model_manual_var.set("")
        self._on_google_manual_input()

    # --- OpenAI 模型获取 ---
    def fetch_openai_models(self):
        """按钮回调：启动后台线程获取 OpenAI 模型列表"""
        if self.is_fetching_openai_models: return
        api_key = self.openai_api_key_var.get().strip()
        base_url = self.openai_api_base_url_var.get().strip()
        custom_headers_str = self.openai_custom_headers_textbox.get("1.0", "end-1c").strip()
        if not api_key: messagebox.showerror("缺少信息", "请输入 OpenAI API Key！", parent=self); return
        if not base_url: base_url = OPENAI_API_BASE; self.openai_api_base_url_var.set(base_url)
        custom_headers = None
        if custom_headers_str:
            try: custom_headers = json.loads(custom_headers_str); assert isinstance(custom_headers, dict)
            except Exception as e: messagebox.showerror("格式错误", f"自定义 Headers 格式无效 (必须是 JSON 对象):\n{e}", parent=self); return
        proxy_config = {"use_proxy": self.use_proxy_var.get(), "proxy_address": self.proxy_address_var.get().strip(), "proxy_port": self.proxy_port_var.get().strip()}
        logger.info(f"准备获取 OpenAI 模型列表: URL='{base_url}', Key=HIDDEN, Headers={custom_headers}, Proxy={proxy_config.get('use_proxy')}") # 使用 logging
        self.is_fetching_openai_models = True
        self.openai_fetch_models_button.configure(state="disabled", text="获取中...")
        self.openai_fetch_status_label.configure(text="正在请求...", text_color="orange")
        thread = threading.Thread(target=self._fetch_openai_models_thread_target, args=(api_key, base_url, custom_headers, proxy_config), daemon=True); thread.start()

    def _fetch_openai_models_thread_target(self, api_key, base_url, custom_headers, proxy_config):
        """后台线程实际执行获取 OpenAI 模型列表的函数"""
        try:
            save_debug = self.app.get_global_llm_config().get("saveDebugInputs", False)
            model_list, error_message = self.app.api_helpers.get_openai_models(api_key, base_url, custom_headers, proxy_config, save_debug=save_debug)
            self.openai_model_fetch_queue.put((model_list, error_message))
        except Exception as e:
            error_msg = f"获取 OpenAI 模型线程内部错误: {e}"
            logger.exception(error_msg) # 使用 logging
            self.openai_model_fetch_queue.put((None, error_msg))

    def _check_openai_model_fetch_queue(self):
        """定时检查 OpenAI 模型获取结果队列并更新 UI"""
        try:
            model_list, error_message = self.openai_model_fetch_queue.get_nowait()
            self.is_fetching_openai_models = False
            self.openai_fetch_models_button.configure(state="normal", text="测试连接\n& 获取模型")
            if error_message:
                self.openai_fetch_status_label.configure(text=f"失败: {error_message[:30]}...", text_color="red")
                messagebox.showerror("获取模型失败", f"无法获取 OpenAI 模型列表:\n{error_message}", parent=self)
            elif model_list:
                self.openai_fetch_status_label.configure(text="获取成功!", text_color="green")
                self.openai_model_combobox.configure(values=model_list, state="normal")
                current_manual = self.openai_model_manual_var.get()
                saved_config_model = self.app.openai_config.get("modelName")
                if current_manual and current_manual in model_list: self.openai_model_combobox.set(current_manual)
                elif saved_config_model and saved_config_model in model_list: self.openai_model_combobox.set(saved_config_model); self.openai_model_manual_var.set("")
                elif model_list: self.openai_model_combobox.set(model_list[0])
                logger.info(f"OpenAI 模型列表已更新: {len(model_list)} 个模型。") # 使用 logging
                self._on_openai_manual_input() # 更新 ComboBox 状态
            else:
                self.openai_fetch_status_label.configure(text="成功但列表为空", text_color="orange")
                self.openai_model_combobox.configure(values=["列表为空"], state="readonly"); self.openai_model_combobox.set("列表为空")
            self.after(5000, lambda: self.openai_fetch_status_label.configure(text=""))
        except Empty: pass
        except Exception as e:
            logger.exception(f"检查 OpenAI 模型队列或更新 UI 时出错: {e}") # 使用 logging
            self.is_fetching_openai_models = False; self.openai_fetch_models_button.configure(state="normal", text="测试连接\n& 获取模型"); self.openai_fetch_status_label.configure(text="UI 更新错误", text_color="red")
        finally: self.after(210, self._check_openai_model_fetch_queue) # 继续检查

    def _on_openai_manual_input(self, event=None):
        """当 OpenAI 手动输入框内容改变时调用"""
        if self.openai_model_manual_var.get().strip():
            self.openai_model_combobox.configure(state="disabled", text_color="gray")
        else:
            if self.openai_model_combobox.cget("values") and self.openai_model_combobox.cget("values")[0] not in ["点击下方按钮获取", "获取失败", "列表为空"]:
                self.openai_model_combobox.configure(state="normal", text_color=ctk.ThemeManager.theme["CTkLabel"]["text_color"])
            else:
                 self.openai_model_combobox.configure(state="readonly", text_color=ctk.ThemeManager.theme["CTkLabel"]["text_color"])

    def _on_openai_combo_select(self, choice):
        """当 OpenAI ComboBox 被选择时调用"""
        self.openai_model_manual_var.set("")
        self._on_openai_manual_input()

    # --- 配置加载与获取 ---
    def load_initial_config(self):
        """加载所有 LLM 相关配置到 UI"""
        logger.info("正在加载 LLM 设置到 UI...") # 使用 logging
        global_config = self.app.llm_global_config
        google_config = self.app.google_config
        openai_config = self.app.openai_config

        # 加载 Google 特定配置
        self.google_api_key_var.set(google_config.get("apiKey", ""))
        self.google_api_endpoint_var.set(google_config.get("apiEndpoint", GOOGLE_API_BASE))
        self.google_model_manual_var.set(google_config.get("modelName", "gemini-1.5-flash-latest"))
        self._on_google_manual_input()

        # 加载 OpenAI 特定配置
        self.openai_api_key_var.set(openai_config.get("apiKey", ""))
        self.openai_api_base_url_var.set(openai_config.get("apiBaseUrl", OPENAI_API_BASE))
        self.openai_model_manual_var.set(openai_config.get("modelName", "gpt-4o"))
        try:
            headers_str = json.dumps(openai_config.get("customHeaders", {}), indent=4, ensure_ascii=False) if openai_config.get("customHeaders") else ""
            if hasattr(self, 'openai_custom_headers_textbox') and self.openai_custom_headers_textbox.winfo_exists():
                self.openai_custom_headers_textbox.delete("1.0", "end"); self.openai_custom_headers_textbox.insert("1.0", headers_str)
        except Exception as e:
            logger.error(f"加载 OpenAI 自定义 Headers 到 UI 时出错: {e}") # 使用 logging
        self._on_openai_manual_input()

        # 加载共享配置
        self.temperature_var.set(str(global_config.get("temperature", 0.2)))
        self.max_tokens_var.set(str(global_config.get("maxOutputTokens", 8192)))
        self.top_p_var.set(str(global_config.get("topP")) if global_config.get("topP") is not None else "")
        self.top_k_var.set(str(global_config.get("topK")) if global_config.get("topK") is not None else "")
        self.use_proxy_var.set(bool(global_config.get("use_proxy", False)))
        self.proxy_address_var.set(global_config.get("proxy_address", ""))
        self.proxy_port_var.set(str(global_config.get("proxy_port", "")))
        try:
            if hasattr(self, 'pre_instruction_textbox') and self.pre_instruction_textbox.winfo_exists(): self.pre_instruction_textbox.delete("1.0", "end"); self.pre_instruction_textbox.insert("1.0", global_config.get("preInstruction", ""))
            if hasattr(self, 'post_instruction_textbox') and self.post_instruction_textbox.winfo_exists(): self.post_instruction_textbox.delete("1.0", "end"); self.post_instruction_textbox.insert("1.0", global_config.get("postInstruction", ""))
        except Exception as e:
            logger.error(f"[LLM Tab] 更新指令文本框时出错: {e}") # 使用 logging
        self.success_sound_var.set(global_config.get("successSoundPath", "assets/success.wav")) # 提供默认值
        self.failure_sound_var.set(global_config.get("failureSoundPath", "assets/failure.wav")) # 提供默认值
        self.save_debug_var.set(bool(global_config.get("saveDebugInputs", False))) # 加载 LLM 调试开关状态
        self.enable_streaming_var.set(bool(global_config.get("enableStreaming", True)))

        self.toggle_proxy_entries()
        self.on_provider_change(self.app.selected_llm_provider_var.get())
        logger.info("[LLM Tab] 配置加载完成。") # 使用 logging

    def get_config_data(self):
        """收集当前的 LLM 配置数据 (包括共享和特定提供商)"""
        logger.info("[LLM Tab] 正在从 UI 收集配置数据...") # 使用 logging

        # --- 收集 Google 特定配置 ---
        google_manual_model = self.google_model_manual_var.get().strip()
        google_selected_model = self.google_model_combobox.get()
        google_final_model = google_manual_model if google_manual_model else google_selected_model
        if google_final_model in ["点击下方按钮获取", "获取失败", "列表为空"]: google_final_model = self.app.google_config.get("modelName", "gemini-1.5-flash-latest")
        google_config_data = { "apiKey": self.google_api_key_var.get().strip(), "apiEndpoint": self.google_api_endpoint_var.get().strip().rstrip('/'), "modelName": google_final_model, }

        # --- 收集 OpenAI 特定配置 ---
        openai_manual_model = self.openai_model_manual_var.get().strip()
        openai_selected_model = self.openai_model_combobox.get()
        openai_final_model = openai_manual_model if openai_manual_model else openai_selected_model
        if openai_final_model in ["点击下方按钮获取", "获取失败", "列表为空"]: openai_final_model = self.app.openai_config.get("modelName", "gpt-4o")
        openai_custom_headers = {}
        headers_str = self.openai_custom_headers_textbox.get("1.0", "end-1c").strip()
        if headers_str:
            try: openai_custom_headers = json.loads(headers_str); assert isinstance(openai_custom_headers, dict)
            except Exception as e: messagebox.showerror("格式错误", f"自定义 Headers 格式无效，将视为空对象:\n{e}", parent=self); openai_custom_headers = {}
        openai_config_data = { "apiKey": self.openai_api_key_var.get().strip(), "apiBaseUrl": self.openai_api_base_url_var.get().strip().rstrip('/'), "modelName": openai_final_model, "customHeaders": openai_custom_headers }

        # --- 收集共享配置 ---
        pre_instruction = ""; post_instruction = ""
        try:
            if hasattr(self, 'pre_instruction_textbox') and self.pre_instruction_textbox.winfo_exists(): pre_instruction = self.pre_instruction_textbox.get("1.0", "end-1c").strip()
            if hasattr(self, 'post_instruction_textbox') and self.post_instruction_textbox.winfo_exists(): post_instruction = self.post_instruction_textbox.get("1.0", "end-1c").strip()
        except Exception as e:
            logger.error(f"[LLM Tab] 获取指令文本时出错: {e}") # 使用 logging

        temperature = None; temp_str = self.temperature_var.get().strip()
        if temp_str:
            try:
                temperature = float(temp_str)
                assert 0.0 <= temperature <= 2.0
            except:
                logger.warning(f"警告: 无效 Temperature '{temp_str}'") # 使用 logging
                messagebox.showwarning("输入错误", f"Temperature 值 '{temp_str}' 不是 0.0 到 2.0 之间的有效数字。", parent=self)
                temperature = None # 使用 None 表示无效

        max_tokens = None; max_tokens_str = self.max_tokens_var.get().strip()
        if max_tokens_str:
            try:
                max_tokens = int(max_tokens_str)
                assert max_tokens >= 1
            except:
                logger.warning(f"警告: 无效 Max Tokens '{max_tokens_str}'") # 使用 logging
                messagebox.showwarning("输入错误", f"Max Tokens 值 '{max_tokens_str}' 不是有效的正整数。", parent=self)
                max_tokens = None

        top_p = None; top_p_str = self.top_p_var.get().strip()
        if top_p_str:
            try:
                top_p = float(top_p_str)
                assert 0.0 <= top_p <= 1.0
            except:
                logger.warning(f"警告: 无效 Top P '{top_p_str}'") # 使用 logging
                messagebox.showwarning("输入错误", f"Top P 值 '{top_p_str}' 不是 0.0 到 1.0 之间的有效数字。", parent=self)
                top_p = None

        top_k = None; top_k_str = self.top_k_var.get().strip()
        if top_k_str:
            try:
                top_k = int(top_k_str)
                assert top_k >= 1
            except:
                logger.warning(f"警告: 无效 Top K '{top_k_str}'") # 使用 logging
                messagebox.showwarning("输入错误", f"Top K 值 '{top_k_str}' 不是有效的正整数。", parent=self)
                top_k = None

        proxy_port_validated = ""; proxy_port_str = self.proxy_port_var.get().strip()
        if self.use_proxy_var.get() and proxy_port_str:
            try:
                port_num = int(proxy_port_str)
                assert 1 <= port_num <= 65535
                proxy_port_validated = proxy_port_str
            except:
                logger.error(f"错误: 无效 LLM 代理端口 '{proxy_port_str}'") # 使用 logging
                messagebox.showwarning("输入错误", f"LLM 代理端口号 '{proxy_port_str}' 无效 (必须是 1-65535)。", parent=self)
                # 保留空字符串表示无效

        shared_config_data = {
            "temperature": temperature, "maxOutputTokens": max_tokens, "topP": top_p, "topK": top_k,
            "preInstruction": pre_instruction, "postInstruction": post_instruction,
            "successSoundPath": self.success_sound_var.get(), "failureSoundPath": self.failure_sound_var.get(),
            "saveDebugInputs": self.save_debug_var.get(), # 收集 LLM 调试开关状态
            "enableStreaming": self.enable_streaming_var.get(),
            "use_proxy": self.use_proxy_var.get(), "proxy_address": self.proxy_address_var.get().strip(), "proxy_port": proxy_port_validated,
        }

        combined_data = { "shared": shared_config_data, "google": google_config_data, "openai": openai_config_data }
        logger.info("[LLM Tab] 配置数据收集完成。") # 使用 logging
        return combined_data