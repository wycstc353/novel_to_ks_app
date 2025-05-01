# ui/workflow_tab_controller.py
import customtkinter as ctk # 功能性备注: 导入 customtkinter 库
from tkinter import messagebox, filedialog # 功能性备注: 导入 Tkinter 相关变量和对话框
from queue import Queue, Empty # 功能性备注: 导入队列，用于线程通信
import threading # 功能性备注: 导入线程模块
import json # 功能性备注: 导入 JSON 模块
import traceback # 功能性备注: 保留用于错误处理
import base64 # 功能性备注: 导入 Base64 模块
from pathlib import Path # 功能性备注: 导入 Path 对象
import os # 功能性备注: 导入 OS 模块
import re # 功能性备注: 导入正则表达式模块
import time # 功能性备注: 导入时间模块
import codecs # 功能性备注: 导入 codecs 模块，用于文件编码
import copy # 功能性备注: 导入 copy 模块
import logging # 功能性备注: 导入日志模块

# 功能性备注: 导入任务逻辑
from tasks import workflow_tasks
from tasks import image_generation_tasks
from tasks import audio_generation_tasks

# --- 尝试导入 Windows 通知库 ---
# 功能性备注: 尝试加载 Windows 通知库，如果失败则禁用通知功能
try:
    from win10toast import ToastNotifier # 尝试导入
    toaster = ToastNotifier() # 创建实例
    WINDOWS_NOTIFICATIONS_AVAILABLE = True # 标记为可用
    logging.info("win10toast 库加载成功 (controller)。") # 功能性备注
except ImportError:
    logging.warning("警告：未找到 win10toast 库。系统通知功能将不可用 (controller)。") # 功能性备注
    WINDOWS_NOTIFICATIONS_AVAILABLE = False
    toaster = None

# 功能性备注: 获取当前模块的 logger 实例
logger = logging.getLogger(__name__)

