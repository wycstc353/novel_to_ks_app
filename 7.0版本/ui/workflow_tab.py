# ui/workflow_tab.py
import customtkinter as ctk
from tkinter import StringVar, messagebox, IntVar, Text, filedialog # 使用标准 tkinter 的 messagebox, Text 和 filedialog
from queue import Queue, Empty # 用于线程间通信，导入 Empty 异常
import threading # 用于后台任务
import json
import traceback
import base64
from pathlib import Path
import os
import re # 需要 re 来解析 KAG 脚本和进行后处理
import time # 需要 time.sleep
import codecs # <--- 新增导入 codecs 模块

# 导入拆分出去的任务逻辑 (使用绝对导入)
from tasks import workflow_tasks # LLM 相关任务
from tasks import image_generation_tasks # 图片生成任务
from tasks import audio_generation_tasks # 新增：语音生成任务
# 导入 utils 模块 (包含后处理函数) (使用绝对导入)
from core import utils

# --- 尝试导入 Windows 通知库 ---
try:
    from win10toast import ToastNotifier # 导入 win10toast
    toaster = ToastNotifier() # 创建通知器实例
    WINDOWS_NOTIFICATIONS_AVAILABLE = True
    print("win10toast 库加载成功，Windows 通知功能已启用。")
except ImportError:
    print("警告：未找到 win10toast 库，将无法显示 Windows 通知。请运行 'pip install win10toast'")
    WINDOWS_NOTIFICATIONS_AVAILABLE = False
    toaster = None # 确保 toaster 在不可用时为 None
# --- 通知库导入结束 ---


