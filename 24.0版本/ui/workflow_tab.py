# ui/workflow_tab.py
import customtkinter as ctk # 功能性备注: 导入 customtkinter 库
from tkinter import StringVar, messagebox, IntVar, Text, filedialog, BooleanVar, DoubleVar # 功能性备注: 导入 Tkinter 相关变量和对话框
from queue import Queue, Empty # 功能性备注: 导入队列，用于线程通信
import threading # 功能性备注: 导入线程模块
import json # 功能性备注: 导入 JSON 模块
import traceback # 功能性备注: 保留用于错误处理（虽然 logger.exception 更好）
import base64 # 功能性备注: 导入 Base64 模块
from pathlib import Path # 功能性备注: 导入 Path 对象
import os # 功能性备注: 导入 OS 模块
import re # 功能性备注: 导入正则表达式模块
import time # 功能性备注: 导入时间模块
import codecs # 功能性备注: 导入 codecs 模块，用于文件编码
import copy # 功能性备注: 导入 copy 模块
import logging # 功能性备注: 导入日志模块

# 功能性备注: 导入 UI 构建器和控制器
from .workflow_tab_builder import WorkflowTabUIBuilder
from .workflow_tab_controller import WorkflowTabController
# 功能性备注: 导入新增的弹窗选择器
from .media_selector_popup import MediaSelectorPopup

# 功能性备注: 获取当前模块的 logger 实例
logger = logging.getLogger(__name__)

