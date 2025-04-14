# ui/workflow_tab.py
import customtkinter as ctk
from tkinter import StringVar, messagebox, IntVar, Text, filedialog, BooleanVar, DoubleVar # 导入 BooleanVar, DoubleVar
from queue import Queue, Empty
import threading
import json
import traceback
import base64
from pathlib import Path
import os
import re
import time
import codecs
import copy # 导入 copy 用于复制配置字典

# 导入任务逻辑
from tasks import workflow_tasks
from tasks import image_generation_tasks
from tasks import audio_generation_tasks
# 导入 utils 模块
from core import utils

# --- 尝试导入 Windows 通知库 ---
try: from win10toast import ToastNotifier; toaster = ToastNotifier(); WINDOWS_NOTIFICATIONS_AVAILABLE = True; print("win10toast 库加载成功。")
except ImportError: print("警告：未找到 win10toast 库。"); WINDOWS_NOTIFICATIONS_AVAILABLE = False; toaster = None
# --- 通知库导入结束 ---


class WorkflowTab(ctk.CTkFrame):
    """核心转换流程的 UI 标签页"""
    def __init__(self, master, config_manager, api_helpers, utils, sound_player, app_instance):
        super().__init__(master, fg_color="transparent")
        self.config_manager = config_manager
        self.api_helpers = api_helpers
        self.utils = utils
        self.sound_player = sound_player
        self.app = app_instance
        self.result_queue = Queue()
        self.task_running = False

        # --- 初始化 KAG 转换温度覆盖相关的变量 ---
        self.override_kag_temp_var = BooleanVar(value=False)
        self.kag_temp_var = StringVar(value="0.1") # 默认低温度

        # --- 创建主滚动框架 ---
        self.scrollable_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scrollable_frame.pack(expand=True, fill="both")

        # --- 将所有 UI 元素放入滚动框架内 ---
        self.build_ui_within_scrollable_frame(self.scrollable_frame)
        self.after(100, self.check_queue)

    def build_ui_within_scrollable_frame(self, master_frame):
        """在指定的父框架（滚动框架）内构建 UI 元素"""
        master_frame.grid_rowconfigure((0, 2, 4, 6), weight=1)
        master_frame.grid_columnconfigure(0, weight=1)

        # --- 步骤一 ---
        step1_frame = ctk.CTkFrame(master_frame, fg_color="transparent"); step1_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 5)); step1_frame.grid_rowconfigure(1, weight=1); step1_frame.grid_columnconfigure(0, weight=1)
        step1_label = ctk.CTkLabel(step1_frame, text="原始小说原文:", anchor="w"); step1_label.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        self.novel_text_widget = ctk.CTkTextbox(step1_frame, wrap="word"); self.novel_text_widget.grid(row=1, column=0, sticky="nsew")
        step1_controls = ctk.CTkFrame(master_frame, fg_color="transparent"); step1_controls.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        self.preprocess_button = ctk.CTkButton(step1_controls, text="第一步：转换小说格式", command=self.run_step1_preprocess); self.preprocess_button.pack(side="left", padx=(0, 10))
        self.import_names_button = ctk.CTkButton(step1_controls, text="导入名称到人物设定", command=self.import_names_from_step1, state="disabled"); self.import_names_button.pack(side="left", padx=(0, 10))
        self.step1_status_label = ctk.CTkLabel(step1_controls, text="", text_color="gray", anchor="w"); self.step1_status_label.pack(side="left", fill="x", expand=True)

        # --- 步骤二 ---
        step2_frame = ctk.CTkFrame(master_frame, fg_color="transparent"); step2_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5); step2_frame.grid_rowconfigure(1, weight=1); step2_frame.grid_columnconfigure(0, weight=1)
        step2_label = ctk.CTkLabel(step2_frame, text="步骤一结果 (格式化文本):", anchor="w"); step2_label.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        self.structured_text_widget = ctk.CTkTextbox(step2_frame, wrap="word", state="normal"); self.structured_text_widget.grid(row=1, column=0, sticky="nsew")
        step2_controls = ctk.CTkFrame(master_frame, fg_color="transparent"); step2_controls.grid(row=3, column=0, sticky="ew", padx=10, pady=5)
        self.enhance_button = ctk.CTkButton(step2_controls, text="第二步：添加提示词", command=self.run_step2_enhance, state="disabled"); self.enhance_button.pack(side="left", padx=(0, 10))
        self.step2_status_label = ctk.CTkLabel(step2_controls, text="", text_color="gray", anchor="w"); self.step2_status_label.pack(side="left", fill="x", expand=True)

        # --- 步骤三 ---
        step3_frame = ctk.CTkFrame(master_frame, fg_color="transparent"); step3_frame.grid(row=4, column=0, sticky="nsew", padx=10, pady=5); step3_frame.grid_rowconfigure(1, weight=1); step3_frame.grid_columnconfigure(0, weight=1)
        step3_label = ctk.CTkLabel(step3_frame, text="步骤二结果 (含提示标记):", anchor="w"); step3_label.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        self.enhanced_text_widget = ctk.CTkTextbox(step3_frame, wrap="word", state="normal"); self.enhanced_text_widget.grid(row=1, column=0, sticky="nsew")
        step3_controls = ctk.CTkFrame(master_frame, fg_color="transparent"); step3_controls.grid(row=5, column=0, sticky="ew", padx=10, pady=5)
        self.convert_button = ctk.CTkButton(step3_controls, text="第三步：建议BGM并转KAG", command=self.run_step3_convert, state="disabled"); self.convert_button.pack(side="left", padx=(0, 10))
        # --- 新增：KAG 转换温度覆盖 ---
        self.override_kag_temp_checkbox = ctk.CTkCheckBox(step3_controls, text="覆盖KAG温度:", variable=self.override_kag_temp_var, command=self.toggle_kag_temp_entry)
        self.override_kag_temp_checkbox.pack(side="left", padx=(10, 0))
        self.kag_temp_entry = ctk.CTkEntry(step3_controls, textvariable=self.kag_temp_var, width=50, state="disabled") # 初始禁用
        self.kag_temp_entry.pack(side="left", padx=(0, 10))
        # --- 新增结束 ---
        img_prefix_label = ctk.CTkLabel(step3_controls, text="图片前缀:"); img_prefix_label.pack(side="left", padx=(10, 5))
        self.image_prefix_var = StringVar(); img_prefix_entry = ctk.CTkEntry(step3_controls, textvariable=self.image_prefix_var, width=100); img_prefix_entry.pack(side="left")
        audio_prefix_label = ctk.CTkLabel(step3_controls, text="音频前缀:"); audio_prefix_label.pack(side="left", padx=(10, 5))
        self.audio_prefix_var = StringVar(value="cv_"); audio_prefix_entry = ctk.CTkEntry(step3_controls, textvariable=self.audio_prefix_var, width=100); audio_prefix_entry.pack(side="left")
        self.step3_status_label = ctk.CTkLabel(step3_controls, text="", text_color="gray", anchor="w"); self.step3_status_label.pack(side="left", fill="x", expand=True, padx=(10, 0))

        # --- 步骤四 ---
        step4_frame = ctk.CTkFrame(master_frame, fg_color="transparent"); step4_frame.grid(row=6, column=0, sticky="nsew", padx=10, pady=5); step4_frame.grid_rowconfigure(1, weight=1); step4_frame.grid_columnconfigure(0, weight=1)
        step4_label = ctk.CTkLabel(step4_frame, text="步骤三结果 (KAG 脚本):", anchor="w"); step4_label.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        self.kag_script_widget = ctk.CTkTextbox(step4_frame, wrap="word", state="normal"); self.kag_script_widget.grid(row=1, column=0, sticky="nsew")

        # --- 生成选项 ---
        gen_options_outer_frame = ctk.CTkFrame(master_frame, fg_color="transparent"); gen_options_outer_frame.grid(row=7, column=0, sticky="ew", padx=10, pady=5); gen_options_outer_frame.grid_columnconfigure(0, weight=1)
        img_gen_options_frame = ctk.CTkFrame(gen_options_outer_frame); img_gen_options_frame.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="ew"); img_gen_options_frame.grid_columnconfigure(3, weight=1)
        img_scope_label = ctk.CTkLabel(img_gen_options_frame, text="图片范围:"); img_scope_label.grid(row=0, column=0, padx=(5, 5), pady=5, sticky="w")
        self.img_gen_scope_var = StringVar(value="all"); img_all_radio = ctk.CTkRadioButton(img_gen_options_frame, text="所有", variable=self.img_gen_scope_var, value="all", command=self.toggle_specific_images_entry); img_all_radio.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        img_specific_radio = ctk.CTkRadioButton(img_gen_options_frame, text="指定:", variable=self.img_gen_scope_var, value="specific", command=self.toggle_specific_images_entry); img_specific_radio.grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.specific_images_var = StringVar(); self.specific_images_entry = ctk.CTkEntry(img_gen_options_frame, textvariable=self.specific_images_var, placeholder_text="文件名,逗号分隔", state="disabled"); self.specific_images_entry.grid(row=0, column=3, padx=5, pady=5, sticky="ew")
        img_n_samples_label = ctk.CTkLabel(img_gen_options_frame, text="数量:"); img_n_samples_label.grid(row=0, column=4, padx=(10, 5), pady=5, sticky="w")
        self.img_n_samples_var = IntVar(value=1); img_n_samples_entry = ctk.CTkEntry(img_gen_options_frame, textvariable=self.img_n_samples_var, width=40); img_n_samples_entry.grid(row=0, column=5, padx=(0, 5), pady=5, sticky="w")
        audio_gen_options_frame = ctk.CTkFrame(gen_options_outer_frame); audio_gen_options_frame.grid(row=1, column=0, padx=(0, 5), pady=5, sticky="ew"); audio_gen_options_frame.grid_columnconfigure(3, weight=1)
        audio_scope_label = ctk.CTkLabel(audio_gen_options_frame, text="语音范围:"); audio_scope_label.grid(row=0, column=0, padx=(5, 5), pady=5, sticky="w")
        self.audio_gen_scope_var = StringVar(value="all"); audio_all_radio = ctk.CTkRadioButton(audio_gen_options_frame, text="所有", variable=self.audio_gen_scope_var, value="all", command=self.toggle_specific_speakers_entry); audio_all_radio.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        audio_specific_radio = ctk.CTkRadioButton(audio_gen_options_frame, text="指定:", variable=self.audio_gen_scope_var, value="specific", command=self.toggle_specific_speakers_entry); audio_specific_radio.grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.specific_speakers_var = StringVar(); self.specific_speakers_entry = ctk.CTkEntry(audio_gen_options_frame, textvariable=self.specific_speakers_var, placeholder_text="语音占位符(PLACEHOLDER_...)", state="disabled"); self.specific_speakers_entry.grid(row=0, column=3, padx=5, pady=5, sticky="ew")

        # --- 步骤四 控制按钮 ---
        step4_controls = ctk.CTkFrame(master_frame, fg_color="transparent"); step4_controls.grid(row=8, column=0, sticky="ew", padx=10, pady=(5, 10)); step4_controls.grid_columnconfigure(1, weight=1)
        self.replace_placeholder_button = ctk.CTkButton(step4_controls, text="手动替换图片占位符", command=self.manual_replace_placeholders); self.replace_placeholder_button.pack(side="left", padx=(0, 10))
        self.image_replace_status_label = ctk.CTkLabel(step4_controls, text="", text_color="gray", anchor="w"); self.image_replace_status_label.pack(side="left", padx=(0, 20))
        gen_status_frame = ctk.CTkFrame(step4_controls, fg_color="transparent"); gen_status_frame.pack(side="left", fill="x", expand=True)
        self.generate_nai_button = ctk.CTkButton(gen_status_frame, text="生成图片 (NAI)", command=self.run_generate_nai, state="disabled", fg_color="#f0ad4e", hover_color="#ec971f"); self.generate_nai_button.grid(row=0, column=0, padx=5, pady=2)
        self.nai_gen_status_label = ctk.CTkLabel(gen_status_frame, text="", text_color="gray", anchor="w"); self.nai_gen_status_label.grid(row=0, column=1, padx=(0, 10), sticky="w")
        self.generate_sd_button = ctk.CTkButton(gen_status_frame, text="生成图片 (SD)", command=self.run_generate_sd, state="disabled", fg_color="#5bc0de", hover_color="#46b8da"); self.generate_sd_button.grid(row=0, column=2, padx=5, pady=2)
        self.sd_gen_status_label = ctk.CTkLabel(gen_status_frame, text="", text_color="gray", anchor="w"); self.sd_gen_status_label.grid(row=0, column=3, padx=(0, 10), sticky="w")
        self.generate_audio_button = ctk.CTkButton(gen_status_frame, text="生成语音 (GPT-SoVITS)", command=self.run_generate_audio, state="disabled", fg_color="#5cb85c", hover_color="#4cae4c"); self.generate_audio_button.grid(row=0, column=4, padx=5, pady=2)
        self.audio_gen_status_label = ctk.CTkLabel(gen_status_frame, text="", text_color="gray", anchor="w"); self.audio_gen_status_label.grid(row=0, column=5, padx=(0, 10), sticky="w")
        self.save_ks_button = ctk.CTkButton(step4_controls, text="保存 KAG 脚本 (.ks)", command=self.save_kag_script, state="disabled"); self.save_ks_button.pack(side="right", padx=(10, 0))

        # --- 绑定事件 ---
        key_release_widgets = [self.novel_text_widget, self.structured_text_widget, self.enhanced_text_widget, self.kag_script_widget]
        for widget in key_release_widgets:
             if widget:
                 try: widget.bind("<KeyRelease>", self.update_button_states)
                 except Exception as bind_e: print(f"警告：绑定 KeyRelease 到 {type(widget).__name__} 出错: {bind_e}")

    def toggle_specific_images_entry(self):
        """切换指定图片输入框状态"""
        if self.img_gen_scope_var.get() == "specific": self.specific_images_entry.configure(state="normal")
        else: self.specific_images_entry.configure(state="disabled"); self.specific_images_var.set("")

    def toggle_specific_speakers_entry(self):
        """切换指定语音占位符输入框状态"""
        if self.audio_gen_scope_var.get() == "specific": self.specific_speakers_entry.configure(state="normal")
        else: self.specific_speakers_entry.configure(state="disabled"); self.specific_speakers_var.set("")

    def toggle_kag_temp_entry(self):
        """切换 KAG 温度覆盖输入框状态"""
        if self.override_kag_temp_var.get():
            self.kag_temp_entry.configure(state="normal")
        else:
            self.kag_temp_entry.configure(state="disabled")

    def update_ui_element(self, element, text=None, state=None, text_color=None, append=False):
        """安全地更新 UI 元素"""
        if not element or not element.winfo_exists(): return
        try:
            configure_options = {}
            if text is not None:
                if isinstance(element, (ctk.CTkLabel, ctk.CTkButton)): configure_options["text"] = text
                elif isinstance(element, ctk.CTkTextbox):
                    try:
                        if not append: element.delete("1.0", "end")
                        element.insert("end", text); element.see("end")
                    except Exception as textbox_e: print(f"错误: 修改 CTkTextbox 内容时出错 ({type(textbox_e).__name__}): {textbox_e}"); traceback.print_exc()
                    text = None
            if state is not None and hasattr(element, 'configure') and not isinstance(element, ctk.CTkTextbox):
                actual_state = state if not self.task_running else "disabled"
                configure_options["state"] = actual_state
            if text_color is not None and isinstance(element, ctk.CTkLabel): configure_options["text_color"] = text_color
            if configure_options and hasattr(element, 'configure'): element.configure(**configure_options)
        except Exception as e: print(f"更新 UI 元素 '{type(element).__name__}' 时发生未预期的错误: {e}"); traceback.print_exc()

    def check_queue(self):
        """定时检查结果队列，并更新 UI"""
        try:
            while not self.result_queue.empty():
                task_id, status, result_type, result_data, update_target, status_label = self.result_queue.get_nowait()
                print(f"从队列收到结果: ID={task_id}, Status={status}, Type={result_type}")

                # 更新状态标签
                if status_label:
                    color = "green" if status == "success" else "red" if status == "error" else "orange"
                    message = ""
                    if result_type == "task_update": message = f"{task_id}: {result_data}"; color="orange"
                    elif result_type == "stream_chunk": message = f"{task_id}: 正在接收..."
                    elif result_type == "stream_done": message = f"{task_id}: 完成!"; color = "green"
                    elif result_type == "stream_error": message = f"{task_id}: 流错误: {result_data}"; color = "red"
                    elif result_type == "stream_warning": message = f"{task_id}: 警告: {result_data}"; color = "orange"
                    elif result_type == "non_stream":
                         message = f"{task_id}: 完成!" if status == "success" else f"{task_id}: 错误: {result_data}"
                         if isinstance(result_data, dict) and 'message' in result_data: message = f"{task_id}: {result_data['message']}"
                    else: message = f"{task_id}: {result_data}"
                    max_len = 100; display_message = message if len(message) <= max_len else message[:max_len-3] + "..."
                    self.update_ui_element(status_label, text=display_message, text_color=color)
                    if result_type in ["stream_done", "stream_error", "non_stream"]:
                        self.after(8000, lambda lbl=status_label: self.update_ui_element(lbl, text="", text_color="gray"))

                # 更新目标文本框
                if update_target:
                     if result_type == "stream_chunk" and isinstance(result_data, str): self.update_ui_element(update_target, text=result_data, append=True)
                     elif (result_type == "non_stream" and status == "success" and isinstance(result_data, str)) or \
                          (result_type == "stream_done" and status == "success"):
                         final_result = result_data if result_type == "non_stream" else update_target.get("1.0", "end-1c")
                         processed_result = final_result
                         if task_id.startswith("步骤三") and update_target == self.kag_script_widget:
                             print("步骤三最终结果到达，调用 KAG 格式后处理 (utils)...")
                             try: processed_result = self.utils.post_process_kag_script(final_result)
                             except Exception as post_proc_e: print(f"错误：调用 KAG 格式后处理失败: {post_proc_e}"); traceback.print_exc()
                             print("步骤三 KAG 脚本准备更新 UI...")
                             print("步骤三成功，延迟调用占位符替换...")
                             self.after(50, lambda: self.manual_replace_placeholders(auto_called=True))
                         self.update_ui_element(update_target, text=processed_result, append=False)

                # 处理图片/语音生成任务的特殊结果
                if task_id in ["NAI 图片生成", "SD 图片生成", "GPT-SoVITS 语音生成"] and status == "success" and result_type == "non_stream":
                     if isinstance(result_data, dict):
                         if "modified_script" in result_data:
                             print(f"{task_id} 检测到修改后的 KAG 脚本...")
                             self.update_ui_element(self.kag_script_widget, text=result_data["modified_script"], append=False)
                         if "details" in result_data:
                             print(f"--- {task_id} 详细日志 ---")
                             for detail_line in result_data.get("details", []): print(detail_line)
                             print(f"--- {task_id} 日志结束 ---")

                # 任务结束处理
                if result_type in ["stream_done", "stream_error", "non_stream"]:
                    if status in ["success", "error"]:
                        # 检查声音通知开关
                        if self.app.llm_config.get("enableSoundNotifications", True):
                            sound_key = "successSoundPath" if status == "success" else "failureSoundPath"
                            sound_path = self.app.llm_config.get(sound_key, "")
                            if sound_path: print(f"准备播放声音: {sound_path}"); sound_thread = threading.Thread(target=self.sound_player.play_sound, args=(sound_path,), daemon=True); sound_thread.start()
                        else: print("声音通知已禁用，跳过播放。")
                        # 检查 Windows 通知开关
                        if WINDOWS_NOTIFICATIONS_AVAILABLE and toaster and self.app.llm_config.get("enableWinNotifications", True):
                            title = f"任务完成: {task_id}" if status == "success" else f"任务失败: {task_id}"
                            notify_message = f"{task_id} 处理完成."
                            max_msg_len = 150
                            if isinstance(result_data, str): notify_message = result_data
                            elif isinstance(result_data, dict) and 'message' in result_data: notify_message = result_data['message']
                            notify_message = notify_message if len(notify_message) <= max_msg_len else notify_message[:max_msg_len-3] + "..."
                            try: toaster.show_toast(title, notify_message, duration=7, threaded=True, icon_path=None); print(f"已发送 Windows 通知: {title}")
                            except Exception as notify_e: print(f"发送 Windows 通知时出错: {notify_e}"); traceback.print_exc()
                        elif not self.app.llm_config.get("enableWinNotifications", True): print("Windows 通知已禁用，跳过发送。")
                    self.task_running = False
                    self.update_button_states()
                    print(f"任务 {task_id} 处理完毕/出错。")
        except Empty: pass
        except Exception as e: print(f"检查队列或更新 UI 时出错: {e}"); traceback.print_exc(); self.task_running = False; self.update_button_states()
        finally: self.after(100, self.check_queue)

    def run_task_in_thread(self, task_func, task_id, update_target_widget, status_label_widget, args=(), is_stream_hint=False):
        """在后台线程中运行指定的任务函数"""
        if self.task_running: messagebox.showwarning("任务进行中", "请等待当前任务完成。", parent=self); return
        print(f"准备启动后台任务: {task_id} (流式提示: {is_stream_hint})")
        self.task_running = True; self.update_button_states()
        if status_label_widget: self.update_ui_element(status_label_widget, text=f"{task_id}: 处理中...", text_color="orange")
        if update_target_widget and isinstance(update_target_widget, ctk.CTkTextbox): self.update_ui_element(update_target_widget, text="", append=False)
        thread = threading.Thread(target=self._thread_wrapper, args=(task_func, task_id, update_target_widget, status_label_widget, args, is_stream_hint), daemon=True); thread.start()
        print(f"后台线程已启动: {task_id}")

    def _thread_wrapper(self, task_func, task_id, update_target_widget, status_label_widget, args, is_stream_hint):
        """后台线程实际执行的包装函数"""
        try:
            print(f"线程开始执行: {task_id} (流式提示: {is_stream_hint})")
            if task_id == "步骤三 (BGM+KAG)":
                # --- 修改：接收可能被修改过的 llm_config ---
                api_helpers, prompt_templates, llm_config_for_step3, enhanced_text = args # 重命名变量
                use_final_stream = llm_config_for_step3.get("enableStreaming", True)
                # 阶段 1: 添加 BGM 建议 (使用传入的 config)
                self.result_queue.put((task_id, "processing", "task_update", "正在添加 BGM 建议...", None, status_label_widget))
                text_with_suggestions, bgm_error = workflow_tasks.task_llm_suggest_bgm(api_helpers, prompt_templates, llm_config_for_step3, enhanced_text)
                if bgm_error: self.result_queue.put((task_id, "error", "non_stream", f"添加 BGM 建议失败: {bgm_error}", update_target_widget, status_label_widget)); return
                if not text_with_suggestions: self.result_queue.put((task_id, "error", "non_stream", "添加 BGM 建议时返回空结果。", update_target_widget, status_label_widget)); return
                # 阶段 2: 转换 KAG (使用传入的 config)
                self.result_queue.put((task_id, "processing", "task_update", "正在转换 KAG 脚本...", None, status_label_widget))
                proxy_config = {k: llm_config_for_step3.get(k) for k in ["use_proxy", "proxy_address", "proxy_port"]}
                kag_prompt = prompt_templates.KAG_CONVERSION_PROMPT_TEMPLATE.format(pre_instruction=llm_config_for_step3.get('preInstruction',''), post_instruction=llm_config_for_step3.get('postInstruction',''), text_chunk_with_suggestions=text_with_suggestions)
                if use_final_stream:
                    print(f"[{task_id}] 执行流式 KAG 转换...")
                    stream_finished_normally = False
                    # 使用传入的 config 调用流式 API
                    for status, data in api_helpers.stream_google_response(
                        llm_config_for_step3.get('apiKey'), llm_config_for_step3.get('apiEndpoint'), llm_config_for_step3.get('modelName'),
                        kag_prompt,
                        llm_config_for_step3.get('temperature'), # 使用 config 中的温度
                        llm_config_for_step3.get('maxOutputTokens'),
                        llm_config_for_step3.get('topP'), llm_config_for_step3.get('topK'), # 传递 topP, topK
                        "KAGConversion", proxy_config
                    ):
                        if status == "chunk": self.result_queue.put((task_id, "success", "stream_chunk", data, update_target_widget, status_label_widget))
                        elif status == "error": self.result_queue.put((task_id, "error", "stream_error", data, update_target_widget, status_label_widget)); return
                        elif status == "warning": self.result_queue.put((task_id, "warning", "stream_warning", data, update_target_widget, status_label_widget))
                        elif status == "done": self.result_queue.put((task_id, "success", "stream_done", data, update_target_widget, status_label_widget)); stream_finished_normally = True; return
                        else: self.result_queue.put((task_id, "warning", "stream_warning", f"未知状态: {status}", update_target_widget, status_label_widget))
                    if not stream_finished_normally: print(f"警告 ({task_id}): KAG 流结束但无 'done' 信号。"); self.result_queue.put((task_id, "success", "stream_done", f"{task_id}: 处理完成", update_target_widget, status_label_widget))
                else:
                    print(f"[{task_id}] 执行非流式 KAG 转换...")
                    # 使用传入的 config 调用非流式任务
                    final_kag, kag_error = workflow_tasks.task_llm_convert_to_kag(api_helpers, prompt_templates, llm_config_for_step3, text_with_suggestions)
                    status = "error" if kag_error else "success"; result_data = kag_error if kag_error else final_kag
                    self.result_queue.put((task_id, status, "non_stream", result_data, update_target_widget, status_label_widget))
                # --- 修改结束 ---
            elif is_stream_hint:
                stream_finished_normally = False
                # --- 修改：确保传递 top_p, top_k ---
                # 解包 args，假设它们按顺序包含所需参数
                api_key, api_base_url, model_name, prompt, temperature, max_output_tokens, top_p, top_k, prompt_type, proxy_config = args
                for status, data in task_func(api_key, api_base_url, model_name, prompt, temperature, max_output_tokens, top_p, top_k, prompt_type, proxy_config):
                # --- 修改结束 ---
                    if status == "chunk": self.result_queue.put((task_id, "success", "stream_chunk", data, update_target_widget, status_label_widget))
                    elif status == "error": self.result_queue.put((task_id, "error", "stream_error", data, update_target_widget, status_label_widget)); return
                    elif status == "warning": self.result_queue.put((task_id, "warning", "stream_warning", data, update_target_widget, status_label_widget))
                    elif status == "done": self.result_queue.put((task_id, "success", "stream_done", data, update_target_widget, status_label_widget)); stream_finished_normally = True; return
                    else: self.result_queue.put((task_id, "warning", "stream_warning", f"未知状态: {status}", update_target_widget, status_label_widget))
                if not stream_finished_normally: print(f"警告 ({task_id}): 流结束但无 'done' 信号。"); self.result_queue.put((task_id, "success", "stream_done", f"{task_id}: 处理完成", update_target_widget, status_label_widget))
            else:
                result, error = task_func(*args)
                status = "error" if error else "success"; result_data = error if error else result
                self.result_queue.put((task_id, status, "non_stream", result_data, update_target_widget, status_label_widget))
            print(f"线程正常完成: {task_id}")
        except Exception as e: print(f"线程 '{task_id}' 发生未捕获错误: {e}"); traceback.print_exc(); error_type = "stream_error" if is_stream_hint else "non_stream"; self.result_queue.put((task_id, "error", error_type, f"线程内部错误: {e}", update_target_widget, status_label_widget))
        finally: print(f"线程退出: {task_id}")

    # --- 步骤回调函数 ---
    def run_step1_preprocess(self):
        novel_text = self.novel_text_widget.get("1.0", "end-1c").strip()
        llm_config = self.app.get_llm_config()
        if not novel_text: messagebox.showwarning("输入缺失", "请输入原始小说原文！", parent=self); return
        if not llm_config or not all(k in llm_config for k in ['apiKey', 'apiEndpoint', 'modelName']): messagebox.showerror("配置错误", "请先在 'LLM 与全局设置' 标签页中配置 LLM！", parent=self); return
        proxy_config = {k: llm_config.get(k) for k in ["use_proxy", "proxy_address", "proxy_port"]}
        use_stream = llm_config.get("enableStreaming", True)
        prompt = self.app.prompt_templates.PREPROCESSING_PROMPT_TEMPLATE.format(pre_instruction=llm_config.get('preInstruction',''), post_instruction=llm_config.get('postInstruction',''), text_chunk=novel_text)
        if use_stream:
            print("步骤一：使用流式"); task_id = "步骤一 (流式)"; task_func = self.api_helpers.stream_google_response
            # --- 修改：传递 top_p, top_k ---
            args = (llm_config.get('apiKey'), llm_config.get('apiEndpoint'), llm_config.get('modelName'), prompt, llm_config.get('temperature'), llm_config.get('maxOutputTokens'), llm_config.get('topP'), llm_config.get('topK'), "Preprocessing", proxy_config); is_stream = True
            # --- 修改结束 ---
        else:
            print("步骤一：使用非流式"); task_id = "步骤一 (非流式)"; task_func = workflow_tasks.task_llm_preprocess
            args = (self.api_helpers, self.app.prompt_templates, llm_config, novel_text); is_stream = False # 非流式任务不需要 top_p/k 在 args 里，它会从 llm_config 取
        self.run_task_in_thread(task_func, task_id, self.structured_text_widget, self.step1_status_label, args=args, is_stream_hint=is_stream)

    def run_step2_enhance(self):
        formatted_text = self.structured_text_widget.get("1.0", "end-1c").strip()
        llm_config = self.app.get_llm_config()
        profiles_dict, profiles_json_for_prompt = self.app.profiles_tab.get_profiles_for_step2()
        if not formatted_text: messagebox.showwarning("输入缺失", "步骤一结果 (格式化文本) 不能为空！", parent=self); return
        if not llm_config or not all(k in llm_config for k in ['apiKey', 'apiEndpoint', 'modelName']): messagebox.showerror("配置错误", "请先在 'LLM 与全局设置' 标签页中配置 LLM！", parent=self); return
        if profiles_dict is None or profiles_json_for_prompt is None: print("步骤二取消：从 ProfilesTab 获取数据失败。"); return
        proxy_config = {k: llm_config.get(k) for k in ["use_proxy", "proxy_address", "proxy_port"]}
        use_stream = llm_config.get("enableStreaming", True)
        prompt = self.app.prompt_templates.PROMPT_ENHANCEMENT_TEMPLATE.format(pre_instruction=llm_config.get('preInstruction',''), post_instruction=llm_config.get('postInstruction',''), character_profiles_json=profiles_json_for_prompt, formatted_text_chunk=formatted_text)
        if use_stream:
            print("步骤二：使用流式"); task_id = "步骤二 (流式)"; task_func = self.api_helpers.stream_google_response
            # --- 修改：传递 top_p, top_k ---
            args = (llm_config.get('apiKey'), llm_config.get('apiEndpoint'), llm_config.get('modelName'), prompt, llm_config.get('temperature'), llm_config.get('maxOutputTokens'), llm_config.get('topP'), llm_config.get('topK'), "PromptEnhancement", proxy_config); is_stream = True
            # --- 修改结束 ---
        else:
            print("步骤二：使用非流式"); task_id = "步骤二 (非流式)"; task_func = workflow_tasks.task_llm_enhance
            args = (self.api_helpers, self.app.prompt_templates, llm_config, formatted_text, profiles_dict); is_stream = False
        self.run_task_in_thread(task_func, task_id, self.enhanced_text_widget, self.step2_status_label, args=args, is_stream_hint=is_stream)

    def run_step3_convert(self):
        """触发步骤三：建议 BGM 并转换 KAG (处理温度覆盖)"""
        enhanced_text = self.enhanced_text_widget.get("1.0", "end-1c").strip()
        # 获取基础 LLM 配置
        base_llm_config = self.app.get_llm_config()
        if not enhanced_text: messagebox.showwarning("输入缺失", "步骤二结果 (含提示标记) 不能为空！", parent=self); return
        if not base_llm_config or not all(k in base_llm_config for k in ['apiKey', 'apiEndpoint', 'modelName']): messagebox.showerror("配置错误", "请先在 'LLM 与全局设置' 标签页中配置 LLM！", parent=self); return

        # --- 新增：处理 KAG 温度覆盖 ---
        llm_config_for_step3 = copy.deepcopy(base_llm_config) # 创建副本以防修改全局配置
        if self.override_kag_temp_var.get():
            temp_str = self.kag_temp_var.get().strip()
            try:
                override_temp = float(temp_str)
                assert 0.0 <= override_temp <= 2.0 # 验证范围
                llm_config_for_step3['temperature'] = override_temp # 覆盖副本中的温度
                print(f"步骤三：使用覆盖温度进行 KAG 转换: {override_temp}")
            except:
                print(f"警告: 无效的 KAG 覆盖温度值 '{temp_str}'，将使用全局温度。")
                messagebox.showwarning("输入错误", f"KAG 覆盖温度值 '{temp_str}' 不是 0.0 到 2.0 之间的有效数字。\n将使用全局设置中的温度。", parent=self)
                # 如果覆盖失败，llm_config_for_step3 仍包含原始全局温度
        else:
            print(f"步骤三：使用全局温度进行 KAG 转换: {llm_config_for_step3.get('temperature')}")
        # --- 新增结束 ---

        task_id = "步骤三 (BGM+KAG)"
        # --- 修改：传递可能被修改过的 llm_config_for_step3 ---
        args = (self.api_helpers, self.app.prompt_templates, llm_config_for_step3, enhanced_text)
        # --- 修改结束 ---
        print(f"运行 {task_id}...")
        self.run_task_in_thread(None, task_id, self.kag_script_widget, self.step3_status_label, args=args, is_stream_hint=False)

    def manual_replace_placeholders(self, auto_called=False):
        print(f"请求替换图片占位符 (自动调用: {auto_called})...")
        kag_script = self.kag_script_widget.get("1.0", "end-1c")
        if not kag_script or not kag_script.strip():
            if not auto_called: messagebox.showwarning("无内容", "KAG 脚本内容为空，无法替换图片占位符。", parent=self)
            print("替换中止：KAG 脚本为空。"); return
        prefix = self.image_prefix_var.get().strip(); print(f"使用图片前缀: '{prefix}'")
        try:
            processed_script, replacements_made = self.utils.replace_kag_placeholders(kag_script, prefix)
            self.update_ui_element(self.kag_script_widget, text=processed_script, append=False)
            if self.image_replace_status_label:
                status_text = f"已替换 {replacements_made} 个图片占位符。" if replacements_made > 0 else "未找到可替换的图片占位符。"
                color = "green" if replacements_made > 0 else "gray"
                self.update_ui_element(self.image_replace_status_label, text=status_text, text_color=color)
                self.after(5000, lambda: self.update_ui_element(self.image_replace_status_label, text="", text_color="gray"))
        except Exception as e:
            print(f"替换图片占位符时出错: {e}"); traceback.print_exc()
            messagebox.showerror("替换错误", f"替换图片占位符时发生错误:\n{e}", parent=self)
            if self.image_replace_status_label:
                self.update_ui_element(self.image_replace_status_label, text="图片替换出错!", text_color="red")
                self.after(5000, lambda: self.update_ui_element(self.image_replace_status_label, text="", text_color="gray"))

    def run_generate_nai(self):
        kag_script = self.kag_script_widget.get("1.0", "end-1c").strip()
        nai_config = self.app.get_nai_config()
        if not kag_script: messagebox.showwarning("无脚本", "KAG 脚本内容为空，无法生成图片。", parent=self); return
        if not nai_config or not all(k in nai_config for k in ['naiApiKey', 'naiImageSaveDir']) or not nai_config['naiApiKey'] or not nai_config['naiImageSaveDir']: messagebox.showerror("配置错误", "请先在 'NAI 设置' 标签页中完整配置 NAI API Key 和图片保存目录！", parent=self); return
        gen_options = {"scope": self.img_gen_scope_var.get(), "specific_files": self.specific_images_var.get() if self.img_gen_scope_var.get() == 'specific' else "", "n_samples": self.img_n_samples_var.get() or 1}
        self.run_task_in_thread(image_generation_tasks.task_generate_images, "NAI 图片生成", None, self.nai_gen_status_label, args=(self.api_helpers, "NAI", nai_config, kag_script, gen_options), is_stream_hint=False)

    def run_generate_sd(self):
        kag_script = self.kag_script_widget.get("1.0", "end-1c").strip()
        sd_config = self.app.get_sd_config()
        if not kag_script: messagebox.showwarning("无脚本", "KAG 脚本内容为空，无法生成图片。", parent=self); return
        if not sd_config or not all(k in sd_config for k in ['sdWebUiUrl', 'sdImageSaveDir']) or not sd_config['sdWebUiUrl'] or not sd_config['sdImageSaveDir']: messagebox.showerror("配置错误", "请先在 'SD WebUI 设置' 标签页中完整配置 WebUI API 地址和图片保存目录！", parent=self); return
        gen_options = {"scope": self.img_gen_scope_var.get(), "specific_files": self.specific_images_var.get() if self.img_gen_scope_var.get() == 'specific' else "", "n_samples": self.img_n_samples_var.get() or 1}
        self.run_task_in_thread(image_generation_tasks.task_generate_images, "SD 图片生成", None, self.sd_gen_status_label, args=(self.api_helpers, "SD", sd_config, kag_script, gen_options), is_stream_hint=False)

    def run_generate_audio(self):
        kag_script = self.kag_script_widget.get("1.0", "end-1c").strip()
        gptsovits_config = self.app.get_gptsovits_config()
        audio_prefix = self.audio_prefix_var.get().strip()
        if not kag_script: messagebox.showwarning("无脚本", "KAG 脚本内容为空，无法生成语音。", parent=self); return
        if not gptsovits_config or not gptsovits_config.get('apiUrl') or not gptsovits_config.get('audioSaveDir') or gptsovits_config.get('character_voice_map') is None: messagebox.showerror("配置错误", "请先在 'GPT-SoVITS 设置' 标签页中完整配置 API 地址、音频保存目录和人物语音映射！", parent=self); return
        if not gptsovits_config.get('character_voice_map'): messagebox.showwarning("配置警告", "人物语音映射为空，无法生成任何语音。请先配置映射。", parent=self); return
        gen_options = {"scope": self.audio_gen_scope_var.get(), "specific_speakers": self.specific_speakers_var.get() if self.audio_gen_scope_var.get() == 'specific' else ""}
        self.run_task_in_thread(audio_generation_tasks.task_generate_audio, "GPT-SoVITS 语音生成", None, self.audio_gen_status_label, args=(self.api_helpers, gptsovits_config, kag_script, audio_prefix, gen_options), is_stream_hint=False)

    def import_names_from_step1(self):
        print("请求从步骤一结果导入名称...")
        formatted_text = self.structured_text_widget.get("1.0", "end-1c")
        if not formatted_text.strip(): messagebox.showwarning("无内容", "步骤一结果为空，无法导入名称。", parent=self); return
        try:
            potential_names = re.findall(r'\[([^\]:]+)\]', formatted_text)
            filtered_names = set()
            for name in potential_names:
                name_lower = name.lower()
                if name_lower not in ['image', 'name'] and not name_lower.startswith('insert_image_here') and name.strip() and not re.fullmatch(r'[\d\W_]+', name): filtered_names.add(name.strip())
            if not filtered_names: messagebox.showinfo("未找到名称", "在步骤一结果中未能自动识别出新的人物名称标记。", parent=self); return
            if hasattr(self.app, 'profiles_tab') and self.app.profiles_tab.winfo_exists():
                profiles_tab = self.app.profiles_tab; added_count = 0; skipped_count = 0
                for name in filtered_names:
                    if name not in profiles_tab.character_profiles: profiles_tab.character_profiles[name] = {"display_name": name, "replacement_name": "", "positive": "", "negative": ""}; added_count += 1; print(f"  > 已添加新名称到人物设定: {name}")
                    else: skipped_count += 1; print(f"  > 跳过已存在名称: {name}")
                if added_count > 0: profiles_tab.render_profiles_list(); profiles_tab.after(100, profiles_tab._scroll_to_bottom); messagebox.showinfo("导入完成", f"成功导入 {added_count} 个新的人物名称到“人物设定”标签页。\n跳过了 {skipped_count} 个已存在的名称。\n\n请前往“人物设定”标签页检查并配置提示词和替换名称。", parent=self)
                else: messagebox.showinfo("无需导入", "所有在步骤一结果中识别出的名称均已存在于人物设定中。", parent=self)
            else: messagebox.showerror("内部错误", "无法访问人物设定标签页。", parent=self)
        except Exception as e: print(f"从步骤一导入名称时出错: {e}"); traceback.print_exc(); messagebox.showerror("导入错误", f"从步骤一结果导入名称时发生错误:\n{e}", parent=self)

    def save_kag_script(self):
        print("请求保存 KAG 脚本...")
        kag_script_content = self.kag_script_widget.get("1.0", "end-1c")
        if not kag_script_content or not kag_script_content.strip(): messagebox.showwarning("无内容", "KAG 脚本内容为空，无法保存。", parent=self); print("保存中止：KAG 脚本为空。"); return
        try:
            filepath = filedialog.asksaveasfilename(title="保存 KAG 脚本", defaultextension=".ks", filetypes=[("KAG 脚本", "*.ks"), ("所有文件", "*.*")], initialfile="scene1.ks", parent=self)
            if not filepath: print("用户取消保存。"); return
            with open(filepath, 'wb') as f: f.write(codecs.BOM_UTF16_LE); f.write(kag_script_content.encode('utf-16-le'))
            print(f"KAG 脚本已成功保存到 (UTF-16 LE with BOM): {filepath}"); messagebox.showinfo("保存成功", f"KAG 脚本已成功保存为 (UTF-16 LE with BOM):\n{filepath}", parent=self)
            if self.step3_status_label: self.update_ui_element(self.step3_status_label, text=f"已保存: {os.path.basename(filepath)}", text_color="green"); self.after(5000, lambda: self.update_ui_element(self.step3_status_label, text="", text_color="gray"))
        except IOError as e: print(f"保存 KAG 脚本时发生 IO 错误: {e}"); traceback.print_exc(); messagebox.showerror("保存错误", f"写入文件时发生错误:\n{e}", parent=self)
        except Exception as e: print(f"保存 KAG 脚本时发生意外错误: {e}"); traceback.print_exc(); messagebox.showerror("保存错误", f"保存 KAG 脚本时发生意外错误:\n{e}", parent=self)

    def update_button_states(self, event=None):
        """更新按钮的启用/禁用状态"""
        required_widget_names = ['preprocess_button', 'import_names_button', 'enhance_button', 'convert_button', 'replace_placeholder_button', 'generate_nai_button', 'generate_sd_button', 'generate_audio_button', 'save_ks_button', 'novel_text_widget', 'structured_text_widget', 'enhanced_text_widget', 'kag_script_widget']
        all_widgets_exist = all(hasattr(self, name) and getattr(self, name) and getattr(self, name).winfo_exists() for name in required_widget_names)
        if not all_widgets_exist: print("警告：尝试更新按钮状态时，部分 UI 控件尚未完全初始化。"); return

        task_running = self.task_running
        step1_ready = self.novel_text_widget.get("1.0", "end-1c").strip() != ""
        step2_ready = self.structured_text_widget.get("1.0", "end-1c").strip() != ""
        step3_ready = self.enhanced_text_widget.get("1.0", "end-1c").strip() != ""
        step4_ready = self.kag_script_widget.get("1.0", "end-1c").strip() != ""
        nai_config = self.app.get_nai_config(); sd_config = self.app.get_sd_config(); gptsovits_config = self.app.get_gptsovits_config()
        nai_gen_ready = step4_ready and nai_config and nai_config.get('naiApiKey') and nai_config.get('naiImageSaveDir')
        sd_gen_ready = step4_ready and sd_config and sd_config.get('sdWebUiUrl') and sd_config.get('sdImageSaveDir')
        audio_gen_ready = step4_ready and gptsovits_config and gptsovits_config.get('apiUrl') and gptsovits_config.get('audioSaveDir') and gptsovits_config.get('character_voice_map')

        self.update_ui_element(self.preprocess_button, state="normal" if step1_ready and not task_running else "disabled")
        self.update_ui_element(self.import_names_button, state="normal" if step2_ready and not task_running else "disabled")
        self.update_ui_element(self.enhance_button, state="normal" if step2_ready and not task_running else "disabled")
        self.update_ui_element(self.convert_button, state="normal" if step3_ready and not task_running else "disabled")
        self.update_ui_element(self.replace_placeholder_button, state="normal" if step4_ready and not task_running else "disabled")
        self.update_ui_element(self.generate_nai_button, state="normal" if nai_gen_ready and not task_running else "disabled")
        self.update_ui_element(self.generate_sd_button, state="normal" if sd_gen_ready and not task_running else "disabled")
        self.update_ui_element(self.generate_audio_button, state="normal" if audio_gen_ready and not task_running else "disabled")
        self.update_ui_element(self.save_ks_button, state="normal" if step4_ready and not task_running else "disabled")