class WorkflowTabController:
    """处理 WorkflowTab 的逻辑和回调""" # 功能性备注: 类定义
    def __init__(self, view):
        # 功能性备注: 初始化，保存对主 WorkflowTab (view) 的引用
        self.view = view
        self.task_running = False # 功能性备注: 标记是否有后台任务正在运行
        self.result_queue = Queue() # 功能性备注: 用于线程通信的结果队列
        self.stop_event = threading.Event() # 功能性备注: 用于发送停止信号的事件对象

    def update_ui_element(self, element, text=None, state=None, text_color=None, append=False):
        """安全地更新 UI 元素（标签、按钮、文本框）的状态和内容"""
        # 功能性备注: 封装 UI 更新逻辑，增加健壮性
        # 逻辑备注: 检查控件是否存在
        if not element or not hasattr(element, 'winfo_exists') or not element.winfo_exists(): return
        try:
            configure_options = {} # 功能性备注: 存储需要更新的选项
            # 功能性备注: 更新文本内容
            if text is not None:
                if isinstance(element, (ctk.CTkLabel, ctk.CTkButton)):
                    configure_options["text"] = text # 功能性备注: 直接设置标签或按钮文本
                elif isinstance(element, ctk.CTkTextbox):
                    try:
                        element.configure(state="normal") # 功能性备注: 启用编辑
                        if not append: element.delete("1.0", "end") # 逻辑备注: 如果不是追加，先清空
                        element.insert("end", text) # 功能性备注: 插入文本
                        element.see("end") # 功能性备注: 滚动到底部
                        # 逻辑修改: 文本框不再自动禁用，允许用户编辑
                        # if not self.task_running:
                        #     element.configure(state="disabled")
                    except Exception as textbox_e: logger.error(f"错误: 修改 CTkTextbox 内容时出错: {textbox_e}", exc_info=True) # 逻辑备注
            # 功能性备注: 更新状态 (禁用/启用)
            if state is not None and hasattr(element, 'configure') and not isinstance(element, ctk.CTkTextbox):
                # 逻辑备注: 如果是停止按钮，其状态由 task_running 直接决定
                # 逻辑修改: 停止按钮现在位于主应用中
                if element == self.view.app.main_stop_button:
                    actual_state = "normal" if self.task_running else "disabled"
                # 逻辑备注: 对于其他按钮，如果任务正在运行，则强制禁用
                else:
                    actual_state = state if not self.task_running else "disabled"
                configure_options["state"] = actual_state
            # 功能性备注: 更新文本颜色 (仅标签)
            if text_color is not None and isinstance(element, ctk.CTkLabel):
                configure_options["text_color"] = text_color
            # 功能性备注: 应用更新
            if configure_options and hasattr(element, 'configure'):
                element.configure(**configure_options)
        except Exception as e:
            logger.exception(f"更新 UI 元素 '{type(element).__name__}' 时发生未预期的错误: {e}") # 逻辑备注

    def process_queue(self):
        """处理后台任务结果队列，并更新 UI"""
        # 功能性备注: 处理后台任务返回的结果
        try:
            # 逻辑备注: 持续从队列中获取结果，直到队列为空
            while not self.result_queue.empty():
                # 功能性备注: 获取任务结果信息
                task_id, status, result_type, result_data, update_target, status_label = self.result_queue.get_nowait()
                logger.debug(f"从队列收到结果: ID={task_id}, Status={status}, Type={result_type}") # 功能性备注

                is_terminal = False # 功能性备注: 标记是否是任务终止状态

                # --- 更新状态标签 ---
                if status_label:
                    # 逻辑备注: 根据状态决定颜色
                    color = "green" if status == "success" else "red" if status == "error" else "orange"
                    message = "" # 功能性备注: 初始化消息文本
                    display_message = "" # 功能性备注: 初始化最终显示的消息
                    # 逻辑备注: 根据结果类型格式化消息
                    if result_type == "task_update": message = f"{task_id}: {result_data}"; color = "orange"
                    elif result_type == "stream_chunk": message = f"{task_id}: 正在接收..."; color = "green" if status == "success" else "orange"
                    elif result_type == "stream_done": message = f"{task_id}: 完成!"; color = "green"; is_terminal = True
                    elif result_type == "stream_error": message = f"{task_id}: 流错误: {result_data}"; color = "red"; is_terminal = True
                    elif result_type == "stream_warning": message = f"{task_id}: 警告: {result_data}"; color = "orange"
                    elif result_type == "non_stream":
                        if isinstance(result_data, dict) and 'message' in result_data: message = f"{task_id}: {result_data['message']}"
                        elif status == "error": message = f"{task_id}: 错误: {result_data}"
                        elif status == "success": message = f"{task_id}: 完成!"
                        else: message = f"{task_id}: {result_data}"
                        color = "green" if status == "success" else "red" if status == "error" else "orange"
                        is_terminal = True
                    elif result_type == "stopped": # 功能性备注: 处理停止状态
                        message = f"{task_id}: 已停止"; color = "orange"; is_terminal = True
                    else: message = f"{task_id}: {result_data}"; color = "green" if status == "success" else "red" if status == "error" else "orange"

                    # 逻辑备注: 限制显示消息长度
                    max_len = 100
                    display_message = message if len(str(message)) <= max_len else str(message)[:max_len-3] + "..."
                    # 功能性备注: 更新状态标签
                    self.update_ui_element(status_label, text=display_message, text_color=color)
                    # 逻辑备注: 如果是终止状态，8秒后清空标签
                    if is_terminal:
                        self.view.after(8000, lambda lbl=status_label: self.update_ui_element(lbl, text="", text_color="gray"))

                # --- 更新目标文本框 ---
                if update_target and update_target.winfo_exists():
                    # 逻辑备注: 处理流式块 (追加内容)
                    if result_type == "stream_chunk" and status == "success" and isinstance(result_data, str):
                        self.view.after(1, lambda target=update_target, chunk=result_data: self._update_textbox_safely(target, chunk, append=True))
                    # 逻辑备注: 处理非流式成功结果 或 KAG 脚本更新
                    elif result_type == "non_stream" and status == "success":
                        final_result = result_data; processed_result = final_result; is_kag_widget_update = False
                        # 逻辑备注: 处理媒体生成任务返回的字典
                        if isinstance(final_result, dict) and "modified_script" in final_result:
                            processed_result = final_result["modified_script"]
                            if task_id in ["NAI 图片生成", "SD WebUI 图片生成", "ComfyUI 图片生成", "GPT-SoVITS 语音生成"] and status_label:
                                final_msg_short = final_result.get('message', f'{task_id} 完成.')[:80] + "..."
                                self.update_ui_element(status_label, text=final_msg_short, text_color="green")
                                self.view.after(8000, lambda lbl=status_label: self.update_ui_element(lbl, text="", text_color="gray"))
                            if "details" in final_result:
                                logger.info(f"--- {task_id} 详细日志 ---"); [logger.info(line) for line in final_result.get("details", [])]; logger.info(f"--- {task_id} 日志结束 ---")
                        elif isinstance(final_result, dict): # 逻辑备注: 其他字典转 JSON
                            try: processed_result = json.dumps(final_result, indent=2, ensure_ascii=False)
                            except Exception: processed_result = str(final_result)
                        # 逻辑备注: 只有字符串结果才更新文本框
                        if isinstance(processed_result, str):
                            if update_target == self.view.widgets['kag_script_widget']: is_kag_widget_update = True
                            # 逻辑备注: 如果是步骤三结果，先进行后处理
                            if task_id.startswith("步骤三"):
                                logger.info("步骤三非流式最终结果到达，调用 KAG 格式后处理 (utils)...")
                                try: processed_result = self.view.utils.post_process_kag_script(processed_result); logger.info("步骤三 KAG 脚本准备更新 UI...")
                                except Exception as post_proc_e: logger.error(f"错误：调用 KAG 格式后处理失败: {post_proc_e}", exc_info=True)

                            # 功能性备注: 在更新 UI 前，对最终要显示的字符串结果进行 strip()
                            cleaned_result = processed_result.strip()

                            # 功能性备注: 延迟更新文本框 (使用清理后的结果)
                            self.view.after(10, lambda target=update_target, res=cleaned_result: self._update_textbox_safely(target, res, append=False))

                            # 逻辑备注: 如果是 KAG 更新且是步骤三，延迟调用占位符替换
                            if is_kag_widget_update and task_id.startswith("步骤三"):
                                logger.info("延迟调用占位符替换 (步骤三 KAG 非流式更新后)...")
                                self.view.after(50, lambda: self.manual_replace_placeholders(auto_called=True))
                        else: logger.warning(f"警告：非流式任务 {task_id} 成功但结果非字符串，无法更新文本框。")

                # --- 处理终止状态 ---
                if is_terminal:
                    logger.info(f"任务 {task_id} 达到终止状态: {status} ({result_type})") # 功能性备注
                    # 功能性备注: 根据状态播放声音和通知
                    if status == "success" or result_type == "stream_done":
                        self._play_notification_sound(success=True)
                        self._show_windows_notification(task_id, result_data, success=True)
                    elif status == "error" or result_type == "stream_error":
                        self._play_notification_sound(success=False)
                        self._show_windows_notification(task_id, result_data, success=False)
                    elif status == "stopped":
                        # 逻辑备注: 可以在这里为停止状态添加特定声音或通知（可选）
                        pass
                    # 功能性备注: 重置任务状态
                    self.task_running = False
                    self.stop_event.clear() # 功能性备注: 清除停止信号
                    self.view.update_button_states() # 功能性备注: 更新所有按钮状态
                    logger.info(f"任务 {task_id} 状态已重置，按钮已更新。") # 功能性备注

        except Empty:
            pass # 逻辑备注: 队列为空时忽略
        except Exception as e:
            logger.exception(f"检查队列或更新 UI 时出错: {e}") # 逻辑备注
            self.task_running = False # 功能性备注: 发生错误时重置状态
            try: self.stop_event.clear() # 功能性备注: 尝试清除停止信号
            except Exception: pass
            self.view.update_button_states() # 功能性备注: 更新按钮状态

    def _update_textbox_safely(self, textbox_widget, content, append=False):
        """安全地更新 Textbox 内容"""
        # 功能性备注: 封装文本框更新
        # 逻辑备注: 检查控件是否存在
        if not textbox_widget or not textbox_widget.winfo_exists(): return
        try:
            textbox_widget.configure(state="normal") # 功能性备注: 启用编辑
            if not append: textbox_widget.delete("1.0", "end") # 逻辑备注: 如果不是追加则清空
            textbox_widget.insert("end", content) # 功能性备注: 插入内容
            textbox_widget.see("end") # 功能性备注: 滚动到底部
            # 逻辑修改: 文本框不再自动禁用
            # if not self.task_running:
            #     textbox_widget.configure(state="disabled")

            # !!! 新增：在更新文本框后，立即调用按钮状态更新 !!!
            self.view.update_button_states() # 功能性备注: 强制更新按钮状态

        except Exception as e:
            logger.exception(f"更新 Textbox 时出错: {e}") # 逻辑备注

    def _play_notification_sound(self, success=True):
        """播放成功或失败的提示音"""
        # 功能性备注: 播放提示音的辅助函数
        global_config = self.view.app.get_global_llm_config()
        if global_config.get("enableSoundNotifications", True):
            sound_key = "successSoundPath" if success else "failureSoundPath"
            default_sound = "assets/success.wav" if success else "assets/failure.wav"
            sound_path = global_config.get(sound_key, default_sound)
            if sound_path and os.path.exists(sound_path):
                logger.info(f"准备播放 {'成功' if success else '失败'} 声音 (Pygame 线程): {sound_path}")
                if hasattr(self.view, 'sound_player') and self.view.sound_player:
                    threading.Thread(target=self.view.sound_player.play_sound, args=(sound_path,), daemon=True).start()

    def _show_windows_notification(self, task_id, result_data, success=True):
        """显示 Windows 系统通知"""
        # 功能性备注: 发送系统通知的辅助函数
        global_config = self.view.app.get_global_llm_config()
        if WINDOWS_NOTIFICATIONS_AVAILABLE and toaster and global_config.get("enableWinNotifications", True):
            title = f"任务{'完成' if success else '失败'}: {task_id}"
            notify_message = ""
            if isinstance(result_data, str): notify_message = result_data
            elif isinstance(result_data, dict) and 'message' in result_data: notify_message = result_data['message']
            else: notify_message = f"{task_id} {'完成' if success else '失败'}."
            max_msg_len = 150
            notify_message = str(notify_message)
            notify_message = notify_message if len(notify_message) <= max_msg_len else notify_message[:max_msg_len-3] + "..."
            try:
                logger.info(f"准备发送 {'成功' if success else '失败'} 通知: {title}")
                toaster.show_toast(title, notify_message, duration=7, threaded=True, icon_path=None)
            except Exception as notify_e: logger.error(f"发送 Windows 通知时出错: {notify_e}")

    def run_task_in_thread(self, task_func, task_id, update_target_widget, status_label_widget, args=(), is_stream_hint=False):
        """在后台线程中运行指定的任务函数"""
        # 功能性备注: 启动后台任务的通用方法
        # 逻辑备注: 检查是否有任务正在运行
        if self.task_running:
            messagebox.showwarning("任务进行中", "请等待当前任务完成。", parent=self.view); return
        logger.info(f"准备启动后台任务: {task_id} (流式提示: {is_stream_hint})") # 功能性备注
        # 功能性备注: 清除之前的停止信号
        self.stop_event.clear()
        # 功能性备注: 设置任务运行状态并更新按钮
        self.task_running = True; self.view.update_button_states()
        # 功能性备注: 更新状态标签为处理中
        if status_label_widget: self.update_ui_element(status_label_widget, text=f"{task_id}: 处理中...", text_color="orange")
        # 逻辑备注: 如果是流式任务，尝试清空目标文本框
        if update_target_widget and isinstance(update_target_widget, ctk.CTkTextbox) and is_stream_hint:
            logger.info(f"清空流式任务的目标文本框: {task_id}") # 功能性备注
            try: update_target_widget.configure(state="normal"); update_target_widget.delete("1.0", "end")
            except Exception as clear_e: logger.error(f"错误: 清空文本框时发生错误: {clear_e}") # 逻辑备注
        # 功能性备注: 创建并启动后台线程，传递 stop_event
        thread = threading.Thread(target=self._thread_wrapper, args=(task_func, task_id, update_target_widget, status_label_widget, args, is_stream_hint, self.stop_event), daemon=True)
        thread.start()
        logger.info(f"后台线程已启动: {task_id}") # 功能性备注

    def _thread_wrapper(self, task_func, task_id, update_target_widget, status_label_widget, args, is_stream_hint, stop_event):
        """后台线程实际执行的包装函数"""
        # 功能性备注: 包装后台任务执行，处理异常和结果传递，并检查停止信号
        try:
            logger.info(f"线程开始执行: {task_id} (流式提示: {is_stream_hint})") # 功能性备注

            # 逻辑备注: 在任务开始前检查停止信号
            if stop_event.is_set(): raise StopIteration("任务在开始前被用户停止")

            # --- 处理步骤三 (BGM+KAG) ---
            if task_id.startswith("步骤三"):
                api_helpers, prompt_templates, llm_config_for_step3, enhanced_text, provider = args
                global_config = self.view.app.get_global_llm_config()
                use_final_stream = global_config.get("enableStreaming", True)
                logger.debug(f"--- [DEBUG] _thread_wrapper ({task_id}): enableStreaming = {use_final_stream} ---")

                # 功能性备注: 第一步：添加 BGM 建议 (需要传递 stop_event)
                self.result_queue.put((task_id, "processing", "task_update", "正在添加 BGM 建议...", None, status_label_widget))
                text_with_suggestions, bgm_error = workflow_tasks.task_llm_suggest_bgm(api_helpers, prompt_templates, llm_config_for_step3, enhanced_text, provider, stop_event=stop_event) # 传递 stop_event
                if stop_event.is_set(): raise StopIteration("任务被用户停止 (BGM 建议后)") # 功能性备注: 调用后检查
                if bgm_error: self.result_queue.put((task_id, "error", "non_stream", f"添加 BGM 建议失败: {bgm_error}", update_target_widget, status_label_widget)); return
                if not text_with_suggestions: self.result_queue.put((task_id, "error", "non_stream", "添加 BGM 建议时返回空结果。", update_target_widget, status_label_widget)); return

                # 功能性备注: 第二步：转换 KAG (需要传递 stop_event)
                self.result_queue.put((task_id, "processing", "task_update", "正在转换 KAG 脚本...", None, status_label_widget))
                final_kag, kag_error = workflow_tasks.task_llm_convert_to_kag(
                    api_helpers, prompt_templates, llm_config_for_step3, text_with_suggestions, provider,
                    use_stream=use_final_stream, result_queue=self.result_queue, task_id=task_id,
                    update_target_widget=update_target_widget, status_label_widget=status_label_widget,
                    stop_event=stop_event # 传递 stop_event
                )
                # 逻辑备注: 对于非流式 KAG 转换，在调用后检查停止信号
                if not use_final_stream:
                    if stop_event.is_set(): raise StopIteration("任务被用户停止 (KAG 转换后)") # 功能性备注: 调用后检查
                    if kag_error: self.result_queue.put((task_id, "error", "non_stream", kag_error, update_target_widget, status_label_widget))
                    else: self.result_queue.put((task_id, "success", "non_stream", final_kag, update_target_widget, status_label_widget))
                # 逻辑备注: 对于流式 KAG 转换，其内部循环应检查 stop_event

            # --- 处理步骤一、二 (LLM 任务) ---
            elif task_id.startswith("步骤一") or task_id.startswith("步骤二"):
                provider, api_helpers_instance, prompt_templates_instance, global_config, text_data, profiles_dict, profiles_json_for_prompt, prompt_style = args[0], args[1], args[2], args[3], args[4], args[5] if len(args) > 5 else None, args[6] if len(args) > 6 else None, args[7] if len(args) > 7 else "sd_comfy"
                use_stream = global_config.get("enableStreaming", True)
                logger.debug(f"--- [DEBUG] _thread_wrapper ({task_id}): enableStreaming = {use_stream}, prompt_style = {prompt_style} ---")

                if use_stream:
                    # 逻辑备注: 流式处理，假设流式函数内部会检查 stop_event
                    stream_func = None; stream_args = (); prompt = ""
                    proxy_config = {k: global_config.get(k) for k in ["use_proxy", "proxy_address", "proxy_port"]}
                    save_debug = global_config.get('saveDebugInputs', False)
                    if task_id.startswith("步骤一"): prompt = prompt_templates_instance.PREPROCESSING_PROMPT_TEMPLATE.format(pre_instruction=global_config.get('preInstruction',''), post_instruction=global_config.get('postInstruction',''), text_chunk=text_data)
                    elif task_id.startswith("步骤二"):
                        template = prompt_templates_instance.NAI_PROMPT_ENHANCEMENT_TEMPLATE if prompt_style == "nai" else prompt_templates_instance.SD_COMFY_PROMPT_ENHANCEMENT_TEMPLATE
                        prompt = template.format(pre_instruction=global_config.get('preInstruction',''), post_instruction=global_config.get('postInstruction',''), character_profiles_json=profiles_json_for_prompt, formatted_text_chunk=text_data)
                    if provider == "Google":
                        google_config = self.view.app.get_google_specific_config()
                        stream_func = api_helpers_instance.stream_google_response
                        stream_args = (google_config.get('apiKey'), google_config.get('apiEndpoint'), google_config.get('modelName'), prompt, global_config.get('temperature'), global_config.get('maxOutputTokens'), global_config.get('topP'), global_config.get('topK'), task_id, proxy_config, save_debug)
                    elif provider == "OpenAI":
                        openai_config = self.view.app.get_openai_specific_config()
                        stream_func = api_helpers_instance.stream_openai_response
                        stream_args = (openai_config.get('apiKey'), openai_config.get('apiBaseUrl'), openai_config.get('modelName'), prompt, global_config.get('temperature'), global_config.get('maxOutputTokens'), openai_config.get('customHeaders'), proxy_config, save_debug)

                    if stream_func:
                        stream_finished_normally = False
                        for status, data in stream_func(*stream_args): # 假设流式函数内部检查 stop_event
                            if stop_event.is_set(): raise StopIteration("任务在流式处理中被用户停止") # 功能性备注: 流式循环中检查
                            if status == "chunk": self.result_queue.put((task_id, "success", "stream_chunk", data, update_target_widget, status_label_widget))
                            elif status == "error": self.result_queue.put((task_id, "error", "stream_error", data, update_target_widget, status_label_widget)); return
                            elif status == "warning": self.result_queue.put((task_id, "warning", "stream_warning", data, update_target_widget, status_label_widget))
                            elif status == "done": self.result_queue.put((task_id, "success", "stream_done", data, update_target_widget, status_label_widget)); stream_finished_normally = True; return
                            else: self.result_queue.put((task_id, "warning", "stream_warning", f"未知状态: {status}", update_target_widget, status_label_widget))
                        if not stream_finished_normally:
                            logger.warning(f"警告 ({task_id}): 流结束但无 'done' 信号。")
                            self.result_queue.put((task_id, "success", "stream_done", f"{task_id}: 处理完成", update_target_widget, status_label_widget))
                    else: self.result_queue.put((task_id, "error", "stream_error", f"找不到 {provider} 的流式 API 函数", update_target_widget, status_label_widget))
                else:
                    # 逻辑备注: 非流式处理
                    actual_task_func = None; task_args = ()
                    if task_id.startswith("步骤一"): actual_task_func = workflow_tasks.task_llm_preprocess; task_args = (api_helpers_instance, prompt_templates_instance, global_config, text_data)
                    elif task_id.startswith("步骤二"): actual_task_func = workflow_tasks.task_llm_enhance; task_args = (api_helpers_instance, prompt_templates_instance, global_config, text_data, profiles_dict, profiles_json_for_prompt, provider, prompt_style)
                    if actual_task_func:
                        # 逻辑备注: 传递 stop_event
                        if task_id.startswith("步骤二"): result, error = actual_task_func(*task_args, stop_event=stop_event) # 直接解包
                        else: result, error = actual_task_func(*task_args, provider=provider, stop_event=stop_event) # 步骤一保持不变
                        if stop_event.is_set(): raise StopIteration("任务在完成后被用户停止 (结果将被丢弃)") # 功能性备注: 调用后检查
                        status = "error" if error else "success"; result_data = error if error else result
                        self.result_queue.put((task_id, status, "non_stream", result_data, update_target_widget, status_label_widget))
                    else: self.result_queue.put((task_id, "error", "non_stream", "未知的 LLM 任务", update_target_widget, status_label_widget))

            # --- 处理非 LLM 任务 (图片/语音生成) ---
            else:
                # 逻辑备注: 传递 stop_event
                result, error = task_func(*args, stop_event=stop_event)
                if stop_event.is_set(): raise StopIteration("任务在完成后被用户停止 (结果将被丢弃)") # 功能性备注: 调用后检查
                status = "error" if error else "success"; result_data = error if error else result
                self.result_queue.put((task_id, status, "non_stream", result_data, update_target_widget, status_label_widget))

            logger.info(f"线程正常完成: {task_id}") # 功能性备注
        except StopIteration as stop_e: # 功能性备注: 捕获停止信号
            logger.info(f"线程 '{task_id}' 收到停止信号: {stop_e}") # 功能性备注
            self.result_queue.put((task_id, "stopped", "stopped", f"任务被用户停止", update_target_widget, status_label_widget)) # 功能性备注: 发送停止状态
        except Exception as e:
            # 逻辑备注: 捕获线程内部的未预期错误
            logger.exception(f"线程 '{task_id}' 发生未捕获错误: {e}") # 逻辑备注
            error_type = "stream_error" if is_stream_hint else "non_stream" # 逻辑备注: 判断错误类型
            self.result_queue.put((task_id, "error", error_type, f"线程内部错误: {e}", update_target_widget, status_label_widget))
        finally:
            # 功能性备注: 线程退出日志
            logger.info(f"线程退出: {task_id}") # 功能性备注

    # --- 步骤回调函数 (保持不变) ---
    def run_step1_preprocess(self):
        """运行步骤一：格式化"""
        # 功能性备注: 触发步骤一后台任务
        novel_text = self.view.widgets['novel_text_widget'].get("1.0", "end-1c").strip() # 功能性备注: 获取原文
        global_config = self.view.app.get_global_llm_config() # 功能性备注: 获取全局 LLM 配置
        provider = global_config.get("selected_provider", "Google") # 功能性备注: 获取选定的提供商
        use_stream = global_config.get("enableStreaming", True) # 功能性备注: 获取是否启用流式
        logger.debug(f"--- [DEBUG] run_step1_preprocess: enableStreaming from global_config = {use_stream} ---") # 功能性备注
        # 逻辑备注: 检查输入和 LLM 配置
        if not novel_text: messagebox.showwarning("输入缺失", "请输入原始小说原文！", parent=self.view); return
        if not self._check_llm_readiness(provider): return # 功能性备注: 检查 LLM 是否就绪
        # 功能性备注: 准备任务参数和 ID
        task_id = f"步骤一 ({provider}{' 流式' if use_stream else ' 非流式'})"
        # 逻辑备注: 调整 args 结构以匹配 _thread_wrapper 的解包逻辑
        args = (provider, self.view.api_helpers, self.view.app.prompt_templates, global_config, novel_text, None, None, None) # 添加一个 None 作为 prompt_style 的占位符
        # 功能性备注: 在后台线程中运行任务
        self.run_task_in_thread(None, task_id, self.view.widgets['structured_text_widget'], self.view.widgets['step1_status_label'], args=args, is_stream_hint=use_stream)

    def run_step2_enhance_nai(self):
        """运行步骤二：添加 NAI 提示词"""
        # 功能性备注: 触发步骤二 (NAI) 后台任务
        formatted_text = self.view.widgets['structured_text_widget'].get("1.0", "end-1c").strip() # 功能性备注: 获取格式化文本
        global_config = self.view.app.get_global_llm_config() # 功能性备注: 获取全局 LLM 配置
        provider = global_config.get("selected_provider", "Google") # 功能性备注: 获取选定的提供商
        # 功能性备注: 获取人物设定 (现在包含所有四个提示词字段)
        profiles_dict, profiles_json_for_prompt = self.view.app.profiles_tab.get_profiles_for_step2() # 获取人物设定
        # 逻辑备注: 检查输入和人物设定
        if not formatted_text: messagebox.showwarning("输入缺失", "步骤一结果 (格式化文本) 不能为空！", parent=self.view); return
        if profiles_dict is None or profiles_json_for_prompt is None:
            logger.warning("步骤二 (NAI) 取消：从 ProfilesTab 获取数据失败。"); return # 逻辑备注
        # 逻辑备注: 检查 LLM 配置
        if not self._check_llm_readiness(provider): return
        # 功能性备注: 准备任务参数和 ID
        use_stream = global_config.get("enableStreaming", True) # 功能性备注: 获取是否启用流式
        task_id = f"步骤二-NAI ({provider}{' 流式' if use_stream else ' 非流式'})"
        # 逻辑备注: 调整 args 结构，添加 prompt_style='nai'
        args = (provider, self.view.api_helpers, self.view.app.prompt_templates, global_config, formatted_text, profiles_dict, profiles_json_for_prompt, "nai")
        # 功能性备注: 在后台线程中运行任务
        self.run_task_in_thread(workflow_tasks.task_llm_enhance, task_id, self.view.widgets['enhanced_text_widget'], self.view.widgets['step2_status_label'], args=args, is_stream_hint=use_stream)

    def run_step2_enhance_sd_comfy(self):
        """运行步骤二：添加 SD/Comfy 提示词"""
        # 功能性备注: 触发步骤二 (SD/Comfy) 后台任务
        formatted_text = self.view.widgets['structured_text_widget'].get("1.0", "end-1c").strip() # 功能性备注: 获取格式化文本
        global_config = self.view.app.get_global_llm_config() # 功能性备注: 获取全局 LLM 配置
        provider = global_config.get("selected_provider", "Google") # 功能性备注: 获取选定的提供商
        # 功能性备注: 获取人物设定 (现在包含所有四个提示词字段)
        profiles_dict, profiles_json_for_prompt = self.view.app.profiles_tab.get_profiles_for_step2() # 获取人物设定
        # 逻辑备注: 检查输入和人物设定
        if not formatted_text: messagebox.showwarning("输入缺失", "步骤一结果 (格式化文本) 不能为空！", parent=self.view); return
        if profiles_dict is None or profiles_json_for_prompt is None:
            logger.warning("步骤二 (SD/Comfy) 取消：从 ProfilesTab 获取数据失败。"); return # 逻辑备注
        # 逻辑备注: 检查 LLM 配置
        if not self._check_llm_readiness(provider): return
        # 功能性备注: 准备任务参数和 ID
        use_stream = global_config.get("enableStreaming", True) # 功能性备注: 获取是否启用流式
        task_id = f"步骤二-SD/Comfy ({provider}{' 流式' if use_stream else ' 非流式'})"
        # 逻辑备注: 调整 args 结构，添加 prompt_style='sd_comfy'
        args = (provider, self.view.api_helpers, self.view.app.prompt_templates, global_config, formatted_text, profiles_dict, profiles_json_for_prompt, "sd_comfy")
        # 功能性备注: 在后台线程中运行任务
        self.run_task_in_thread(workflow_tasks.task_llm_enhance, task_id, self.view.widgets['enhanced_text_widget'], self.view.widgets['step2_status_label'], args=args, is_stream_hint=use_stream)

    def run_step3_convert(self):
        """运行步骤三：转换（建议 BGM 并转 KAG）"""
        # 功能性备注: 触发步骤三后台任务
        enhanced_text = self.view.widgets['enhanced_text_widget'].get("1.0", "end-1c").strip() # 功能性备注: 获取含提示标记的文本
        global_config = self.view.app.get_global_llm_config() # 功能性备注: 获取全局 LLM 配置
        provider = global_config.get("selected_provider", "Google") # 功能性备注: 获取选定的提供商
        # 逻辑备注: 检查输入和 LLM 配置
        if not enhanced_text: messagebox.showwarning("输入缺失", "步骤二结果 (含提示标记) 不能为空！", parent=self.view); return
        if not self._check_llm_readiness(provider): return
        # 功能性备注: 准备步骤三专用的 LLM 配置（可能覆盖温度）
        llm_config_for_step3 = copy.deepcopy(global_config) # 功能性备注: 深拷贝全局配置
        if self.view.override_kag_temp_var.get(): # 逻辑备注: 如果启用温度覆盖
            try:
                override_temp = float(self.view.kag_temp_var.get().strip()) # 功能性备注: 获取覆盖温度值
                assert 0.0 <= override_temp <= 2.0 # 逻辑备注: 校验范围
                llm_config_for_step3['temperature'] = override_temp # 功能性备注: 应用覆盖温度
                logger.info(f"步骤三 ({provider})：使用覆盖温度进行 KAG 转换: {override_temp}") # 功能性备注
            except:
                # 逻辑备注: 无效温度值警告
                logger.warning(f"警告: 无效的 KAG 覆盖温度值，将使用全局温度。") # 逻辑备注
                messagebox.showwarning("输入错误", "KAG 覆盖温度值不是 0.0 到 2.0 之间的有效数字。", parent=self.view)
        # 功能性备注: 准备任务参数和 ID
        task_id = f"步骤三 (BGM+KAG, {provider})"
        args = (self.view.api_helpers, self.view.app.prompt_templates, llm_config_for_step3, enhanced_text, provider)
        # 功能性备注: 在后台线程中运行任务 (步骤三总是非流式，由内部函数处理流式细节)
        self.run_task_in_thread(None, task_id, self.view.widgets['kag_script_widget'], self.view.widgets['step3_status_label'], args=args, is_stream_hint=False) # is_stream_hint=False

    def _check_llm_readiness(self, provider):
        """检查指定 LLM 提供商的配置是否就绪"""
        # 功能性备注: 验证 LLM 配置是否完整
        if provider == "Google":
            google_config = self.view.app.get_google_specific_config();
            # 逻辑备注: 检查 Google 配置是否完整
            if not google_config or not google_config.get('apiKey') or not google_config.get('apiEndpoint') or not google_config.get('modelName'):
                messagebox.showerror("配置错误", "请先在 'LLM 设置' 标签页中完整配置 Google API Key, Base URL 和模型！", parent=self.view); return False
        elif provider == "OpenAI":
            openai_config = self.view.app.get_openai_specific_config();
            # 逻辑备注: 检查 OpenAI 配置是否完整
            if not openai_config or not openai_config.get('apiKey') or not openai_config.get('modelName'):
                messagebox.showerror("配置错误", "请先在 'LLM 设置' 标签页中完整配置 OpenAI API Key 和模型！", parent=self.view); return False
        else:
            # 逻辑备注: 未知提供商错误
            messagebox.showerror("错误", f"未知的 LLM 提供商: {provider}", parent=self.view); return False
        return True # 逻辑备注: 配置检查通过

    # --- 图片/语音生成按钮回调 (逻辑修改: 传递新的范围值) ---
    def _run_generate_media(self, api_type, status_label_widget):
        """通用的媒体生成函数（图片或语音）"""
        # 功能性备注: 触发图片或语音生成任务
        kag_script = self.view.widgets['kag_script_widget'].get("1.0", "end-1c").strip() # 功能性备注: 获取 KAG 脚本内容
        # 逻辑备注: 检查脚本是否为空
        if not kag_script: messagebox.showwarning("无脚本", "KAG 脚本内容为空，无法生成媒体。", parent=self.view); return
        # 功能性备注: 初始化变量
        specific_config = None; shared_config = None; task_func = None; task_id_prefix = ""; gen_options = {}; args = (); character_profiles = {}

        # 逻辑备注: 如果是图片生成任务，获取人物设定（主要用于图生图）
        if api_type in ["NAI", "SD WebUI", "ComfyUI"]:
            if hasattr(self.view.app, 'profiles_tab') and self.view.app.profiles_tab:
                 character_profiles = self.view.app.profiles_tab.character_profiles.copy() # 功能性备注: 获取人物设定副本
                 # 逻辑备注: 如果启用了图生图但没有人物设定，则警告
                 if not character_profiles and self.view.use_img2img_var.get():
                     messagebox.showwarning("需要人物设定", "图生图功能已启用，但当前未加载任何人物设定数据。", parent=self.view); return
                 elif not character_profiles:
                     logger.info("信息：将执行文生图，无需人物设定数据。") # 功能性备注
            elif self.view.use_img2img_var.get(): # 逻辑备注: 启用了图生图但无法访问人物设定 Tab
                messagebox.showerror("内部错误", "无法访问人物设定标签页，无法执行图生图。", parent=self.view); return

        # 逻辑备注: 根据 API 类型准备配置和参数
        if api_type == "NAI":
            specific_config = self.view.app.get_nai_config() # 功能性备注: 获取 NAI 特定配置
            shared_config = self.view.app.get_image_gen_shared_config() # 功能性备注: 获取图片共享配置
            task_func = image_generation_tasks.task_generate_images # 功能性备注: 指定任务函数
            task_id_prefix = "NAI 图片生成"
            # 逻辑备注: 检查 NAI 配置是否完整
            if not specific_config or not specific_config.get('naiApiKey') or not specific_config.get('naiImageSaveDir'):
                messagebox.showerror("配置错误", "请先在 'NAI 设置' 标签页中完整配置 NAI API Key 和图片保存目录！", parent=self.view); return
            # 功能性备注: 准备生成选项 (逻辑修改: 传递新的范围值)
            gen_options = {"scope": self.view.img_gen_scope_var.get(), "specific_files": self.view.specific_images_var.get() if self.view.img_gen_scope_var.get() == 'specific' else "", "n_samples": self.view.img_n_samples_var.get() or 1}
            args=(self.view.api_helpers, api_type, shared_config, specific_config, kag_script, gen_options, self.view.use_img2img_var.get(), character_profiles)
        elif api_type == "SD WebUI":
            specific_config = self.view.app.get_sd_config() # 功能性备注: 获取 SD 特定配置
            shared_config = self.view.app.get_image_gen_shared_config() # 功能性备注: 获取图片共享配置
            task_func = image_generation_tasks.task_generate_images # 功能性备注: 指定任务函数
            task_id_prefix = "SD WebUI 图片生成"
            # 逻辑备注: 检查 SD 配置是否完整
            if not specific_config or not specific_config.get('sdWebUiUrl'):
                messagebox.showerror("配置错误", "请先在 '图片生成设置' 标签页中配置 SD WebUI API 地址！", parent=self.view); return
            # 逻辑备注: 检查共享图片保存目录是否配置
            if not shared_config or not shared_config.get('imageSaveDir'):
                messagebox.showerror("配置错误", "请先在 '图片生成设置' 标签页中配置共享图片保存目录！", parent=self.view); return
            # 功能性备注: 准备生成选项 (逻辑修改: 传递新的范围值)
            gen_options = {"scope": self.view.img_gen_scope_var.get(), "specific_files": self.view.specific_images_var.get() if self.view.img_gen_scope_var.get() == 'specific' else "", "n_samples": self.view.img_n_samples_var.get() or 1}
            args=(self.view.api_helpers, api_type, shared_config, specific_config, kag_script, gen_options, self.view.use_img2img_var.get(), character_profiles)
        elif api_type == "ComfyUI":
            specific_config = self.view.app.get_comfyui_config() # 功能性备注: 获取 ComfyUI 特定配置
            shared_config = self.view.app.get_image_gen_shared_config() # 功能性备注: 获取图片共享配置
            task_func = image_generation_tasks.task_generate_images # 功能性备注: 指定任务函数
            task_id_prefix = "ComfyUI 图片生成"
            workflow_path = specific_config.get('comfyWorkflowFile', '') # 功能性备注: 获取工作流路径
            # 逻辑备注: 检查 ComfyUI 配置是否完整
            if not specific_config or not specific_config.get('comfyapiUrl') or not workflow_path:
                messagebox.showerror("配置错误", "请先在 '图片生成设置' 标签页中完整配置 ComfyUI API 地址和工作流文件路径！", parent=self.view); return
            # 逻辑备注: 检查工作流文件是否存在
            if not os.path.exists(workflow_path):
                messagebox.showerror("配置错误", f"指定的 ComfyUI 工作流文件不存在:\n{workflow_path}", parent=self.view); return
            # 逻辑备注: 检查共享图片保存目录是否配置
            if not shared_config or not shared_config.get('imageSaveDir'):
                messagebox.showerror("配置错误", "请先在 '图片生成设置' 标签页中配置共享图片保存目录！", parent=self.view); return
            # 功能性备注: 准备生成选项 (逻辑修改: 传递新的范围值)
            gen_options = {"scope": self.view.img_gen_scope_var.get(), "specific_files": self.view.specific_images_var.get() if self.view.img_gen_scope_var.get() == 'specific' else "", "n_samples": self.view.img_n_samples_var.get() or 1}
            args=(self.view.api_helpers, api_type, shared_config, specific_config, kag_script, gen_options, self.view.use_img2img_var.get(), character_profiles)
        elif api_type == "GPT-SoVITS":
            specific_config = self.view.app.get_gptsovits_config() # 功能性备注: 获取 GPT-SoVITS 配置
            task_func = audio_generation_tasks.task_generate_audio # 功能性备注: 指定任务函数
            task_id_prefix = "GPT-SoVITS 语音生成"
            audio_prefix = self.view.audio_prefix_var.get().strip() # 功能性备注: 获取音频前缀
            # 逻辑备注: 检查 GPT-SoVITS 配置是否完整
            if not specific_config or not specific_config.get('apiUrl') or not specific_config.get('audioSaveDir'):
                messagebox.showerror("配置错误", "请先在 'GPT-SoVITS 设置' 标签页中完整配置 API 地址和音频保存目录！", parent=self.view); return
            # 逻辑备注: 检查语音映射是否为空
            if not specific_config.get('character_voice_map'):
                messagebox.showwarning("配置警告", "人物语音映射为空，无法生成任何语音。", parent=self.view); return
            # 功能性备注: 准备生成选项 (逻辑修改: 传递新的范围值)
            gen_options = {"scope": self.view.audio_gen_scope_var.get(), "specific_speakers": self.view.specific_speakers_var.get() if self.view.audio_gen_scope_var.get() == 'specific' else ""}
            args=(self.view.api_helpers, specific_config, kag_script, audio_prefix, gen_options) # 逻辑备注: 参数调整为适应 audio_generation_tasks
        else:
            # 逻辑备注: 未知媒体类型错误
            messagebox.showerror("内部错误", f"未知的媒体生成类型: {api_type}", parent=self.view); return
        # 功能性备注: 在后台线程中运行媒体生成任务 (媒体生成总是非流式)
        self.run_task_in_thread(task_func, task_id_prefix, self.view.widgets['kag_script_widget'], status_label_widget, args=args, is_stream_hint=False)

    # 功能性备注: 为每个媒体生成按钮绑定 _run_generate_media 函数
    def run_generate_nai(self): self._run_generate_media("NAI", self.view.widgets['nai_gen_status_label'])
    def run_generate_sd_webui(self): self._run_generate_media("SD WebUI", self.view.widgets['sd_gen_status_label'])
    def run_generate_comfyui(self): self._run_generate_media("ComfyUI", self.view.widgets['comfy_gen_status_label'])
    def run_generate_audio(self): self._run_generate_media("GPT-SoVITS", self.view.widgets['audio_gen_status_label'])

    # --- 其他辅助函数 (保持不变) ---
    def manual_replace_placeholders(self, auto_called=False):
        """手动或自动替换 KAG 脚本中的图片占位符"""
        # 功能性备注: 将脚本中的图片占位符替换为注释掉的 image 标签
        logger.info(f"请求替换图片占位符 (自动调用: {auto_called})...") # 功能性备注
        kag_script = self.view.widgets['kag_script_widget'].get("1.0", "end-1c") # 功能性备注: 获取 KAG 脚本
        # 逻辑备注: 检查脚本是否为空
        if not kag_script or not kag_script.strip():
            if not auto_called: messagebox.showwarning("无内容", "KAG 脚本内容为空，无法替换图片占位符。", parent=self.view)
            logger.warning("替换中止：KAG 脚本为空。"); return # 逻辑备注
        # 功能性备注: 获取图片前缀
        prefix = self.view.image_prefix_var.get().strip(); logger.info(f"使用图片前缀: '{prefix}'") # 功能性备注
        try:
            # 功能性备注: 调用 utils 中的替换函数
            processed_script, replacements_made = self.view.utils.replace_kag_placeholders(kag_script, prefix)
            # 功能性备注: 更新 KAG 脚本框内容
            self.update_ui_element(self.view.widgets['kag_script_widget'], text=processed_script, append=False)
            # 功能性备注: 更新状态标签
            status_label = self.view.widgets.get('image_replace_status_label')
            if status_label:
                status_text = f"已替换 {replacements_made} 个图片占位符。" if replacements_made > 0 else "未找到可替换的图片占位符。"
                color = "green" if replacements_made > 0 else "gray"
                self.update_ui_element(status_label, text=status_text, text_color=color)
                # 功能性备注: 5秒后清空状态
                self.view.after(5000, lambda: self.update_ui_element(status_label, text="", text_color="gray"))
        except Exception as e:
            # 逻辑备注: 处理替换错误
            logger.exception(f"替换图片占位符时出错: {e}"); messagebox.showerror("替换错误", f"替换图片占位符时发生错误:\n{e}", parent=self.view) # 逻辑备注
            status_label = self.view.widgets.get('image_replace_status_label')
            if status_label:
                self.update_ui_element(status_label, text="图片替换出错!", text_color="red")
                self.view.after(5000, lambda: self.update_ui_element(status_label, text="", text_color="gray"))

    def import_names_from_step1(self):
        """从步骤一结果中提取名称并导入到人物设定"""
        # 功能性备注: 自动从格式化文本中提取人物名称
        logger.info("请求从步骤一结果导入名称...") # 功能性备注
        formatted_text = self.view.widgets['structured_text_widget'].get("1.0", "end-1c") # 功能性备注: 获取格式化文本
        # 逻辑备注: 检查文本是否为空
        if not formatted_text.strip(): messagebox.showwarning("无内容", "步骤一结果为空，无法导入名称。", parent=self.view); return
        try:
            # 功能性备注: 使用正则表达式查找 [名字] 格式的标记
            potential_names = re.findall(r'\[([^\]:]+)\]', formatted_text)
            # 逻辑备注: 过滤掉无效名称（空、纯符号、数字、特定关键字如 image/name/insert_image_here）
            filtered_names = set(name.strip() for name in potential_names if name.strip() and not re.fullmatch(r'[\d\W_]+', name) and name.lower() not in ['image', 'name'] and not name.lower().startswith('insert_image_here'))
            # 逻辑备注: 如果没有找到有效名称
            if not filtered_names: messagebox.showinfo("未找到名称", "在步骤一结果中未能自动识别出新的人物名称标记。", parent=self.view); return
            # 逻辑备注: 检查人物设定 Tab 是否可用
            if hasattr(self.view.app, 'profiles_tab') and self.view.app.profiles_tab.winfo_exists():
                profiles_tab = self.view.app.profiles_tab; added_count = 0; skipped_count = 0
                # 功能性备注: 遍历找到的名称
                for name in filtered_names:
                    if name not in profiles_tab.character_profiles: # 逻辑备注: 如果名称不在现有设定中
                        # 功能性备注: 添加新的默认设定条目 (包含新字段)
                        profiles_tab.character_profiles[name] = {"display_name": name, "replacement_name": "", "nai_positive": "", "nai_negative": "", "sd_positive": "", "sd_negative": "", "image_path": "", "mask_path": "", "loras": [] }
                        added_count += 1; logger.info(f"  > 已添加新名称到人物设定: {name}") # 功能性备注
                    else: skipped_count += 1 # 逻辑备注: 如果已存在则跳过
                # 逻辑备注: 如果添加了新名称
                if added_count > 0:
                    profiles_tab._update_profile_selector() # 功能性备注: 更新下拉列表
                    messagebox.showinfo("导入完成", f"成功导入 {added_count} 个新的人物名称到“人物设定”标签页。\n跳过了 {skipped_count} 个已存在的名称。", parent=self.view)
                else: messagebox.showinfo("无需导入", "所有在步骤一结果中识别出的名称均已存在于人物设定中。", parent=self.view)
            else: messagebox.showerror("内部错误", "无法访问人物设定标签页。", parent=self.view)
        except Exception as e:
            # 逻辑备注: 处理导入错误
            logger.exception(f"从步骤一导入名称时出错: {e}"); messagebox.showerror("导入错误", f"从步骤一结果导入名称时发生错误:\n{e}", parent=self.view) # 逻辑备注

    def save_kag_script(self):
        """保存 KAG 脚本到文件"""
        # 功能性备注: 将 KAG 脚本框内容保存为 .ks 文件
        logger.info("请求保存 KAG 脚本...") # 功能性备注
        kag_script_content = self.view.widgets['kag_script_widget'].get("1.0", "end-1c") # 功能性备注: 获取 KAG 脚本内容
        # 逻辑备注: 检查内容是否为空
        if not kag_script_content or not kag_script_content.strip():
            messagebox.showwarning("无内容", "KAG 脚本内容为空，无法保存。", parent=self.view); logger.warning("保存中止：KAG 脚本为空。"); return # 逻辑备注
        try:
            # 功能性备注: 弹出文件保存对话框
            filepath = filedialog.asksaveasfilename(
                title="保存 KAG 脚本",
                defaultextension=".ks",
                filetypes=[("KAG 脚本", "*.ks"), ("所有文件", "*.*")],
                initialfile="scene1.ks", # 功能性备注: 默认文件名
                parent=self.view
            )
            if not filepath: logger.info("用户取消保存。"); return # 功能性备注
            # 功能性备注: 以 UTF-16 LE 编码（带 BOM 头）写入文件
            with open(filepath, 'wb') as f:
                f.write(codecs.BOM_UTF16_LE) # 功能性备注: 写入 BOM
                f.write(kag_script_content.encode('utf-16-le')) # 功能性备注: 写入内容
            logger.info(f"KAG 脚本已成功保存到 (UTF-16 LE with BOM): {filepath}") # 功能性备注
            messagebox.showinfo("保存成功", f"KAG 脚本已成功保存为 (UTF-16 LE with BOM):\n{filepath}", parent=self.view)
            # 功能性备注: 更新状态标签
            status_label = self.view.widgets.get('step3_status_label')
            if status_label:
                self.update_ui_element(status_label, text=f"已保存: {os.path.basename(filepath)}", text_color="green")
                self.view.after(5000, lambda: self.update_ui_element(status_label, text="", text_color="gray")) # 功能性备注: 5秒后清空
        except Exception as e:
            # 逻辑备注: 处理保存错误
            logger.exception(f"保存 KAG 脚本时发生意外错误: {e}"); messagebox.showerror("保存错误", f"保存 KAG 脚本时发生意外错误:\n{e}", parent=self.view) # 逻辑备注

    # 逻辑备注: 移除重新注释功能
    # def recomment_image_tags(self): ...
    # def recomment_audio_tags(self): ...

    # --- 新增：停止任务方法 ---
    def stop_current_task(self):
        """请求停止当前正在运行的后台任务"""
        # 功能性备注: 由“停止”按钮触发
        if self.task_running:
            logger.info("用户请求停止当前任务...") # 功能性备注
            self.stop_event.set() # 功能性备注: 设置停止信号
            # 功能性备注: 更新 UI，例如禁用停止按钮防止重复点击，并显示“正在停止”
            # 逻辑修改: 停止按钮现在位于主应用中
            stop_button = self.view.app.main_stop_button
            if stop_button: self.update_ui_element(stop_button, state="disabled")
            # 逻辑备注: 找到当前活动的状态标签并更新
            active_status_label = None
            # (这里可以根据 task_id 或其他逻辑找到对应的状态标签)
            # 示例：简单地更新所有状态标签
            for label_key in ['step1_status_label', 'step2_status_label', 'step3_status_label', 'nai_gen_status_label', 'sd_gen_status_label', 'comfy_gen_status_label', 'audio_gen_status_label']:
                 lbl = self.view.widgets.get(label_key)
                 if lbl and lbl.winfo_exists() and "处理中" in lbl.cget("text"): # 逻辑修改: 增加控件存在性检查
                     active_status_label = lbl
                     break
            if active_status_label:
                self.update_ui_element(active_status_label, text="正在停止...", text_color="orange")
            else: # 逻辑备注: 如果找不到活动标签，更新主状态栏
                if hasattr(self.view.app, 'status_label') and self.view.app.status_label.winfo_exists():
                    self.view.app.status_label.configure(text="正在停止任务...", text_color="orange")
        else:
            logger.info("没有任务正在运行，忽略停止请求。") # 功能性备注
