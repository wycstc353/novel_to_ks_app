# ui_tabs/workflow_tab.py
import customtkinter as ctk
from tkinter import StringVar, messagebox, IntVar, Text # 使用标准 tkinter 的 messagebox 和 Text
from queue import Queue, Empty # 用于线程间通信，导入 Empty 异常
import threading # 用于后台任务
import json
import traceback
import base64
from pathlib import Path
import os
import re # 需要 re 来解析 KAG 脚本
import time # 需要 time.sleep
import zipfile # 需要 zipfile 来处理 NAI 返回的 zip
import io      # 需要 io 来处理内存中的 bytes

# 导入拆分出去的任务逻辑
import workflow_tasks

class WorkflowTab(ctk.CTkFrame):
    """核心转换流程的 UI 标签页"""
    def __init__(self, master, config_manager, api_helpers, utils, sound_player, app_instance):
        super().__init__(master, fg_color="transparent")
        self.config_manager = config_manager
        self.api_helpers = api_helpers
        self.utils = utils
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
        # **重要：确保用于接收结果的 Textbox 初始状态为 normal**
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
        # **重要：确保用于接收结果的 Textbox 初始状态为 normal**
        self.enhanced_text_widget = ctk.CTkTextbox(step3_frame, wrap="word", state="normal")
        self.enhanced_text_widget.grid(row=1, column=0, sticky="nsew")

        step3_controls = ctk.CTkFrame(self, fg_color="transparent")
        step3_controls.grid(row=5, column=0, sticky="ew", padx=10, pady=5)
        self.convert_button = ctk.CTkButton(step3_controls, text="第三步：转 KAG (生成占位符)", command=self.run_step3_convert, state="disabled") # 初始禁用
        self.convert_button.pack(side="left", padx=(0, 10))
        prefix_label = ctk.CTkLabel(step3_controls, text="图片前缀:")
        prefix_label.pack(side="left", padx=(10, 5))
        self.prefix_var = StringVar() # 用于存储图片文件名前缀
        prefix_entry = ctk.CTkEntry(step3_controls, textvariable=self.prefix_var, width=120)
        prefix_entry.pack(side="left")
        self.step3_status_label = ctk.CTkLabel(step3_controls, text="", text_color="gray", anchor="w")
        self.step3_status_label.pack(side="left", fill="x", expand=True, padx=(10, 0))

        # --- 步骤四：KAG 脚本输出 ---
        step4_frame = ctk.CTkFrame(self, fg_color="transparent")
        step4_frame.grid(row=6, column=0, sticky="nsew", padx=10, pady=5)
        step4_frame.grid_rowconfigure(1, weight=1)
        step4_frame.grid_columnconfigure(0, weight=1)

        step4_label = ctk.CTkLabel(step4_frame, text="步骤三结果 (KAG 脚本):", anchor="w")
        step4_label.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        # **重要：确保用于接收结果的 Textbox 初始状态为 normal**
        self.kag_script_widget = ctk.CTkTextbox(step4_frame, wrap="word", state="normal")
        self.kag_script_widget.grid(row=1, column=0, sticky="nsew")

        # --- 图片生成选项 ---
        gen_options_frame = ctk.CTkFrame(self, fg_color="transparent")
        gen_options_frame.grid(row=7, column=0, sticky="ew", padx=10, pady=5)
        gen_options_frame.grid_columnconfigure(3, weight=1) # 让指定图片输入框扩展

        self.gen_scope_var = StringVar(value="all") # 图片生成范围变量 (all 或 specific)
        scope_label = ctk.CTkLabel(gen_options_frame, text="生成范围:")
        scope_label.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="w")

        all_radio = ctk.CTkRadioButton(gen_options_frame, text="所有图片", variable=self.gen_scope_var, value="all", command=self.toggle_specific_images_entry)
        all_radio.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        specific_radio = ctk.CTkRadioButton(gen_options_frame, text="指定图片:", variable=self.gen_scope_var, value="specific", command=self.toggle_specific_images_entry)
        specific_radio.grid(row=0, column=2, padx=5, pady=5, sticky="w")

        self.specific_images_var = StringVar() # 存储指定图片文件名的变量
        self.specific_images_entry = ctk.CTkEntry(gen_options_frame, textvariable=self.specific_images_var, placeholder_text="输入文件名, 用逗号分隔", state="disabled") # 初始禁用
        self.specific_images_entry.grid(row=0, column=3, padx=5, pady=5, sticky="ew")

        # 每张图片生成数量选项
        n_samples_frame = ctk.CTkFrame(gen_options_frame, fg_color="transparent")
        n_samples_frame.grid(row=1, column=0, columnspan=4, pady=(0,5), sticky="w")
        n_samples_label = ctk.CTkLabel(n_samples_frame, text="每张生成数量:")
        n_samples_label.pack(side="left", padx=(0, 5))
        self.n_samples_var = IntVar(value=1) # 存储生成数量的变量
        n_samples_entry = ctk.CTkEntry(n_samples_frame, textvariable=self.n_samples_var, width=60)
        n_samples_entry.pack(side="left")

        # --- 步骤四 控制按钮 ---
        step4_controls = ctk.CTkFrame(self, fg_color="transparent")
        step4_controls.grid(row=8, column=0, sticky="ew", padx=10, pady=(5, 10))

        # 手动替换占位符按钮
        self.replace_placeholder_button = ctk.CTkButton(step4_controls, text="手动替换占位符", command=self.manual_replace_placeholders)
        self.replace_placeholder_button.pack(side="left", padx=(0, 10))
        self.image_replace_status_label = ctk.CTkLabel(step4_controls, text="", text_color="gray", anchor="w")
        self.image_replace_status_label.pack(side="left", padx=(0, 20))

        # 图片生成按钮区域
        gen_button_frame = ctk.CTkFrame(step4_controls, fg_color="transparent")
        gen_button_frame.pack(side="left", fill="x", expand=True)

        self.generate_nai_button = ctk.CTkButton(gen_button_frame, text="生成图片 (NAI)", command=self.run_generate_nai, state="disabled", fg_color="#f0ad4e", hover_color="#ec971f") # 初始禁用，橙色系
        self.generate_nai_button.pack(side="left", padx=5)
        self.nai_gen_status_label = ctk.CTkLabel(gen_button_frame, text="", text_color="gray", anchor="w")
        self.nai_gen_status_label.pack(side="left", padx=(0, 10))

        self.generate_sd_button = ctk.CTkButton(gen_button_frame, text="生成图片 (SD)", command=self.run_generate_sd, state="disabled", fg_color="#5bc0de", hover_color="#46b8da") # 初始禁用，蓝色系
        self.generate_sd_button.pack(side="left", padx=5)
        self.sd_gen_status_label = ctk.CTkLabel(gen_button_frame, text="", text_color="gray", anchor="w")
        self.sd_gen_status_label.pack(side="left", padx=(0, 10))

        # --- 绑定事件 ---
        # 绑定 KeyRelease 事件到文本框，用于实时更新按钮状态
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

        # 初始状态更新将由 main_app 通过 deferred_initial_updates 调用

    def toggle_specific_images_entry(self):
        """根据范围选择启用/禁用指定图片输入框"""
        if self.gen_scope_var.get() == "specific":
            self.specific_images_entry.configure(state="normal")
        else:
            self.specific_images_entry.configure(state="disabled")
            self.specific_images_var.set("")

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
                task_id, status, result_type, result_data, update_target, status_label = self.result_queue.get_nowait()
                print(f"从队列收到结果: ID={task_id}, Status={status}, Type={result_type}")
                if status_label:
                    color = "green" if status == "success" else "red" if status == "error" else "orange"
                    message = ""
                    if result_type == "stream_chunk": message = f"{task_id}: 正在接收..."
                    elif result_type == "stream_done": message = f"{task_id}: 完成!"; color = "green"
                    elif result_type == "stream_error": message = f"{task_id}: 流错误: {result_data}"; color = "red"
                    elif result_type == "stream_warning": message = f"{task_id}: 警告: {result_data}"; color = "orange"
                    elif result_type == "non_stream":
                         message = result_data if status != "success" else f"{task_id}: 完成!"
                         if isinstance(result_data, dict) and 'message' in result_data: message = f"{task_id}: {result_data['message']}"
                    else: message = f"{task_id}: {result_data}"
                    max_len = 100; display_message = message if len(message) <= max_len else message[:max_len-3] + "..."
                    self.update_ui_element(status_label, text=display_message, text_color=color)
                    if result_type in ["stream_done", "stream_error", "non_stream"]:
                        self.after(8000, lambda lbl=status_label: self.update_ui_element(lbl, text="", text_color="gray"))
                if update_target:
                     if result_type == "stream_chunk" and isinstance(result_data, str):
                         self.update_ui_element(update_target, text=result_data, append=True)
                     elif result_type == "non_stream" and status == "success" and isinstance(result_data, str):
                         self.update_ui_element(update_target, text=result_data, append=False)
                         if task_id.startswith("步骤三"):
                             print("步骤三成功，延迟调用占位符替换...")
                             self.after(50, lambda: self.manual_replace_placeholders(auto_called=True))
                if task_id in ["NAI 图片生成", "SD 图片生成"] and status == "success" and result_type == "non_stream":
                     if isinstance(result_data, dict):
                         if "modified_script" in result_data:
                             print(f"{task_id} 检测到修改后的 KAG 脚本...")
                             self.update_ui_element(self.kag_script_widget, text=result_data["modified_script"], append=False)
                         if "details" in result_data:
                             print(f"--- {task_id} 详细日志 ---"); [print(d) for d in result_data.get("details", [])]; print(f"--- {task_id} 日志结束 ---")
                if result_type in ["stream_done", "stream_error", "non_stream"]:
                    if status in ["success", "error"]:
                        sound_key = "successSoundPath" if status == "success" else "failureSoundPath"; llm_config_sound = self.app.get_llm_config(); sound_path = llm_config_sound.get(sound_key, "") if llm_config_sound else ""
                        if sound_path:
                            print(f"准备播放声音: {sound_path}"); sound_thread = threading.Thread(target=self.sound_player.play_sound, args=(sound_path,), daemon=True); sound_thread.start()
                    self.task_running = False; self.update_button_states(); print(f"任务 {task_id} 处理完毕/出错。")
        except Empty: pass
        except Exception as e: print(f"检查队列或更新 UI 时出错: {e}"); traceback.print_exc(); self.task_running = False; self.update_button_states()
        finally: self.after(100, self.check_queue)

    def run_task_in_thread(self, task_func, task_id, update_target_widget, status_label_widget, args=(), is_stream=False):
        """在后台线程中运行指定的任务函数"""
        if self.task_running:
            messagebox.showwarning("任务进行中", "请等待当前任务完成。", parent=self)
            return
        print(f"准备启动后台任务: {task_id} (流式: {is_stream})")
        self.task_running = True
        self.update_button_states()
        if status_label_widget:
            self.update_ui_element(status_label_widget, text=f"{task_id}: 处理中...", text_color="orange")
        if update_target_widget and isinstance(update_target_widget, ctk.CTkTextbox):
            self.update_ui_element(update_target_widget, text="", append=False)
        thread = threading.Thread(target=self._thread_wrapper, args=(task_func, task_id, update_target_widget, status_label_widget, args, is_stream), daemon=True)
        thread.start()
        print(f"后台线程已启动: {task_id}")

    def _thread_wrapper(self, task_func, task_id, update_target_widget, status_label_widget, args, is_stream):
        """后台线程实际执行的包装函数"""
        try:
            print(f"线程开始执行: {task_id} (流式: {is_stream})")
            if is_stream:
                stream_finished_normally = False
                for status, data in task_func(*args): # 流式任务直接迭代生成器
                    if status == "chunk": self.result_queue.put((task_id, "success", "stream_chunk", data, update_target_widget, status_label_widget))
                    elif status == "error": self.result_queue.put((task_id, "error", "stream_error", data, update_target_widget, status_label_widget)); return
                    elif status == "warning": self.result_queue.put((task_id, "warning", "stream_warning", data, update_target_widget, status_label_widget))
                    elif status == "done": self.result_queue.put((task_id, "success", "stream_done", data, update_target_widget, status_label_widget)); stream_finished_normally = True; return
                    else: self.result_queue.put((task_id, "warning", "stream_warning", f"未知状态: {status}", update_target_widget, status_label_widget))
                if not stream_finished_normally: print(f"警告 ({task_id}): 流结束但无 'done' 信号。"); self.result_queue.put((task_id, "success", "stream_done", f"{task_id}: 处理完成", update_target_widget, status_label_widget))
            else:
                # 非流式任务调用函数，期望返回 (result, error)
                result, error = task_func(*args)
                status = "error" if error else "success"; result_data = error if error else result
                self.result_queue.put((task_id, status, "non_stream", result_data, update_target_widget, status_label_widget))
            print(f"线程正常完成: {task_id}")
        except Exception as e: print(f"线程 '{task_id}' 发生未捕获错误: {e}"); traceback.print_exc(); error_type = "stream_error" if is_stream else "non_stream"; self.result_queue.put((task_id, "error", error_type, f"线程内部错误: {e}", update_target_widget, status_label_widget))

    # --- 步骤回调函数 ---

    def run_step1_preprocess(self):
        """触发步骤一：格式化（支持流式/非流式）"""
        novel_text = self.novel_text_widget.get("1.0", "end-1c").strip()
        llm_config = self.app.get_llm_config()
        if not novel_text: messagebox.showwarning("输入缺失", "请输入原始小说原文！", parent=self); return
        if not llm_config or not all(k in llm_config for k in ['apiKey', 'apiEndpoint', 'modelName']): messagebox.showerror("配置错误", "请先在 'LLM 与全局设置' 标签页中配置 LLM！", parent=self); return

        proxy_config = {k: llm_config.get(k) for k in ["use_proxy", "proxy_address", "proxy_port"]}
        use_stream = llm_config.get("enableStreaming", True)
        prompt = self.app.prompt_templates.PREPROCESSING_PROMPT_TEMPLATE.format(
            pre_instruction=llm_config.get('preInstruction',''),
            post_instruction=llm_config.get('postInstruction',''),
            text_chunk=novel_text
        )

        if use_stream:
            print("步骤一：使用流式")
            task_id = "步骤一 (流式)"
            task_func = self.api_helpers.stream_google_response
            args = (
                llm_config.get('apiKey'), llm_config.get('apiEndpoint'), llm_config.get('modelName'),
                prompt, llm_config.get('temperature'), llm_config.get('maxOutputTokens'),
                "Preprocessing", proxy_config
            )
            is_stream = True
        else:
            print("步骤一：使用非流式")
            task_id = "步骤一 (非流式)"
            task_func = workflow_tasks.task_llm_preprocess # 调用 workflow_tasks 中的函数
            args = (self.api_helpers, self.app.prompt_templates, llm_config, novel_text) # 传递依赖
            is_stream = False

        self.run_task_in_thread(task_func, task_id, self.structured_text_widget, self.step1_status_label, args=args, is_stream=is_stream)

    def run_step2_enhance(self):
        """触发步骤二：添加提示词（支持流式/非流式）"""
        formatted_text = self.structured_text_widget.get("1.0", "end-1c").strip()
        llm_config = self.app.get_llm_config()
        profiles_json = self.app.get_profiles_json()
        if not formatted_text: messagebox.showwarning("输入缺失", "步骤一结果 (格式化文本) 不能为空！", parent=self); return
        if not llm_config or not all(k in llm_config for k in ['apiKey', 'apiEndpoint', 'modelName']): messagebox.showerror("配置错误", "请先在 'LLM 与全局设置' 标签页中配置 LLM！", parent=self); return
        if profiles_json is None: return

        proxy_config = {k: llm_config.get(k) for k in ["use_proxy", "proxy_address", "proxy_port"]}
        use_stream = llm_config.get("enableStreaming", True)
        prompt = self.app.prompt_templates.PROMPT_ENHANCEMENT_TEMPLATE.format(
            pre_instruction=llm_config.get('preInstruction',''),
            post_instruction=llm_config.get('postInstruction',''),
            character_profiles_json=profiles_json,
            formatted_text_chunk=formatted_text
        )

        if use_stream:
            print("步骤二：使用流式")
            task_id = "步骤二 (流式)"
            task_func = self.api_helpers.stream_google_response
            args = (
                llm_config.get('apiKey'), llm_config.get('apiEndpoint'), llm_config.get('modelName'),
                prompt, llm_config.get('temperature'), llm_config.get('maxOutputTokens'),
                "PromptEnhancement", proxy_config
            )
            is_stream = True
        else:
            print("步骤二：使用非流式")
            task_id = "步骤二 (非流式)"
            task_func = workflow_tasks.task_llm_enhance # 调用 workflow_tasks 中的函数
            args = (self.api_helpers, self.app.prompt_templates, llm_config, formatted_text, profiles_json)
            is_stream = False

        self.run_task_in_thread(task_func, task_id, self.enhanced_text_widget, self.step2_status_label, args=args, is_stream=is_stream)

    def run_step3_convert(self):
        """触发步骤三：转换 KAG（支持流式/非流式）"""
        enhanced_text = self.enhanced_text_widget.get("1.0", "end-1c").strip()
        llm_config = self.app.get_llm_config()
        if not enhanced_text: messagebox.showwarning("输入缺失", "步骤二结果 (含提示标记) 不能为空！", parent=self); return
        if not llm_config or not all(k in llm_config for k in ['apiKey', 'apiEndpoint', 'modelName']): messagebox.showerror("配置错误", "请先在 'LLM 与全局设置' 标签页中配置 LLM！", parent=self); return

        proxy_config = {k: llm_config.get(k) for k in ["use_proxy", "proxy_address", "proxy_port"]}
        use_stream = llm_config.get("enableStreaming", True)
        prompt = self.app.prompt_templates.KAG_CONVERSION_PROMPT_TEMPLATE.format(
            pre_instruction=llm_config.get('preInstruction',''),
            post_instruction=llm_config.get('postInstruction',''),
            text_chunk=enhanced_text
        )

        if use_stream:
            print("步骤三：使用流式")
            task_id = "步骤三 (流式)"
            task_func = self.api_helpers.stream_google_response
            args = (
                llm_config.get('apiKey'), llm_config.get('apiEndpoint'), llm_config.get('modelName'),
                prompt, llm_config.get('temperature'), llm_config.get('maxOutputTokens'),
                "KAGConversion", proxy_config
            )
            is_stream = True
        else:
            print("步骤三：使用非流式")
            task_id = "步骤三 (非流式)"
            task_func = workflow_tasks.task_llm_convert_to_kag # 调用 workflow_tasks 中的函数
            args = (self.api_helpers, self.app.prompt_templates, llm_config, enhanced_text)
            is_stream = False

        self.run_task_in_thread(task_func, task_id, self.kag_script_widget, self.step3_status_label, args=args, is_stream=is_stream)

    # --- 手动替换占位符 ---
    def manual_replace_placeholders(self, auto_called=False):
        """手动或自动触发替换 KAG 脚本中的占位符"""
        print(f"请求替换占位符 (自动调用: {auto_called})...")
        kag_script = self.kag_script_widget.get("1.0", "end-1c")
        if not kag_script or not kag_script.strip():
            if not auto_called: messagebox.showwarning("无内容", "KAG 脚本内容为空，无法替换占位符。", parent=self)
            print("替换中止：KAG 脚本为空。"); return
        prefix = self.prefix_var.get().strip(); print(f"使用前缀: '{prefix}'")
        try:
            processed_script, replacements_made = self.utils.replace_kag_placeholders(kag_script, prefix)
            self.update_ui_element(self.kag_script_widget, text=processed_script, append=False)
            if self.image_replace_status_label:
                status_text = f"已替换 {replacements_made} 个图片占位符。" if replacements_made > 0 else "未找到可替换的图片占位符。"
                color = "green" if replacements_made > 0 else "gray"
                self.update_ui_element(self.image_replace_status_label, text=status_text, text_color=color)
                self.after(5000, lambda: self.update_ui_element(self.image_replace_status_label, text="", text_color="gray"))
        except Exception as e:
            print(f"替换占位符时出错: {e}"); traceback.print_exc(); messagebox.showerror("替换错误", f"替换占位符时发生错误:\n{e}", parent=self)
            if self.image_replace_status_label: self.update_ui_element(self.image_replace_status_label, text="替换出错!", text_color="red"); self.after(5000, lambda: self.update_ui_element(self.image_replace_status_label, text="", text_color="gray"))

    # --- 图片生成任务 ---
    def run_generate_nai(self):
        """触发 NAI 图片生成任务"""
        kag_script = self.kag_script_widget.get("1.0", "end-1c").strip()
        nai_config = self.app.get_nai_config()
        if not kag_script: messagebox.showwarning("无脚本", "KAG 脚本内容为空，无法生成图片。", parent=self); return
        if not nai_config or not all(k in nai_config for k in ['naiApiKey', 'naiImageSaveDir']) or not nai_config['naiApiKey'] or not nai_config['naiImageSaveDir']: messagebox.showerror("配置错误", "请先在 'NAI 设置' 标签页中完整配置 NAI API Key 和图片保存目录！", parent=self); return
        gen_options = {"scope": self.gen_scope_var.get(), "specific_files": self.specific_images_var.get() if self.gen_scope_var.get() == 'specific' else "", "n_samples": self.n_samples_var.get() or 1}
        self.run_task_in_thread(
            workflow_tasks.task_generate_images, # 调用 workflow_tasks 中的函数
            "NAI 图片生成",
            None,
            self.nai_gen_status_label,
            args=(self.api_helpers, "NAI", nai_config, kag_script, gen_options), # 传递依赖
            is_stream=False
        )

    def run_generate_sd(self):
        """触发 SD 图片生成任务"""
        kag_script = self.kag_script_widget.get("1.0", "end-1c").strip()
        sd_config = self.app.get_sd_config()
        if not kag_script: messagebox.showwarning("无脚本", "KAG 脚本内容为空，无法生成图片。", parent=self); return
        if not sd_config or not all(k in sd_config for k in ['sdWebUiUrl', 'sdImageSaveDir']) or not sd_config['sdWebUiUrl'] or not sd_config['sdImageSaveDir']: messagebox.showerror("配置错误", "请先在 'SD WebUI 设置' 标签页中完整配置 WebUI API 地址和图片保存目录！", parent=self); return
        gen_options = {"scope": self.gen_scope_var.get(), "specific_files": self.specific_images_var.get() if self.gen_scope_var.get() == 'specific' else "", "n_samples": self.n_samples_var.get() or 1}
        self.run_task_in_thread(
            workflow_tasks.task_generate_images, # 调用 workflow_tasks 中的函数
            "SD 图片生成",
            None,
            self.sd_gen_status_label,
            args=(self.api_helpers, "SD", sd_config, kag_script, gen_options), # 传递依赖
            is_stream=False
        )

    def update_button_states(self, event=None):
        """根据文本框内容、配置和任务状态更新按钮的启用/禁用状态"""
        required_widget_names = [
            'preprocess_button', 'enhance_button', 'convert_button',
            'replace_placeholder_button', 'generate_nai_button', 'generate_sd_button',
            'novel_text_widget', 'structured_text_widget', 'enhanced_text_widget', 'kag_script_widget'
        ]
        all_widgets_exist = all(
            hasattr(self, name) and getattr(self, name) and getattr(self, name).winfo_exists()
            for name in required_widget_names
        )
        if not all_widgets_exist: return

        task_running = self.task_running
        step1_ready = self.novel_text_widget.get("1.0", "end-1c").strip() != ""
        step2_ready = self.structured_text_widget.get("1.0", "end-1c").strip() != ""
        step3_ready = self.enhanced_text_widget.get("1.0", "end-1c").strip() != ""
        step4_ready = self.kag_script_widget.get("1.0", "end-1c").strip() != ""

        nai_config = self.app.get_nai_config()
        sd_config = self.app.get_sd_config()

        nai_gen_ready = step4_ready and nai_config and \
                        nai_config.get('naiApiKey') and nai_config.get('naiImageSaveDir')
        sd_gen_ready = step4_ready and sd_config and \
                       sd_config.get('sdWebUiUrl') and sd_config.get('sdImageSaveDir')

        self.update_ui_element(self.preprocess_button, state="normal" if step1_ready else "disabled")
        self.update_ui_element(self.enhance_button, state="normal" if step2_ready else "disabled")
        self.update_ui_element(self.convert_button, state="normal" if step3_ready else "disabled")
        self.update_ui_element(self.replace_placeholder_button, state="normal" if step4_ready else "disabled")
        self.update_ui_element(self.generate_nai_button, state="normal" if nai_gen_ready else "disabled")
        self.update_ui_element(self.generate_sd_button, state="normal" if sd_gen_ready else "disabled")