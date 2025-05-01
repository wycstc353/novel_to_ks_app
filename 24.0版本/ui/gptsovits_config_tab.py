# ui/gptsovits_config_tab.py
import customtkinter as ctk
from tkinter import StringVar, IntVar, DoubleVar, BooleanVar, messagebox, filedialog
from customtkinter import CTkFont # 导入 CTkFont
import json
import os
import traceback # 保留用于错误处理
from pathlib import Path
import logging # 导入日志模块
# 导入 UI 辅助函数
from .ui_helpers import create_help_button

# 获取当前模块的 logger 实例
logger = logging.getLogger(__name__)

class GPTSoVITSConfigTab(ctk.CTkFrame):
    """GPT-SoVITS API 设置和人物语音映射的 UI 标签页"""
    def __init__(self, master, config_manager, app_instance):
        super().__init__(master, fg_color="transparent")
        self.config_manager = config_manager
        self.app = app_instance
        self.character_voice_map = {}
        self.map_widgets = {}
        # 语言名称到代码的映射
        self.lang_name_to_code = {"中文": "zh", "英语": "en", "日语": "ja", "中英混合": "all_zh", "日英混合": "all_ja", "粤语": "yue", "韩语": "ko", "多语种混合": "auto", "多语种混合(粤语)": "auto_yue"}
        # 语言代码到名称的映射
        self.lang_code_to_name = {v: k for k, v in self.lang_name_to_code.items()}
        # 语言名称选项列表
        self.lang_name_options = list(self.lang_name_to_code.keys())

        # 初始化 UI 变量
        self.api_url_var = StringVar()
        self.model_name_var = StringVar()
        self.save_dir_var = StringVar()
        self.audio_prefix_var = StringVar(value="cv_")
        self.how_to_cut_var = StringVar(value="不切")
        self.top_k_var = IntVar(value=5)
        self.top_p_var = DoubleVar(value=1.0)
        self.temperature_var = DoubleVar(value=1.0)
        self.ref_free_var = BooleanVar(value=False)
        self.audio_dl_url_var = StringVar()
        self.batch_size_var = IntVar(value=1)
        self.batch_threshold_var = DoubleVar(value=0.75)
        self.split_bucket_var = BooleanVar(value=True)
        self.speed_facter_var = DoubleVar(value=1.0)
        self.fragment_interval_var = DoubleVar(value=0.3)
        self.parallel_infer_var = BooleanVar(value=True)
        self.repetition_penalty_var = DoubleVar(value=1.35)
        self.seed_var = IntVar(value=-1)
        self.save_gsv_debug_var = BooleanVar(value=False) # GPT-SoVITS 调试开关

        # --- 创建主滚动框架 ---
        self.scrollable_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scrollable_frame.pack(expand=True, fill="both")

        # --- 将所有 UI 元素放入滚动框架内 ---
        self.build_ui_within_scrollable_frame(self.scrollable_frame)
        # 加载初始配置
        self.load_initial_config()
        logger.info("[GPTSoVITS Tab] UI 构建完成。") # 使用 logging

    def build_ui_within_scrollable_frame(self, master_frame):
        """在指定的父框架（滚动框架）内构建 UI 元素"""
        # 配置滚动框架内部网格
        master_frame.grid_columnconfigure(1, weight=1) # 让右侧列扩展
        master_frame.grid_columnconfigure(2, weight=0) # 帮助按钮列
        # 调整行配置，为顶部的说明文本留出空间
        master_frame.grid_rowconfigure(7, weight=1) # 让映射列表区域扩展 (原为 6)
        current_row = 0 # 用于跟踪当前行号

        # --- 顶部说明文本 ---
        info_text = "提示：本工具的 GPT-SoVITS 功能主要基于 AI Hobbyist 的整合包 API 进行测试。\n整合包下载地址: https://gsv.acgnai.top/"
        info_textbox = ctk.CTkTextbox(
            master_frame,
            wrap="word",
            height=50, # 调整高度以适应两行文本
            activate_scrollbars=False, # 不需要滚动条
            border_width=0, # 无边框
            corner_radius=0, # 无圆角
            font=CTkFont(size=14, weight="bold"), # 加大加粗字体
            fg_color="transparent" # 背景透明
        )
        info_textbox.grid(row=current_row, column=0, columnspan=3, padx=10, pady=(10, 0), sticky="ew") # 调整 pady
        info_textbox.insert("1.0", info_text)
        info_textbox.configure(state="disabled") # 设置为只读，但允许复制
        current_row += 1 # 行号增加

        # --- 新增：顶部提示文字 ---
        warning_text = "每次修改后要点击保存所有设置，不然修改不起效。"
        warning_textbox = ctk.CTkTextbox(
            master_frame,
            wrap="word",
            height=25,
            activate_scrollbars=False,
            border_width=1,
            border_color="orange",
            corner_radius=5,
            font=CTkFont(size=12),
            fg_color="transparent"
        )
        warning_textbox.grid(row=current_row, column=0, columnspan=3, padx=10, pady=(5, 5), sticky="ew")
        warning_textbox.insert("1.0", warning_text)
        warning_textbox.configure(state="disabled")
        current_row += 1

        # --- API 和路径设置 ---
        api_frame = ctk.CTkFrame(master_frame, fg_color="transparent")
        api_frame.grid(row=current_row, column=0, columnspan=3, padx=10, pady=(0, 5), sticky="ew") # 调整 pady
        api_frame.grid_columnconfigure(1, weight=1)
        api_frame.grid_columnconfigure(3, weight=0) # Help button column for browse
        row_api = 0
        url_label = ctk.CTkLabel(api_frame, text="API 地址:")
        url_label.grid(row=row_api, column=0, padx=(0, 5), pady=5, sticky="w")
        url_entry = ctk.CTkEntry(api_frame, textvariable=self.api_url_var, placeholder_text="例如: http://127.0.0.1:9880")
        url_entry.grid(row=row_api, column=1, padx=5, pady=5, sticky="ew")
        url_entry.bind("<FocusOut>", self.trigger_workflow_button_update) # 绑定失去焦点事件
        if help_btn := create_help_button(api_frame, "gptsovits", "apiUrl"): help_btn.grid(row=row_api, column=2, padx=(0, 5), pady=5, sticky="w")
        row_api += 1
        model_name_label = ctk.CTkLabel(api_frame, text="模型名称 (TTS):")
        model_name_label.grid(row=row_api, column=0, padx=(0, 5), pady=5, sticky="w")
        model_name_entry = ctk.CTkEntry(api_frame, textvariable=self.model_name_var, placeholder_text="API /infer_ref 需要的模型名")
        model_name_entry.grid(row=row_api, column=1, padx=5, pady=5, sticky="ew")
        model_name_entry.bind("<FocusOut>", self.trigger_workflow_button_update) # 绑定失去焦点事件
        if help_btn := create_help_button(api_frame, "gptsovits", "model_name"): help_btn.grid(row=row_api, column=2, padx=(0, 5), pady=5, sticky="w")
        row_api += 1
        save_dir_label = ctk.CTkLabel(api_frame, text="音频保存目录:")
        save_dir_label.grid(row=row_api, column=0, padx=(0, 5), pady=5, sticky="w")
        dir_entry = ctk.CTkEntry(api_frame, textvariable=self.save_dir_var, placeholder_text="应用可访问的完整目录路径")
        dir_entry.grid(row=row_api, column=1, padx=5, pady=5, sticky="ew")
        dir_entry.bind("<FocusOut>", self.trigger_workflow_button_update) # 绑定失去焦点事件
        button_frame_dir = ctk.CTkFrame(api_frame, fg_color="transparent")
        button_frame_dir.grid(row=row_api, column=2, columnspan=2, padx=(5, 0), pady=5, sticky="w")
        browse_button = ctk.CTkButton(button_frame_dir, text="浏览...", width=60, command=self.browse_save_directory) # 浏览目录按钮
        browse_button.pack(side="left", padx=0)
        if help_btn := create_help_button(button_frame_dir, "gptsovits", "audioSaveDir"): help_btn.pack(side="left", padx=(5, 0))
        row_api += 1
        prefix_label = ctk.CTkLabel(api_frame, text="音频文件前缀:")
        prefix_label.grid(row=row_api, column=0, padx=(0, 5), pady=5, sticky="w")
        prefix_entry = ctk.CTkEntry(api_frame, textvariable=self.audio_prefix_var, width=150)
        prefix_entry.grid(row=row_api, column=1, padx=5, pady=5, sticky="w")
        if help_btn := create_help_button(api_frame, "gptsovits", "audioPrefix"): help_btn.grid(row=row_api, column=2, padx=(0, 5), pady=5, sticky="w")
        current_row += 1 # API Frame 占一行

        # --- 默认生成参数 (第一部分) ---
        param_frame1 = ctk.CTkFrame(master_frame, fg_color="transparent")
        param_frame1.grid(row=current_row, column=0, columnspan=3, padx=10, pady=5, sticky="ew")
        param_frame1.grid_columnconfigure((0, 2, 4, 6, 8), weight=1, uniform="gptsv_params1")
        param_frame1.grid_columnconfigure((1, 3, 5, 7, 9), weight=0)
        col_param1 = 0
        cut_label = ctk.CTkLabel(param_frame1, text="切分方式:")
        cut_label.grid(row=0, column=col_param1, padx=5, pady=5, sticky="w")
        cut_options = ["不切", "凑四句一切", "凑50字一切", "按英文句号.切", "按中文句号。切", "按标点符号切"]
        cut_combo = ctk.CTkComboBox(param_frame1, values=cut_options, variable=self.how_to_cut_var, width=120)
        cut_combo.grid(row=1, column=col_param1, padx=5, pady=5, sticky="ew")
        if help_btn := create_help_button(param_frame1, "gptsovits", "how_to_cut"): help_btn.grid(row=1, column=col_param1+1, padx=(2, 5), pady=5, sticky="w")
        col_param1 += 2
        top_k_label = ctk.CTkLabel(param_frame1, text="Top K:")
        top_k_label.grid(row=0, column=col_param1, padx=5, pady=5, sticky="w")
        top_k_entry = ctk.CTkEntry(param_frame1, textvariable=self.top_k_var, width=60)
        top_k_entry.grid(row=1, column=col_param1, padx=5, pady=5, sticky="ew")
        if help_btn := create_help_button(param_frame1, "gptsovits", "top_k"): help_btn.grid(row=1, column=col_param1+1, padx=(2, 5), pady=5, sticky="w")
        col_param1 += 2
        top_p_label = ctk.CTkLabel(param_frame1, text="Top P:")
        top_p_label.grid(row=0, column=col_param1, padx=5, pady=5, sticky="w")
        top_p_entry = ctk.CTkEntry(param_frame1, textvariable=self.top_p_var, width=60)
        top_p_entry.grid(row=1, column=col_param1, padx=5, pady=5, sticky="ew")
        if help_btn := create_help_button(param_frame1, "gptsovits", "top_p"): help_btn.grid(row=1, column=col_param1+1, padx=(2, 5), pady=5, sticky="w")
        col_param1 += 2
        temp_label = ctk.CTkLabel(param_frame1, text="Temperature:")
        temp_label.grid(row=0, column=col_param1, padx=5, pady=5, sticky="w")
        temp_entry = ctk.CTkEntry(param_frame1, textvariable=self.temperature_var, width=60)
        temp_entry.grid(row=1, column=col_param1, padx=5, pady=5, sticky="ew")
        if help_btn := create_help_button(param_frame1, "gptsovits", "temperature"): help_btn.grid(row=1, column=col_param1+1, padx=(2, 5), pady=5, sticky="w")
        col_param1 += 2
        ref_free_check = ctk.CTkCheckBox(param_frame1, text="无参考模式", variable=self.ref_free_var)
        ref_free_check.grid(row=1, column=col_param1, padx=5, pady=5, sticky="w")
        if help_btn := create_help_button(param_frame1, "gptsovits", "ref_free"): help_btn.grid(row=1, column=col_param1+1, padx=(2, 5), pady=5, sticky="w")
        current_row += 1 # 参数 Frame 1 占一行

        # --- 默认生成参数 (第二部分) ---
        param_frame2 = ctk.CTkFrame(master_frame, fg_color="transparent")
        param_frame2.grid(row=current_row, column=0, columnspan=3, padx=10, pady=5, sticky="ew")
        param_frame2.grid_columnconfigure(1, weight=1)
        param_frame2.grid_columnconfigure(2, weight=0)
        current_row_param2 = 0
        dl_url_label = ctk.CTkLabel(param_frame2, text="下载 URL 前缀 (可选):")
        dl_url_label.grid(row=current_row_param2, column=0, padx=(0, 5), pady=5, sticky="w")
        dl_url_entry = ctk.CTkEntry(param_frame2, textvariable=self.audio_dl_url_var, placeholder_text="例如: http://your_ip:port")
        dl_url_entry.grid(row=current_row_param2, column=1, padx=5, pady=5, sticky="ew")
        if help_btn := create_help_button(param_frame2, "gptsovits", "audio_dl_url"): help_btn.grid(row=current_row_param2, column=2, padx=(0, 5), pady=5, sticky="w")
        current_row_param2 += 1
        param_grid_frame2 = ctk.CTkFrame(param_frame2, fg_color="transparent")
        param_grid_frame2.grid(row=current_row_param2, column=0, columnspan=3, sticky="ew")
        param_grid_frame2.grid_columnconfigure((0, 2, 4, 6), weight=1, uniform="gptsv_params2")
        param_grid_frame2.grid_columnconfigure((1, 3, 5, 7), weight=0)
        grid_row2 = 0; grid_col2 = 0
        batch_size_label = ctk.CTkLabel(param_grid_frame2, text="批处理大小:")
        batch_size_label.grid(row=grid_row2, column=grid_col2, padx=5, pady=5, sticky="w")
        batch_size_entry = ctk.CTkEntry(param_grid_frame2, textvariable=self.batch_size_var, width=60)
        batch_size_entry.grid(row=grid_row2+1, column=grid_col2, padx=5, pady=5, sticky="ew")
        if help_btn := create_help_button(param_grid_frame2, "gptsovits", "batch_size"): help_btn.grid(row=grid_row2+1, column=grid_col2+1, padx=(2, 5), pady=5, sticky="w")
        grid_col2 += 2
        batch_thres_label = ctk.CTkLabel(param_grid_frame2, text="批处理阈值:")
        batch_thres_label.grid(row=grid_row2, column=grid_col2, padx=5, pady=5, sticky="w")
        batch_thres_entry = ctk.CTkEntry(param_grid_frame2, textvariable=self.batch_threshold_var, width=60)
        batch_thres_entry.grid(row=grid_row2+1, column=grid_col2, padx=5, pady=5, sticky="ew")
        if help_btn := create_help_button(param_grid_frame2, "gptsovits", "batch_threshold"): help_btn.grid(row=grid_row2+1, column=grid_col2+1, padx=(2, 5), pady=5, sticky="w")
        grid_col2 += 2
        speed_label = ctk.CTkLabel(param_grid_frame2, text="语速因子:")
        speed_label.grid(row=grid_row2, column=grid_col2, padx=5, pady=5, sticky="w")
        speed_entry = ctk.CTkEntry(param_grid_frame2, textvariable=self.speed_facter_var, width=60)
        speed_entry.grid(row=grid_row2+1, column=grid_col2, padx=5, pady=5, sticky="ew")
        if help_btn := create_help_button(param_grid_frame2, "gptsovits", "speed_facter"): help_btn.grid(row=grid_row2+1, column=grid_col2+1, padx=(2, 5), pady=5, sticky="w")
        grid_col2 += 2
        rep_pen_label = ctk.CTkLabel(param_grid_frame2, text="重复惩罚:")
        rep_pen_label.grid(row=grid_row2, column=grid_col2, padx=5, pady=5, sticky="w")
        rep_pen_entry = ctk.CTkEntry(param_grid_frame2, textvariable=self.repetition_penalty_var, width=60)
        rep_pen_entry.grid(row=grid_row2+1, column=grid_col2, padx=5, pady=5, sticky="ew")
        if help_btn := create_help_button(param_grid_frame2, "gptsovits", "repetition_penalty"): help_btn.grid(row=grid_row2+1, column=grid_col2+1, padx=(2, 5), pady=5, sticky="w")
        grid_row2 += 2; grid_col2 = 0
        frag_int_label = ctk.CTkLabel(param_grid_frame2, text="分片间隔:")
        frag_int_label.grid(row=grid_row2, column=grid_col2, padx=5, pady=5, sticky="w")
        frag_int_entry = ctk.CTkEntry(param_grid_frame2, textvariable=self.fragment_interval_var, width=60)
        frag_int_entry.grid(row=grid_row2+1, column=grid_col2, padx=5, pady=5, sticky="ew")
        if help_btn := create_help_button(param_grid_frame2, "gptsovits", "fragment_interval"): help_btn.grid(row=grid_row2+1, column=grid_col2+1, padx=(2, 5), pady=5, sticky="w")
        grid_col2 += 2
        seed_label = ctk.CTkLabel(param_grid_frame2, text="随机种子:")
        seed_label.grid(row=grid_row2, column=grid_col2, padx=5, pady=5, sticky="w")
        seed_entry = ctk.CTkEntry(param_grid_frame2, textvariable=self.seed_var, width=60)
        seed_entry.grid(row=grid_row2+1, column=grid_col2, padx=5, pady=5, sticky="ew")
        if help_btn := create_help_button(param_grid_frame2, "gptsovits", "seed"): help_btn.grid(row=grid_row2+1, column=grid_col2+1, padx=(2, 5), pady=5, sticky="w")
        grid_col2 += 2
        split_bucket_check = ctk.CTkCheckBox(param_grid_frame2, text="启用分桶", variable=self.split_bucket_var)
        split_bucket_check.grid(row=grid_row2+1, column=grid_col2, padx=5, pady=5, sticky="w")
        if help_btn := create_help_button(param_grid_frame2, "gptsovits", "split_bucket"): help_btn.grid(row=grid_row2+1, column=grid_col2+1, padx=(2, 5), pady=5, sticky="w")
        grid_col2 += 2
        parallel_infer_check = ctk.CTkCheckBox(param_grid_frame2, text="并行推理", variable=self.parallel_infer_var)
        parallel_infer_check.grid(row=grid_row2+1, column=grid_col2, padx=5, pady=5, sticky="w")
        if help_btn := create_help_button(param_grid_frame2, "gptsovits", "parallel_infer"): help_btn.grid(row=grid_row2+1, column=grid_col2+1, padx=(2, 5), pady=5, sticky="w")
        current_row += 1 # 参数 Frame 2 占一行

        # --- 新增：GPT-SoVITS 调试开关 ---
        debug_frame = ctk.CTkFrame(master_frame, fg_color="transparent")
        debug_frame.grid(row=current_row, column=0, columnspan=3, pady=(10, 5), sticky="w", padx=10)
        save_gsv_debug_check = ctk.CTkCheckBox(debug_frame, text="保存 GPT-SoVITS 调试输入?", variable=self.save_gsv_debug_var)
        save_gsv_debug_check.pack(side="left", padx=(0, 5))
        if help_btn := create_help_button(debug_frame, "gptsovits", "saveGsvDebugInputs"): help_btn.pack(side="left", padx=(0, 20))
        current_row += 1 # 调试开关占一行

        # --- 人物语音映射管理 ---
        map_manage_frame = ctk.CTkFrame(master_frame, fg_color="transparent")
        map_manage_frame.grid(row=current_row, column=0, columnspan=3, padx=10, pady=(10, 0), sticky="ew")
        add_map_button = ctk.CTkButton(map_manage_frame, text="添加映射条目", command=self.add_new_voice_map_entry) # 添加映射按钮
        add_map_button.pack(side="left", padx=5)
        import_names_button = ctk.CTkButton(map_manage_frame, text="从人物设定导入名称", command=self.import_names_from_profiles) # 从设定导入按钮
        import_names_button.pack(side="left", padx=5)
        current_row += 1 # 映射管理按钮占一行

        # --- 人物语音映射列表 ---
        self.map_scrollable_frame = ctk.CTkScrollableFrame(master_frame, label_text="人物语音映射")
        self.map_scrollable_frame.grid(row=current_row, column=0, columnspan=3, padx=10, pady=(0, 10), sticky="nsew")
        self.map_scrollable_frame.grid_columnconfigure(2, weight=1); self.map_scrollable_frame.grid_columnconfigure(4, weight=1) # 配置列宽

        self.render_voice_map_list() # 初始渲染

    def browse_save_directory(self):
        """选择音频保存目录"""
        directory = filedialog.askdirectory(title="选择 GPT-SoVITS 音频保存目录", parent=self)
        if directory:
            self.save_dir_var.set(directory)
            logger.info(f"GPT-SoVITS 音频保存目录已设置为: {directory}") # 使用 logging
            self.trigger_workflow_button_update() # 更新按钮状态
        else:
            logger.info("用户取消选择目录。") # 使用 logging

    def browse_reference(self, kag_name, entry_var):
        """根据模式选择参考文件或文件夹"""
        if kag_name not in self.character_voice_map: return
        mode = self.character_voice_map[kag_name].get("mode", "map")
        if mode == "map":
            # 映射模式：选择单个 WAV 文件
            filepath = filedialog.askopenfilename(title=f"为 '{kag_name}' 选择参考音频 (.wav)", filetypes=[("WAV 文件", "*.wav"), ("所有文件", "*.*")], parent=self)
            if filepath:
                entry_var.set(filepath)
                self.update_voice_map_field(kag_name, "refer_wav_path", filepath)
                self.trigger_workflow_button_update() # 更新按钮状态
            else:
                logger.info("用户取消选择参考音频。") # 使用 logging
        elif mode == "random":
            # 随机模式：选择包含 WAV 和对应文本文件的文件夹
            directory = filedialog.askdirectory(title=f"为 '{kag_name}' 选择随机参考文件夹", parent=self)
            if directory:
                entry_var.set(directory)
                self.update_voice_map_field(kag_name, "refer_wav_path", directory)
                self.trigger_workflow_button_update() # 更新按钮状态
            else:
                logger.info("用户取消选择随机参考文件夹。") # 使用 logging

    def update_mode(self, kag_name, selected_mode):
        """更新角色模式并调整 UI 状态"""
        logger.info(f"[GPTSoVITS Tab] 模式更新: 人物='{kag_name}', 新模式='{selected_mode}'") # 使用 logging
        if kag_name in self.character_voice_map and isinstance(self.character_voice_map[kag_name], dict):
            self.character_voice_map[kag_name]['mode'] = selected_mode # 更新内存中的模式
            widgets = self.map_widgets.get(kag_name) # 获取该角色的 UI 控件
            if widgets:
                is_random = (selected_mode == "random")
                field_state = "disabled" if is_random else "normal" # 随机模式下禁用参考文本输入
                ref_wav_entry = widgets.get('ref_wav_entry')
                # 更新参考路径输入框的占位符和状态
                if ref_wav_entry:
                    ref_wav_entry.configure(state="normal"); ref_wav_entry.delete(0, 'end')
                    placeholder = "随机模式: 参考文件夹路径" if is_random else "映射模式: 参考音频 .wav 路径"
                    ref_wav_entry.configure(placeholder_text=placeholder)
                    current_path = self.character_voice_map[kag_name].get("refer_wav_path", "")
                    ref_wav_entry.insert(0, current_path); ref_wav_entry.configure(state="normal")
                # 更新参考文本输入框的状态和内容
                ref_text_entry = widgets.get('ref_text_entry')
                if ref_text_entry:
                    ref_text_entry.configure(state=field_state)
                    if is_random: ref_text_entry.delete(0, 'end') # 随机模式清空参考文本
                    else: ref_text_entry.delete(0, 'end'); ref_text_entry.insert(0, self.character_voice_map[kag_name].get("prompt_text", "")) # 映射模式恢复文本
            else:
                logger.warning(f"警告：找不到人物 '{kag_name}' 对应的 UI 控件来更新状态。") # 使用 logging
            self.trigger_workflow_button_update() # 更新按钮状态
        else:
            logger.error(f"错误：尝试更新不存在或无效的人物 '{kag_name}' 的模式。") # 使用 logging

    def render_voice_map_list(self):
        """重新绘制映射列表 UI"""
        logger.info("[GPTSoVITS Tab] 开始渲染人物语音映射列表...") # 使用 logging
        for widget in self.map_scrollable_frame.winfo_children(): widget.destroy() # 清空旧 UI
        self.map_widgets = {} # 清空控件引用
        # 检查映射数据是否为字典
        if not isinstance(self.character_voice_map, dict):
            logger.error("错误: self.character_voice_map 不是字典类型！已重置为空字典。") # 使用 logging
            self.character_voice_map = {}
        kag_names = sorted(self.character_voice_map.keys()) # 获取排序后的 KAG 名称列表
        logger.info(f"[GPTSoVITS Tab] 准备渲染 {len(kag_names)} 个映射条目。") # 使用 logging

        # 如果列表为空，显示提示信息
        if not kag_names:
            no_map_label = ctk.CTkLabel(self.map_scrollable_frame, text="请点击“添加映射条目”或“从人物设定导入名称”", text_color="gray")
            no_map_label.grid(row=0, column=0, columnspan=8, padx=10, pady=20, sticky="n")
        else:
            # 创建表头
            current_row = 0
            headers = ["KAG 名称", "模式", "参考路径 (文件/文件夹)", "", "参考文本 (映射模式)", "参考语言", "文本语言", ""]
            col_widths = [100, 80, None, 25, None, 80, 80, 60] # 定义列宽（部分为 None 表示自适应）
            for col, text in enumerate(headers):
                if text: header = ctk.CTkLabel(self.map_scrollable_frame, text=text, font=ctk.CTkFont(weight="bold")); header.grid(row=current_row, column=col, padx=5, pady=2, sticky="w")
            current_row += 1

            # 遍历每个 KAG 名称，创建对应的 UI 行
            for kag_name in kag_names:
                voice_data = self.character_voice_map.get(kag_name, {});
                if not isinstance(voice_data, dict): continue # 跳过无效数据
                current_mode = voice_data.get("mode", "map"); is_random = (current_mode == "random")
                ref_text_state = "disabled" if is_random else "normal" # 参考文本状态
                ref_path_placeholder = "随机模式: 参考文件夹路径" if is_random else "映射模式: 参考音频 .wav 路径" # 参考路径占位符

                # --- 定义回调函数 (使用闭包捕获当前循环的变量) ---
                def create_remove_callback(name): return lambda: (self.remove_voice_map_entry(name), self.trigger_workflow_button_update())
                def create_update_callback(name, field_key, entry_var):
                    # 特殊处理语言选择框，需要将名称转为代码
                    if field_key in ["prompt_language_name", "text_language_name"]:
                        lang_code_key = "prompt_language" if field_key == "prompt_language_name" else "text_language"
                        return lambda event=None: (self.update_voice_map_field(name, lang_code_key, self.lang_name_to_code.get(entry_var.get(), "zh")), self.trigger_workflow_button_update())
                    else: # 其他字段直接更新
                        return lambda event=None: (self.update_voice_map_field(name, field_key, entry_var.get()), self.trigger_workflow_button_update())
                def create_mode_update_callback(name): return lambda selected_value: self.update_mode(name, selected_value)
                def create_browse_ref_callback(name, entry_var): return lambda: self.browse_reference(name, entry_var)

                # --- 创建 UI 控件 ---
                name_label = ctk.CTkLabel(self.map_scrollable_frame, text=kag_name, anchor="w", width=col_widths[0]); name_label.grid(row=current_row, column=0, padx=5, pady=2, sticky="w")
                mode_options = ["map", "random"]; mode_var = StringVar(value=current_mode); mode_optionmenu = ctk.CTkOptionMenu(self.map_scrollable_frame, values=mode_options, variable=mode_var, width=col_widths[1], command=create_mode_update_callback(kag_name)); mode_optionmenu.grid(row=current_row, column=1, padx=5, pady=2, sticky="w")
                ref_wav_var = StringVar(value=voice_data.get("refer_wav_path", "")); ref_wav_entry = ctk.CTkEntry(self.map_scrollable_frame, textvariable=ref_wav_var, placeholder_text=ref_path_placeholder, state="normal"); ref_wav_entry.grid(row=current_row, column=2, padx=5, pady=2, sticky="ew"); ref_wav_entry.bind("<FocusOut>", create_update_callback(kag_name, "refer_wav_path", ref_wav_var))
                browse_ref_button = ctk.CTkButton(self.map_scrollable_frame, text="...", width=col_widths[3], command=create_browse_ref_callback(kag_name, ref_wav_var)); browse_ref_button.grid(row=current_row, column=3, padx=(0, 5), pady=2, sticky="w")
                ref_text_var = StringVar(value=voice_data.get("prompt_text", "")); ref_text_entry = ctk.CTkEntry(self.map_scrollable_frame, textvariable=ref_text_var, placeholder_text="映射模式: 参考文本", state=ref_text_state); ref_text_entry.grid(row=current_row, column=4, padx=5, pady=2, sticky="ew"); ref_text_entry.bind("<FocusOut>", create_update_callback(kag_name, "prompt_text", ref_text_var))
                prompt_lang_code = voice_data.get("prompt_language", "zh"); prompt_lang_name = self.lang_code_to_name.get(prompt_lang_code, "中文"); prompt_lang_name_var = StringVar(value=prompt_lang_name); prompt_lang_combo = ctk.CTkComboBox(self.map_scrollable_frame, values=self.lang_name_options, variable=prompt_lang_name_var, width=col_widths[5], command=create_update_callback(kag_name, "prompt_language_name", prompt_lang_name_var)); prompt_lang_combo.grid(row=current_row, column=5, padx=5, pady=2, sticky="w")
                text_lang_code = voice_data.get("text_language", "zh"); text_lang_name = self.lang_code_to_name.get(text_lang_code, "中文"); text_lang_name_var = StringVar(value=text_lang_name); text_lang_combo = ctk.CTkComboBox(self.map_scrollable_frame, values=self.lang_name_options, variable=text_lang_name_var, width=col_widths[6], command=create_update_callback(kag_name, "text_language_name", text_lang_name_var)); text_lang_combo.grid(row=current_row, column=6, padx=5, pady=2, sticky="w")
                remove_btn = ctk.CTkButton(self.map_scrollable_frame, text="删除", width=col_widths[7], fg_color="#DB3E3E", hover_color="#B82E2E", command=create_remove_callback(kag_name)); remove_btn.grid(row=current_row, column=7, padx=(10, 5), pady=2, sticky="e")
                # 存储控件引用，用于后续更新状态
                self.map_widgets[kag_name] = {'ref_wav_entry': ref_wav_entry, 'ref_text_entry': ref_text_entry, 'mode_optionmenu': mode_optionmenu, 'browse_button': browse_ref_button, 'prompt_lang_combo': prompt_lang_combo, 'text_lang_combo': text_lang_combo}
                current_row += 1
        logger.info("[GPTSoVITS Tab] 语音映射列表渲染完成。") # 使用 logging

    def add_new_voice_map_entry(self):
        """添加新的空映射条目"""
        logger.info("[GPTSoVITS Tab] 请求添加新映射条目...") # 使用 logging
        dialog = ctk.CTkInputDialog(text="请输入 KAG 脚本中的人物名称:", title="添加语音映射"); kag_name_raw = dialog.get_input()
        if kag_name_raw is not None:
            kag_name = kag_name_raw.strip()
            if not kag_name: messagebox.showerror("名称错误", "KAG 脚本人物名称不能为空！", parent=self); return
            if kag_name in self.character_voice_map: messagebox.showerror("名称冲突", f"人物名称 '{kag_name}' 的映射已存在！", parent=self); return
            # 添加默认映射数据
            self.character_voice_map[kag_name] = {"mode": "map", "refer_wav_path": "", "prompt_text": "", "prompt_language": "zh", "text_language": "zh"}
            logger.info(f"[GPTSoVITS Tab] 新映射条目 '{kag_name}' 已添加到内存 (模式: map)。") # 使用 logging
            self.render_voice_map_list(); self.after(100, self._scroll_to_bottom) # 重新渲染并滚动
        else:
            logger.info("[GPTSoVITS Tab] 用户取消添加映射条目。") # 使用 logging

    def import_names_from_profiles(self):
        """从 ProfilesTab 导入名称到映射"""
        logger.info("[GPTSoVITS Tab] 请求从人物设定导入名称...") # 使用 logging
        try:
            # 检查 ProfilesTab 是否存在
            if hasattr(self.app, 'profiles_tab') and self.app.profiles_tab.winfo_exists():
                profile_keys = self.app.profiles_tab.character_profiles.keys(); added_count = 0; skipped_count = 0
                if not profile_keys: messagebox.showinfo("无人物设定", "人物设定标签页中当前没有人物名称可供导入。", parent=self); return
                # 遍历人物设定中的 Key
                for key in profile_keys:
                    if key not in self.character_voice_map: # 如果语音映射中不存在
                        # 添加默认映射
                        self.character_voice_map[key] = {"mode": "map", "refer_wav_path": "", "prompt_text": "", "prompt_language": "zh", "text_language": "zh"}; added_count += 1
                    else: skipped_count += 1 # 如果已存在则跳过
                # 根据导入结果显示信息
                if added_count > 0:
                    logger.info(f"[GPTSoVITS Tab] 成功导入 {added_count} 个新名称，跳过 {skipped_count} 个已存在名称。") # 使用 logging
                    self.render_voice_map_list(); self.after(100, self._scroll_to_bottom); messagebox.showinfo("导入完成", f"已成功导入 {added_count} 个新的人物名称到语音映射。", parent=self)
                else: messagebox.showinfo("无需导入", "所有人物设定中的名称均已存在于语音映射中。", parent=self)
            else: messagebox.showerror("错误", "无法访问人物设定标签页。", parent=self)
        except Exception as e:
            logger.exception(f"错误：从人物设定导入名称时出错: {e}"); messagebox.showerror("导入错误", f"从人物设定导入名称时发生错误:\n{e}", parent=self) # 使用 logging

    def remove_voice_map_entry(self, name_to_remove):
        """移除指定的语音映射条目"""
        logger.info(f"[GPTSoVITS Tab] 请求删除映射条目: '{name_to_remove}'") # 使用 logging
        if name_to_remove in self.character_voice_map:
            if messagebox.askyesno("确认删除", f"确定要删除人物 '{name_to_remove}' 的语音映射吗？", parent=self):
                try:
                    del self.character_voice_map[name_to_remove] # 从内存中删除
                    logger.info(f"[GPTSoVITS Tab] 映射条目 '{name_to_remove}' 已从内存删除。") # 使用 logging
                    self.render_voice_map_list() # 重新渲染 UI
                except Exception as e:
                    logger.exception(f"错误：删除映射条目 '{name_to_remove}' 时出错: {e}"); messagebox.showerror("删除错误", f"删除映射条目时出错:\n{e}", parent=self); self.render_voice_map_list() # 使用 logging
        else:
            logger.warning(f"警告: 尝试删除不存在的映射条目 '{name_to_remove}'。") # 使用 logging
            self.render_voice_map_list() # 即使删除失败也刷新列表

    def update_voice_map_field(self, name, field_key, value):
        """更新内存中指定映射条目的字段值"""
        if field_key == 'mode': return # 模式更新由 update_mode 处理
        logger.info(f"[GPTSoVITS Tab] 更新映射字段: 人物='{name}', 字段='{field_key}', 新值='{str(value)[:50]}...'") # 使用 logging
        if name in self.character_voice_map and isinstance(self.character_voice_map[name], dict):
            # 更新内存中的值
            self.character_voice_map[name][field_key] = value.strip() if isinstance(value, str) else value
            logger.info(f"[GPTSoVITS Tab] 内存中 '{name}' 的 '{field_key}' 字段已更新。") # 使用 logging
        else:
            logger.warning(f"警告/错误: 尝试更新不存在或无效的人物 '{name}' 的字段 '{field_key}'。") # 使用 logging

    def _scroll_to_bottom(self):
        """尝试将映射列表滚动到底部"""
        try:
            # 访问内部画布并滚动
            if hasattr(self.map_scrollable_frame, '_parent_canvas') and self.map_scrollable_frame._parent_canvas:
                self.map_scrollable_frame._parent_canvas.yview_moveto(1.0)
                logger.info("[GPTSoVITS Tab] 已尝试滚动映射列表到底部。") # 使用 logging
        except Exception as e:
            logger.warning(f"警告：滚动映射列表到底部时出错: {e}") # 使用 logging

    def load_initial_config(self):
        """从配置文件加载初始 GPT-SoVITS 配置并更新 UI"""
        logger.info("正在加载 GPT-SoVITS 配置到 UI...") # 使用 logging
        config = self.config_manager.load_config("gptsovits") # 加载配置
        # 设置 UI 变量
        self.api_url_var.set(config.get("apiUrl", ""))
        self.model_name_var.set(config.get("model_name", ""))
        self.save_dir_var.set(config.get("audioSaveDir", ""))
        self.audio_prefix_var.set(config.get("audioPrefix", "cv_"))
        self.how_to_cut_var.set(config.get("how_to_cut", "不切"))
        self.top_k_var.set(int(config.get("top_k", 5)))
        self.top_p_var.set(float(config.get("top_p", 1.0)))
        self.temperature_var.set(float(config.get("temperature", 1.0)))
        self.ref_free_var.set(bool(config.get("ref_free", False)))
        self.audio_dl_url_var.set(config.get("audio_dl_url", ""))
        self.batch_size_var.set(int(config.get("batch_size", 1)))
        self.batch_threshold_var.set(float(config.get("batch_threshold", 0.75)))
        self.split_bucket_var.set(bool(config.get("split_bucket", True)))
        self.speed_facter_var.set(float(config.get("speed_facter", 1.0)))
        self.fragment_interval_var.set(float(config.get("fragment_interval", 0.3)))
        self.parallel_infer_var.set(bool(config.get("parallel_infer", True)))
        self.repetition_penalty_var.set(float(config.get("repetition_penalty", 1.35)))
        self.seed_var.set(int(config.get("seed", -1)))
        self.save_gsv_debug_var.set(bool(config.get("saveGsvDebugInputs", False))) # 加载 GSV 调试开关
        # 加载语音映射
        self.character_voice_map = config.get("character_voice_map", {})
        if not isinstance(self.character_voice_map, dict):
            logger.warning("警告：加载的 character_voice_map 不是字典，已重置为空。") # 使用 logging
            self.character_voice_map = {}
        self.render_voice_map_list() # 渲染映射列表
        logger.info("GPT-SoVITS 配置加载完成。") # 使用 logging

    def get_config_data(self):
        """从 UI 元素收集当前的 GPT-SoVITS 配置数据"""
        logger.info("正在从 UI 收集 GPT-SoVITS 配置数据...") # 使用 logging
        # 输入校验和类型转换
        try: top_k = int(self.top_k_var.get()); assert top_k >= 0
        except: top_k = 5; logger.warning("警告: 无效的 Top K 输入，使用默认值 5。"); self.top_k_var.set(top_k) # 使用 logging
        try: top_p = float(self.top_p_var.get()); assert 0.0 <= top_p <= 1.0
        except: top_p = 1.0; logger.warning("警告: 无效的 Top P 输入，使用默认值 1.0。"); self.top_p_var.set(top_p) # 使用 logging
        try: temperature = float(self.temperature_var.get()); assert temperature > 0.0
        except: temperature = 1.0; logger.warning("警告: 无效的 Temperature 输入，使用默认值 1.0。"); self.temperature_var.set(temperature) # 使用 logging
        try: batch_size = int(self.batch_size_var.get()); assert batch_size >= 1
        except: batch_size = 1; logger.warning("警告: 无效的 Batch Size 输入，使用默认值 1。"); self.batch_size_var.set(batch_size) # 使用 logging
        try: batch_threshold = float(self.batch_threshold_var.get()); assert 0.0 <= batch_threshold <= 1.0
        except: batch_threshold = 0.75; logger.warning("警告: 无效的 Batch Threshold 输入，使用默认值 0.75。"); self.batch_threshold_var.set(batch_threshold) # 使用 logging
        try: speed_facter = float(self.speed_facter_var.get()); assert speed_facter > 0.0
        except: speed_facter = 1.0; logger.warning("警告: 无效的 Speed Factor 输入，使用默认值 1.0。"); self.speed_facter_var.set(speed_facter) # 使用 logging
        try: fragment_interval = float(self.fragment_interval_var.get()); assert fragment_interval >= 0.0
        except: fragment_interval = 0.3; logger.warning("警告: 无效的 Fragment Interval 输入，使用默认值 0.3。"); self.fragment_interval_var.set(fragment_interval) # 使用 logging
        try: repetition_penalty = float(self.repetition_penalty_var.get()); assert repetition_penalty >= 1.0
        except: repetition_penalty = 1.35; logger.warning("警告: 无效的 Repetition Penalty 输入，使用默认值 1.35。"); self.repetition_penalty_var.set(repetition_penalty) # 使用 logging
        try: seed = int(self.seed_var.get())
        except: seed = -1; logger.warning("警告: 无效的 Seed 输入，使用默认值 -1。"); self.seed_var.set(seed) # 使用 logging

        # 处理语音映射表，确保数据类型正确
        final_voice_map = {}
        for name, data in self.character_voice_map.items():
            if isinstance(data, dict):
                mode = str(data.get("mode", "map")); ref_path = str(data.get("refer_wav_path", "")); prompt_text = str(data.get("prompt_text", ""))
                prompt_lang_code = str(data.get("prompt_language", "zh")); text_lang_code = str(data.get("text_language", "zh"))
                if mode == "random": prompt_text = "" # 随机模式下清空参考文本
                final_voice_map[name] = {"mode": mode, "refer_wav_path": ref_path, "prompt_text": prompt_text, "prompt_language": prompt_lang_code, "text_language": text_lang_code}

        # 组合配置字典
        config_data = {
            "apiUrl": self.api_url_var.get().rstrip('/'), "model_name": self.model_name_var.get().strip(),
            "audioSaveDir": self.save_dir_var.get(), "audioPrefix": self.audio_prefix_var.get(),
            "how_to_cut": self.how_to_cut_var.get(), "top_k": top_k, "top_p": top_p, "temperature": temperature,
            "ref_free": self.ref_free_var.get(), "audio_dl_url": self.audio_dl_url_var.get().strip().rstrip('/'),
            "batch_size": batch_size, "batch_threshold": batch_threshold, "split_bucket": self.split_bucket_var.get(),
            "speed_facter": speed_facter, "fragment_interval": fragment_interval, "parallel_infer": self.parallel_infer_var.get(),
            "repetition_penalty": repetition_penalty, "seed": seed,
            "saveGsvDebugInputs": self.save_gsv_debug_var.get(), # 收集 GSV 调试开关状态
            "character_voice_map": final_voice_map
        }
        logger.info("GPT-SoVITS 配置数据收集完成。") # 使用 logging
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