class WorkflowTab(ctk.CTkFrame):
    """核心转换流程的 UI 标签页"""
    def __init__(self, master, config_manager, api_helpers, utils, sound_player, app_instance):
        super().__init__(master, fg_color="transparent")
        self.config_manager = config_manager
        self.api_helpers = api_helpers # api_helpers 现在是 facade
        self.utils = utils # utils 实例，现在包含后处理函数
        self.sound_player = sound_player
        self.app = app_instance # 主应用程序实例的引用
        self.result_queue = Queue() # 用于从后台线程接收结果的队列
        self.task_running = False # 标记是否有后台任务正在运行

        self.build_ui() # 构建界面元素
        self.after(100, self.check_queue) # 启动定时检查队列的任务

    def build_ui(self):
        """构建工作流界面的 UI 元素"""
        # 配置网格布局的行和列权重
        self.grid_rowconfigure((0, 2, 4, 6), weight=1) # 让文本框所在的行可以扩展
        self.grid_columnconfigure(0, weight=1) # 让列可以扩展

        # --- 步骤一：原始小说输入 ---
        step1_frame = ctk.CTkFrame(self, fg_color="transparent")
        step1_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 5))
        step1_frame.grid_rowconfigure(1, weight=1) # 让文本框行扩展
        step1_frame.grid_columnconfigure(0, weight=1) # 让文本框列扩展

        step1_label = ctk.CTkLabel(step1_frame, text="原始小说原文:", anchor="w")
        step1_label.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        self.novel_text_widget = ctk.CTkTextbox(step1_frame, wrap="word") # 允许自动换行
        self.novel_text_widget.grid(row=1, column=0, sticky="nsew")

        step1_controls = ctk.CTkFrame(self, fg_color="transparent")
        step1_controls.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        self.preprocess_button = ctk.CTkButton(step1_controls, text="第一步：转换小说格式", command=self.run_step1_preprocess)
        self.preprocess_button.pack(side="left", padx=(0, 10))
        self.step1_status_label = ctk.CTkLabel(step1_controls, text="", text_color="gray", anchor="w")
        self.step1_status_label.pack(side="left", fill="x", expand=True)

        # --- 步骤二：格式化文本输出 ---
        step2_frame = ctk.CTkFrame(self, fg_color="transparent")
        step2_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        step2_frame.grid_rowconfigure(1, weight=1)
        step2_frame.grid_columnconfigure(0, weight=1)

        step2_label = ctk.CTkLabel(step2_frame, text="步骤一结果 (格式化文本):", anchor="w")
        step2_label.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        self.structured_text_widget = ctk.CTkTextbox(step2_frame, wrap="word", state="normal")
        self.structured_text_widget.grid(row=1, column=0, sticky="nsew")

        step2_controls = ctk.CTkFrame(self, fg_color="transparent")
        step2_controls.grid(row=3, column=0, sticky="ew", padx=10, pady=5)
        self.enhance_button = ctk.CTkButton(step2_controls, text="第二步：添加提示词", command=self.run_step2_enhance, state="disabled") # 初始禁用
        self.enhance_button.pack(side="left", padx=(0, 10))
        self.step2_status_label = ctk.CTkLabel(step2_controls, text="", text_color="gray", anchor="w")
        self.step2_status_label.pack(side="left", fill="x", expand=True)

        # --- 步骤三：增强文本输出 (含提示词标记) ---
        step3_frame = ctk.CTkFrame(self, fg_color="transparent")
        step3_frame.grid(row=4, column=0, sticky="nsew", padx=10, pady=5)
        step3_frame.grid_rowconfigure(1, weight=1)
        step3_frame.grid_columnconfigure(0, weight=1)

        step3_label = ctk.CTkLabel(step3_frame, text="步骤二结果 (含提示标记):", anchor="w")
        step3_label.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        self.enhanced_text_widget = ctk.CTkTextbox(step3_frame, wrap="word", state="normal")
        self.enhanced_text_widget.grid(row=1, column=0, sticky="nsew")

        step3_controls = ctk.CTkFrame(self, fg_color="transparent")
        step3_controls.grid(row=5, column=0, sticky="ew", padx=10, pady=5)
        self.convert_button = ctk.CTkButton(step3_controls, text="第三步：建议BGM并转KAG", command=self.run_step3_convert, state="disabled") # 初始禁用
        self.convert_button.pack(side="left", padx=(0, 10))
        # 图片前缀
        img_prefix_label = ctk.CTkLabel(step3_controls, text="图片前缀:")
        img_prefix_label.pack(side="left", padx=(10, 5))
        self.image_prefix_var = StringVar() # 用于存储图片文件名前缀
        img_prefix_entry = ctk.CTkEntry(step3_controls, textvariable=self.image_prefix_var, width=100)
        img_prefix_entry.pack(side="left")
        # 音频前缀 (新增)
        audio_prefix_label = ctk.CTkLabel(step3_controls, text="音频前缀:")
        audio_prefix_label.pack(side="left", padx=(10, 5))
        self.audio_prefix_var = StringVar(value="cv_") # 用于存储音频文件名前缀, 默认 "cv_"
        audio_prefix_entry = ctk.CTkEntry(step3_controls, textvariable=self.audio_prefix_var, width=100)
        audio_prefix_entry.pack(side="left")

        self.step3_status_label = ctk.CTkLabel(step3_controls, text="", text_color="gray", anchor="w")
        self.step3_status_label.pack(side="left", fill="x", expand=True, padx=(10, 0))

        # --- 步骤四：KAG 脚本输出 ---
        step4_frame = ctk.CTkFrame(self, fg_color="transparent")
        step4_frame.grid(row=6, column=0, sticky="nsew", padx=10, pady=5)
        step4_frame.grid_rowconfigure(1, weight=1)
        step4_frame.grid_columnconfigure(0, weight=1)

        step4_label = ctk.CTkLabel(step4_frame, text="步骤三结果 (KAG 脚本):", anchor="w")
        step4_label.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        self.kag_script_widget = ctk.CTkTextbox(step4_frame, wrap="word", state="normal")
        self.kag_script_widget.grid(row=1, column=0, sticky="nsew")

        # --- 图片/语音生成选项 ---
        gen_options_outer_frame = ctk.CTkFrame(self, fg_color="transparent")
        gen_options_outer_frame.grid(row=7, column=0, sticky="ew", padx=10, pady=5)
        gen_options_outer_frame.grid_columnconfigure(0, weight=1) # 让内部框架扩展

        # 图片生成选项 Frame
        img_gen_options_frame = ctk.CTkFrame(gen_options_outer_frame)
        img_gen_options_frame.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="ew")
        img_gen_options_frame.grid_columnconfigure(3, weight=1) # 让指定图片输入框扩展

        img_scope_label = ctk.CTkLabel(img_gen_options_frame, text="图片范围:")
        img_scope_label.grid(row=0, column=0, padx=(5, 5), pady=5, sticky="w")
        self.img_gen_scope_var = StringVar(value="all") # 图片生成范围变量
        img_all_radio = ctk.CTkRadioButton(img_gen_options_frame, text="所有", variable=self.img_gen_scope_var, value="all", command=self.toggle_specific_images_entry)
        img_all_radio.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        img_specific_radio = ctk.CTkRadioButton(img_gen_options_frame, text="指定:", variable=self.img_gen_scope_var, value="specific", command=self.toggle_specific_images_entry)
        img_specific_radio.grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.specific_images_var = StringVar() # 存储指定图片文件名的变量
        self.specific_images_entry = ctk.CTkEntry(img_gen_options_frame, textvariable=self.specific_images_var, placeholder_text="文件名,逗号分隔", state="disabled")
        self.specific_images_entry.grid(row=0, column=3, padx=5, pady=5, sticky="ew")
        img_n_samples_label = ctk.CTkLabel(img_gen_options_frame, text="数量:")
        img_n_samples_label.grid(row=0, column=4, padx=(10, 5), pady=5, sticky="w")
        self.img_n_samples_var = IntVar(value=1) # 图片生成数量
        img_n_samples_entry = ctk.CTkEntry(img_gen_options_frame, textvariable=self.img_n_samples_var, width=40)
        img_n_samples_entry.grid(row=0, column=5, padx=(0, 5), pady=5, sticky="w")

        # 语音生成选项 Frame (新增)
        audio_gen_options_frame = ctk.CTkFrame(gen_options_outer_frame)
        audio_gen_options_frame.grid(row=1, column=0, padx=(0, 5), pady=5, sticky="ew")
        audio_gen_options_frame.grid_columnconfigure(3, weight=1) # 让指定说话人输入框扩展

        audio_scope_label = ctk.CTkLabel(audio_gen_options_frame, text="语音范围:")
        audio_scope_label.grid(row=0, column=0, padx=(5, 5), pady=5, sticky="w")
        self.audio_gen_scope_var = StringVar(value="all") # 语音生成范围变量
        audio_all_radio = ctk.CTkRadioButton(audio_gen_options_frame, text="所有", variable=self.audio_gen_scope_var, value="all", command=self.toggle_specific_speakers_entry)
        audio_all_radio.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        audio_specific_radio = ctk.CTkRadioButton(audio_gen_options_frame, text="指定:", variable=self.audio_gen_scope_var, value="specific", command=self.toggle_specific_speakers_entry)
        audio_specific_radio.grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.specific_speakers_var = StringVar() # 存储指定说话人名称的变量
        self.specific_speakers_entry = ctk.CTkEntry(audio_gen_options_frame, textvariable=self.specific_speakers_var, placeholder_text="说话人名称,逗号分隔", state="disabled")
        self.specific_speakers_entry.grid(row=0, column=3, padx=5, pady=5, sticky="ew")
        # 语音生成数量通常为1，暂不提供选项


        # --- 步骤四 控制按钮 ---
        step4_controls = ctk.CTkFrame(self, fg_color="transparent")
        step4_controls.grid(row=8, column=0, sticky="ew", padx=10, pady=(5, 10))
        step4_controls.grid_columnconfigure(1, weight=1) # 让状态标签区域扩展

        # 手动替换占位符按钮
        self.replace_placeholder_button = ctk.CTkButton(step4_controls, text="手动替换图片占位符", command=self.manual_replace_placeholders)
        self.replace_placeholder_button.pack(side="left", padx=(0, 10))
        self.image_replace_status_label = ctk.CTkLabel(step4_controls, text="", text_color="gray", anchor="w")
        self.image_replace_status_label.pack(side="left", padx=(0, 20))

        # 生成按钮和状态标签 Frame
        gen_status_frame = ctk.CTkFrame(step4_controls, fg_color="transparent")
        gen_status_frame.pack(side="left", fill="x", expand=True) # 让这个 frame 填充

        # NAI 图片生成
        self.generate_nai_button = ctk.CTkButton(gen_status_frame, text="生成图片 (NAI)", command=self.run_generate_nai, state="disabled", fg_color="#f0ad4e", hover_color="#ec971f")
        self.generate_nai_button.grid(row=0, column=0, padx=5, pady=2)
        self.nai_gen_status_label = ctk.CTkLabel(gen_status_frame, text="", text_color="gray", anchor="w")
        self.nai_gen_status_label.grid(row=0, column=1, padx=(0, 10), sticky="w")

        # SD 图片生成
        self.generate_sd_button = ctk.CTkButton(gen_status_frame, text="生成图片 (SD)", command=self.run_generate_sd, state="disabled", fg_color="#5bc0de", hover_color="#46b8da")
        self.generate_sd_button.grid(row=0, column=2, padx=5, pady=2)
        self.sd_gen_status_label = ctk.CTkLabel(gen_status_frame, text="", text_color="gray", anchor="w")
        self.sd_gen_status_label.grid(row=0, column=3, padx=(0, 10), sticky="w")

        # GPT-SoVITS 语音生成
        self.generate_audio_button = ctk.CTkButton(gen_status_frame, text="生成语音 (GPT-SoVITS)", command=self.run_generate_audio, state="disabled", fg_color="#5cb85c", hover_color="#4cae4c") # 绿色系
        self.generate_audio_button.grid(row=0, column=4, padx=5, pady=2)
        self.audio_gen_status_label = ctk.CTkLabel(gen_status_frame, text="", text_color="gray", anchor="w")
        self.audio_gen_status_label.grid(row=0, column=5, padx=(0, 10), sticky="w")

        # --- 新增：保存 KAG 脚本按钮 ---
        # 将保存按钮放在 step4_controls 的最右侧
        self.save_ks_button = ctk.CTkButton(step4_controls, text="保存 KAG 脚本 (.ks)", command=self.save_kag_script, state="disabled")
        self.save_ks_button.pack(side="right", padx=(10, 0)) # 使用 pack 放在右侧


        # --- 绑定事件 ---
        key_release_widgets = [
            self.novel_text_widget,
            self.structured_text_widget,
            self.enhanced_text_widget,
            self.kag_script_widget
        ]
        for widget in key_release_widgets:
             if widget:
                 try:
                     widget.bind("<KeyRelease>", self.update_button_states)
                 except Exception as bind_e:
                     print(f"警告：绑定 KeyRelease 到 {type(widget).__name__} 出错: {bind_e}")

    def toggle_specific_images_entry(self):
        """根据图片范围选择启用/禁用指定图片输入框"""
        if self.img_gen_scope_var.get() == "specific":
            self.specific_images_entry.configure(state="normal")
        else:
            self.specific_images_entry.configure(state="disabled")
            self.specific_images_var.set("")

    def toggle_specific_speakers_entry(self):
        """根据语音范围选择启用/禁用指定说话人输入框"""
        if self.audio_gen_scope_var.get() == "specific":
            self.specific_speakers_entry.configure(state="normal")
        else:
            self.specific_speakers_entry.configure(state="disabled")
            self.specific_speakers_var.set("")


    def update_ui_element(self, element, text=None, state=None, text_color=None, append=False):
        """
        安全地更新 UI 元素 (设计为在主线程中调用)。
        可以更新文本、状态、文本颜色，并支持向文本框追加文本。
        **修正：** 移除对 CTkTextbox 的 cget("state") 调用。
        """
        if not element or not element.winfo_exists():
            return
        try:
            configure_options = {} # 收集 configure() 支持的选项

            # --- 更新文本 ---
            if text is not None:
                if isinstance(element, (ctk.CTkLabel, ctk.CTkButton)):
                    configure_options["text"] = text
                elif isinstance(element, ctk.CTkTextbox):
                    # CTkTextbox 的文本更新需要特殊处理，不通过 configure
                    try:
                        # **修正：直接尝试修改，不再检查 state**
                        # 假设 Textbox 状态为 normal (由 build_ui 保证)
                        if not append:
                            element.delete("1.0", "end")
                        element.insert("end", text)
                        element.see("end")
                    except Exception as textbox_e:
                        # 捕获修改时可能发生的 Tkinter 错误
                        print(f"错误: 修改 CTkTextbox 内容时出错 ({type(textbox_e).__name__}): {textbox_e}")
                        traceback.print_exc()
                    text = None # 标记文本已处理

            # --- 更新状态 ---
            # 仅对支持 state 配置的非 Textbox 控件设置 state
            if state is not None and hasattr(element, 'configure') and not isinstance(element, ctk.CTkTextbox):
                # 注意：这里没有检查控件是否真的支持 'state'，依赖于调用者正确使用
                # 并且，如果任务正在运行，强制禁用
                actual_state = state if not self.task_running else "disabled"
                configure_options["state"] = actual_state

            # --- 更新文本颜色 (主要用于 Label) ---
            if text_color is not None and isinstance(element, ctk.CTkLabel):
                configure_options["text_color"] = text_color

            # --- 应用 configure() 支持的更新 ---
            if configure_options and hasattr(element, 'configure'):
                element.configure(**configure_options)

        except Exception as e:
            print(f"更新 UI 元素 '{type(element).__name__}' 时发生未预期的错误: {e}")
            traceback.print_exc()

    def check_queue(self):
        """定时检查结果队列，并根据收到的消息更新 UI (处理流式和非流式)"""
        try:
            while not self.result_queue.empty():
                # 从队列中获取一个任务结果
                task_id, status, result_type, result_data, update_target, status_label = self.result_queue.get_nowait()
                print(f"从队列收到结果: ID={task_id}, Status={status}, Type={result_type}")

                # --- 更新状态标签 ---
                if status_label:
                    # 根据状态决定颜色
                    color = "green" if status == "success" else "red" if status == "error" else "orange"
                    message = ""
                    # 根据结果类型生成状态消息
                    if result_type == "task_update": # 用于步骤三内部状态更新
                        message = f"{task_id}: {result_data}"; color="orange"
                    elif result_type == "stream_chunk": message = f"{task_id}: 正在接收..."
                    elif result_type == "stream_done": message = f"{task_id}: 完成!"; color = "green"
                    elif result_type == "stream_error": message = f"{task_id}: 流错误: {result_data}"; color = "red"
                    elif result_type == "stream_warning": message = f"{task_id}: 警告: {result_data}"; color = "orange"
                    elif result_type == "non_stream":
                         # 非流式任务，成功显示完成，失败显示错误
                         message = f"{task_id}: 完成!" if status == "success" else f"{task_id}: 错误: {result_data}"
                         # 如果结果是字典且包含 'message' (例如图片/语音生成)，使用该消息
                         if isinstance(result_data, dict) and 'message' in result_data:
                             message = f"{task_id}: {result_data['message']}"
                    else: message = f"{task_id}: {result_data}" # 其他未知类型

                    # 限制显示长度，避免过长消息撑爆 UI
                    max_len = 100; display_message = message if len(message) <= max_len else message[:max_len-3] + "..."
                    # 更新状态标签的文本和颜色
                    self.update_ui_element(status_label, text=display_message, text_color=color)
                    # 如果任务已结束 (非 task_update)，则 8 秒后清除状态标签
                    if result_type in ["stream_done", "stream_error", "non_stream"]:
                        self.after(8000, lambda lbl=status_label: self.update_ui_element(lbl, text="", text_color="gray"))

                # --- 更新目标文本框 ---
                if update_target:
                     # 处理流式块 (只可能来自 KAG 转换阶段)
                     if result_type == "stream_chunk" and isinstance(result_data, str):
                         # 追加文本到目标文本框
                         self.update_ui_element(update_target, text=result_data, append=True)
                     # 处理非流式成功结果 或 流式完成信号
                     elif (result_type == "non_stream" and status == "success" and isinstance(result_data, str)) or \
                          (result_type == "stream_done" and status == "success"):

                         # 如果是流式完成，需要从 update_target (文本框) 获取完整文本
                         # 如果是非流式，result_data 就是完整文本
                         final_result = result_data if result_type == "non_stream" else update_target.get("1.0", "end-1c")

                         processed_result = final_result # 默认使用获取到的结果

                         # --- 步骤三 KAG 格式后处理 ---
                         # 检查是否是步骤三的最终结果 (无论是流式完成还是非流式成功)
                         # 并且目标是 KAG 脚本框
                         if task_id.startswith("步骤三") and update_target == self.kag_script_widget:
                             print("步骤三最终结果到达，调用 KAG 格式后处理 (utils)...")
                             try:
                                 # 调用 utils 中的后处理函数
                                 processed_result = self.utils.post_process_kag_script(final_result)
                             except Exception as post_proc_e:
                                 # 如果后处理出错，打印错误但继续使用未处理的结果
                                 print(f"错误：调用 KAG 格式后处理失败: {post_proc_e}")
                                 traceback.print_exc()
                             # --- 后处理结束 ---
                             print("步骤三 KAG 脚本准备更新 UI...")
                             # 触发后续的占位符替换 (在 UI 更新后稍作延迟)
                             print("步骤三成功，延迟调用占位符替换...")
                             self.after(50, lambda: self.manual_replace_placeholders(auto_called=True))
                         # --- KAG 后处理结束 ---

                         # 使用最终处理后的结果更新 UI (替换，非追加)
                         self.update_ui_element(update_target, text=processed_result, append=False)

                # --- 处理图片/语音生成任务的特殊结果 ---
                # 使用 image_generation_tasks.task_generate_images 或 audio_generation_tasks.task_generate_audio 返回的 task_id
                if task_id in ["NAI 图片生成", "SD 图片生成", "GPT-SoVITS 语音生成"] and status == "success" and result_type == "non_stream":
                     if isinstance(result_data, dict):
                         # 如果返回了修改后的 KAG 脚本，更新 KAG 文本框
                         if "modified_script" in result_data:
                             print(f"{task_id} 检测到修改后的 KAG 脚本...")
                             self.update_ui_element(self.kag_script_widget, text=result_data["modified_script"], append=False)
                         # 打印详细日志
                         if "details" in result_data:
                             print(f"--- {task_id} 详细日志 ---")
                             for detail_line in result_data.get("details", []):
                                 print(detail_line)
                             print(f"--- {task_id} 日志结束 ---")

                # --- 任务结束处理 (不包括 task_update) ---
                if result_type in ["stream_done", "stream_error", "non_stream"]:
                    if status in ["success", "error"]:
                        # --- 播放声音 ---
                        sound_key = "successSoundPath" if status == "success" else "failureSoundPath"
                        llm_config_sound = self.app.get_llm_config()
                        sound_path = llm_config_sound.get(sound_key, "") if llm_config_sound else ""
                        if sound_path:
                            print(f"准备播放声音: {sound_path}")
                            # 在单独线程播放声音，避免阻塞 UI
                            sound_thread = threading.Thread(target=self.sound_player.play_sound, args=(sound_path,), daemon=True)
                            sound_thread.start()

                        # --- 发送 Windows 通知 ---
                        if WINDOWS_NOTIFICATIONS_AVAILABLE and toaster:
                            title = f"任务完成: {task_id}" if status == "success" else f"任务失败: {task_id}"
                            # 准备通知消息
                            notify_message = f"{task_id} 处理完成."
                            max_msg_len = 150 # 限制消息长度
                            # 尝试从结果中获取更具体的消息
                            if isinstance(result_data, str):
                                notify_message = result_data
                            elif isinstance(result_data, dict) and 'message' in result_data:
                                notify_message = result_data['message']
                            # 截断过长的消息
                            notify_message = notify_message if len(notify_message) <= max_msg_len else notify_message[:max_msg_len-3] + "..."
                            try:
                                # 显示通知
                                toaster.show_toast(
                                    title,
                                    notify_message,
                                    duration=7, # 显示 7 秒
                                    threaded=True, # 在单独线程显示
                                    icon_path=None # 可选：指定图标路径
                                )
                                print(f"已发送 Windows 通知: {title}")
                            except Exception as notify_e:
                                # 处理发送通知时可能发生的错误
                                print(f"发送 Windows 通知时出错: {notify_e}")
                                traceback.print_exc()

                    # 标记任务结束，重新启用按钮
                    self.task_running = False
                    self.update_button_states()
                    print(f"任务 {task_id} 处理完毕/出错。")

        except Empty:
            # 队列为空，是正常情况，直接跳过
            pass
        except Exception as e:
            # 捕获检查队列或更新 UI 过程中的其他所有错误
            print(f"检查队列或更新 UI 时出错: {e}")
            traceback.print_exc()
            # 发生错误时，也应该重置任务状态，允许用户重试
            self.task_running = False
            self.update_button_states()
        finally:
            # 无论如何，100ms 后再次安排检查队列的任务
            self.after(100, self.check_queue)

    def run_task_in_thread(self, task_func, task_id, update_target_widget, status_label_widget, args=(), is_stream_hint=False):
        """在后台线程中运行指定的任务函数"""
        # 防止同时运行多个任务
        if self.task_running:
            messagebox.showwarning("任务进行中", "请等待当前任务完成。", parent=self)
            return
        print(f"准备启动后台任务: {task_id} (流式提示: {is_stream_hint})")
        self.task_running = True # 标记任务开始
        self.update_button_states() # 禁用按钮
        # 更新状态标签为处理中
        if status_label_widget:
            self.update_ui_element(status_label_widget, text=f"{task_id}: 处理中...", text_color="orange")
        # 清空目标文本框 (如果是文本框)
        if update_target_widget and isinstance(update_target_widget, ctk.CTkTextbox):
            self.update_ui_element(update_target_widget, text="", append=False)

        # 创建并启动后台线程
        # daemon=True 意味着主程序退出时，这些线程也会被强制结束
        thread = threading.Thread(target=self._thread_wrapper, args=(task_func, task_id, update_target_widget, status_label_widget, args, is_stream_hint), daemon=True)
        thread.start()
        print(f"后台线程已启动: {task_id}")

    def _thread_wrapper(self, task_func, task_id, update_target_widget, status_label_widget, args, is_stream_hint):
        """后台线程实际执行的包装函数，处理任务逻辑并将结果放入队列"""
        try:
            print(f"线程开始执行: {task_id} (流式提示: {is_stream_hint})")

            # --- 特殊处理：步骤三 (BGM+KAG) ---
            if task_id == "步骤三 (BGM+KAG)":
                # 解包从 run_step3_convert 传来的参数
                api_helpers, prompt_templates, llm_config, enhanced_text = args
                # 检查用户是否在 LLM 设置中启用了流式传输
                use_final_stream = llm_config.get("enableStreaming", True)

                # --- 阶段 1: 添加 BGM 建议 (此阶段强制非流式) ---
                # 发送一个中间状态更新到主线程
                self.result_queue.put((task_id, "processing", "task_update", "正在添加 BGM 建议...", None, status_label_widget))
                # 调用 BGM 建议任务函数 (从 workflow_tasks 导入)
                text_with_suggestions, bgm_error = workflow_tasks.task_llm_suggest_bgm(
                    api_helpers, prompt_templates, llm_config, enhanced_text
                )
                # 检查阶段 1 是否出错
                if bgm_error:
                    # 如果出错，将错误信息放入队列并结束线程
                    self.result_queue.put((task_id, "error", "non_stream", f"添加 BGM 建议失败: {bgm_error}", update_target_widget, status_label_widget))
                    return
                if not text_with_suggestions:
                    # 如果结果为空（理论上不应发生除非出错），也视为错误
                    self.result_queue.put((task_id, "error", "non_stream", "添加 BGM 建议时返回空结果。", update_target_widget, status_label_widget))
                    return

                # --- 阶段 2: 转换 KAG (根据配置决定流式/非流式) ---
                # 发送另一个中间状态更新
                self.result_queue.put((task_id, "processing", "task_update", "正在转换 KAG 脚本...", None, status_label_widget))
                # 提取代理配置
                proxy_config = {k: llm_config.get(k) for k in ["use_proxy", "proxy_address", "proxy_port"]}
                # 构建 KAG 转换的 Prompt
                kag_prompt = prompt_templates.KAG_CONVERSION_PROMPT_TEMPLATE.format(
                    pre_instruction=llm_config.get('preInstruction',''),
                    post_instruction=llm_config.get('postInstruction',''),
                    text_chunk_with_suggestions=text_with_suggestions # 使用阶段 1 的输出作为输入
                )

                # 根据用户配置决定执行流式还是非流式 KAG 转换
                if use_final_stream:
                    # --- 执行流式 KAG 转换 ---
                    print(f"[{task_id}] 执行流式 KAG 转换...")
                    stream_finished_normally = False
                    # 调用流式 API 助手 (通过 facade)
                    for status, data in api_helpers.stream_google_response(
                        llm_config.get('apiKey'), llm_config.get('apiEndpoint'), llm_config.get('modelName'),
                        kag_prompt, llm_config.get('temperature'), llm_config.get('maxOutputTokens'),
                        "KAGConversion", proxy_config # 任务类型标识
                    ):
                        # 将流事件转发到主线程队列，使用原始 task_id
                        if status == "chunk": self.result_queue.put((task_id, "success", "stream_chunk", data, update_target_widget, status_label_widget))
                        elif status == "error": self.result_queue.put((task_id, "error", "stream_error", data, update_target_widget, status_label_widget)); return # 出错则结束
                        elif status == "warning": self.result_queue.put((task_id, "warning", "stream_warning", data, update_target_widget, status_label_widget))
                        elif status == "done": self.result_queue.put((task_id, "success", "stream_done", data, update_target_widget, status_label_widget)); stream_finished_normally = True; return # 完成则结束
                        else: self.result_queue.put((task_id, "warning", "stream_warning", f"未知状态: {status}", update_target_widget, status_label_widget)) # 未知状态视为警告
                    # 如果流结束但没有收到 "done" 信号 (异常情况)
                    if not stream_finished_normally:
                        print(f"警告 ({task_id}): KAG 流结束但无 'done' 信号。")
                        # 仍然发送完成信号，以便 UI 知道任务结束
                        self.result_queue.put((task_id, "success", "stream_done", f"{task_id}: 处理完成", update_target_widget, status_label_widget))
                else:
                    # --- 执行非流式 KAG 转换 ---
                    print(f"[{task_id}] 执行非流式 KAG 转换...")
                    # 调用非流式 KAG 转换任务函数 (从 workflow_tasks 导入)
                    final_kag, kag_error = workflow_tasks.task_llm_convert_to_kag(
                        api_helpers, prompt_templates, llm_config, text_with_suggestions
                    )
                    # 根据结果准备状态和数据
                    status = "error" if kag_error else "success"
                    result_data = kag_error if kag_error else final_kag
                    # 将最终结果放入队列
                    self.result_queue.put((task_id, status, "non_stream", result_data, update_target_widget, status_label_widget))

            # --- 处理普通流式任务 (例如步骤一、二如果启用流式) ---
            elif is_stream_hint:
                stream_finished_normally = False
                # task_func 此时是 api_helpers.stream_google_response (通过 facade)
                for status, data in task_func(*args):
                    if status == "chunk": self.result_queue.put((task_id, "success", "stream_chunk", data, update_target_widget, status_label_widget))
                    elif status == "error": self.result_queue.put((task_id, "error", "stream_error", data, update_target_widget, status_label_widget)); return
                    elif status == "warning": self.result_queue.put((task_id, "warning", "stream_warning", data, update_target_widget, status_label_widget))
                    elif status == "done": self.result_queue.put((task_id, "success", "stream_done", data, update_target_widget, status_label_widget)); stream_finished_normally = True; return
                    else: self.result_queue.put((task_id, "warning", "stream_warning", f"未知状态: {status}", update_target_widget, status_label_widget))
                if not stream_finished_normally:
                    print(f"警告 ({task_id}): 流结束但无 'done' 信号。")
                    self.result_queue.put((task_id, "success", "stream_done", f"{task_id}: 处理完成", update_target_widget, status_label_widget))

            # --- 处理普通非流式任务 (图片/语音生成, 或步骤一、二如果禁用流式) ---
            else:
                # task_func 此时是 workflow_tasks, image_generation_tasks 或 audio_generation_tasks 里的某个非流式任务函数
                result, error = task_func(*args)
                status = "error" if error else "success"
                result_data = error if error else result
                self.result_queue.put((task_id, status, "non_stream", result_data, update_target_widget, status_label_widget))

            # 线程正常执行完毕
            print(f"线程正常完成: {task_id}")
        except Exception as e:
            # 捕获线程执行过程中的任何未捕获异常
            print(f"线程 '{task_id}' 发生未捕获错误: {e}")
            traceback.print_exc()
            # 将错误信息放入队列，以便 UI 知道任务失败
            error_type = "stream_error" if is_stream_hint else "non_stream" # 根据提示判断错误类型
            self.result_queue.put((task_id, "error", error_type, f"线程内部错误: {e}", update_target_widget, status_label_widget))

    # --- 步骤回调函数 ---

    def run_step1_preprocess(self):
        """触发步骤一：格式化（支持流式/非流式）"""
        novel_text = self.novel_text_widget.get("1.0", "end-1c").strip()
        llm_config = self.app.get_llm_config()
        # 输入和配置检查
        if not novel_text: messagebox.showwarning("输入缺失", "请输入原始小说原文！", parent=self); return
        if not llm_config or not all(k in llm_config for k in ['apiKey', 'apiEndpoint', 'modelName']): messagebox.showerror("配置错误", "请先在 'LLM 与全局设置' 标签页中配置 LLM！", parent=self); return

        # 准备代理和 Prompt
        proxy_config = {k: llm_config.get(k) for k in ["use_proxy", "proxy_address", "proxy_port"]}
        use_stream = llm_config.get("enableStreaming", True)
        prompt = self.app.prompt_templates.PREPROCESSING_PROMPT_TEMPLATE.format(
            pre_instruction=llm_config.get('preInstruction',''),
            post_instruction=llm_config.get('postInstruction',''),
            text_chunk=novel_text
        )

        # 根据配置选择流式或非流式执行
        if use_stream:
            print("步骤一：使用流式")
            task_id = "步骤一 (流式)"
            task_func = self.api_helpers.stream_google_response # 目标函数是流式助手 (通过 facade)
            args = (
                llm_config.get('apiKey'), llm_config.get('apiEndpoint'), llm_config.get('modelName'),
                prompt, llm_config.get('temperature'), llm_config.get('maxOutputTokens'),
                "Preprocessing", proxy_config # 任务类型标识
            )
            is_stream = True
        else:
            print("步骤一：使用非流式")
            task_id = "步骤一 (非流式)"
            task_func = workflow_tasks.task_llm_preprocess # 目标函数是任务文件中的函数
            args = (self.api_helpers, self.app.prompt_templates, llm_config, novel_text) # 传递依赖
            is_stream = False

        # 启动后台任务
        self.run_task_in_thread(task_func, task_id, self.structured_text_widget, self.step1_status_label, args=args, is_stream_hint=is_stream)

    def run_step2_enhance(self):
        """触发步骤二：添加提示词（支持流式/非流式）"""
        formatted_text = self.structured_text_widget.get("1.0", "end-1c").strip()
        llm_config = self.app.get_llm_config()
        profiles_json = self.app.get_profiles_json() # 获取人物设定
        # 输入和配置检查
        if not formatted_text: messagebox.showwarning("输入缺失", "步骤一结果 (格式化文本) 不能为空！", parent=self); return
        if not llm_config or not all(k in llm_config for k in ['apiKey', 'apiEndpoint', 'modelName']): messagebox.showerror("配置错误", "请先在 'LLM 与全局设置' 标签页中配置 LLM！", parent=self); return
        if profiles_json is None:
            # get_profiles_json 内部会处理 None 和弹出警告
            print("步骤二取消：人物设定 JSON 无效或为空。")
            return

        # 准备代理和 Prompt
        proxy_config = {k: llm_config.get(k) for k in ["use_proxy", "proxy_address", "proxy_port"]}
        use_stream = llm_config.get("enableStreaming", True)
        prompt = self.app.prompt_templates.PROMPT_ENHANCEMENT_TEMPLATE.format(
            pre_instruction=llm_config.get('preInstruction',''),
            post_instruction=llm_config.get('postInstruction',''),
            character_profiles_json=profiles_json,
            formatted_text_chunk=formatted_text
        )

        # 根据配置选择流式或非流式执行
        if use_stream:
            print("步骤二：使用流式")
            task_id = "步骤二 (流式)"
            task_func = self.api_helpers.stream_google_response # 通过 facade
            args = (
                llm_config.get('apiKey'), llm_config.get('apiEndpoint'), llm_config.get('modelName'),
                prompt, llm_config.get('temperature'), llm_config.get('maxOutputTokens'),
                "PromptEnhancement", proxy_config
            )
            is_stream = True
        else:
            print("步骤二：使用非流式")
            task_id = "步骤二 (非流式)"
            task_func = workflow_tasks.task_llm_enhance # 从 workflow_tasks 导入
            args = (self.api_helpers, self.app.prompt_templates, llm_config, formatted_text, profiles_json)
            is_stream = False

        # 启动后台任务
        self.run_task_in_thread(task_func, task_id, self.enhanced_text_widget, self.step2_status_label, args=args, is_stream_hint=is_stream)

    def run_step3_convert(self):
        """触发步骤三：建议 BGM 并转换 KAG（KAG 转换阶段支持流式）"""
        enhanced_text = self.enhanced_text_widget.get("1.0", "end-1c").strip()
        llm_config = self.app.get_llm_config()
        # 输入和配置检查
        if not enhanced_text: messagebox.showwarning("输入缺失", "步骤二结果 (含提示标记) 不能为空！", parent=self); return
        if not llm_config or not all(k in llm_config for k in ['apiKey', 'apiEndpoint', 'modelName']): messagebox.showerror("配置错误", "请先在 'LLM 与全局设置' 标签页中配置 LLM！", parent=self); return

        # 准备参数
        task_id = "步骤三 (BGM+KAG)" # 新的任务 ID，表明是组合任务
        # 这些参数将被传递给 _thread_wrapper，由它内部处理两个阶段
        args = (self.api_helpers, self.app.prompt_templates, llm_config, enhanced_text)

        print(f"运行 {task_id}...")
        # 启动后台任务
        # is_stream_hint 设为 False，因为整个任务包含非流式部分
        # _thread_wrapper 内部会根据配置决定 KAG 转换阶段是否流式
        self.run_task_in_thread(
            None, # task_func 设为 None，因为 _thread_wrapper 会处理特殊 task_id
            task_id,
            self.kag_script_widget, # 最终结果更新到 KAG 脚本框
            self.step3_status_label, # 状态标签
            args=args,
            is_stream_hint=False # 标记整个任务不是单一流式
        )

    def manual_replace_placeholders(self, auto_called=False):
        """手动或自动触发替换 KAG 脚本中的图片占位符"""
        print(f"请求替换图片占位符 (自动调用: {auto_called})...")
        kag_script = self.kag_script_widget.get("1.0", "end-1c")
        # 检查脚本是否为空
        if not kag_script or not kag_script.strip():
            if not auto_called: # 只有手动点击时才提示
                messagebox.showwarning("无内容", "KAG 脚本内容为空，无法替换图片占位符。", parent=self)
            print("替换中止：KAG 脚本为空。")
            return
        # 获取图片前缀
        prefix = self.image_prefix_var.get().strip()
        print(f"使用图片前缀: '{prefix}'")
        try:
            # 调用 utils 中的替换函数
            processed_script, replacements_made = self.utils.replace_kag_placeholders(kag_script, prefix)
            # 更新 KAG 脚本框
            self.update_ui_element(self.kag_script_widget, text=processed_script, append=False)
            # 更新状态标签
            if self.image_replace_status_label:
                status_text = f"已替换 {replacements_made} 个图片占位符。" if replacements_made > 0 else "未找到可替换的图片占位符。"
                color = "green" if replacements_made > 0 else "gray"
                self.update_ui_element(self.image_replace_status_label, text=status_text, text_color=color)
                # 5 秒后清除状态
                self.after(5000, lambda: self.update_ui_element(self.image_replace_status_label, text="", text_color="gray"))
        except Exception as e:
            # 处理替换过程中可能发生的错误
            print(f"替换图片占位符时出错: {e}")
            traceback.print_exc()
            messagebox.showerror("替换错误", f"替换图片占位符时发生错误:\n{e}", parent=self)
            # 更新状态标签显示错误
            if self.image_replace_status_label:
                self.update_ui_element(self.image_replace_status_label, text="图片替换出错!", text_color="red")
                self.after(5000, lambda: self.update_ui_element(self.image_replace_status_label, text="", text_color="gray"))

    def run_generate_nai(self):
        """触发 NAI 图片生成任务"""
        kag_script = self.kag_script_widget.get("1.0", "end-1c").strip()
        nai_config = self.app.get_nai_config()
        # 输入和配置检查
        if not kag_script: messagebox.showwarning("无脚本", "KAG 脚本内容为空，无法生成图片。", parent=self); return
        if not nai_config or not all(k in nai_config for k in ['naiApiKey', 'naiImageSaveDir']) or not nai_config['naiApiKey'] or not nai_config['naiImageSaveDir']:
            messagebox.showerror("配置错误", "请先在 'NAI 设置' 标签页中完整配置 NAI API Key 和图片保存目录！", parent=self); return
        # 获取生成选项
        gen_options = {
            "scope": self.img_gen_scope_var.get(),
            "specific_files": self.specific_images_var.get() if self.img_gen_scope_var.get() == 'specific' else "",
            "n_samples": self.img_n_samples_var.get() or 1 # 确保至少为 1
        }
        # 启动后台任务 (图片生成总是非流式)
        self.run_task_in_thread(
            image_generation_tasks.task_generate_images, # 从新模块导入
            "NAI 图片生成", # 任务 ID
            None, # 图片生成不直接更新文本框
            self.nai_gen_status_label, # 状态标签
            args=(self.api_helpers, "NAI", nai_config, kag_script, gen_options), # 传递依赖和参数
            is_stream_hint=False # 非流式
        )

    def run_generate_sd(self):
        """触发 SD 图片生成任务"""
        kag_script = self.kag_script_widget.get("1.0", "end-1c").strip()
        sd_config = self.app.get_sd_config()
        # 输入和配置检查
        if not kag_script: messagebox.showwarning("无脚本", "KAG 脚本内容为空，无法生成图片。", parent=self); return
        if not sd_config or not all(k in sd_config for k in ['sdWebUiUrl', 'sdImageSaveDir']) or not sd_config['sdWebUiUrl'] or not sd_config['sdImageSaveDir']:
            messagebox.showerror("配置错误", "请先在 'SD WebUI 设置' 标签页中完整配置 WebUI API 地址和图片保存目录！", parent=self); return
        # 获取生成选项
        gen_options = {
            "scope": self.img_gen_scope_var.get(),
            "specific_files": self.specific_images_var.get() if self.img_gen_scope_var.get() == 'specific' else "",
            "n_samples": self.img_n_samples_var.get() or 1 # 确保至少为 1
        }
        # 启动后台任务 (图片生成总是非流式)
        self.run_task_in_thread(
            image_generation_tasks.task_generate_images, # 从新模块导入
            "SD 图片生成", # 任务 ID
            None, # 图片生成不直接更新文本框
            self.sd_gen_status_label, # 状态标签
            args=(self.api_helpers, "SD", sd_config, kag_script, gen_options), # 传递依赖和参数
            is_stream_hint=False # 非流式
        )

    def run_generate_audio(self):
        """触发 GPT-SoVITS 语音生成任务"""
        kag_script = self.kag_script_widget.get("1.0", "end-1c").strip()
        gptsovits_config = self.app.get_gptsovits_config()
        audio_prefix = self.audio_prefix_var.get().strip() # 获取音频前缀

        # 输入和配置检查
        if not kag_script: messagebox.showwarning("无脚本", "KAG 脚本内容为空，无法生成语音。", parent=self); return
        if not gptsovits_config or \
           not gptsovits_config.get('apiUrl') or \
           not gptsovits_config.get('audioSaveDir') or \
           gptsovits_config.get('character_voice_map') is None: # 检查映射是否存在
            messagebox.showerror("配置错误", "请先在 'GPT-SoVITS 设置' 标签页中完整配置 API 地址、音频保存目录和人物语音映射！", parent=self); return
        if not gptsovits_config.get('character_voice_map'):
             messagebox.showwarning("配置警告", "人物语音映射为空，无法生成任何语音。请先配置映射。", parent=self); return

        # 获取生成选项
        gen_options = {
            "scope": self.audio_gen_scope_var.get(),
            "specific_speakers": self.specific_speakers_var.get() if self.audio_gen_scope_var.get() == 'specific' else "",
            # "n_samples": 1 # 语音通常只生成1个
        }

        # 启动后台任务 (语音生成总是非流式)
        self.run_task_in_thread(
            audio_generation_tasks.task_generate_audio, # 从新模块导入
            "GPT-SoVITS 语音生成", # 任务 ID
            None, # 语音生成不直接更新文本框 (结果通过修改脚本体现)
            self.audio_gen_status_label, # 状态标签
            args=(self.api_helpers, gptsovits_config, kag_script, audio_prefix, gen_options), # 传递依赖和参数
            is_stream_hint=False # 非流式
        )

    # --- 新增：保存 KAG 脚本方法 ---
    def save_kag_script(self):
        """将 KAG 脚本编辑区的内容保存为 .ks 文件 (UTF-16 LE 带 BOM)"""
        print("请求保存 KAG 脚本...")
        kag_script_content = self.kag_script_widget.get("1.0", "end-1c")

        if not kag_script_content or not kag_script_content.strip():
            messagebox.showwarning("无内容", "KAG 脚本内容为空，无法保存。", parent=self)
            print("保存中止：KAG 脚本为空。")
            return

        try:
            # 弹出文件保存对话框
            filepath = filedialog.asksaveasfilename(
                title="保存 KAG 脚本",
                defaultextension=".ks",
                filetypes=[("KAG 脚本", "*.ks"), ("所有文件", "*.*")],
                initialfile="scene1.ks", # 默认文件名
                parent=self
            )

            if not filepath:
                print("用户取消保存。")
                return

            # --- 关键：使用二进制模式写入，并手动添加 UTF-16 LE BOM ---
            with open(filepath, 'wb') as f: # 使用 'wb' 二进制写入模式
                # 写入 UTF-16 Little Endian 的 BOM (0xFF, 0xFE)
                f.write(codecs.BOM_UTF16_LE)
                # 将字符串内容编码为 UTF-16 LE 字节流并写入
                f.write(kag_script_content.encode('utf-16-le'))

            print(f"KAG 脚本已成功保存到 (UTF-16 LE with BOM): {filepath}")
            messagebox.showinfo("保存成功", f"KAG 脚本已成功保存为 (UTF-16 LE with BOM):\n{filepath}", parent=self)
            # 更新状态标签 (可选)
            if self.step3_status_label:
                self.update_ui_element(self.step3_status_label, text=f"已保存: {os.path.basename(filepath)}", text_color="green")
                self.after(5000, lambda: self.update_ui_element(self.step3_status_label, text="", text_color="gray"))

        except IOError as e:
            print(f"保存 KAG 脚本时发生 IO 错误: {e}")
            traceback.print_exc()
            messagebox.showerror("保存错误", f"写入文件时发生错误:\n{e}", parent=self)
        except Exception as e:
            print(f"保存 KAG 脚本时发生意外错误: {e}")
            traceback.print_exc()
            messagebox.showerror("保存错误", f"保存 KAG 脚本时发生意外错误:\n{e}", parent=self)
    # --- 保存 KAG 脚本方法结束 ---


    def update_button_states(self, event=None):
        """根据文本框内容、配置和任务状态更新按钮的启用/禁用状态"""
        # 检查所需控件是否存在
        required_widget_names = [
            'preprocess_button', 'enhance_button', 'convert_button',
            'replace_placeholder_button', 'generate_nai_button', 'generate_sd_button',
            'generate_audio_button', 'save_ks_button', # <-- 添加 save_ks_button
            'novel_text_widget', 'structured_text_widget', 'enhanced_text_widget', 'kag_script_widget'
        ]
        all_widgets_exist = all(
            hasattr(self, name) and getattr(self, name) and getattr(self, name).winfo_exists()
            for name in required_widget_names
        )
        if not all_widgets_exist:
            print("警告：尝试更新按钮状态时，部分 UI 控件尚未完全初始化。")
            return

        # 获取当前状态
        task_running = self.task_running
        # 检查各步骤的输入文本框是否有内容
        step1_ready = self.novel_text_widget.get("1.0", "end-1c").strip() != ""
        step2_ready = self.structured_text_widget.get("1.0", "end-1c").strip() != ""
        step3_ready = self.enhanced_text_widget.get("1.0", "end-1c").strip() != ""
        step4_ready = self.kag_script_widget.get("1.0", "end-1c").strip() != ""

        # 获取配置
        nai_config = self.app.get_nai_config()
        sd_config = self.app.get_sd_config()
        gptsovits_config = self.app.get_gptsovits_config() # 获取语音配置

        # 判断图片生成按钮是否可用
        nai_gen_ready = step4_ready and nai_config and \
                        nai_config.get('naiApiKey') and nai_config.get('naiImageSaveDir')
        sd_gen_ready = step4_ready and sd_config and \
                       sd_config.get('sdWebUiUrl') and sd_config.get('sdImageSaveDir')
        # 判断语音生成按钮是否可用
        audio_gen_ready = step4_ready and gptsovits_config and \
                          gptsovits_config.get('apiUrl') and gptsovits_config.get('audioSaveDir') and \
                          gptsovits_config.get('character_voice_map') # 检查映射是否非空

        # 更新按钮状态
        self.update_ui_element(self.preprocess_button, state="normal" if step1_ready and not task_running else "disabled")
        self.update_ui_element(self.enhance_button, state="normal" if step2_ready and not task_running else "disabled")
        self.update_ui_element(self.convert_button, state="normal" if step3_ready and not task_running else "disabled")
        self.update_ui_element(self.replace_placeholder_button, state="normal" if step4_ready and not task_running else "disabled")
        self.update_ui_element(self.generate_nai_button, state="normal" if nai_gen_ready and not task_running else "disabled")
        self.update_ui_element(self.generate_sd_button, state="normal" if sd_gen_ready and not task_running else "disabled")
        self.update_ui_element(self.generate_audio_button, state="normal" if audio_gen_ready and not task_running else "disabled") # 更新语音按钮状态
        # --- 新增：更新保存按钮状态 ---
        self.update_ui_element(self.save_ks_button, state="normal" if step4_ready and not task_running else "disabled")