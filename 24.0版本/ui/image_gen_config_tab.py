# ui/image_gen_config_tab.py
import customtkinter as ctk
from tkinter import StringVar, IntVar, DoubleVar, BooleanVar, filedialog, messagebox
import os
import traceback # 保留用于错误处理
import json
from customtkinter import CTkFont # 导入 CTkFont
import logging # 导入日志模块
import random # 功能性备注: 导入 random 模块用于生成随机种子
# 导入 UI 辅助函数
from .ui_helpers import create_help_button

# 获取当前模块的 logger 实例
logger = logging.getLogger(__name__)

class ImageGenConfigTab(ctk.CTkFrame):
    """统一的图片生成设置 UI 标签页 (SD WebUI & ComfyUI)"""
    def __init__(self, master, config_manager, app_instance):
        super().__init__(master, fg_color="transparent")
        self.config_manager = config_manager
        self.app = app_instance # 保存主应用实例引用
        # 共享采样器列表
        self.shared_samplers = [
            "Euler a", "Euler", "LMS", "Heun", "DPM2", "DPM2 a", "DPM++ 2S a", "DPM++ 2M",
            "DPM++ SDE", "DPM++ 2M SDE", "DPM fast", "DPM adaptive", "LMS Karras",
            "DPM2 Karras", "DPM2 a Karras", "DPM++ 2S a Karras", "DPM++ 2M Karras",
            "DPM++ SDE Karras", "DPM++ 2M SDE Karras", "DDIM", "PLMS", "UniPC"
        ]
        # 共享调度器列表
        self.shared_schedulers = ["normal", "karras", "exponential", "simple", "ddim_uniform"]
        # SD WebUI 相关选项映射
        self.sd_inpainting_fill_options = {"Fill": 0, "Original": 1, "Latent Noise": 2, "Latent Nothing": 3}
        self.sd_inpainting_fill_names = list(self.sd_inpainting_fill_options.keys())
        self.sd_mask_mode_options = {"Inpaint masked": 0, "Inpaint not masked": 1}
        self.sd_mask_mode_names = list(self.sd_mask_mode_options.keys())
        self.sd_inpaint_area_options = {"Whole picture": 0, "Only masked": 1}
        self.sd_inpaint_area_names = list(self.sd_inpaint_area_options.keys())
        self.sd_resize_mode_options = {"Just resize": 0, "Crop and resize": 1, "Resize and fill": 2, "Just resize (latent upscale)": 3}
        self.sd_resize_mode_names = list(self.sd_resize_mode_options.keys())

        # 用于存储 ComfyUI 节点标题输入框控件的字典
        self.comfy_title_entries = {}
        # 获取默认文本颜色和导入成功颜色
        self._default_text_color = ctk.ThemeManager.theme["CTkEntry"]["text_color"]
        self._imported_text_color = "green"

        # --- 功能性备注: 添加共享随机种子变量 ---
        self.shared_random_seed_var = BooleanVar(value=False)

        # --- 创建主滚动框架 ---
        self.scrollable_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scrollable_frame.pack(expand=True, fill="both")

        # --- 将所有 UI 元素放入滚动框架内 ---
        self.build_ui_within_scrollable_frame(self.scrollable_frame)
        # 加载初始配置
        self.load_initial_config()
        # 根据主应用中记录的提供商选择，初始显示对应的 Frame
        self.on_provider_change(self.app.selected_image_provider_var.get())

    def build_ui_within_scrollable_frame(self, master_frame):
        """在指定的父框架（滚动框架）内构建 UI 元素"""
        # 配置网格布局
        master_frame.grid_columnconfigure(1, weight=1) # 让右侧列扩展
        master_frame.grid_columnconfigure(2, weight=0) # 帮助按钮列
        current_row = 0 # 用于跟踪当前行

        # --- 顶部提示文字 (修改警告内容和高度) ---
        warning_text = (
            "每次修改后要点击保存所有设置，不然修改不起效。\n"
            "【ComfyUI 用户注意】: 请确保下方“工作流节点标题约定”中的标题与您加载的“工作流文件(.json)”中对应节点的标题完全一致！"
            "标题不匹配将导致 API 调用失败、参数无法注入或生成非预期结果。"
            "工作流文件必须通过 ComfyUI 界面的 'Save (API Format)' 按钮导出。"
            "本页面的节点标题对应 API 格式 JSON 中节点的 `_meta` -> `title` 值。"
            "如果将某个标题留空，程序将无法找到对应节点进行修改。"
        )
        warning_textbox = ctk.CTkTextbox(
            master_frame, wrap="word", height=75, activate_scrollbars=False, # 增加高度
            border_width=1, border_color="orange", corner_radius=5,
            font=CTkFont(size=12), fg_color="transparent"
        )
        warning_textbox.grid(row=current_row, column=0, columnspan=3, padx=10, pady=(10, 5), sticky="ew")
        warning_textbox.insert("1.0", warning_text)
        warning_textbox.configure(state="disabled")
        current_row += 1

        # --- 提供商特定设置 Frame (占位) ---
        self.provider_specific_frame = ctk.CTkFrame(master_frame, fg_color="transparent")
        self.provider_specific_frame.grid(row=current_row, column=0, columnspan=3, padx=10, pady=5, sticky="ew")
        self.provider_specific_frame.grid_columnconfigure(1, weight=1)
        self.provider_specific_frame.grid_columnconfigure(2, weight=0) # 帮助按钮列
        current_row += 1

        # --- SD WebUI 特定设置 Frame ---
        self.sd_webui_frame = ctk.CTkFrame(self.provider_specific_frame) # SD 设置内框
        self.sd_webui_frame.grid_columnconfigure(1, weight=1)
        self.sd_webui_frame.grid_columnconfigure(2, weight=0) # Help button column
        sd_row = 0
        sd_header = ctk.CTkLabel(self.sd_webui_frame, text="SD WebUI 特定设置", font=ctk.CTkFont(weight="bold"))
        sd_header.grid(row=sd_row, column=0, columnspan=3, padx=10, pady=(5, 10), sticky="w")
        sd_row += 1
        sd_url_label = ctk.CTkLabel(self.sd_webui_frame, text="API 地址:")
        sd_url_label.grid(row=sd_row, column=0, padx=(10,0), pady=5, sticky="w")
        self.sd_url_var = StringVar()
        sd_url_entry = ctk.CTkEntry(self.sd_webui_frame, textvariable=self.sd_url_var, placeholder_text="例如: http://127.0.0.1:7860") # SD API 地址输入
        sd_url_entry.grid(row=sd_row, column=1, padx=5, pady=5, sticky="ew")
        sd_url_entry.bind("<FocusOut>", self.trigger_workflow_button_update) # 绑定失去焦点事件
        if help_btn := create_help_button(self.sd_webui_frame, "sd", "sdWebUiUrl"): help_btn.grid(row=sd_row, column=2, padx=(0, 10), pady=5, sticky="w")
        sd_row += 1
        # SD 覆盖设置
        sd_override_frame = ctk.CTkFrame(self.sd_webui_frame, fg_color="transparent")
        sd_override_frame.grid(row=sd_row, column=0, columnspan=3, padx=10, pady=5, sticky="ew")
        sd_override_frame.grid_columnconfigure((1, 3), weight=1)
        sd_override_label = ctk.CTkLabel(sd_override_frame, text="覆盖设置 (可选):")
        sd_override_label.grid(row=0, column=0, columnspan=6, pady=(0,5), sticky="w")
        sd_override_model_label = ctk.CTkLabel(sd_override_frame, text="模型:")
        sd_override_model_label.grid(row=1, column=0, padx=(0,5), pady=2, sticky="w")
        self.sd_override_model_var = StringVar()
        sd_override_model_entry = ctk.CTkEntry(sd_override_frame, textvariable=self.sd_override_model_var, placeholder_text="model.safetensors") # 覆盖模型输入
        sd_override_model_entry.grid(row=1, column=1, padx=(0,5), pady=2, sticky="ew")
        if help_btn := create_help_button(sd_override_frame, "sd", "sdOverrideModel"): help_btn.grid(row=1, column=2, padx=(0,10), pady=2, sticky="w")
        sd_override_vae_label = ctk.CTkLabel(sd_override_frame, text="VAE:")
        sd_override_vae_label.grid(row=1, column=3, padx=(10,5), pady=2, sticky="w")
        self.sd_override_vae_var = StringVar()
        sd_override_vae_entry = ctk.CTkEntry(sd_override_frame, textvariable=self.sd_override_vae_var, placeholder_text="vae.safetensors 或 Automatic") # 覆盖 VAE 输入
        sd_override_vae_entry.grid(row=1, column=4, padx=(0,5), pady=2, sticky="ew")
        if help_btn := create_help_button(sd_override_frame, "sd", "sdOverrideVAE"): help_btn.grid(row=1, column=5, padx=(0,10), pady=2, sticky="w")
        sd_row += 1
        # SD 高清修复设置
        sd_hr_frame = ctk.CTkFrame(self.sd_webui_frame, fg_color="transparent")
        sd_hr_frame.grid(row=sd_row, column=0, columnspan=3, padx=10, pady=5, sticky="ew")
        sd_hr_frame.grid_columnconfigure((1, 3, 5, 7), weight=1, uniform="hr_params")
        sd_hr_frame.grid_columnconfigure((2, 4, 6, 8), weight=0)
        self.sd_enable_hr_var = BooleanVar()
        sd_enable_hr_check = ctk.CTkCheckBox(sd_hr_frame, text="启用高清修复 (Hires. Fix)", variable=self.sd_enable_hr_var) # 高清修复开关
        sd_enable_hr_check.grid(row=0, column=0, columnspan=2, padx=(0,5), pady=5, sticky="w")
        if help_btn := create_help_button(sd_hr_frame, "sd", "sdEnableHR"): help_btn.grid(row=0, column=2, padx=(0,10), pady=5, sticky="w")
        sd_hr_scale_label = ctk.CTkLabel(sd_hr_frame, text="倍数:")
        sd_hr_scale_label.grid(row=0, column=3, padx=(10,5), pady=5, sticky="w")
        self.sd_hr_scale_var = DoubleVar(value=2.0)
        sd_hr_scale_entry = ctk.CTkEntry(sd_hr_frame, textvariable=self.sd_hr_scale_var, width=60) # 放大倍数输入
        sd_hr_scale_entry.grid(row=0, column=4, padx=0, pady=5, sticky="w")
        if help_btn := create_help_button(sd_hr_frame, "sd", "sdHRScale"): help_btn.grid(row=0, column=5, padx=(2,10), pady=5, sticky="w")
        sd_hr_upscaler_label = ctk.CTkLabel(sd_hr_frame, text="放大器:")
        sd_hr_upscaler_label.grid(row=0, column=6, padx=(10,5), pady=5, sticky="w")
        self.sd_hr_upscaler_var = StringVar(value="Latent")
        sd_hr_upscaler_entry = ctk.CTkEntry(sd_hr_frame, textvariable=self.sd_hr_upscaler_var) # 放大算法输入
        sd_hr_upscaler_entry.grid(row=0, column=7, padx=0, pady=5, sticky="ew")
        if help_btn := create_help_button(sd_hr_frame, "sd", "sdHRUpscaler"): help_btn.grid(row=0, column=8, padx=(2,10), pady=5, sticky="w")
        sd_hr_steps_label = ctk.CTkLabel(sd_hr_frame, text="HR步数:")
        sd_hr_steps_label.grid(row=1, column=3, padx=(10,5), pady=5, sticky="w")
        self.sd_hr_steps_var = IntVar(value=0)
        sd_hr_steps_entry = ctk.CTkEntry(sd_hr_frame, textvariable=self.sd_hr_steps_var, width=60) # 第二次步数输入
        sd_hr_steps_entry.grid(row=1, column=4, padx=0, pady=5, sticky="w")
        if help_btn := create_help_button(sd_hr_frame, "sd", "sdHRSteps"): help_btn.grid(row=1, column=5, padx=(2,10), pady=5, sticky="w")
        sd_row += 1
        # SD 内绘/图生图设置
        sd_inpaint_frame = ctk.CTkFrame(self.sd_webui_frame, fg_color="transparent")
        sd_inpaint_frame.grid(row=sd_row, column=0, columnspan=3, padx=10, pady=5, sticky="ew")
        sd_inpaint_frame.grid_columnconfigure((1, 3, 5, 7), weight=1, uniform="inpaint_params")
        sd_inpaint_frame.grid_columnconfigure((2, 4, 6, 8), weight=0)
        inpaint_header = ctk.CTkLabel(sd_inpaint_frame, text="局部重绘 (Inpainting) / 图生图 (Img2Img) 设置:")
        inpaint_header.grid(row=0, column=0, columnspan=8, pady=(5,5), sticky="w")
        sd_inpaint_fill_label = ctk.CTkLabel(sd_inpaint_frame, text="填充方式:")
        sd_inpaint_fill_label.grid(row=1, column=0, padx=(0,5), pady=2, sticky="w")
        self.sd_inpainting_fill_var = StringVar(value=self.sd_inpainting_fill_names[1])
        sd_inpaint_fill_combo = ctk.CTkComboBox(sd_inpaint_frame, values=self.sd_inpainting_fill_names, variable=self.sd_inpainting_fill_var) # 填充方式选择
        sd_inpaint_fill_combo.grid(row=1, column=1, padx=0, pady=2, sticky="ew")
        if help_btn := create_help_button(sd_inpaint_frame, "sd", "sdInpaintingFill"): help_btn.grid(row=1, column=2, padx=(2,10), pady=2, sticky="w")
        sd_mask_mode_label = ctk.CTkLabel(sd_inpaint_frame, text="蒙版模式:")
        sd_mask_mode_label.grid(row=1, column=3, padx=(10,5), pady=2, sticky="w")
        self.sd_mask_mode_var = StringVar(value=self.sd_mask_mode_names[0])
        sd_mask_mode_combo = ctk.CTkComboBox(sd_inpaint_frame, values=self.sd_mask_mode_names, variable=self.sd_mask_mode_var) # 蒙版模式选择
        sd_mask_mode_combo.grid(row=1, column=4, padx=0, pady=2, sticky="ew")
        if help_btn := create_help_button(sd_inpaint_frame, "sd", "sdMaskMode"): help_btn.grid(row=1, column=5, padx=(2,10), pady=2, sticky="w")
        sd_inpaint_area_label = ctk.CTkLabel(sd_inpaint_frame, text="重绘区域:")
        sd_inpaint_area_label.grid(row=2, column=0, padx=(0,5), pady=2, sticky="w")
        self.sd_inpaint_area_var = StringVar(value=self.sd_inpaint_area_names[1])
        sd_inpaint_area_combo = ctk.CTkComboBox(sd_inpaint_frame, values=self.sd_inpaint_area_names, variable=self.sd_inpaint_area_var) # 重绘区域选择
        sd_inpaint_area_combo.grid(row=2, column=1, padx=0, pady=2, sticky="ew")
        if help_btn := create_help_button(sd_inpaint_frame, "sd", "sdInpaintArea"): help_btn.grid(row=2, column=2, padx=(2,10), pady=2, sticky="w")
        sd_resize_mode_label = ctk.CTkLabel(sd_inpaint_frame, text="调整模式:")
        sd_resize_mode_label.grid(row=2, column=3, padx=(10,5), pady=2, sticky="w")
        self.sd_resize_mode_var = StringVar(value=self.sd_resize_mode_names[1])
        sd_resize_mode_combo = ctk.CTkComboBox(sd_inpaint_frame, values=self.sd_resize_mode_names, variable=self.sd_resize_mode_var) # 调整模式选择
        sd_resize_mode_combo.grid(row=2, column=4, padx=0, pady=2, sticky="ew")
        if help_btn := create_help_button(sd_inpaint_frame, "sd", "sdResizeMode"): help_btn.grid(row=2, column=5, padx=(2,10), pady=2, sticky="w")
        sd_row += 1

        # --- ComfyUI 特定设置 Frame ---
        self.comfyui_frame = ctk.CTkFrame(self.provider_specific_frame) # ComfyUI 设置内框
        self.comfyui_frame.grid_columnconfigure(1, weight=1) # 输入框列扩展
        self.comfyui_frame.grid_columnconfigure(3, weight=0) # 浏览/导入按钮列
        comfy_row = 0
        comfy_header = ctk.CTkLabel(self.comfyui_frame, text="ComfyUI 特定设置", font=ctk.CTkFont(weight="bold"))
        comfy_header.grid(row=comfy_row, column=0, columnspan=4, padx=10, pady=(5, 10), sticky="w")
        comfy_row += 1
        # ComfyUI API URL
        comfy_url_label = ctk.CTkLabel(self.comfyui_frame, text="API 地址:")
        comfy_url_label.grid(row=comfy_row, column=0, padx=(10,0), pady=5, sticky="w")
        self.comfy_url_var = StringVar()
        comfy_url_entry = ctk.CTkEntry(self.comfyui_frame, textvariable=self.comfy_url_var, placeholder_text="例如: http://127.0.0.1:8188") # Comfy API 地址输入
        comfy_url_entry.grid(row=comfy_row, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        comfy_url_entry.bind("<FocusOut>", self.trigger_workflow_button_update) # 绑定失去焦点事件
        if help_btn := create_help_button(self.comfyui_frame, "comfyui", "comfyapiUrl"): help_btn.grid(row=comfy_row, column=3, padx=(0, 10), pady=5, sticky="w")
        comfy_row += 1
        # ComfyUI Workflow File
        comfy_wf_label = ctk.CTkLabel(self.comfyui_frame, text="工作流文件:")
        comfy_wf_label.grid(row=comfy_row, column=0, padx=(10,0), pady=5, sticky="w")
        self.comfy_workflow_file_var = StringVar()
        comfy_wf_entry = ctk.CTkEntry(self.comfyui_frame, textvariable=self.comfy_workflow_file_var, placeholder_text="选择基础工作流 .json 文件 (API Format)") # 工作流文件路径输入
        comfy_wf_entry.grid(row=comfy_row, column=1, columnspan=2, padx=(5, 0), pady=5, sticky="ew")
        comfy_wf_entry.bind("<FocusOut>", self.trigger_workflow_button_update) # 绑定失去焦点事件
        # 浏览和导入按钮的容器 Frame
        button_frame_wf = ctk.CTkFrame(self.comfyui_frame, fg_color="transparent")
        button_frame_wf.grid(row=comfy_row, column=3, padx=(5, 10), pady=5, sticky="w")
        comfy_wf_browse_button = ctk.CTkButton(button_frame_wf, text="浏览...", width=60, command=self.browse_workflow_file) # 浏览文件按钮
        comfy_wf_browse_button.pack(side="left", padx=0)
        import_titles_button = ctk.CTkButton(button_frame_wf, text="导入标题", width=70, command=self.import_node_titles_from_workflow) # 导入标题按钮
        import_titles_button.pack(side="left", padx=(5,0))
        if help_btn := create_help_button(button_frame_wf, "comfyui", "comfyWorkflowFile"): help_btn.pack(side="left", padx=(5, 0))
        comfy_row += 1
        # ComfyUI 覆盖设置 (Checkpoint, VAE, LoRA)
        comfy_override_frame = ctk.CTkFrame(self.comfyui_frame, fg_color="transparent")
        comfy_override_frame.grid(row=comfy_row, column=0, columnspan=4, padx=10, pady=5, sticky="ew")
        comfy_override_frame.grid_columnconfigure((1, 3), weight=1) # 输入框列扩展
        comfy_override_header = ctk.CTkLabel(comfy_override_frame, text="覆盖工作流设置 (可选):")
        comfy_override_header.grid(row=0, column=0, columnspan=9, pady=(0,5), sticky="w")
        # Checkpoint
        comfy_ckpt_label = ctk.CTkLabel(comfy_override_frame, text="Checkpoint:")
        comfy_ckpt_label.grid(row=1, column=0, padx=(0,5), pady=2, sticky="w")
        self.comfy_ckpt_name_var = StringVar()
        comfy_ckpt_entry = ctk.CTkEntry(comfy_override_frame, textvariable=self.comfy_ckpt_name_var, placeholder_text="model.safetensors") # 覆盖模型输入
        comfy_ckpt_entry.grid(row=1, column=1, padx=(0,5), pady=2, sticky="ew")
        if help_btn := create_help_button(comfy_override_frame, "comfyui", "comfyCkptName"): help_btn.grid(row=1, column=2, padx=(0,10), pady=2, sticky="w")
        # VAE
        comfy_vae_label = ctk.CTkLabel(comfy_override_frame, text="VAE:")
        comfy_vae_label.grid(row=1, column=3, padx=(10,5), pady=2, sticky="w")
        self.comfy_vae_name_var = StringVar()
        comfy_vae_entry = ctk.CTkEntry(comfy_override_frame, textvariable=self.comfy_vae_name_var, placeholder_text="vae.safetensors") # 覆盖 VAE 输入
        comfy_vae_entry.grid(row=1, column=4, padx=(0,5), pady=2, sticky="ew")
        if help_btn := create_help_button(comfy_override_frame, "comfyui", "comfyVaeName"): help_btn.grid(row=1, column=5, padx=(0,10), pady=2, sticky="w")
        # LoRA 名称
        comfy_lora_label = ctk.CTkLabel(comfy_override_frame, text="LoRA 1:")
        comfy_lora_label.grid(row=2, column=0, padx=(0,5), pady=2, sticky="w")
        self.comfy_lora_name_var = StringVar()
        comfy_lora_entry = ctk.CTkEntry(comfy_override_frame, textvariable=self.comfy_lora_name_var, placeholder_text="lora_name.safetensors") # LoRA 名称输入
        comfy_lora_entry.grid(row=2, column=1, padx=(0,5), pady=2, sticky="ew")
        if help_btn := create_help_button(comfy_override_frame, "comfyui", "comfyLoraName"): help_btn.grid(row=2, column=2, padx=(0,10), pady=2, sticky="w")
        # LoRA 权重 (模型和CLIP)
        comfy_lora_strength_model_label = ctk.CTkLabel(comfy_override_frame, text="模型权重:")
        comfy_lora_strength_model_label.grid(row=2, column=3, padx=(10,5), pady=2, sticky="w")
        self.comfy_lora_strength_model_var = DoubleVar(value=0.7)
        comfy_lora_strength_model_entry = ctk.CTkEntry(comfy_override_frame, textvariable=self.comfy_lora_strength_model_var, width=60) # LoRA 模型权重输入
        comfy_lora_strength_model_entry.grid(row=2, column=4, padx=(0,0), pady=2, sticky="w")
        if help_btn := create_help_button(comfy_override_frame, "comfyui", "comfyLoraStrengthModel"): help_btn.grid(row=2, column=5, padx=(2,5), pady=2, sticky="w")
        comfy_lora_strength_clip_label = ctk.CTkLabel(comfy_override_frame, text="CLIP权重:")
        comfy_lora_strength_clip_label.grid(row=2, column=6, padx=(10,5), pady=2, sticky="w")
        self.comfy_lora_strength_clip_var = DoubleVar(value=0.7)
        comfy_lora_strength_clip_entry = ctk.CTkEntry(comfy_override_frame, textvariable=self.comfy_lora_strength_clip_var, width=60) # LoRA CLIP 权重输入
        comfy_lora_strength_clip_entry.grid(row=2, column=7, padx=(0,0), pady=2, sticky="w")
        if help_btn := create_help_button(comfy_override_frame, "comfyui", "comfyLoraStrengthClip"): help_btn.grid(row=2, column=8, padx=(2,10), pady=2, sticky="w")
        comfy_row += 1
        # ComfyUI Node Titles Frame (用于配置节点标题约定)
        comfy_node_title_frame = ctk.CTkFrame(self.comfyui_frame) # 内框
        comfy_node_title_frame.grid(row=comfy_row, column=0, columnspan=4, padx=10, pady=10, sticky="ew")
        comfy_node_title_frame.grid_columnconfigure((1, 4), weight=1) # 输入框列扩展
        comfy_node_title_frame.grid_columnconfigure((2, 5), weight=0) # 帮助按钮列
        title_row = 0
        comfy_node_header_label = ctk.CTkLabel(comfy_node_title_frame, text="工作流节点标题约定", font=ctk.CTkFont(weight="bold"))
        comfy_node_header_label.grid(row=title_row, column=0, columnspan=6, padx=10, pady=(5, 10), sticky="w")
        title_row += 1

        # 动态创建标题输入框并存储引用
        self.comfy_title_vars = {} # 存储 StringVar
        title_definitions = [ # 定义所有需要的标题及其配置键和默认值
            ("comfyPositiveNodeTitle", "正向提示:", "Positive_Prompt_Input"),
            ("comfyNegativeNodeTitle", "负向提示:", "Negative_Prompt_Input"),
            ("comfyOutputNodeTitle", "保存图片:", "Save_Image_Output"),
            ("comfySamplerNodeTitle", "采样器:", "Main_Sampler"),
            ("comfyLatentImageNodeTitle", "潜空间:", "Empty_Latent_Image"),
            ("comfyCheckpointNodeTitle", "模型加载:", "Load_Checkpoint"),
            ("comfyVAENodeTitle", "VAE 加载/解码:", "VAE_Decode"),
            ("comfyClipTextEncodeNodeTitle", "CLIP 编码(Skip):", "Positive_Prompt_Input"),
            ("comfyLoraLoaderNodeTitle", "LoRA 加载:", "LoraLoaderNode"),
            ("comfyLoadImageNodeTitle", "加载图像(图生图):", "LoadImageNode"),
            # --- 新增开始 ---
            ("comfyLoadMaskNodeTitle", "加载蒙版(内/外绘):", "Load_Mask_Image"),
            # --- 新增结束 ---
            ("comfyFaceDetailerNodeTitle", "面部修复 (可选):", "OptionalFaceDetailer"),
            ("comfyTilingSamplerNodeTitle", "Tiling 节点 (可选):", "OptionalTilingSampler"),
        ]

        # 循环创建节点标题输入行
        for i, (key, label_text, default_value) in enumerate(title_definitions):
            row = title_row + i // 2 # 每行放两个
            col_label = 0 if i % 2 == 0 else 3 # 标签列
            col_entry = 1 if i % 2 == 0 else 4 # 输入框列
            col_help = 2 if i % 2 == 0 else 5 # 帮助按钮列
            padx_label = (10, 5)
            padx_entry = (0, 5)
            padx_help = (0, 10)

            # 创建标签
            label = ctk.CTkLabel(comfy_node_title_frame, text=label_text)
            label.grid(row=row, column=col_label, padx=padx_label, pady=5, sticky="w")
            # 创建 StringVar 并存储
            var = StringVar()
            self.comfy_title_vars[key] = var
            # 创建输入框并存储引用
            entry = ctk.CTkEntry(comfy_node_title_frame, textvariable=var)
            entry.grid(row=row, column=col_entry, padx=padx_entry, pady=5, sticky="ew")
            # 绑定键盘事件以重置颜色
            entry.bind("<KeyRelease>", lambda event, k=key: self._on_title_entry_manual_edit(event, k))
            self.comfy_title_entries[key] = entry # 存储输入框控件引用
            # 创建帮助按钮
            if help_btn := create_help_button(comfy_node_title_frame, "comfyui", key):
                help_btn.grid(row=row, column=col_help, padx=padx_help, pady=5, sticky="w")

        comfy_row += (len(title_definitions) + 1) // 2 # 更新 comfy_row

        # --- 共享参数区域 ---
        shared_params_frame = ctk.CTkFrame(master_frame) # 共享参数内框
        shared_params_frame.grid(row=current_row, column=0, columnspan=3, padx=10, pady=10, sticky="ew")
        shared_params_frame.grid_columnconfigure(1, weight=1)
        shared_params_frame.grid_columnconfigure(3, weight=0)
        shared_row = 0
        shared_header_label = ctk.CTkLabel(shared_params_frame, text="共享图片生成参数", font=ctk.CTkFont(weight="bold"))
        shared_header_label.grid(row=shared_row, column=0, columnspan=4, padx=10, pady=(5, 10), sticky="w")
        shared_row += 1
        shared_save_dir_label = ctk.CTkLabel(shared_params_frame, text="图片保存目录:")
        shared_save_dir_label.grid(row=shared_row, column=0, padx=(10,5), pady=5, sticky="w")
        self.shared_save_dir_var = StringVar()
        shared_dir_entry = ctk.CTkEntry(shared_params_frame, textvariable=self.shared_save_dir_var, placeholder_text="应用可访问的完整目录路径") # 共享保存目录输入
        shared_dir_entry.grid(row=shared_row, column=1, columnspan=2, padx=(0, 0), pady=5, sticky="ew")
        shared_dir_entry.bind("<FocusOut>", self.trigger_workflow_button_update) # 绑定失去焦点事件
        button_frame_shared_dir = ctk.CTkFrame(shared_params_frame, fg_color="transparent")
        button_frame_shared_dir.grid(row=shared_row, column=3, padx=(5, 10), pady=5, sticky="w")
        shared_browse_button = ctk.CTkButton(button_frame_shared_dir, text="浏览...", width=60, command=self.browse_shared_save_directory) # 浏览共享目录按钮
        shared_browse_button.pack(side="left", padx=0)
        if help_btn := create_help_button(button_frame_shared_dir, "image_gen_shared", "imageSaveDir"): help_btn.pack(side="left", padx=(5, 0))
        shared_row += 1
        # 共享参数第一行 (采样器, 调度器, 步数, CFG)
        shared_grid_frame1 = ctk.CTkFrame(shared_params_frame, fg_color="transparent")
        shared_grid_frame1.grid(row=shared_row, column=0, columnspan=4, sticky="ew", padx=5, pady=(5,0))
        shared_grid_frame1.grid_columnconfigure((0, 2, 4, 6), weight=1, uniform="group_img_shared_1")
        shared_grid_frame1.grid_columnconfigure((1, 3, 5, 7), weight=0)
        grid_row1 = 0; grid_col1 = 0
        shared_sampler_label = ctk.CTkLabel(shared_grid_frame1, text="采样器:")
        shared_sampler_label.grid(row=grid_row1, column=grid_col1, padx=5, pady=2, sticky="w")
        self.shared_sampler_var = StringVar(value="Euler a")
        shared_sampler_combo = ctk.CTkComboBox(shared_grid_frame1, values=self.shared_samplers, variable=self.shared_sampler_var) # 采样器选择
        shared_sampler_combo.grid(row=grid_row1+1, column=grid_col1, padx=5, pady=2, sticky="ew")
        if help_btn := create_help_button(shared_grid_frame1, "image_gen_shared", "sampler"): help_btn.grid(row=grid_row1+1, column=grid_col1+1, padx=(2, 5), pady=2, sticky="w")
        grid_col1 += 2
        shared_scheduler_label = ctk.CTkLabel(shared_grid_frame1, text="调度器:")
        shared_scheduler_label.grid(row=grid_row1, column=grid_col1, padx=5, pady=2, sticky="w")
        self.shared_scheduler_var = StringVar(value="karras")
        shared_scheduler_combo = ctk.CTkComboBox(shared_grid_frame1, values=self.shared_schedulers, variable=self.shared_scheduler_var) # 调度器选择
        shared_scheduler_combo.grid(row=grid_row1+1, column=grid_col1, padx=5, pady=2, sticky="ew")
        if help_btn := create_help_button(shared_grid_frame1, "image_gen_shared", "scheduler"): help_btn.grid(row=grid_row1+1, column=grid_col1+1, padx=(2, 5), pady=2, sticky="w")
        grid_col1 += 2
        shared_steps_label = ctk.CTkLabel(shared_grid_frame1, text="步数:")
        shared_steps_label.grid(row=grid_row1, column=grid_col1, padx=5, pady=2, sticky="w")
        self.shared_steps_var = IntVar(value=20)
        shared_steps_entry = ctk.CTkEntry(shared_grid_frame1, textvariable=self.shared_steps_var) # 步数输入
        shared_steps_entry.grid(row=grid_row1+1, column=grid_col1, padx=5, pady=2, sticky="ew")
        if help_btn := create_help_button(shared_grid_frame1, "image_gen_shared", "steps"): help_btn.grid(row=grid_row1+1, column=grid_col1+1, padx=(2, 5), pady=2, sticky="w")
        grid_col1 += 2
        shared_cfg_label = ctk.CTkLabel(shared_grid_frame1, text="CFG Scale:")
        shared_cfg_label.grid(row=grid_row1, column=grid_col1, padx=5, pady=2, sticky="w")
        self.shared_cfg_scale_var = DoubleVar(value=7.0)
        shared_cfg_entry = ctk.CTkEntry(shared_grid_frame1, textvariable=self.shared_cfg_scale_var) # CFG 输入
        shared_cfg_entry.grid(row=grid_row1+1, column=grid_col1, padx=5, pady=2, sticky="ew")
        if help_btn := create_help_button(shared_grid_frame1, "image_gen_shared", "cfgScale"): help_btn.grid(row=grid_row1+1, column=grid_col1+1, padx=(2, 5), pady=2, sticky="w")
        shared_row += 1
        # 共享参数第二行 (宽度, 高度, 种子, 重绘幅度)
        shared_grid_frame2 = ctk.CTkFrame(shared_params_frame, fg_color="transparent")
        shared_grid_frame2.grid(row=shared_row, column=0, columnspan=4, sticky="ew", padx=5, pady=(0,0))
        shared_grid_frame2.grid_columnconfigure((0, 2, 4, 6), weight=1, uniform="group_img_shared_2")
        shared_grid_frame2.grid_columnconfigure((1, 3, 5, 7), weight=0)
        grid_row2 = 0; grid_col2 = 0
        shared_width_label = ctk.CTkLabel(shared_grid_frame2, text="宽度:")
        shared_width_label.grid(row=grid_row2, column=grid_col2, padx=5, pady=2, sticky="w")
        self.shared_width_var = IntVar(value=512)
        shared_width_entry = ctk.CTkEntry(shared_grid_frame2, textvariable=self.shared_width_var) # 宽度输入
        shared_width_entry.grid(row=grid_row2+1, column=grid_col2, padx=5, pady=2, sticky="ew")
        if help_btn := create_help_button(shared_grid_frame2, "image_gen_shared", "width"): help_btn.grid(row=grid_row2+1, column=grid_col2+1, padx=(2, 5), pady=2, sticky="w")
        grid_col2 += 2
        shared_height_label = ctk.CTkLabel(shared_grid_frame2, text="高度:")
        shared_height_label.grid(row=grid_row2, column=grid_col2, padx=5, pady=2, sticky="w")
        self.shared_height_var = IntVar(value=512)
        shared_height_entry = ctk.CTkEntry(shared_grid_frame2, textvariable=self.shared_height_var) # 高度输入
        shared_height_entry.grid(row=grid_row2+1, column=grid_col2, padx=5, pady=2, sticky="ew")
        if help_btn := create_help_button(shared_grid_frame2, "image_gen_shared", "height"): help_btn.grid(row=grid_row2+1, column=grid_col2+1, padx=(2, 5), pady=2, sticky="w")
        grid_col2 += 2
        # 功能性备注: 共享种子输入和随机开关
        shared_seed_label = ctk.CTkLabel(shared_grid_frame2, text="种子:")
        shared_seed_label.grid(row=grid_row2, column=grid_col2, padx=5, pady=2, sticky="w")
        seed_frame = ctk.CTkFrame(shared_grid_frame2, fg_color="transparent") # 内部 Frame
        seed_frame.grid(row=grid_row2+1, column=grid_col2, columnspan=2, padx=5, pady=2, sticky="ew")
        seed_frame.grid_columnconfigure(0, weight=1) # 输入框扩展
        self.shared_seed_var = IntVar(value=-1)
        self.shared_seed_entry = ctk.CTkEntry(seed_frame, textvariable=self.shared_seed_var) # 种子输入
        self.shared_seed_entry.grid(row=0, column=0, padx=(0, 5), pady=0, sticky="ew")
        if help_btn := create_help_button(seed_frame, "image_gen_shared", "seed"): help_btn.grid(row=0, column=1, padx=(0, 5), pady=0, sticky="w")
        self.shared_random_seed_check = ctk.CTkCheckBox(seed_frame, text="随机", variable=self.shared_random_seed_var, command=self._toggle_shared_seed_entry) # 随机种子开关
        self.shared_random_seed_check.grid(row=0, column=2, padx=(5, 0), pady=0, sticky="w")
        if help_btn := create_help_button(seed_frame, "image_gen_shared", "sharedRandomSeed"): help_btn.grid(row=0, column=3, padx=(2, 0), pady=0, sticky="w")
        grid_col2 += 2 # 种子部分占两列
        # 重绘幅度
        shared_denoise_label = ctk.CTkLabel(shared_grid_frame2, text="重绘幅度:")
        shared_denoise_label.grid(row=grid_row2, column=grid_col2, padx=5, pady=2, sticky="w")
        self.shared_denoise_var = DoubleVar(value=0.7)
        shared_denoise_entry = ctk.CTkEntry(shared_grid_frame2, textvariable=self.shared_denoise_var) # 重绘幅度输入
        shared_denoise_entry.grid(row=grid_row2+1, column=grid_col2, padx=5, pady=2, sticky="ew")
        if help_btn := create_help_button(shared_grid_frame2, "image_gen_shared", "denoisingStrength"): help_btn.grid(row=grid_row2+1, column=grid_col2+1, padx=(2, 5), pady=2, sticky="w")
        shared_row += 1
        # 共享参数第三行 (CLIP Skip, 蒙版模糊, 面部修复, 平铺)
        shared_grid_frame3 = ctk.CTkFrame(shared_params_frame, fg_color="transparent")
        shared_grid_frame3.grid(row=shared_row, column=0, columnspan=4, sticky="ew", padx=5, pady=(0,0))
        shared_grid_frame3.grid_columnconfigure((0, 2, 4, 6), weight=1, uniform="group_img_shared_3")
        shared_grid_frame3.grid_columnconfigure((1, 3, 5, 7), weight=0)
        grid_row3 = 0; grid_col3 = 0
        shared_clipskip_label = ctk.CTkLabel(shared_grid_frame3, text="CLIP Skip:")
        shared_clipskip_label.grid(row=grid_row3, column=grid_col3, padx=5, pady=5, sticky="w")
        self.shared_clipskip_var = IntVar(value=1)
        shared_clipskip_entry = ctk.CTkEntry(shared_grid_frame3, textvariable=self.shared_clipskip_var) # CLIP Skip 输入
        shared_clipskip_entry.grid(row=grid_row3+1, column=grid_col3, padx=5, pady=5, sticky="ew")
        if help_btn := create_help_button(shared_grid_frame3, "image_gen_shared", "clipSkip"): help_btn.grid(row=grid_row3+1, column=grid_col3+1, padx=(2, 5), pady=5, sticky="w")
        grid_col3 += 2
        shared_maskblur_label = ctk.CTkLabel(shared_grid_frame3, text="蒙版模糊:")
        shared_maskblur_label.grid(row=grid_row3, column=grid_col3, padx=5, pady=5, sticky="w")
        self.shared_maskblur_var = IntVar(value=4)
        shared_maskblur_entry = ctk.CTkEntry(shared_grid_frame3, textvariable=self.shared_maskblur_var) # 蒙版模糊输入
        shared_maskblur_entry.grid(row=grid_row3+1, column=grid_col3, padx=5, pady=5, sticky="ew")
        if help_btn := create_help_button(shared_grid_frame3, "image_gen_shared", "maskBlur"): help_btn.grid(row=grid_row3+1, column=grid_col3+1, padx=(2, 5), pady=5, sticky="w")
        grid_col3 += 2
        self.shared_restore_faces_var = BooleanVar(value=False)
        shared_restore_check = ctk.CTkCheckBox(shared_grid_frame3, text="面部修复", variable=self.shared_restore_faces_var) # 面部修复开关
        shared_restore_check.grid(row=grid_row3+1, column=grid_col3, padx=5, pady=5, sticky="w")
        if help_btn := create_help_button(shared_grid_frame3, "image_gen_shared", "restoreFaces"): help_btn.grid(row=grid_row3+1, column=grid_col3+1, padx=(2, 5), pady=5, sticky="w")
        grid_col3 += 2
        self.shared_tiling_var = BooleanVar(value=False)
        shared_tiling_check = ctk.CTkCheckBox(shared_grid_frame3, text="平铺/无缝", variable=self.shared_tiling_var) # 平铺开关
        shared_tiling_check.grid(row=grid_row3+1, column=grid_col3, padx=5, pady=5, sticky="w")
        if help_btn := create_help_button(shared_grid_frame3, "image_gen_shared", "tiling"): help_btn.grid(row=grid_row3+1, column=grid_col3+1, padx=(2, 5), pady=5, sticky="w")
        shared_row += 1
        # 全局附加提示词
        shared_add_pos_label = ctk.CTkLabel(shared_params_frame, text="全局附加正向提示:")
        shared_add_pos_label.grid(row=shared_row, column=0, padx=10, pady=(10, 5), sticky="nw")
        self.shared_add_pos_textbox = ctk.CTkTextbox(shared_params_frame, height=60, wrap="word") # 正向附加提示词输入
        self.shared_add_pos_textbox.grid(row=shared_row, column=1, columnspan=2, padx=10, pady=(10, 5), sticky="ew")
        if help_btn := create_help_button(shared_params_frame, "image_gen_shared", "additionalPositivePrompt"): help_btn.grid(row=shared_row, column=3, padx=(0, 10), pady=(10, 5), sticky="nw")
        shared_row += 1
        shared_add_neg_label = ctk.CTkLabel(shared_params_frame, text="全局附加负向提示:")
        shared_add_neg_label.grid(row=shared_row, column=0, padx=10, pady=5, sticky="nw")
        self.shared_add_neg_textbox = ctk.CTkTextbox(shared_params_frame, height=60, wrap="word") # 负向附加提示词输入
        self.shared_add_neg_textbox.grid(row=shared_row, column=1, columnspan=2, padx=10, pady=5, sticky="ew")
        if help_btn := create_help_button(shared_params_frame, "image_gen_shared", "additionalNegativePrompt"): help_btn.grid(row=shared_row, column=3, padx=(0, 10), pady=5, sticky="nw")
        shared_row += 1
        # 图片生成调试开关
        debug_frame = ctk.CTkFrame(shared_params_frame, fg_color="transparent")
        debug_frame.grid(row=shared_row, column=0, columnspan=4, pady=(10, 5), sticky="w", padx=10)
        self.save_img_debug_var = BooleanVar()
        save_img_debug_check = ctk.CTkCheckBox(debug_frame, text="保存图片生成调试输入?", variable=self.save_img_debug_var) # 图片调试开关
        save_img_debug_check.pack(side="left", padx=(0, 5))
        if help_btn := create_help_button(debug_frame, "image_gen_shared", "saveImageDebugInputs"): help_btn.pack(side="left", padx=(0, 20))

        # 功能性备注: 初始化共享种子输入框状态
        self._toggle_shared_seed_entry()

    # 功能性备注: 添加切换共享种子输入框状态的方法
    def _toggle_shared_seed_entry(self):
        """根据随机种子复选框状态切换种子输入框的启用/禁用"""
        is_random = self.shared_random_seed_var.get()
        new_state = "disabled" if is_random else "normal"
        if hasattr(self, 'shared_seed_entry') and self.shared_seed_entry.winfo_exists():
            self.shared_seed_entry.configure(state=new_state)
            if is_random:
                self.shared_seed_entry.configure(text_color="gray") # 禁用时变灰
            else:
                self.shared_seed_entry.configure(text_color=self._default_text_color) # 启用时恢复默认颜色

    def _set_title_entry_color(self, key, color):
        """安全地设置指定标题输入框的文本颜色"""
        entry_widget = self.comfy_title_entries.get(key)
        if entry_widget and entry_widget.winfo_exists():
            try:
                entry_widget.configure(text_color=color)
            except Exception as e:
                logger.warning(f"警告：设置标题输入框 '{key}' 颜色为 '{color}' 时出错: {e}") # 使用 logging

    def _on_title_entry_manual_edit(self, event, key):
        """当用户手动编辑标题输入框时，恢复默认文本颜色"""
        logger.debug(f"DEBUG: 用户手动编辑标题 '{key}'") # 使用 logging
        self._set_title_entry_color(key, self._default_text_color)

    def on_provider_change(self, selected_provider):
        """根据选择的提供商显示/隐藏特定设置区域"""
        # 先隐藏所有特定 Frame (使用 grid_remove 保留布局信息)
        if hasattr(self, 'sd_webui_frame'): self.sd_webui_frame.grid_remove()
        if hasattr(self, 'comfyui_frame'): self.comfyui_frame.grid_remove()
        # 再根据选择显示对应的 Frame
        if selected_provider == "SD WebUI":
            if hasattr(self, 'sd_webui_frame'):
                self.sd_webui_frame.grid(row=0, column=0, columnspan=3, sticky="new", padx=0, pady=0) # 显示 SD Frame
        elif selected_provider == "ComfyUI":
            if hasattr(self, 'comfyui_frame'):
                self.comfyui_frame.grid(row=0, column=0, columnspan=3, sticky="new", padx=0, pady=0) # 显示 Comfy Frame

    def browse_workflow_file(self):
        """打开文件选择对话框选择工作流 JSON 文件"""
        filepath = filedialog.askopenfilename(title="选择 ComfyUI 工作流文件 (API Format)", filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")], parent=self)
        if filepath:
            self.comfy_workflow_file_var.set(filepath) # 更新变量
            logger.info(f"ComfyUI 工作流文件已选择: {filepath}") # 使用 logging
            # 尝试验证 JSON 格式
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    json.load(f) # 尝试解析
                logger.info("工作流文件 JSON 格式有效。") # 使用 logging
                # 验证通过后，可以提示用户导入标题
                messagebox.showinfo("提示", "工作流文件已选择。\n您现在可以点击旁边的“导入标题”按钮尝试自动填充节点标题配置。", parent=self)
            except Exception as e:
                messagebox.showwarning("文件警告", f"选择的工作流文件无法解析为 JSON 或读取失败:\n{e}", parent=self)
            self.trigger_workflow_button_update() # 更新按钮状态
        else:
            logger.info("用户取消选择工作流文件。") # 使用 logging

    def import_node_titles_from_workflow(self):
        """从选定的工作流 JSON 文件中导入节点标题到 UI"""
        workflow_path = self.comfy_workflow_file_var.get().strip()
        # 检查路径是否有效
        if not workflow_path or not os.path.exists(workflow_path):
            messagebox.showerror("错误", "请先选择一个有效的工作流 JSON 文件。", parent=self)
            return

        logger.info(f"尝试从工作流 '{os.path.basename(workflow_path)}' 导入节点标题...") # 使用 logging
        try:
            with open(workflow_path, 'r', encoding='utf-8') as f:
                workflow_data = json.load(f) # 加载工作流数据

            # --- 节点识别与标题提取逻辑 ---
            nodes = workflow_data # API 格式 JSON 的顶层就是节点字典

            # 定义查找函数
            def find_first_node_by_type(target_type_part):
                """根据类型关键词查找第一个匹配的节点"""
                for node_id, node_data in nodes.items():
                    # 确保节点数据是字典
                    if isinstance(node_data, dict):
                        class_type = node_data.get("class_type", "")
                        if target_type_part.lower() in class_type.lower():
                            # 获取标题，若无则用类型名作为默认值
                            title = node_data.get("_meta", {}).get("title", class_type)
                            logger.debug(f"  > 找到类型 '{target_type_part}' 的节点: ID={node_id}, Title='{title}'") # 使用 logging
                            return node_id, node_data, title
                    else:
                        logger.warning(f"警告：节点 ID '{node_id}' 的数据不是字典格式，已跳过。") # 使用 logging
                logger.debug(f"  > 未找到类型包含 '{target_type_part}' 的节点。") # 使用 logging
                return None, None, None

            # --- 开始导入前，重置所有标题输入框的颜色为默认 ---
            logger.info("  > 重置所有标题输入框颜色为默认...") # 使用 logging
            for key in self.comfy_title_entries:
                self._set_title_entry_color(key, self._default_text_color)

            # 查找主要节点
            ckpt_id, _, ckpt_title = find_first_node_by_type("CheckpointLoader")
            sampler_id, sampler_node, sampler_title = find_first_node_by_type("Sampler")
            latent_id, _, latent_title = find_first_node_by_type("EmptyLatentImage")
            save_id, _, save_title = find_first_node_by_type("SaveImage")
            vae_decode_id, _, vae_decode_title = find_first_node_by_type("VAEDecode")
            lora_id, _, lora_title = find_first_node_by_type("LoraLoader")
            load_image_id, _, load_image_title = find_first_node_by_type("LoadImage")
            face_detailer_id, _, face_detailer_title = find_first_node_by_type("Detailer")
            tiling_id, _, tiling_title = find_first_node_by_type("Tiling")

            # --- 查找正负向提示节点 (需要通过连接关系) ---
            pos_title = None
            neg_title = None
            clip_enc_for_skip_title = None # 用于 Clip Skip 的节点标题
            cte_nodes = {nid: nd for nid, nd in nodes.items() if isinstance(nd, dict) and nd.get("class_type") == "CLIPTextEncode"}

            if sampler_id and sampler_node and cte_nodes:
                positive_link_id = None
                negative_link_id = None
                sampler_inputs = sampler_node.get("inputs", [])
                if isinstance(sampler_inputs, list):
                    for inp in sampler_inputs:
                        if isinstance(inp, dict):
                            if inp.get("name") == "positive": positive_link_id = inp.get("link")
                            elif inp.get("name") == "negative": negative_link_id = inp.get("link")
                        else:
                            logger.warning(f"警告：采样器节点 (ID={sampler_id}) 的 inputs 列表中发现非字典元素: {inp}") # 使用 logging
                else:
                    logger.warning(f"警告：采样器节点 (ID={sampler_id}) 的 'inputs' 字段不是列表: {sampler_inputs}") # 使用 logging

                found_pos = False
                found_neg = False
                for cte_id, cte_node in cte_nodes.items():
                    outputs = cte_node.get("outputs", [])
                    if isinstance(outputs, list) and len(outputs) > 0 and \
                       isinstance(outputs[0], dict) and \
                       isinstance(outputs[0].get("links"), list):
                        output_links = outputs[0]["links"]
                        if positive_link_id is not None and positive_link_id in output_links:
                            pos_title = cte_node.get("_meta", {}).get("title", "CLIPTextEncode")
                            logger.debug(f"  > 找到正向提示节点: ID={cte_id}, Title='{pos_title}'") # 使用 logging
                            clip_enc_for_skip_title = pos_title # 默认将正向作为 Skip 目标
                            found_pos = True
                        if negative_link_id is not None and negative_link_id in output_links:
                            neg_title = cte_node.get("_meta", {}).get("title", "CLIPTextEncode")
                            logger.debug(f"  > 找到负向提示节点: ID={cte_id}, Title='{neg_title}'") # 使用 logging
                            found_neg = True
                    else:
                        logger.warning(f"警告：CLIPTextEncode 节点 (ID={cte_id}) 的 'outputs' 结构异常: {outputs}") # 使用 logging
                    if found_pos and found_neg: break
                if not found_pos: logger.info("  > 未能通过连接关系明确找到正向提示节点。") # 使用 logging
                if not found_neg: logger.info("  > 未能通过连接关系明确找到负向提示节点。") # 使用 logging
            else:
                logger.info("  > 无法查找正负向提示节点，缺少采样器或 CLIPTextEncode 节点信息。") # 使用 logging
            # --- 查找逻辑结束 ---

            # --- 更新 UI 变量和颜色 (只更新找到的标题) ---
            update_count = 0
            imported_keys = set() # 记录成功导入的 key

            def update_ui(key, title):
                """更新 StringVar 并设置颜色"""
                nonlocal update_count
                if title and key in self.comfy_title_vars:
                    self.comfy_title_vars[key].set(title)
                    self._set_title_entry_color(key, self._imported_text_color) # 设置为导入颜色
                    update_count += 1
                    imported_keys.add(key)
                    return True
                return False

            # 更新 UI
            update_ui("comfyPositiveNodeTitle", pos_title)
            update_ui("comfyNegativeNodeTitle", neg_title)
            update_ui("comfyOutputNodeTitle", save_title)
            update_ui("comfySamplerNodeTitle", sampler_title)
            update_ui("comfyLatentImageNodeTitle", latent_title)
            update_ui("comfyCheckpointNodeTitle", ckpt_title)
            update_ui("comfyVAENodeTitle", vae_decode_title) # 使用 VAE 解码节点标题
            update_ui("comfyClipTextEncodeNodeTitle", clip_enc_for_skip_title)
            update_ui("comfyLoraLoaderNodeTitle", lora_title)
            update_ui("comfyLoadImageNodeTitle", load_image_title)
            # --- 新增开始 ---
            # 逻辑备注：蒙版加载节点通常也是 LoadImage，难以自动区分，
            # 所以这里不尝试自动导入，让用户手动填写或保持默认。
            # 如果需要尝试，可以查找第二个 LoadImage 节点，但这不可靠。
            # update_ui("comfyLoadMaskNodeTitle", None) # 保持默认颜色
            # --- 新增结束 ---
            update_ui("comfyFaceDetailerNodeTitle", face_detailer_title)
            update_ui("comfyTilingSamplerNodeTitle", tiling_title)

            # 检查哪些标题未被导入，确保它们的颜色是默认色
            all_title_keys = set(self.comfy_title_entries.keys())
            not_imported_keys = all_title_keys - imported_keys
            for key in not_imported_keys:
                # --- 修改：确保新加的蒙版节点标题也被设为默认色（如果未导入） ---
                if key == "comfyLoadMaskNodeTitle" and key not in imported_keys:
                    self._set_title_entry_color(key, self._default_text_color)
                elif key != "comfyLoadMaskNodeTitle": # 其他未导入的设为默认色
                    self._set_title_entry_color(key, self._default_text_color)
                # --- 修改结束 ---


            # 根据导入结果给出反馈
            if update_count > 0:
                messagebox.showinfo("导入成功", f"成功从工作流导入了 {update_count} 个节点标题（显示为绿色）。\n请检查并确认是否所有必要的标题都已正确填充。\n未自动导入的标题请手动填写。", parent=self)
            else:
                messagebox.showwarning("导入失败", "未能在工作流中自动识别并导入任何节点标题。\n请检查工作流文件或手动填写。", parent=self)

        except FileNotFoundError:
            messagebox.showerror("错误", f"找不到工作流文件:\n{workflow_path}", parent=self)
        except json.JSONDecodeError:
            messagebox.showerror("错误", f"无法解析工作流文件，请确保它是有效的 JSON 格式:\n{workflow_path}", parent=self)
        except Exception as e:
            messagebox.showerror("导入错误", f"导入节点标题时发生未知错误:\n{e}", parent=self)
            logger.exception(f"导入节点标题时发生未知错误: {e}") # 使用 logging

    def browse_shared_save_directory(self):
        """打开目录选择对话框 (用于共享保存目录)"""
        directory = filedialog.askdirectory(title="选择图片保存目录", parent=self)
        if directory:
            self.shared_save_dir_var.set(directory) # 更新变量
            logger.info(f"共享图片保存目录已设置为: {directory}") # 使用 logging
            self.trigger_workflow_button_update() # 更新按钮状态
        else:
            logger.info("用户取消选择目录。") # 使用 logging

    def load_initial_config(self):
        """加载所有图片生成相关配置到 UI，并设置默认颜色"""
        logger.info("正在加载图片生成设置到 UI...") # 使用 logging
        # 加载 SD WebUI 独立配置
        sd_config = self.config_manager.load_config("sd")
        self.sd_url_var.set(sd_config.get("sdWebUiUrl", "http://127.0.0.1:7860"))
        self.sd_override_model_var.set(sd_config.get("sdOverrideModel", ""))
        self.sd_override_vae_var.set(sd_config.get("sdOverrideVAE", ""))
        self.sd_enable_hr_var.set(bool(sd_config.get("sdEnableHR", False)))
        self.sd_hr_scale_var.set(float(sd_config.get("sdHRScale", 2.0)))
        self.sd_hr_upscaler_var.set(sd_config.get("sdHRUpscaler", "Latent"))
        self.sd_hr_steps_var.set(int(sd_config.get("sdHRSteps", 0)))
        fill_idx = sd_config.get("sdInpaintingFill", 1)
        self.sd_inpainting_fill_var.set(self.sd_inpainting_fill_names[fill_idx] if 0 <= fill_idx < len(self.sd_inpainting_fill_names) else self.sd_inpainting_fill_names[1])
        mask_mode_idx = sd_config.get("sdMaskMode", 0)
        self.sd_mask_mode_var.set(self.sd_mask_mode_names[mask_mode_idx] if 0 <= mask_mode_idx < len(self.sd_mask_mode_names) else self.sd_mask_mode_names[0])
        inpaint_area_idx = sd_config.get("sdInpaintArea", 1)
        self.sd_inpaint_area_var.set(self.sd_inpaint_area_names[inpaint_area_idx] if 0 <= inpaint_area_idx < len(self.sd_inpaint_area_names) else self.sd_inpaint_area_names[1])
        resize_mode_idx = sd_config.get("sdResizeMode", 1)
        self.sd_resize_mode_var.set(self.sd_resize_mode_names[resize_mode_idx] if 0 <= resize_mode_idx < len(self.sd_resize_mode_names) else self.sd_resize_mode_names[1])

        # 加载 ComfyUI 独立配置
        comfy_config = self.config_manager.load_config("comfyui")
        self.comfy_url_var.set(comfy_config.get("comfyapiUrl", "http://127.0.0.1:8188"))
        self.comfy_workflow_file_var.set(comfy_config.get("comfyWorkflowFile", ""))
        self.comfy_ckpt_name_var.set(comfy_config.get("comfyCkptName", ""))
        self.comfy_vae_name_var.set(comfy_config.get("comfyVaeName", ""))
        self.comfy_lora_name_var.set(comfy_config.get("comfyLoraName", ""))
        self.comfy_lora_strength_model_var.set(float(comfy_config.get("comfyLoraStrengthModel", 0.7)))
        self.comfy_lora_strength_clip_var.set(float(comfy_config.get("comfyLoraStrengthClip", 0.7)))
        # 加载节点标题配置，并设置默认颜色
        for key, var in self.comfy_title_vars.items():
            default_title = self.config_manager.DEFAULT_COMFYUI_CONFIG.get(key, "") # 获取默认值
            var.set(comfy_config.get(key, default_title)) # 加载配置值，若无则用默认值
            self._set_title_entry_color(key, self._default_text_color) # 设置为默认颜色

        # 加载共享配置
        shared_config = self.config_manager.load_config("image_gen_shared")
        self.shared_save_dir_var.set(shared_config.get("imageSaveDir", ""))
        self.shared_sampler_var.set(shared_config.get("sampler", "Euler a"))
        self.shared_scheduler_var.set(shared_config.get("scheduler", "karras"))
        self.shared_steps_var.set(int(shared_config.get("steps", 20)))
        self.shared_cfg_scale_var.set(float(shared_config.get("cfgScale", 7.0)))
        self.shared_width_var.set(int(shared_config.get("width", 512)))
        self.shared_height_var.set(int(shared_config.get("height", 512)))
        self.shared_seed_var.set(int(shared_config.get("seed", -1)))
        # 功能性备注: 加载共享随机种子开关状态
        self.shared_random_seed_var.set(bool(shared_config.get("sharedRandomSeed", False)))
        self._toggle_shared_seed_entry() # 功能性备注: 根据加载的状态更新输入框启用/禁用
        self.shared_denoise_var.set(float(shared_config.get("denoisingStrength", 0.7)))
        self.shared_clipskip_var.set(int(shared_config.get("clipSkip", 1)))
        self.shared_maskblur_var.set(int(shared_config.get("maskBlur", 4)))
        self.shared_restore_faces_var.set(bool(shared_config.get("restoreFaces", False)))
        self.shared_tiling_var.set(bool(shared_config.get("tiling", False)))
        self.save_img_debug_var.set(bool(shared_config.get("saveImageDebugInputs", False))) # 加载图片调试开关
        # 安全地更新文本框内容
        if hasattr(self, 'shared_add_pos_textbox') and self.shared_add_pos_textbox.winfo_exists():
            self.shared_add_pos_textbox.delete("1.0", "end")
            self.shared_add_pos_textbox.insert("1.0", shared_config.get("additionalPositivePrompt", ""))
        if hasattr(self, 'shared_add_neg_textbox') and self.shared_add_neg_textbox.winfo_exists():
            self.shared_add_neg_textbox.delete("1.0", "end")
            self.shared_add_neg_textbox.insert("1.0", shared_config.get("additionalNegativePrompt", ""))

        logger.info("图片生成设置加载完成。") # 使用 logging
        # 确保根据当前选择显示正确的 Frame
        self.on_provider_change(self.app.selected_image_provider_var.get())

    def get_config_data(self):
        """收集当前的图片生成配置数据 (包括共享和特定提供商)"""
        logger.info("正在从 UI 收集图片生成配置数据...") # 使用 logging

        # --- 收集 SD WebUI 独立配置 ---
        sd_config_data = {
            "sdWebUiUrl": self.sd_url_var.get().strip().rstrip('/'),
            "sdOverrideModel": self.sd_override_model_var.get().strip(),
            "sdOverrideVAE": self.sd_override_vae_var.get().strip(),
            "sdEnableHR": self.sd_enable_hr_var.get(),
            "sdHRScale": self.sd_hr_scale_var.get(),
            "sdHRUpscaler": self.sd_hr_upscaler_var.get().strip(),
            "sdHRSteps": self.sd_hr_steps_var.get(),
            "sdInpaintingFill": self.sd_inpainting_fill_options.get(self.sd_inpainting_fill_var.get(), 1),
            "sdMaskMode": self.sd_mask_mode_options.get(self.sd_mask_mode_var.get(), 0),
            "sdInpaintArea": self.sd_inpaint_area_options.get(self.sd_inpaint_area_var.get(), 1),
            "sdResizeMode": self.sd_resize_mode_options.get(self.sd_resize_mode_var.get(), 1),
        }

        # --- 收集 ComfyUI 独立配置 ---
        comfy_config_data = {
            "comfyapiUrl": self.comfy_url_var.get().strip().rstrip('/'),
            "comfyWorkflowFile": self.comfy_workflow_file_var.get().strip(),
            "comfyCkptName": self.comfy_ckpt_name_var.get().strip(),
            "comfyVaeName": self.comfy_vae_name_var.get().strip(),
            "comfyLoraName": self.comfy_lora_name_var.get().strip(),
            "comfyLoraStrengthModel": self.comfy_lora_strength_model_var.get(),
            "comfyLoraStrengthClip": self.comfy_lora_strength_clip_var.get(),
        }
        # 收集所有节点标题 StringVar 的值
        for key, var in self.comfy_title_vars.items():
            comfy_config_data[key] = var.get().strip()

        # --- 收集共享配置 ---
        # 输入校验
        try: steps = int(self.shared_steps_var.get()); assert steps > 0
        except: logger.warning(f"警告: 无效的共享步数 '{self.shared_steps_var.get()}'"); steps = 20; self.shared_steps_var.set(steps) # 使用 logging
        try: cfg = float(self.shared_cfg_scale_var.get())
        except: logger.warning(f"警告: 无效的共享 CFG '{self.shared_cfg_scale_var.get()}'"); cfg = 7.0; self.shared_cfg_scale_var.set(cfg) # 使用 logging
        try: width = int(self.shared_width_var.get()); assert width > 0 and width % 8 == 0
        except: logger.warning(f"警告: 无效的共享宽度 '{self.shared_width_var.get()}'"); width = 512; self.shared_width_var.set(width) # 使用 logging
        try: height = int(self.shared_height_var.get()); assert height > 0 and height % 8 == 0
        except: logger.warning(f"警告: 无效的共享高度 '{self.shared_height_var.get()}'"); height = 512; self.shared_height_var.set(height) # 使用 logging
        # 功能性备注: 处理共享种子
        seed = -1 # 默认值
        if self.shared_random_seed_var.get():
            seed = random.randint(1, 2**31 - 1) # 客户端生成随机正整数
            logger.info(f"使用客户端生成的随机种子: {seed}") # 使用 logging
        else:
            try: seed = int(self.shared_seed_var.get()) # 使用用户输入的值
            except: logger.warning(f"警告: 无效的共享种子输入 '{self.shared_seed_var.get()}'，使用默认值 -1"); seed = -1; self.shared_seed_var.set(seed) # 使用 logging
        try: denoise = float(self.shared_denoise_var.get()); assert 0.0 <= denoise <= 1.0
        except: logger.warning(f"警告: 无效的重绘幅度 '{self.shared_denoise_var.get()}'"); denoise = 0.7; self.shared_denoise_var.set(denoise) # 使用 logging
        try: clip_skip = int(self.shared_clipskip_var.get()); assert clip_skip >= 0
        except: logger.warning(f"警告: 无效的 CLIP Skip '{self.shared_clipskip_var.get()}'"); clip_skip = 1; self.shared_clipskip_var.set(clip_skip) # 使用 logging
        try: mask_blur = int(self.shared_maskblur_var.get()); assert mask_blur >= 0
        except: logger.warning(f"警告: 无效的蒙版模糊 '{self.shared_maskblur_var.get()}'"); mask_blur = 4; self.shared_maskblur_var.set(mask_blur) # 使用 logging
        add_pos = ""; add_neg = ""
        # 安全地获取文本框内容
        if hasattr(self, 'shared_add_pos_textbox') and self.shared_add_pos_textbox.winfo_exists():
            add_pos = self.shared_add_pos_textbox.get("1.0", "end-1c").strip()
        if hasattr(self, 'shared_add_neg_textbox') and self.shared_add_neg_textbox.winfo_exists():
            add_neg = self.shared_add_neg_textbox.get("1.0", "end-1c").strip()
        shared_config_data = {
            "imageSaveDir": self.shared_save_dir_var.get().strip(),
            "sampler": self.shared_sampler_var.get(),
            "scheduler": self.shared_scheduler_var.get(),
            "steps": steps, "cfgScale": cfg, "width": width, "height": height, "seed": seed,
            "sharedRandomSeed": self.shared_random_seed_var.get(), # 功能性备注: 保存随机种子开关状态
            "denoisingStrength": denoise,
            "clipSkip": clip_skip,
            "maskBlur": mask_blur,
            "restoreFaces": self.shared_restore_faces_var.get(),
            "tiling": self.shared_tiling_var.get(),
            "additionalPositivePrompt": add_pos,
            "additionalNegativePrompt": add_neg,
            "saveImageDebugInputs": self.save_img_debug_var.get() # 收集图片调试开关状态
        }

        # 返回包含所有部分的字典
        combined_data = {
            "shared": shared_config_data,
            "sd_webui": sd_config_data,
            "comfyui": comfy_config_data
        }
        logger.info("图片生成配置数据收集完成。") # 使用 logging
        return combined_data

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