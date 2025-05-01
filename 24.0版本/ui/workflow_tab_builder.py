# ui/workflow_tab_builder.py
import customtkinter as ctk # 功能性备注: 导入 customtkinter 库
from tkinter import StringVar, IntVar, BooleanVar # 功能性备注: 导入 Tkinter 相关变量
# 功能性备注: 导入 UI 辅助函数
from .ui_helpers import create_help_button
import logging # 功能性备注: 导入日志模块

# 功能性备注: 获取当前模块的 logger 实例
logger = logging.getLogger(__name__)

class WorkflowTabUIBuilder:
    """负责构建 WorkflowTab 的 UI 元素""" # 功能性备注: 类定义
    def __init__(self, view, app_instance):
        # 功能性备注: 初始化
        self.view = view # 功能性备注: 保存主 WorkflowTab 实例 (view) 的引用
        self.app = app_instance # 功能性备注: 保存主 App 实例的引用

    def build_ui_within_scrollable_frame(self, master_frame):
        """在指定的父框架（滚动框架）内构建 UI 元素"""
        # 功能性备注: 配置网格布局，让主要文本区域可扩展
        master_frame.grid_rowconfigure((0, 2, 4, 6), weight=1) # 行 0, 2, 4, 6 可垂直扩展
        master_frame.grid_columnconfigure(0, weight=1) # 第 0 列可水平扩展

        # 功能性备注: 创建一个字典来存储需要引用的控件
        widgets = {}

        # --- 步骤一: 原始小说原文 ---
        # 功能性备注: 创建步骤一的框架和控件
        step1_frame = ctk.CTkFrame(master_frame, fg_color="transparent")
        step1_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 5))
        step1_frame.grid_rowconfigure(1, weight=1) # 文本框行可扩展
        step1_frame.grid_columnconfigure(0, weight=1) # 文本框列可扩展
        step1_label = ctk.CTkLabel(step1_frame, text="原始小说原文:", anchor="w")
        step1_label.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        widgets['novel_text_widget'] = ctk.CTkTextbox(step1_frame, wrap="word") # 原始小说文本框
        widgets['novel_text_widget'].grid(row=1, column=0, sticky="nsew")
        # 功能性备注: 步骤一的控制按钮和状态标签
        step1_controls = ctk.CTkFrame(master_frame, fg_color="transparent")
        step1_controls.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        # 功能性备注: 按钮命令将在主类中绑定到 Controller
        widgets['preprocess_button'] = ctk.CTkButton(step1_controls, text="第一步：转换小说格式 (LLM)") # 运行步骤一按钮
        widgets['preprocess_button'].pack(side="left", padx=(0, 10))
        widgets['import_names_button'] = ctk.CTkButton(step1_controls, text="导入名称到人物设定", state="disabled") # 导入名称按钮，初始禁用
        widgets['import_names_button'].pack(side="left", padx=(0, 10))
        widgets['step1_status_label'] = ctk.CTkLabel(step1_controls, text="", text_color="gray", anchor="w") # 步骤一状态标签
        widgets['step1_status_label'].pack(side="left", fill="x", expand=True)

        # --- 步骤二: 格式化文本 ---
        # 功能性备注: 创建步骤二的框架和控件
        step2_frame = ctk.CTkFrame(master_frame, fg_color="transparent")
        step2_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        step2_frame.grid_rowconfigure(1, weight=1)
        step2_frame.grid_columnconfigure(0, weight=1)
        step2_label = ctk.CTkLabel(step2_frame, text="步骤一结果 (格式化文本):", anchor="w")
        step2_label.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        widgets['structured_text_widget'] = ctk.CTkTextbox(step2_frame, wrap="word", state="normal") # 格式化文本框
        widgets['structured_text_widget'].grid(row=1, column=0, sticky="nsew")
        # 功能性备注: 步骤二的控制按钮和状态标签
        step2_controls = ctk.CTkFrame(master_frame, fg_color="transparent")
        step2_controls.grid(row=3, column=0, sticky="ew", padx=10, pady=5)
        # 功能性备注: NAI 和 SD/Comfy 提示词按钮
        widgets['enhance_nai_button'] = ctk.CTkButton(step2_controls, text="第二步：添加 NAI 提示词 (LLM)", state="disabled") # 功能性备注: NAI 提示词按钮
        widgets['enhance_nai_button'].pack(side="left", padx=(0, 10))
        widgets['enhance_sd_comfy_button'] = ctk.CTkButton(step2_controls, text="第二步：添加 SD/Comfy 提示词 (LLM)", state="disabled") # 功能性备注: SD/Comfy 提示词按钮
        widgets['enhance_sd_comfy_button'].pack(side="left", padx=(0, 10))
        widgets['step2_status_label'] = ctk.CTkLabel(step2_controls, text="", text_color="gray", anchor="w") # 步骤二状态标签
        widgets['step2_status_label'].pack(side="left", fill="x", expand=True)

        # --- 步骤三: 含提示标记文本 ---
        # 功能性备注: 创建步骤三的框架和控件
        step3_frame = ctk.CTkFrame(master_frame, fg_color="transparent")
        step3_frame.grid(row=4, column=0, sticky="nsew", padx=10, pady=5)
        step3_frame.grid_rowconfigure(1, weight=1)
        step3_frame.grid_columnconfigure(0, weight=1)
        step3_label = ctk.CTkLabel(step3_frame, text="步骤二结果 (含提示标记):", anchor="w")
        step3_label.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        widgets['enhanced_text_widget'] = ctk.CTkTextbox(step3_frame, wrap="word", state="normal") # 含提示标记文本框
        widgets['enhanced_text_widget'].grid(row=1, column=0, sticky="nsew")
        # 功能性备注: 步骤三的控制按钮和选项
        step3_controls = ctk.CTkFrame(master_frame, fg_color="transparent")
        step3_controls.grid(row=5, column=0, sticky="ew", padx=10, pady=5)
        step3_controls.grid_columnconfigure(11, weight=1) # 让最右侧的状态标签可扩展
        widgets['convert_button'] = ctk.CTkButton(step3_controls, text="第三步：建议BGM并转KAG (LLM)", state="disabled") # 运行步骤三按钮，初始禁用
        widgets['convert_button'].grid(row=0, column=0, padx=(0, 10))
        # 功能性备注: KAG 温度覆盖选项
        widgets['override_kag_temp_checkbox'] = ctk.CTkCheckBox(step3_controls, text="覆盖KAG温度:", variable=self.view.override_kag_temp_var, command=self.view.toggle_kag_temp_entry) # 温度覆盖开关
        widgets['override_kag_temp_checkbox'].grid(row=0, column=1, padx=(10, 0))
        if help_btn := create_help_button(step3_controls, "workflow_tab_ui", "override_kag_temp"): help_btn.grid(row=0, column=2, padx=(2, 5)) # 温度覆盖帮助按钮
        widgets['kag_temp_entry'] = ctk.CTkEntry(step3_controls, textvariable=self.view.kag_temp_var, width=50, state="disabled") # 温度覆盖输入框，初始禁用
        widgets['kag_temp_entry'].grid(row=0, column=3, padx=(0, 5))
        if help_btn := create_help_button(step3_controls, "workflow_tab_ui", "kag_temp"): help_btn.grid(row=0, column=4, padx=(0, 10)) # 温度覆盖值帮助按钮
        # 功能性备注: 图片文件名前缀
        img_prefix_label = ctk.CTkLabel(step3_controls, text="图片前缀:")
        img_prefix_label.grid(row=0, column=5, padx=(10, 5))
        widgets['img_prefix_entry'] = ctk.CTkEntry(step3_controls, textvariable=self.view.image_prefix_var, width=80) # 图片前缀输入框
        widgets['img_prefix_entry'].grid(row=0, column=6, padx=(0, 5))
        if help_btn := create_help_button(step3_controls, "workflow_tab_ui", "image_prefix"): help_btn.grid(row=0, column=7, padx=(0, 10)) # 图片前缀帮助按钮
        # 功能性备注: 音频文件名前缀
        audio_prefix_label = ctk.CTkLabel(step3_controls, text="音频前缀:")
        audio_prefix_label.grid(row=0, column=8, padx=(10, 5))
        widgets['audio_prefix_entry'] = ctk.CTkEntry(step3_controls, textvariable=self.view.audio_prefix_var, width=80) # 音频前缀输入框
        widgets['audio_prefix_entry'].grid(row=0, column=9, padx=(0, 5))
        if help_btn := create_help_button(step3_controls, "workflow_tab_ui", "audio_prefix"): help_btn.grid(row=0, column=10, padx=(0, 10)) # 音频前缀帮助按钮
        # 功能性备注: 步骤三状态标签
        widgets['step3_status_label'] = ctk.CTkLabel(step3_controls, text="", text_color="gray", anchor="w") # 步骤三状态标签
        widgets['step3_status_label'].grid(row=0, column=11, sticky="ew", padx=(10, 0))

        # --- 步骤四: KAG 脚本结果 ---
        # 功能性备注: 创建步骤四的框架和控件
        step4_frame = ctk.CTkFrame(master_frame, fg_color="transparent")
        step4_frame.grid(row=6, column=0, sticky="nsew", padx=10, pady=5)
        step4_frame.grid_rowconfigure(1, weight=1)
        step4_frame.grid_columnconfigure(0, weight=1)
        step4_label = ctk.CTkLabel(step4_frame, text="步骤三结果 (KAG 脚本):", anchor="w")
        step4_label.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        widgets['kag_script_widget'] = ctk.CTkTextbox(step4_frame, wrap="word", state="normal") # KAG 脚本结果文本框
        widgets['kag_script_widget'].grid(row=1, column=0, sticky="nsew")

        # --- 生成选项 (图片和语音) ---
        # 功能性备注: 创建生成选项的框架
        gen_options_outer_frame = ctk.CTkFrame(master_frame, fg_color="transparent")
        gen_options_outer_frame.grid(row=7, column=0, sticky="ew", padx=10, pady=5)
        gen_options_outer_frame.grid_columnconfigure(0, weight=1)

        # --- 图片生成选项 ---
        # 功能性备注: 创建图片生成选项的框架
        img_gen_options_frame = ctk.CTkFrame(gen_options_outer_frame) # 图片选项内框
        img_gen_options_frame.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="ew")
        img_gen_options_frame.grid_columnconfigure(1, weight=1) # 让指定输入框扩展

        # 功能性备注: 图片范围选择框
        img_scope_frame = ctk.CTkFrame(img_gen_options_frame, fg_color="transparent") # 范围选项的内框
        img_scope_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        img_scope_label = ctk.CTkLabel(img_scope_frame, text="生成图片范围:") # 范围标签
        img_scope_label.pack(side="left", padx=(5, 10))
        widgets['img_all_radio'] = ctk.CTkRadioButton(img_scope_frame, text="所有", variable=self.view.img_gen_scope_var, value="all", command=self.view.toggle_specific_images_entry)
        widgets['img_all_radio'].pack(side="left", padx=5)
        widgets['img_uncommented_radio'] = ctk.CTkRadioButton(img_scope_frame, text="未生成", variable=self.view.img_gen_scope_var, value="uncommented", command=self.view.toggle_specific_images_entry)
        widgets['img_uncommented_radio'].pack(side="left", padx=5)
        widgets['img_commented_radio'] = ctk.CTkRadioButton(img_scope_frame, text="已生成", variable=self.view.img_gen_scope_var, value="commented", command=self.view.toggle_specific_images_entry)
        widgets['img_commented_radio'].pack(side="left", padx=5)
        if help_btn := create_help_button(img_scope_frame, "workflow_tab_ui", "img_gen_scope"): help_btn.pack(side="left", padx=(10, 5)) # 范围帮助按钮

        # 功能性备注: 图片指定行
        img_specify_frame = ctk.CTkFrame(img_gen_options_frame, fg_color="transparent") # 指定选项的内框
        img_specify_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
        img_specify_frame.grid_columnconfigure(2, weight=1) # 让输入框扩展
        widgets['img_specific_radio'] = ctk.CTkRadioButton(img_specify_frame, text="指定:", variable=self.view.img_gen_scope_var, value="specific", command=self.view.toggle_specific_images_entry)
        widgets['img_specific_radio'].grid(row=0, column=0, padx=(5, 5), pady=5, sticky="w")
        # 功能性备注: 添加“选择...”按钮
        widgets['img_select_button'] = ctk.CTkButton(img_specify_frame, text="选择...", width=60, command=lambda: self.view._open_media_selector_popup('image')) # 图片选择按钮
        widgets['img_select_button'].grid(row=0, column=1, padx=(0, 5), pady=5, sticky="w")
        widgets['specific_images_entry'] = ctk.CTkEntry(img_specify_frame, textvariable=self.view.specific_images_var, placeholder_text="文件名,逗号分隔", state="disabled") # 指定图片文件名输入框，初始禁用
        widgets['specific_images_entry'].grid(row=0, column=2, padx=5, pady=5, sticky="ew")
        if help_btn := create_help_button(img_specify_frame, "workflow_tab_ui", "specific_images"): help_btn.grid(row=0, column=3, padx=(5, 5), pady=5, sticky="w") # 指定图片帮助

        # 功能性备注: 图片生成数量和图生图开关放在同一行
        img_extra_options_frame = ctk.CTkFrame(img_gen_options_frame, fg_color="transparent")
        img_extra_options_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        img_n_samples_label = ctk.CTkLabel(img_extra_options_frame, text="数量:") # 生成数量标签
        img_n_samples_label.pack(side="left", padx=(5, 5))
        widgets['img_n_samples_entry'] = ctk.CTkEntry(img_extra_options_frame, textvariable=self.view.img_n_samples_var, width=40) # 生成数量输入框
        widgets['img_n_samples_entry'].pack(side="left", padx=(0, 5))
        if help_btn := create_help_button(img_extra_options_frame, "workflow_tab_ui", "img_n_samples"): help_btn.pack(side="left", padx=(0, 15)) # 生成数量帮助
        widgets['use_img2img_check'] = ctk.CTkCheckBox(img_extra_options_frame, text="启用图生图/内绘", variable=self.view.use_img2img_var) # 图生图开关
        widgets['use_img2img_check'].pack(side="left", padx=(10, 0))
        if help_btn := create_help_button(img_extra_options_frame, "workflow_tab_ui", "workflowEnableImg2Img"): help_btn.pack(side="left", padx=(2, 5)) # 图生图帮助

        # --- 语音生成选项 ---
        # 功能性备注: 创建语音生成选项的框架
        audio_gen_options_frame = ctk.CTkFrame(gen_options_outer_frame) # 语音选项内框
        audio_gen_options_frame.grid(row=1, column=0, padx=(0, 5), pady=5, sticky="ew")
        audio_gen_options_frame.grid_columnconfigure(1, weight=1) # 让指定输入框扩展

        # 功能性备注: 语音范围选择框
        audio_scope_frame = ctk.CTkFrame(audio_gen_options_frame, fg_color="transparent") # 范围选项的内框
        audio_scope_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        audio_scope_label = ctk.CTkLabel(audio_scope_frame, text="生成语音范围:") # 范围标签
        audio_scope_label.pack(side="left", padx=(5, 10))
        widgets['audio_all_radio'] = ctk.CTkRadioButton(audio_scope_frame, text="所有", variable=self.view.audio_gen_scope_var, value="all", command=self.view.toggle_specific_speakers_entry)
        widgets['audio_all_radio'].pack(side="left", padx=5)
        widgets['audio_uncommented_radio'] = ctk.CTkRadioButton(audio_scope_frame, text="未生成", variable=self.view.audio_gen_scope_var, value="uncommented", command=self.view.toggle_specific_speakers_entry)
        widgets['audio_uncommented_radio'].pack(side="left", padx=5)
        widgets['audio_commented_radio'] = ctk.CTkRadioButton(audio_scope_frame, text="已生成", variable=self.view.audio_gen_scope_var, value="commented", command=self.view.toggle_specific_speakers_entry)
        widgets['audio_commented_radio'].pack(side="left", padx=5)
        if help_btn := create_help_button(audio_scope_frame, "workflow_tab_ui", "audio_gen_scope"): help_btn.pack(side="left", padx=(10, 5)) # 范围帮助按钮

        # 功能性备注: 语音指定行
        audio_specify_frame = ctk.CTkFrame(audio_gen_options_frame, fg_color="transparent") # 指定选项的内框
        audio_specify_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
        audio_specify_frame.grid_columnconfigure(2, weight=1) # 让输入框扩展
        widgets['audio_specific_radio'] = ctk.CTkRadioButton(audio_specify_frame, text="指定:", variable=self.view.audio_gen_scope_var, value="specific", command=self.view.toggle_specific_speakers_entry)
        widgets['audio_specific_radio'].grid(row=0, column=0, padx=(5, 5), pady=5, sticky="w")
        # 功能性备注: 添加“选择...”按钮
        widgets['audio_select_button'] = ctk.CTkButton(audio_specify_frame, text="选择...", width=60, command=lambda: self.view._open_media_selector_popup('audio')) # 语音选择按钮
        widgets['audio_select_button'].grid(row=0, column=1, padx=(0, 5), pady=5, sticky="w")
        widgets['specific_speakers_entry'] = ctk.CTkEntry(audio_specify_frame, textvariable=self.view.specific_speakers_var, placeholder_text="语音占位符(PLACEHOLDER_...)", state="disabled") # 指定语音占位符输入框，初始禁用
        widgets['specific_speakers_entry'].grid(row=0, column=2, padx=5, pady=5, sticky="ew")
        if help_btn := create_help_button(audio_specify_frame, "workflow_tab_ui", "specific_speakers"): help_btn.grid(row=0, column=3, padx=(5, 5), pady=5, sticky="w") # 指定语音帮助

        # --- 步骤四 控制按钮 (多行布局) ---
        # 功能性备注: 创建步骤四的控制按钮框架
        step4_controls = ctk.CTkFrame(master_frame, fg_color="transparent")
        step4_controls.grid(row=8, column=0, sticky="ew", padx=10, pady=(5, 10))
        # 逻辑备注: 配置列权重，让状态标签列可扩展
        step4_controls.grid_columnconfigure(2, weight=1) # 第一行状态
        step4_controls.grid_columnconfigure(3, weight=1) # 第二行状态
        step4_controls.grid_columnconfigure(1, weight=1) # 第三行状态

        current_step4_row = 0
        # 第一行：手动替换
        row1_frame = ctk.CTkFrame(step4_controls, fg_color="transparent")
        row1_frame.grid(row=current_step4_row, column=0, columnspan=4, sticky="ew")
        widgets['replace_placeholder_button'] = ctk.CTkButton(row1_frame, text="手动替换图片占位符")
        widgets['replace_placeholder_button'].pack(side="left", padx=(0, 2))
        if help_btn := create_help_button(row1_frame, "workflow_tab_ui", "manual_replace_placeholders"): help_btn.pack(side="left", padx=(0, 5))
        widgets['image_replace_status_label'] = ctk.CTkLabel(row1_frame, text="", text_color="gray", width=10) # 图片替换状态标签
        widgets['image_replace_status_label'].pack(side="left", padx=(0, 10))
        # 逻辑备注: 移除重新注释按钮
        # widgets['recomment_image_button'] = ctk.CTkButton(row1_frame, text="重新注释图片", state="disabled")
        # widgets['recomment_image_button'].pack(side="left", padx=(5, 5))
        # widgets['recomment_audio_button'] = ctk.CTkButton(row1_frame, text="重新注释语音", state="disabled")
        # widgets['recomment_audio_button'].pack(side="left", padx=(5, 5))
        current_step4_row += 1

        # 第二行：图片生成按钮
        row2_frame = ctk.CTkFrame(step4_controls, fg_color="transparent")
        row2_frame.grid(row=current_step4_row, column=0, columnspan=4, sticky="ew", pady=(5,0))
        # 逻辑备注: 修改按钮文本
        widgets['generate_nai_button'] = ctk.CTkButton(row2_frame, text="生成图片 (NAI)", state="disabled", fg_color="#f0ad4e", hover_color="#ec971f") # NAI 按钮，初始禁用
        widgets['generate_nai_button'].pack(side="left", padx=(0, 5))
        widgets['nai_gen_status_label'] = ctk.CTkLabel(row2_frame, text="", text_color="gray", width=10) # NAI 状态标签
        widgets['nai_gen_status_label'].pack(side="left", padx=(0, 10))
        widgets['generate_sd_button'] = ctk.CTkButton(row2_frame, text="生成图片 (SD WebUI)", state="disabled", fg_color="#5bc0de", hover_color="#46b8da") # SD 按钮，初始禁用
        widgets['generate_sd_button'].pack(side="left", padx=(5, 5))
        widgets['sd_gen_status_label'] = ctk.CTkLabel(row2_frame, text="", text_color="gray", width=10) # SD 状态标签
        widgets['sd_gen_status_label'].pack(side="left", padx=(0, 10))
        widgets['generate_comfy_button'] = ctk.CTkButton(row2_frame, text="生成图片 (ComfyUI)", state="disabled", fg_color="#4cae4c", hover_color="#45a049") # ComfyUI 按钮，初始禁用
        widgets['generate_comfy_button'].pack(side="left", padx=(5, 5))
        widgets['comfy_gen_status_label'] = ctk.CTkLabel(row2_frame, text="", text_color="gray", width=10) # ComfyUI 状态标签
        widgets['comfy_gen_status_label'].pack(side="left", padx=(0, 10))
        current_step4_row += 1

        # 第三行：语音生成、保存脚本
        row3_frame = ctk.CTkFrame(step4_controls, fg_color="transparent")
        row3_frame.grid(row=current_step4_row, column=0, columnspan=4, sticky="ew", pady=(5,0))
        row3_frame.grid_columnconfigure(2, weight=1) # 让保存按钮前的空白扩展
        # 逻辑备注: 修改按钮文本
        widgets['generate_audio_button'] = ctk.CTkButton(row3_frame, text="生成语音 (GPT-SoVITS)", state="disabled", fg_color="#5cb85c", hover_color="#4cae4c") # 语音按钮，初始禁用
        widgets['generate_audio_button'].grid(row=0, column=0, padx=(0, 5))
        widgets['audio_gen_status_label'] = ctk.CTkLabel(row3_frame, text="", text_color="gray", width=10) # 语音状态标签
        widgets['audio_gen_status_label'].grid(row=0, column=1, padx=(0, 10), sticky="w")
        widgets['save_ks_button'] = ctk.CTkButton(row3_frame, text="保存 KAG 脚本 (.ks)", state="disabled") # 保存脚本按钮，初始禁用
        widgets['save_ks_button'].grid(row=0, column=3, padx=(10, 0), sticky="e") # 放置在最右侧

        return widgets # 功能性备注: 返回包含控件引用的字典