class WorkflowTab(ctk.CTkFrame):
    """核心转换流程的 UI 标签页""" # 功能性备注: 类定义
    def __init__(self, master, config_manager, api_helpers, utils, sound_player, app_instance):
        # 功能性备注: 初始化父类 Frame
        super().__init__(master, fg_color="transparent")
        self.config_manager = config_manager
        self.api_helpers = api_helpers
        self.utils = utils
        self.sound_player = sound_player # 功能性备注: 保存 sound_player 实例
        self.app = app_instance # 功能性备注: 保存主应用实例引用

        # 功能性备注: UI 状态变量
        self.override_kag_temp_var = BooleanVar(value=False) # 是否覆盖 KAG 转换温度
        self.kag_temp_var = StringVar(value="0.1") # KAG 转换的覆盖温度值
        self.use_img2img_var = BooleanVar(value=False) # 是否启用图生图/内绘模式
        self.img_gen_scope_var = StringVar(value="uncommented") # 图片生成范围 ('all', 'uncommented', 'commented', 'specific')
        self.specific_images_var = StringVar() # 指定的图片文件名 (逗号分隔)
        self.img_n_samples_var = IntVar(value=1) # 每个任务生成的图片数量
        self.audio_gen_scope_var = StringVar(value="uncommented") # 语音生成范围 ('all', 'uncommented', 'commented', 'specific')
        self.specific_speakers_var = StringVar() # 指定的语音占位符
        self.image_prefix_var = StringVar() # 手动替换图片占位符时使用的前缀
        self.audio_prefix_var = StringVar(value="cv_") # 语音生成时使用的文件名前缀

        # 功能性备注: 主滚动框架，容纳所有 UI 元素
        self.scrollable_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scrollable_frame.pack(expand=True, fill="both")

        # 功能性备注: 实例化 UI 构建器并构建界面
        self.builder = WorkflowTabUIBuilder(self, self.app)
        self.widgets = self.builder.build_ui_within_scrollable_frame(self.scrollable_frame) # 功能性备注: 保存控件引用

        # 功能性备注: 实例化控制器
        self.controller = WorkflowTabController(self)

        # 功能性备注: 连接按钮命令到控制器方法
        self.widgets['preprocess_button'].configure(command=self.controller.run_step1_preprocess)
        self.widgets['import_names_button'].configure(command=self.controller.import_names_from_step1)
        self.widgets['enhance_nai_button'].configure(command=self.controller.run_step2_enhance_nai)
        self.widgets['enhance_sd_comfy_button'].configure(command=self.controller.run_step2_enhance_sd_comfy)
        self.widgets['convert_button'].configure(command=self.controller.run_step3_convert)
        self.widgets['replace_placeholder_button'].configure(command=self.controller.manual_replace_placeholders)
        self.widgets['generate_nai_button'].configure(command=self.controller.run_generate_nai)
        self.widgets['generate_sd_button'].configure(command=self.controller.run_generate_sd_webui)
        self.widgets['generate_comfy_button'].configure(command=self.controller.run_generate_comfyui)
        self.widgets['generate_audio_button'].configure(command=self.controller.run_generate_audio)
        self.widgets['save_ks_button'].configure(command=self.controller.save_kag_script)

        # 功能性备注: 绑定事件 (移到这里，使用 self.widgets 访问)
        key_release_widgets = [
            self.widgets['novel_text_widget'], self.widgets['structured_text_widget'],
            self.widgets['enhanced_text_widget'], self.widgets['kag_script_widget']
        ]
        for widget in key_release_widgets:
            if widget:
                try: widget.bind("<KeyRelease>", self.update_button_states)
                except Exception as bind_e: logger.warning(f"警告：绑定 KeyRelease 到 {type(widget).__name__} 出错: {bind_e}") # 功能性备注

        # 功能性备注: 启动队列检查循环，定时处理后台任务结果
        self.after(100, self.check_queue)

    def check_queue(self):
        """定时检查后台任务结果队列，并委托给控制器处理"""
        # 功能性备注: 将队列处理委托给控制器
        self.controller.process_queue()
        # 逻辑备注: 无论如何，100ms 后再次检查队列
        self.after(100, self.check_queue)

    # 功能性备注: toggle_specific_images_entry, toggle_specific_speakers_entry, toggle_kag_temp_entry 保持不变
    def toggle_specific_images_entry(self):
        """切换指定图片文件名输入框和选择按钮的启用状态"""
        # 功能性备注: 控制指定图片输入框和按钮的可用性
        is_specific = self.img_gen_scope_var.get() == "specific"
        new_state = "normal" if is_specific else "disabled"
        # 逻辑备注: 检查控件是否存在
        if 'specific_images_entry' in self.widgets and self.widgets['specific_images_entry'].winfo_exists():
            self.widgets['specific_images_entry'].configure(state=new_state)
            if not is_specific: self.specific_images_var.set("") # 功能性备注: 非指定模式时清空输入
        else:
            logger.warning("尝试切换指定图片输入框状态，但控件不存在。")
        # 功能性备注: 同时控制选择按钮的状态
        if 'img_select_button' in self.widgets and self.widgets['img_select_button'].winfo_exists():
            self.widgets['img_select_button'].configure(state=new_state)
        else:
            logger.warning("尝试切换图片选择按钮状态，但控件不存在。")

    def toggle_specific_speakers_entry(self):
        """切换指定语音占位符输入框和选择按钮的启用状态"""
        # 功能性备注: 控制指定语音输入框和按钮的可用性
        is_specific = self.audio_gen_scope_var.get() == "specific"
        new_state = "normal" if is_specific else "disabled"
        # 逻辑备注: 检查控件是否存在
        if 'specific_speakers_entry' in self.widgets and self.widgets['specific_speakers_entry'].winfo_exists():
            self.widgets['specific_speakers_entry'].configure(state=new_state)
            if not is_specific: self.specific_speakers_var.set("") # 功能性备注: 非指定模式时清空输入
        else:
            logger.warning("尝试切换指定语音输入框状态，但控件不存在。")
        # 功能性备注: 同时控制选择按钮的状态
        if 'audio_select_button' in self.widgets and self.widgets['audio_select_button'].winfo_exists():
            self.widgets['audio_select_button'].configure(state=new_state)
        else:
            logger.warning("尝试切换语音选择按钮状态，但控件不存在。")

    def toggle_kag_temp_entry(self):
        """切换 KAG 温度覆盖输入框的启用状态"""
        # 功能性备注: 控制 KAG 温度输入框的可用性
        is_override = self.override_kag_temp_var.get()
        new_state = "normal" if is_override else "disabled"
        # 逻辑备注: 检查控件是否存在
        if 'kag_temp_entry' in self.widgets and self.widgets['kag_temp_entry'].winfo_exists():
            self.widgets['kag_temp_entry'].configure(state=new_state)
        else:
            logger.warning("尝试切换 KAG 温度输入框状态，但控件不存在。")

    def update_button_states(self, event=None):
        """更新所有按钮的启用/禁用状态"""
        # 功能性备注: 根据当前状态控制所有按钮的可用性
        # 逻辑备注: 检查窗口是否存在，避免在关闭过程中出错
        if not self.winfo_exists(): return
        # 逻辑备注: 检查必要的 UI 元素是否存在 (防御性编程)
        required_widget_keys = [
            'preprocess_button', 'import_names_button',
            'enhance_nai_button', 'enhance_sd_comfy_button',
            'convert_button', 'replace_placeholder_button',
            'generate_nai_button', 'generate_sd_button', 'generate_comfy_button',
            'generate_audio_button', 'save_ks_button',
            'novel_text_widget', 'structured_text_widget', 'enhanced_text_widget',
            'kag_script_widget'
        ]
        # 逻辑备注: 检查主应用的停止按钮是否存在
        main_stop_button_exists = hasattr(self.app, 'main_stop_button') and self.app.main_stop_button and self.app.main_stop_button.winfo_exists()

        if not all(key in self.widgets and self.widgets[key] and self.widgets[key].winfo_exists() for key in required_widget_keys) or not main_stop_button_exists:
            logger.warning("警告：尝试更新按钮状态时，部分 UI 控件尚未完全初始化或已销毁。") # 逻辑备注
            return

        # 功能性备注: 获取当前状态
        task_running = self.controller.task_running # 从控制器获取任务状态
        step1_ready = self.widgets['novel_text_widget'].get("1.0", "end-1c").strip() != "" # 原文框是否有内容
        step2_ready = self.widgets['structured_text_widget'].get("1.0", "end-1c").strip() != "" # 格式化框是否有内容
        step3_ready = self.widgets['enhanced_text_widget'].get("1.0", "end-1c").strip() != "" # 提示词框是否有内容
        step4_ready = self.widgets['kag_script_widget'].get("1.0", "end-1c").strip() != "" # KAG脚本框是否有内容

        selected_llm_provider = self.app.selected_llm_provider_var.get() # 功能性备注: 当前选择的 LLM 提供商
        llm_ready = self.controller._check_llm_readiness(selected_llm_provider) # 功能性备注: LLM 配置是否就绪 (调用控制器的方法)

        # 功能性备注: 获取图片和语音配置
        shared_img_config = self.app.get_image_gen_shared_config()
        sd_config = self.app.get_sd_config()
        comfy_config = self.app.get_comfyui_config()
        nai_config = self.app.get_nai_config()
        gptsovits_config = self.app.get_gptsovits_config()

        # 功能性备注: 判断各 API 是否就绪
        img_shared_ready = shared_img_config and shared_img_config.get('imageSaveDir') # 共享图片保存目录是否配置
        sd_ready = sd_config and sd_config.get('sdWebUiUrl') # SD URL 是否配置
        comfy_workflow_path = comfy_config.get('comfyWorkflowFile', '') # Comfy 工作流路径
        comfy_ready = comfy_config and comfy_config.get('comfyapiUrl') and comfy_workflow_path and os.path.exists(comfy_workflow_path) # Comfy URL、工作流路径且文件存在
        nai_ready = nai_config and nai_config.get('naiApiKey') and nai_config.get('naiImageSaveDir') # NAI Key 和保存目录是否配置
        audio_ready = gptsovits_config and gptsovits_config.get('apiUrl') and gptsovits_config.get('audioSaveDir') and gptsovits_config.get('character_voice_map') # GPT-SoVITS URL、保存目录、语音映射是否配置

        # --- 功能性备注: 更新按钮状态 (根据条件判断是否启用) ---
        self.controller.update_ui_element(self.widgets['preprocess_button'], state="normal" if step1_ready and llm_ready else "disabled")
        self.controller.update_ui_element(self.widgets['import_names_button'], state="normal" if step2_ready else "disabled")
        self.controller.update_ui_element(self.widgets['enhance_nai_button'], state="normal" if step2_ready and llm_ready else "disabled")
        self.controller.update_ui_element(self.widgets['enhance_sd_comfy_button'], state="normal" if step2_ready and llm_ready else "disabled")
        self.controller.update_ui_element(self.widgets['convert_button'], state="normal" if step3_ready and llm_ready else "disabled")
        self.controller.update_ui_element(self.widgets['replace_placeholder_button'], state="normal" if step4_ready else "disabled")
        self.controller.update_ui_element(self.widgets['generate_nai_button'], state="normal" if step4_ready and nai_ready else "disabled")
        self.controller.update_ui_element(self.widgets['generate_sd_button'], state="normal" if step4_ready and img_shared_ready and sd_ready else "disabled")
        self.controller.update_ui_element(self.widgets['generate_comfy_button'], state="normal" if step4_ready and img_shared_ready and comfy_ready else "disabled")
        self.controller.update_ui_element(self.widgets['generate_audio_button'], state="normal" if step4_ready and audio_ready else "disabled")
        self.controller.update_ui_element(self.widgets['save_ks_button'], state="normal" if step4_ready else "disabled")
        # 逻辑备注: 更新位于 main_app 中的停止按钮的状态
        self.controller.update_ui_element(self.app.main_stop_button, state="normal" if task_running else "disabled")

    # 功能性备注: get_workflow_texts, set_workflow_texts, get_workflow_ui_state, set_workflow_ui_state 保持不变
    def get_workflow_texts(self):
        """获取四个主要文本框的内容"""
        # 功能性备注: 提供文本框内容给外部
        return {
            "novel": self.widgets['novel_text_widget'].get("1.0", "end-1c"),
            "structured": self.widgets['structured_text_widget'].get("1.0", "end-1c"),
            "enhanced": self.widgets['enhanced_text_widget'].get("1.0", "end-1c"),
            "kag": self.widgets['kag_script_widget'].get("1.0", "end-1c")
        }

    def set_workflow_texts(self, texts_dict):
        """设置四个主要文本框的内容"""
        # 功能性备注: 从外部加载文本内容
        if not isinstance(texts_dict, dict): return # 逻辑备注: 检查输入是否为字典
        # 功能性备注: 安全地更新每个文本框 (使用 controller 的方法)
        self.controller.update_ui_element(self.widgets['novel_text_widget'], text=texts_dict.get("novel", ""), append=False)
        self.controller.update_ui_element(self.widgets['structured_text_widget'], text=texts_dict.get("structured", ""), append=False)
        self.controller.update_ui_element(self.widgets['enhanced_text_widget'], text=texts_dict.get("enhanced", ""), append=False)
        self.controller.update_ui_element(self.widgets['kag_script_widget'], text=texts_dict.get("kag", ""), append=False)
        # 功能性备注: 更新按钮状态以反映文本框内容变化
        self.update_button_states()

    def get_workflow_ui_state(self):
        """获取 Workflow Tab 的特定 UI 状态变量值"""
        # 功能性备注: 提供 UI 状态给外部
        return {
            "override_kag_temp": self.override_kag_temp_var.get(),
            "kag_temp": self.kag_temp_var.get(),
            "use_img2img": self.use_img2img_var.get(),
            "img_gen_scope": self.img_gen_scope_var.get(), # 逻辑修改: 保存新的范围值
            "specific_images": self.specific_images_var.get(),
            "img_n_samples": self.img_n_samples_var.get(),
            "audio_gen_scope": self.audio_gen_scope_var.get(), # 逻辑修改: 保存新的范围值
            "specific_speakers": self.specific_speakers_var.get(),
            "image_prefix": self.image_prefix_var.get(),
            "audio_prefix": self.audio_prefix_var.get()
        }

    def set_workflow_ui_state(self, state_dict):
        """恢复 Workflow Tab 的特定 UI 状态"""
        # 功能性备注: 从外部加载 UI 状态
        if not isinstance(state_dict, dict): return # 逻辑备注: 检查输入是否为字典
        # 功能性备注: 恢复各个 UI 状态变量的值，提供默认值以防 key 不存在
        self.override_kag_temp_var.set(state_dict.get("override_kag_temp", False))
        self.kag_temp_var.set(state_dict.get("kag_temp", "0.1"))
        self.use_img2img_var.set(state_dict.get("use_img2img", False))
        self.img_gen_scope_var.set(state_dict.get("img_gen_scope", "uncommented"))
        self.specific_images_var.set(state_dict.get("specific_images", ""))
        self.img_n_samples_var.set(state_dict.get("img_n_samples", 1))
        self.audio_gen_scope_var.set(state_dict.get("audio_gen_scope", "uncommented"))
        self.specific_speakers_var.set(state_dict.get("specific_speakers", ""))
        self.image_prefix_var.set(state_dict.get("image_prefix", ""))
        self.audio_prefix_var.set(state_dict.get("audio_prefix", "cv_"))
        # 功能性备注: 根据恢复的状态更新依赖这些变量的 UI 控件的状态
        self.toggle_kag_temp_entry()
        self.toggle_specific_images_entry()
        self.toggle_specific_speakers_entry()
        self.update_button_states() # 功能性备注: 更新所有按钮状态

    # --- 新增：打开媒体选择弹窗的方法 ---
    def _open_media_selector_popup(self, media_type):
        """打开用于选择图片或语音任务的弹窗"""
        # 功能性备注: 弹出选择窗口，让用户选择要生成的特定媒体项
        logger.info(f"请求打开 {media_type} 选择弹窗...")
        kag_script = self.widgets['kag_script_widget'].get("1.0", "end-1c") # 功能性备注: 获取 KAG 脚本
        if not kag_script.strip():
            messagebox.showwarning("无脚本", "KAG 脚本内容为空，无法解析任务列表。", parent=self)
            return

        items_with_status = [] # 功能性备注: 存储解析出的任务及其状态
        save_dir = None # 功能性备注: 初始化保存目录
        try:
            if media_type == 'image':
                # 逻辑备注: 获取共享图片保存目录
                shared_img_config = self.app.get_image_gen_shared_config()
                save_dir = shared_img_config.get('imageSaveDir')
                # 逻辑备注: 解析图片任务，提取更多信息
                pattern = re.compile(
                    r"^\s*(;\s*(?:NAI|IMG)\s+Prompt for\s*(.*?):\s*Positive=\[(.*?)\](?:\s*Negative=\[(.*?)\])?)\s*$\n"
                    r"(?:\s*(?:;\s*SD Prompt for\s*.*?:?\s*Positive=\[.*?\](?:\s*Negative=\[.*?\])?)\s*$\n)?"
                    r"\s*((;?)(\[image\s+storage=\"(.*?)\".*?\]))",
                    re.MULTILINE | re.IGNORECASE
                )
                character_profiles = self.app.profiles_tab.character_profiles if hasattr(self.app, 'profiles_tab') else {}
                for match in pattern.finditer(kag_script):
                    name = match.group(2).strip() if match.group(2) else "Unknown"
                    positive_prompt = match.group(3).strip() if match.group(3) else ""
                    negative_prompt = match.group(4).strip() if match.group(4) is not None else ""
                    is_commented = match.group(6) == ";"
                    filename = match.group(8).strip() if match.group(8) else ""
                    if not filename: continue

                    profile_data = character_profiles.get(name, {})
                    ref_image_path = profile_data.get("image_path", "")
                    mask_image_path = profile_data.get("mask_path", "")

                    config_valid = name in character_profiles
                    status = "error"
                    if config_valid: status = "ready" if is_commented else "generated"

                    items_with_status.append({
                        "id": filename, "name": name, "status": status,
                        "positive_prompt": positive_prompt, "negative_prompt": negative_prompt,
                        "ref_image_path": ref_image_path, "mask_image_path": mask_image_path
                    })

            elif media_type == 'audio':
                # 逻辑备注: 解析语音任务，并提取对应的文本
                pattern = re.compile(
                    r"^\s*((;?)(\s*@playse\s+storage=\"(PLACEHOLDER_.*?)\".*?;\s*name=\"(.*?)\"))\s*$\n\s*(?:「(.*?)」|\（(.*?)\）)\[p\]",
                    re.MULTILINE | re.IGNORECASE
                )
                voice_map = self.app.get_gptsovits_config().get("character_voice_map", {})
                for match in pattern.finditer(kag_script):
                    is_commented = match.group(2) == ";"
                    placeholder = match.group(4).strip()
                    speaker_name = match.group(5).strip()
                    dialogue_content = match.group(6); monologue_content = match.group(7)
                    text_to_speak = ""
                    if dialogue_content is not None: text_to_speak = dialogue_content.strip()
                    elif monologue_content is not None: text_to_speak = monologue_content.strip()

                    if not placeholder: continue

                    config_valid = speaker_name in voice_map
                    status = "error"
                    if config_valid: status = "ready" if is_commented else "generated"
                    # 逻辑备注: 添加提取到的文本到字典
                    items_with_status.append({"id": placeholder, "name": speaker_name, "status": status, "text": text_to_speak})
            else:
                logger.error(f"未知的媒体类型: {media_type}")
                return

            # 逻辑备注: 去重并排序
            unique_items = {item['id']: item for item in items_with_status}.values()
            sorted_items = sorted(list(unique_items), key=lambda x: x['id'])

            if not sorted_items:
                messagebox.showinfo("无任务", f"在 KAG 脚本中未找到可选择的 {media_type} 任务。", parent=self)
                return

            # 功能性备注: 打开弹窗，传递 save_dir (仅图片类型需要)
            popup = MediaSelectorPopup(
                self,
                title=f"选择 {media_type.capitalize()} 任务",
                items=sorted_items,
                media_type=media_type,
                save_dir=save_dir if media_type == 'image' else None # 功能性备注: 传递保存目录
            )
            selected_ids = popup.show() # 功能性备注: 显示弹窗并等待结果

            # 功能性备注: 处理弹窗返回的结果
            if selected_ids is not None: # 逻辑备注: 检查是否是 None (用户可能取消)
                logger.info(f"用户通过弹窗选择了 {len(selected_ids)} 个 {media_type} 任务。")
                selected_str = ",".join(selected_ids)
                if media_type == 'image':
                    self.specific_images_var.set(selected_str)
                elif media_type == 'audio':
                    self.specific_speakers_var.set(selected_str)
            else:
                logger.info(f"用户取消了 {media_type} 选择弹窗。")

        except Exception as e:
            logger.exception(f"打开或处理 {media_type} 选择弹窗时出错: {e}")
            messagebox.showerror("错误", f"处理 {media_type} 选择列表时出错:\n{e}", parent=self)