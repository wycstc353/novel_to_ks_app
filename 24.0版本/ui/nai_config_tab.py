# ui/nai_config_tab.py
import customtkinter as ctk
from tkinter import StringVar, IntVar, DoubleVar, BooleanVar, messagebox, filedialog
import os
import traceback # 保留用于错误处理
from customtkinter import CTkFont # 导入 CTkFont
import logging # 导入日志模块
import random # 功能性备注: 导入 random 模块用于生成随机种子
# 导入 UI 辅助函数
from .ui_helpers import create_help_button

# 获取当前模块的 logger 实例
logger = logging.getLogger(__name__)

class NAIConfigTab(ctk.CTkFrame):
    """NAI API 设置（包括代理和新增参数）的 UI 标签页"""
    def __init__(self, master, config_manager, app_instance):
        super().__init__(master, fg_color="transparent")
        self.config_manager = config_manager
        self.app = app_instance
        self.nai_models = self.config_manager.load_nai_models() # 加载 NAI 模型列表
        # 创建模型名称到值、值到名称的映射字典
        self._model_name_to_value = {m['name']: m['value'] for m in self.nai_models}
        self._model_value_to_name = {m['value']: m['name'] for m in self.nai_models}
        # 创建负面预设值到名称、名称到值的映射字典
        self._uc_preset_map = {0: "Heavy", 1: "Light", 2: "Human Focus", 3: "None"}
        self._uc_preset_name_to_value = {v: k for k, v in self._uc_preset_map.items()}

        # --- 功能性备注: 添加 NAI 随机种子变量 ---
        self.nai_random_seed_var = BooleanVar(value=False)
        # 功能性备注: 获取默认文本颜色
        self._default_text_color = ctk.ThemeManager.theme["CTkEntry"]["text_color"]

        # --- 创建主滚动框架 ---
        self.scrollable_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scrollable_frame.pack(expand=True, fill="both")

        # --- 将所有 UI 元素放入滚动框架内 ---
        self.build_ui_within_scrollable_frame(self.scrollable_frame)
        self.load_initial_config() # 加载初始配置

    def build_ui_within_scrollable_frame(self, master_frame):
        """在指定的父框架（滚动框架）内构建 UI 元素"""
        # 配置网格布局
        master_frame.grid_columnconfigure(1, weight=1) # 输入框列
        master_frame.grid_columnconfigure(2, weight=0) # 浏览/帮助按钮列
        master_frame.grid_columnconfigure(3, weight=0) # 仅用于 API Key 的帮助按钮
        row = 0 # 当前行号

        # --- 顶部提示文字 ---
        warning_text = "每次修改后要点击保存所有设置，不然修改不起效。"
        warning_textbox = ctk.CTkTextbox(
            master_frame, wrap="word", height=25, activate_scrollbars=False,
            border_width=1, border_color="orange", corner_radius=5,
            font=CTkFont(size=12), fg_color="transparent"
        )
        warning_textbox.grid(row=row, column=0, columnspan=4, padx=10, pady=(10, 5), sticky="ew")
        warning_textbox.insert("1.0", warning_text)
        warning_textbox.configure(state="disabled")
        row += 1

        # --- NAI API Key ---
        api_key_label = ctk.CTkLabel(master_frame, text="NAI API Key:")
        api_key_label.grid(row=row, column=0, padx=10, pady=5, sticky="w")
        self.api_key_var = StringVar()
        api_key_entry = ctk.CTkEntry(master_frame, textvariable=self.api_key_var, show="*")
        api_key_entry.grid(row=row, column=1, padx=10, pady=5, sticky="ew")
        api_key_entry.bind("<FocusOut>", self.trigger_workflow_button_update) # 绑定失去焦点事件
        if help_btn := create_help_button(master_frame, "nai", "naiApiKey"): help_btn.grid(row=row, column=2, padx=(0, 5), pady=5, sticky="w")

        # --- 图片保存目录 ---
        row += 1
        save_dir_label = ctk.CTkLabel(master_frame, text="图片保存目录:")
        save_dir_label.grid(row=row, column=0, padx=10, pady=5, sticky="w")
        self.save_dir_var = StringVar()
        dir_entry = ctk.CTkEntry(master_frame, textvariable=self.save_dir_var, placeholder_text="应用可访问的完整目录路径")
        dir_entry.grid(row=row, column=1, padx=(10, 0), pady=5, sticky="ew")
        dir_entry.bind("<FocusOut>", self.trigger_workflow_button_update) # 绑定失去焦点事件
        button_frame_dir = ctk.CTkFrame(master_frame, fg_color="transparent")
        button_frame_dir.grid(row=row, column=2, columnspan=2, padx=(5, 10), pady=5, sticky="w")
        browse_button = ctk.CTkButton(button_frame_dir, text="浏览...", width=60, command=self.browse_save_directory) # 浏览目录按钮
        browse_button.pack(side="left", padx=0)
        if help_btn := create_help_button(button_frame_dir, "nai", "naiImageSaveDir"): help_btn.pack(side="left", padx=(5, 0))

        # --- NAI 代理设置 ---
        row += 1
        nai_proxy_frame = ctk.CTkFrame(master_frame, fg_color="transparent")
        nai_proxy_frame.grid(row=row, column=0, columnspan=4, padx=10, pady=(10, 0), sticky="ew")
        nai_proxy_frame.grid_columnconfigure(3, weight=1) # 地址输入框列扩展
        nai_proxy_frame.grid_columnconfigure(6, weight=0) # Help button column
        self.nai_use_proxy_var = BooleanVar()
        nai_proxy_checkbox = ctk.CTkCheckBox(nai_proxy_frame, text="使用代理访问 NAI API?", variable=self.nai_use_proxy_var, command=self.toggle_nai_proxy_entries) # 代理开关
        nai_proxy_checkbox.grid(row=0, column=0, padx=(0, 5), pady=10, sticky="w")
        if help_btn := create_help_button(nai_proxy_frame, "nai", "nai_use_proxy"): help_btn.grid(row=0, column=1, padx=(0, 10), pady=10, sticky="w")
        nai_proxy_addr_label = ctk.CTkLabel(nai_proxy_frame, text="地址:")
        nai_proxy_addr_label.grid(row=0, column=2, padx=(10, 5), pady=10, sticky="w")
        self.nai_proxy_address_var = StringVar()
        self.nai_proxy_address_entry = ctk.CTkEntry(nai_proxy_frame, textvariable=self.nai_proxy_address_var, placeholder_text="例如: 127.0.0.1") # 代理地址输入
        self.nai_proxy_address_entry.grid(row=0, column=3, padx=5, pady=10, sticky="ew")
        if help_btn := create_help_button(nai_proxy_frame, "nai", "nai_proxy_address"): help_btn.grid(row=0, column=4, padx=(0, 5), pady=10, sticky="w")
        nai_proxy_port_label = ctk.CTkLabel(nai_proxy_frame, text="端口:")
        nai_proxy_port_label.grid(row=0, column=5, padx=(10, 5), pady=10, sticky="w")
        self.nai_proxy_port_var = StringVar()
        self.nai_proxy_port_entry = ctk.CTkEntry(nai_proxy_frame, textvariable=self.nai_proxy_port_var, placeholder_text="例如: 7890", width=80) # 代理端口输入
        self.nai_proxy_port_entry.grid(row=0, column=6, padx=(0, 5), pady=10, sticky="w")
        if help_btn := create_help_button(nai_proxy_frame, "nai", "nai_proxy_port"): help_btn.grid(row=0, column=7, padx=(0, 10), pady=10, sticky="w")

        # --- NAI 生成参数 (第一行) ---
        row += 1
        param_frame1 = ctk.CTkFrame(master_frame, fg_color="transparent")
        param_frame1.grid(row=row, column=0, columnspan=4, sticky="ew", padx=5, pady=(5, 0))
        param_frame1.grid_columnconfigure((0, 2, 4, 6), weight=1, uniform="group_nai_params1") # Param columns
        param_frame1.grid_columnconfigure((1, 3, 5, 7), weight=0) # Help button columns
        col1 = 0; row_param1 = 0
        # 模型
        model_label = ctk.CTkLabel(param_frame1, text="模型:")
        model_label.grid(row=row_param1, column=col1, padx=5, pady=2, sticky="w")
        model_options = [m['name'] for m in self.nai_models] if self.nai_models else ["未加载模型列表"] # 模型选项列表
        self.model_display_var = StringVar(value=model_options[0] if model_options else "")
        self.model_combobox = ctk.CTkComboBox(param_frame1, values=model_options, variable=self.model_display_var) # 模型选择框
        self.model_combobox.grid(row=row_param1+1, column=col1, padx=5, pady=2, sticky="ew")
        if not self.nai_models: self.model_combobox.configure(state="disabled") # 如果没加载到模型则禁用
        if help_btn := create_help_button(param_frame1, "nai", "naiModel"): help_btn.grid(row=row_param1+1, column=col1+1, padx=(2, 5), pady=2, sticky="w")
        col1 += 2
        # 采样器
        sampler_label = ctk.CTkLabel(param_frame1, text="采样器:")
        sampler_label.grid(row=row_param1, column=col1, padx=5, pady=2, sticky="w")
        self.sampler_var = StringVar(value="k_euler")
        sampler_options = ["k_euler", "k_euler_ancestral", "k_dpmpp_2s_ancestral", "k_dpmpp_2m", "k_dpmpp_sde", "ddim"] # 采样器选项
        sampler_combo = ctk.CTkComboBox(param_frame1, values=sampler_options, variable=self.sampler_var) # 采样器选择框
        sampler_combo.grid(row=row_param1+1, column=col1, padx=5, pady=2, sticky="ew")
        if help_btn := create_help_button(param_frame1, "nai", "naiSampler"): help_btn.grid(row=row_param1+1, column=col1+1, padx=(2, 5), pady=2, sticky="w")
        col1 += 2
        # 步数
        steps_label = ctk.CTkLabel(param_frame1, text="步数:")
        steps_label.grid(row=row_param1, column=col1, padx=5, pady=2, sticky="w")
        self.steps_var = IntVar(value=28)
        steps_entry = ctk.CTkEntry(param_frame1, textvariable=self.steps_var) # 步数输入
        steps_entry.grid(row=row_param1+1, column=col1, padx=5, pady=2, sticky="ew")
        if help_btn := create_help_button(param_frame1, "nai", "naiSteps"): help_btn.grid(row=row_param1+1, column=col1+1, padx=(2, 5), pady=2, sticky="w")
        col1 += 2
        # 引导强度
        scale_label = ctk.CTkLabel(param_frame1, text="引导强度:")
        scale_label.grid(row=row_param1, column=col1, padx=5, pady=2, sticky="w")
        self.scale_var = DoubleVar(value=7.0)
        scale_entry = ctk.CTkEntry(param_frame1, textvariable=self.scale_var) # 引导强度输入
        scale_entry.grid(row=row_param1+1, column=col1, padx=5, pady=2, sticky="ew")
        if help_btn := create_help_button(param_frame1, "nai", "naiScale"): help_btn.grid(row=row_param1+1, column=col1+1, padx=(2, 5), pady=2, sticky="w")

        # --- NAI 生成参数 (第二行) ---
        row += 1
        param_frame2 = ctk.CTkFrame(master_frame, fg_color="transparent")
        param_frame2.grid(row=row, column=0, columnspan=4, sticky="ew", padx=5, pady=(0, 0))
        param_frame2.grid_columnconfigure((0, 2, 4, 6), weight=1, uniform="group_nai_params2") # Param columns
        param_frame2.grid_columnconfigure((1, 3, 5, 7), weight=0) # Help button columns
        col2 = 0; row_param2 = 0
        # 种子
        seed_label = ctk.CTkLabel(param_frame2, text="种子 (-1随机):")
        seed_label.grid(row=row_param2, column=col2, padx=5, pady=2, sticky="w")
        # 功能性备注: 使用内部 Frame 组合种子输入和随机开关
        nai_seed_frame = ctk.CTkFrame(param_frame2, fg_color="transparent")
        nai_seed_frame.grid(row=row_param2+1, column=col2, columnspan=2, padx=5, pady=2, sticky="ew")
        nai_seed_frame.grid_columnconfigure(0, weight=1) # 输入框扩展
        self.seed_var = IntVar(value=-1)
        self.nai_seed_entry = ctk.CTkEntry(nai_seed_frame, textvariable=self.seed_var) # 种子输入
        self.nai_seed_entry.grid(row=0, column=0, padx=(0, 5), pady=0, sticky="ew")
        if help_btn := create_help_button(nai_seed_frame, "nai", "naiSeed"): help_btn.grid(row=0, column=1, padx=(0, 5), pady=0, sticky="w")
        self.nai_random_seed_check = ctk.CTkCheckBox(nai_seed_frame, text="随机", variable=self.nai_random_seed_var, command=self._toggle_nai_seed_entry) # 随机种子开关
        self.nai_random_seed_check.grid(row=0, column=2, padx=(5, 0), pady=0, sticky="w")
        if help_btn := create_help_button(nai_seed_frame, "nai", "naiRandomSeed"): help_btn.grid(row=0, column=3, padx=(2, 0), pady=0, sticky="w")
        col2 += 2 # 种子部分占两列
        # 负面预设
        uc_label = ctk.CTkLabel(param_frame2, text="负面预设:")
        uc_label.grid(row=row_param2, column=col2, padx=5, pady=2, sticky="w")
        uc_preset_options = list(self._uc_preset_map.values()) # 负面预设选项
        self.uc_preset_display_var = StringVar(value=uc_preset_options[0] if uc_preset_options else "")
        uc_combo = ctk.CTkComboBox(param_frame2, values=uc_preset_options, variable=self.uc_preset_display_var) # 负面预设选择框
        uc_combo.grid(row=row_param2+1, column=col2, padx=5, pady=2, sticky="ew")
        if help_btn := create_help_button(param_frame2, "nai", "naiUcPreset"): help_btn.grid(row=row_param2+1, column=col2+1, padx=(2, 5), pady=2, sticky="w")
        col2 += 2
        # 负面强度
        uncond_scale_label = ctk.CTkLabel(param_frame2, text="负面强度:")
        uncond_scale_label.grid(row=row_param2, column=col2, padx=5, pady=2, sticky="w")
        self.uncond_scale_var = DoubleVar(value=1.0)
        uncond_scale_entry = ctk.CTkEntry(param_frame2, textvariable=self.uncond_scale_var) # 负面强度输入
        uncond_scale_entry.grid(row=row_param2+1, column=col2, padx=5, pady=2, sticky="ew")
        if help_btn := create_help_button(param_frame2, "nai", "naiUncondScale"): help_btn.grid(row=row_param2+1, column=col2+1, padx=(2, 5), pady=2, sticky="w")
        col2 += 2
        # 质量标签
        quality_label = ctk.CTkLabel(param_frame2, text="质量标签:")
        quality_label.grid(row=row_param2, column=col2, padx=5, pady=2, sticky="w")
        self.quality_toggle_var = BooleanVar(value=True)
        quality_check = ctk.CTkCheckBox(param_frame2, text="", variable=self.quality_toggle_var) # 质量标签开关
        quality_check.grid(row=row_param2+1, column=col2, padx=5, pady=2, sticky="w")
        if help_btn := create_help_button(param_frame2, "nai", "naiQualityToggle"): help_btn.grid(row=row_param2+1, column=col2+1, padx=(2, 5), pady=2, sticky="w")

        # --- NAI 生成参数 (第三行 - 开关) ---
        row += 1
        param_frame3 = ctk.CTkFrame(master_frame, fg_color="transparent")
        param_frame3.grid(row=row, column=0, columnspan=4, sticky="ew", padx=5, pady=(0, 0))
        # SMEA
        self.smea_var = BooleanVar()
        smea_check = ctk.CTkCheckBox(param_frame3, text="SMEA", variable=self.smea_var) # SMEA 开关
        smea_check.grid(row=0, column=0, padx=(5, 0), pady=5, sticky="w")
        if help_btn := create_help_button(param_frame3, "nai", "naiSmea"): help_btn.grid(row=0, column=1, padx=(2, 10), pady=5, sticky="w")
        # SMEA DYN
        self.smea_dyn_var = BooleanVar()
        smea_dyn_check = ctk.CTkCheckBox(param_frame3, text="SMEA DYN", variable=self.smea_dyn_var) # SMEA DYN 开关
        smea_dyn_check.grid(row=0, column=2, padx=(10, 0), pady=5, sticky="w")
        if help_btn := create_help_button(param_frame3, "nai", "naiSmeaDyn"): help_btn.grid(row=0, column=3, padx=(2, 10), pady=5, sticky="w")
        # Dynamic Thresholding
        self.dyn_thresh_var = BooleanVar()
        dyn_thresh_check = ctk.CTkCheckBox(param_frame3, text="动态阈值", variable=self.dyn_thresh_var) # 动态阈值开关
        dyn_thresh_check.grid(row=0, column=4, padx=(10, 0), pady=5, sticky="w")
        if help_btn := create_help_button(param_frame3, "nai", "naiDynamicThresholding"): help_btn.grid(row=0, column=5, padx=(2, 10), pady=5, sticky="w")

        # --- NAI 生成参数 (第四行 - 图生图) ---
        row += 1
        param_frame4 = ctk.CTkFrame(master_frame, fg_color="transparent")
        param_frame4.grid(row=row, column=0, columnspan=4, sticky="ew", padx=5, pady=(0, 0))
        param_frame4.grid_columnconfigure((0, 2, 4), weight=1, uniform="group_nai_params4") # Param columns
        param_frame4.grid_columnconfigure((1, 3, 5), weight=0) # Help button columns
        col4 = 0; row_param4 = 0
        img2img_header = ctk.CTkLabel(param_frame4, text="图生图 / 变体参数:")
        img2img_header.grid(row=row_param4, column=0, columnspan=6, pady=(5,2), sticky="w")
        row_param4 += 1
        # 参考强度
        ref_strength_label = ctk.CTkLabel(param_frame4, text="参考强度:")
        ref_strength_label.grid(row=row_param4, column=col4, padx=5, pady=2, sticky="w")
        self.ref_strength_var = DoubleVar(value=0.6)
        ref_strength_entry = ctk.CTkEntry(param_frame4, textvariable=self.ref_strength_var) # 参考强度输入
        ref_strength_entry.grid(row=row_param4+1, column=col4, padx=5, pady=2, sticky="ew")
        if help_btn := create_help_button(param_frame4, "nai", "naiReferenceStrength"): help_btn.grid(row=row_param4+1, column=col4+1, padx=(2, 5), pady=2, sticky="w")
        col4 += 2
        # 参考信息提取
        ref_info_label = ctk.CTkLabel(param_frame4, text="信息提取:")
        ref_info_label.grid(row=row_param4, column=col4, padx=5, pady=2, sticky="w")
        self.ref_info_var = DoubleVar(value=0.7)
        ref_info_entry = ctk.CTkEntry(param_frame4, textvariable=self.ref_info_var) # 信息提取输入
        ref_info_entry.grid(row=row_param4+1, column=col4, padx=5, pady=2, sticky="ew")
        if help_btn := create_help_button(param_frame4, "nai", "naiReferenceInfoExtracted"): help_btn.grid(row=row_param4+1, column=col4+1, padx=(2, 5), pady=2, sticky="w")
        col4 += 2
        # 添加原图 (变体)
        add_orig_label = ctk.CTkLabel(param_frame4, text="添加原图(变体):")
        add_orig_label.grid(row=row_param4, column=col4, padx=5, pady=2, sticky="w")
        self.add_orig_var = BooleanVar(value=True)
        add_orig_check = ctk.CTkCheckBox(param_frame4, text="", variable=self.add_orig_var) # 添加原图开关
        add_orig_check.grid(row=row_param4+1, column=col4, padx=5, pady=2, sticky="w")
        if help_btn := create_help_button(param_frame4, "nai", "naiAddOriginalImage"): help_btn.grid(row=row_param4+1, column=col4+1, padx=(2, 5), pady=2, sticky="w")

        # --- NAI 调试开关 ---
        row += 1
        debug_frame = ctk.CTkFrame(master_frame, fg_color="transparent")
        debug_frame.grid(row=row, column=0, columnspan=4, pady=(10, 5), sticky="w", padx=10)
        self.save_nai_debug_var = BooleanVar()
        save_nai_debug_check = ctk.CTkCheckBox(debug_frame, text="保存 NAI 调试输入?", variable=self.save_nai_debug_var) # NAI 调试开关
        save_nai_debug_check.pack(side="left", padx=(0, 5))
        if help_btn := create_help_button(debug_frame, "nai", "saveNaiDebugInputs"): help_btn.pack(side="left", padx=(0, 20))

        # 初始化代理输入框状态
        self.toggle_nai_proxy_entries()
        # 功能性备注: 初始化 NAI 种子输入框状态
        self._toggle_nai_seed_entry()

    # 功能性备注: 添加切换 NAI 种子输入框状态的方法
    def _toggle_nai_seed_entry(self):
        """根据 NAI 随机种子复选框状态切换种子输入框的启用/禁用"""
        is_random = self.nai_random_seed_var.get()
        new_state = "disabled" if is_random else "normal"
        if hasattr(self, 'nai_seed_entry') and self.nai_seed_entry.winfo_exists():
            self.nai_seed_entry.configure(state=new_state)
            if is_random:
                self.nai_seed_entry.configure(text_color="gray") # 禁用时变灰
            else:
                self.nai_seed_entry.configure(text_color=self._default_text_color) # 启用时恢复默认颜色

    def browse_save_directory(self):
        """打开目录选择对话框"""
        directory = filedialog.askdirectory(title="选择 NAI 图片保存目录", parent=self)
        if directory:
            self.save_dir_var.set(directory)
            logger.info(f"NAI 图片保存目录已设置为: {directory}") # 使用 logging
            self.trigger_workflow_button_update() # 更新按钮状态
        else:
            logger.info("用户取消选择目录。") # 使用 logging

    def toggle_nai_proxy_entries(self):
        """切换 NAI 代理输入框状态"""
        use_proxy = self.nai_use_proxy_var.get()
        new_state = "normal" if use_proxy else "disabled"
        # 安全地更新控件状态
        if hasattr(self, 'nai_proxy_address_entry') and self.nai_proxy_address_entry.winfo_exists():
             self.nai_proxy_address_entry.configure(state=new_state)
             if not use_proxy: self.nai_proxy_address_var.set("") # 禁用时清空
        if hasattr(self, 'nai_proxy_port_entry') and self.nai_proxy_port_entry.winfo_exists():
             self.nai_proxy_port_entry.configure(state=new_state)
             if not use_proxy: self.nai_proxy_port_var.set("") # 禁用时清空

    def load_initial_config(self):
        """加载初始 NAI 配置"""
        logger.info("正在加载 NAI 配置到 UI...") # 使用 logging
        config = self.config_manager.load_config("nai") # 加载配置
        # 设置 UI 变量
        self.api_key_var.set(config.get("naiApiKey", ""))
        self.save_dir_var.set(config.get("naiImageSaveDir", ""))
        saved_model_value = config.get("naiModel", "")
        saved_model_name = self._model_value_to_name.get(saved_model_value) # 将值转为名称
        if saved_model_name and self.nai_models: self.model_display_var.set(saved_model_name) # 如果找到名称则设置
        elif self.nai_models: self.model_display_var.set(self.nai_models[0]['name']) # 否则用第一个
        else: self.model_display_var.set("未加载模型列表"); self.model_combobox.configure(state="disabled") # 如果模型列表为空
        self.sampler_var.set(config.get("naiSampler", "k_euler"))
        self.steps_var.set(int(config.get("naiSteps", 28)))
        self.scale_var.set(float(config.get("naiScale", 7.0)))
        self.seed_var.set(int(config.get("naiSeed", -1)))
        # 功能性备注: 加载 NAI 随机种子开关状态
        self.nai_random_seed_var.set(bool(config.get("naiRandomSeed", False)))
        self._toggle_nai_seed_entry() # 功能性备注: 根据加载的状态更新输入框启用/禁用
        uc_preset_value = config.get("naiUcPreset", 0)
        uc_preset_name = self._uc_preset_map.get(uc_preset_value, "Heavy") # 将值转为名称
        self.uc_preset_display_var.set(uc_preset_name)
        self.quality_toggle_var.set(bool(config.get("naiQualityToggle", True)))
        self.smea_var.set(bool(config.get("naiSmea", False)))
        self.smea_dyn_var.set(bool(config.get("naiSmeaDyn", False)))
        self.dyn_thresh_var.set(bool(config.get("naiDynamicThresholding", False)))
        self.uncond_scale_var.set(float(config.get("naiUncondScale", 1.0)))
        self.ref_strength_var.set(float(config.get("naiReferenceStrength", 0.6)))
        self.ref_info_var.set(float(config.get("naiReferenceInfoExtracted", 0.7)))
        self.add_orig_var.set(bool(config.get("naiAddOriginalImage", True)))
        self.nai_use_proxy_var.set(bool(config.get("nai_use_proxy", False)))
        self.nai_proxy_address_var.set(config.get("nai_proxy_address", ""))
        self.nai_proxy_port_var.set(str(config.get("nai_proxy_port", "")))
        self.save_nai_debug_var.set(bool(config.get("saveNaiDebugInputs", False))) # 加载 NAI 调试开关
        self.toggle_nai_proxy_entries() # 更新代理输入框状态
        logger.info("NAI 配置加载完成。") # 使用 logging

    def get_config_data(self):
        """收集当前的 NAI 配置数据"""
        logger.info("正在从 UI 收集 NAI 配置数据...") # 使用 logging
        # 获取模型值
        selected_model_name = self.model_display_var.get()
        model_value = self._model_name_to_value.get(selected_model_name, "")
        if not model_value and self.nai_models:
            logger.warning(f"警告: 未找到模型名称 '{selected_model_name}' 对应的值，将使用第一个模型的值。") # 使用 logging
            model_value = self.nai_models[0]['value']
        # 获取负面预设值
        selected_uc_preset_name = self.uc_preset_display_var.get()
        uc_preset_value = self._uc_preset_name_to_value.get(selected_uc_preset_name, 0)
        # 输入校验
        try: steps = int(self.steps_var.get()); assert steps > 0
        except: logger.warning(f"警告: 无效的步数输入 '{self.steps_var.get()}'"); steps = 28; self.steps_var.set(steps) # 使用 logging
        try: scale = float(self.scale_var.get())
        except: logger.warning(f"警告: 无效的引导强度输入 '{self.scale_var.get()}'"); scale = 7.0; self.scale_var.set(scale) # 使用 logging
        # 功能性备注: 处理 NAI 种子
        seed = -1 # 默认值
        if self.nai_random_seed_var.get():
            seed = random.randint(1, 2**31 - 1) # 客户端生成随机正整数
            logger.info(f"NAI 使用客户端生成的随机种子: {seed}") # 使用 logging
        else:
            try: seed = int(self.seed_var.get()) # 使用用户输入的值
            except: logger.warning(f"警告: 无效的 NAI 种子输入 '{self.seed_var.get()}'，使用默认值 -1"); seed = -1; self.seed_var.set(seed) # 使用 logging
        try: uncond_scale = float(self.uncond_scale_var.get())
        except: logger.warning(f"警告: 无效的负面强度输入 '{self.uncond_scale_var.get()}'"); uncond_scale = 1.0; self.uncond_scale_var.set(uncond_scale) # 使用 logging
        try: ref_strength = float(self.ref_strength_var.get()); assert 0.0 <= ref_strength <= 1.0
        except: logger.warning(f"警告: 无效的参考强度输入 '{self.ref_strength_var.get()}'"); ref_strength = 0.6; self.ref_strength_var.set(ref_strength) # 使用 logging
        try: ref_info = float(self.ref_info_var.get()); assert 0.0 <= ref_info <= 1.0
        except: logger.warning(f"警告: 无效的信息提取输入 '{self.ref_info_var.get()}'"); ref_info = 0.7; self.ref_info_var.set(ref_info) # 使用 logging

        # 校验代理端口
        nai_proxy_port_validated = ""; nai_proxy_port_str = self.nai_proxy_port_var.get().strip()
        if self.nai_use_proxy_var.get() and nai_proxy_port_str:
             try: port_num = int(nai_proxy_port_str); assert 1 <= port_num <= 65535; nai_proxy_port_validated = nai_proxy_port_str
             except: messagebox.showwarning("输入错误", f"NAI 代理端口号 '{nai_proxy_port_str}' 无效 (必须是 1-65535)。", parent=self); logger.error(f"错误: 无效的 NAI 代理端口号 '{nai_proxy_port_str}'。") # 使用 logging
        # 组合配置字典
        config_data = {
            "naiApiKey": self.api_key_var.get(), "naiImageSaveDir": self.save_dir_var.get(),
            "naiModel": model_value, "naiSampler": self.sampler_var.get(), "naiSteps": steps,
            "naiScale": scale, "naiSeed": seed, "naiUcPreset": uc_preset_value,
            "naiRandomSeed": self.nai_random_seed_var.get(), # 功能性备注: 保存 NAI 随机种子开关状态
            "naiQualityToggle": self.quality_toggle_var.get(),
            "naiSmea": self.smea_var.get(),
            "naiSmeaDyn": self.smea_dyn_var.get(),
            "naiDynamicThresholding": self.dyn_thresh_var.get(),
            "naiUncondScale": uncond_scale,
            "naiReferenceStrength": ref_strength,
            "naiReferenceInfoExtracted": ref_info,
            "naiAddOriginalImage": self.add_orig_var.get(),
            "nai_use_proxy": self.nai_use_proxy_var.get(),
            "nai_proxy_address": self.nai_proxy_address_var.get().strip(),
            "nai_proxy_port": nai_proxy_port_validated,
            "saveNaiDebugInputs": self.save_nai_debug_var.get() # 收集 NAI 调试开关状态
        }
        logger.info("NAI 配置数据收集完成。") # 使用 logging
        return config_data

    def trigger_workflow_button_update(self, event=None):
        """通知 WorkflowTab 更新按钮状态"""
        try:
            # 检查主应用的 workflow_tab 是否存在且有效
            if hasattr(self.app, 'workflow_tab') and self.app.workflow_tab and self.app.workflow_tab.winfo_exists():
                # 调用 workflow_tab 的更新按钮状态方法
                self.app.workflow_tab.update_button_states()
        except Exception as e:
            # 捕获并记录异常
            logger.exception(f"错误: 在 trigger_workflow_button_update ({type(self).__name__}) 中发生异常: {e}") # 使用 logging