# main_app.py
import customtkinter as ctk
from tkinter import messagebox, BooleanVar, StringVar, filedialog # 功能性备注: 导入 filedialog
import threading
import queue # 功能性备注: 导入 queue 用于日志和结果处理
import os
import sys
import json # 功能性备注: 导入 json 用于状态保存/加载
import traceback
from pathlib import Path
import logging # 功能性备注: 导入标准日志库

# --- 导入自定义模块 ---
# 功能性备注: 保持导入不变
try:
    from core import config_manager, utils, sound_player, logger_setup # 导入 logger_setup
    # 新增：导入配置初始化模块
    from core import config_initializer
    from api import api_helpers # Facade for all API helpers
    from core.prompts import PromptTemplates
    from tasks import workflow_tasks, image_generation_tasks, audio_generation_tasks
except ImportError as e:
    # 初始导入错误时，日志系统可能尚未设置，仍使用 print
    print(f"严重错误：无法导入核心模块: {e}")
    print("请确保所有 .py 文件位于正确的子目录 (api, core, tasks, ui) 且包含 __init__.py。")
    try: root = ctk.CTk(); root.withdraw(); messagebox.showerror("启动错误", f"无法加载核心模块: {e}\n请检查项目文件结构。"); root.destroy()
    except: pass
    sys.exit(1)

# --- 导入 UI 标签页类 ---
# 功能性备注: 保持导入不变
try:
    from ui.llm_config_tab import LLMConfigTab
    from ui.image_gen_config_tab import ImageGenConfigTab # 统一图片设置 Tab
    from ui.nai_config_tab import NAIConfigTab
    from ui.profiles_tab import ProfilesTab
    from ui.workflow_tab import WorkflowTab
    from ui.gptsovits_config_tab import GPTSoVITSConfigTab
    from ui.logging_tab import LoggingTab # 导入新的日志标签页
except ImportError as e:
    # 初始导入错误时，日志系统可能尚未设置，仍使用 print
    print(f"严重错误：无法导入 UI 标签页模块: {e}")
    print("请确保 'ui' 文件夹存在且包含所需的 .py 文件和 __init__.py。")
    try: root = ctk.CTk(); root.withdraw(); messagebox.showerror("启动错误", f"无法加载界面模块: {e}\n请检查项目文件结构。"); root.destroy()
    except: pass
    sys.exit(1)

# --- 调试日志目录 ---
# 功能性备注: 保持不变
DEBUG_LOG_DIR = Path("debug_logs") / "api_requests" # 全局定义 DEBUG_LOG_DIR

# --- 获取主模块的 logger ---
# 功能性备注: 保持不变
logger = logging.getLogger(__name__)

class NovelConverterApp(ctk.CTk):
    """主应用程序类""" # 功能性备注: 保持不变
    def __init__(self):
        super().__init__()

        # --- 初始化日志系统 (尽早调用) ---
        # 功能性备注: 保持不变
        logger_setup.setup_logging()
        logger.info("主应用程序日志系统已启动。")

        # --- 新增：确保所有配置文件存在 (在加载配置之前调用) ---
        # 功能性备注: 保持不变
        try:
            config_initializer.ensure_all_configs_exist()
        except Exception as init_e:
            # 记录初始化配置文件时的错误，但不中断程序启动
            logger.exception(f"初始化配置文件时发生错误: {init_e}")
            messagebox.showwarning("配置初始化警告", f"检查或创建默认配置文件时出错:\n{init_e}\n程序将继续尝试加载现有配置。")

        # 功能性备注: 保持窗口设置不变
        self.title("小说转 KAG 工具 (统一图片设置版)")
        self.geometry("1200x850")
        self.minsize(1000, 650)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        # --- 初始化核心模块实例 ---
        # 功能性备注: 保持不变
        self.config_manager = config_manager
        self.api_helpers = api_helpers; setattr(self.api_helpers, 'app', self) # 注入 app 引用
        self.utils = utils
        self.sound_player = sound_player
        self.prompt_templates = PromptTemplates()

        # --- 初始化状态变量 ---
        # 功能性备注: 保持不变
        self.enable_sound_var = BooleanVar(value=True)
        self.enable_win_notify_var = BooleanVar(value=True)
        self.selected_llm_provider_var = StringVar(value="Google")
        self.selected_image_provider_var = StringVar(value="SD WebUI")

        # --- 加载初始配置到内存缓存 ---
        # 功能性备注: 保持不变
        try:
            logger.info("正在加载初始配置...")
            self.llm_global_config = self.config_manager.load_config("llm_global")
            self.image_global_config = self.config_manager.load_config("image_global")
            self.image_gen_shared_config = self.config_manager.load_config("image_gen_shared") # 加载共享图片配置
            self.google_config = self.config_manager.load_config("google")
            self.openai_config = self.config_manager.load_config("openai")
            self.nai_config = self.config_manager.load_config("nai")
            self.sd_config = self.config_manager.load_config("sd") # SD 独立配置
            self.comfyui_config = self.config_manager.load_config("comfyui") # ComfyUI 独立配置
            self.gptsovits_config = self.config_manager.load_config("gptsovits")

            # 更新变量状态
            self.enable_sound_var.set(self.llm_global_config.get("enableSoundNotifications", True))
            self.enable_win_notify_var.set(self.llm_global_config.get("enableWinNotifications", True))
            self.selected_llm_provider_var.set(self.llm_global_config.get("selected_provider", "Google"))
            self.selected_image_provider_var.set(self.image_global_config.get("selected_image_provider", "SD WebUI"))
            logger.info("初始配置加载完成。")
        except Exception as e:
             # 使用 logging 记录严重错误，exc_info=True 会自动附加 traceback
             logger.critical(f"严重错误：加载初始配置时发生错误: {e}", exc_info=True)
             messagebox.showerror("配置加载错误", f"加载配置文件时出错:\n{e}\n将使用默认设置。")
             # 使用默认值初始化
             self.llm_global_config = config_manager.DEFAULT_LLM_GLOBAL_CONFIG.copy()
             self.image_global_config = config_manager.DEFAULT_IMAGE_GLOBAL_CONFIG.copy()
             self.image_gen_shared_config = config_manager.DEFAULT_IMAGE_GEN_SHARED_CONFIG.copy()
             self.google_config = config_manager.DEFAULT_GOOGLE_CONFIG.copy()
             self.openai_config = config_manager.DEFAULT_OPENAI_CONFIG.copy()
             self.nai_config = config_manager.DEFAULT_NAI_CONFIG.copy()
             self.sd_config = config_manager.DEFAULT_SD_CONFIG.copy()
             self.comfyui_config = config_manager.DEFAULT_COMFYUI_CONFIG.copy()
             self.gptsovits_config = config_manager.DEFAULT_GPTSOVITS_CONFIG.copy()
             # 更新变量状态
             self.enable_sound_var.set(self.llm_global_config.get("enableSoundNotifications", True))
             self.enable_win_notify_var.set(self.llm_global_config.get("enableWinNotifications", True))
             self.selected_llm_provider_var.set(self.llm_global_config.get("selected_provider", "Google"))
             self.selected_image_provider_var.set(self.image_global_config.get("selected_image_provider", "SD WebUI"))

        # --- 创建主界面 ---
        # 功能性备注: 保持不变
        try:
            logger.info("正在构建主界面...")
            self.build_main_ui()
            logger.info("主界面构建完成。")
            self.after(100, self.deferred_initial_updates) # 延迟更新
        except Exception as e:
             logger.critical(f"严重错误：构建主界面时发生错误: {e}", exc_info=True)
             messagebox.showerror("界面构建错误", f"创建主界面时出错:\n{e}\n程序即将退出。"); self.quit()

        # --- 启动日志队列处理循环 ---
        # 功能性备注: 保持不变
        self.after(100, self._process_log_queue)

    def build_main_ui(self):
        """构建主窗口的 UI 布局"""
        # 功能性备注: 配置主窗口网格
        self.grid_rowconfigure(1, weight=1); self.grid_columnconfigure(0, weight=1)

        # --- 顶部操作栏 ---
        # 功能性备注: 创建顶部框架
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="ew")
        # 逻辑备注: 配置 top_frame 的列权重，让状态标签列可扩展
        top_frame.grid_columnconfigure(3, weight=1) # 让最后一列扩展

        # --- 逻辑备注: 使用 grid 布局顶部按钮和控件 ---
        current_top_row = 0
        # 第一行：状态保存/加载
        save_state_button = ctk.CTkButton(top_frame, text="保存状态 (.json)", command=self.save_app_state)
        save_state_button.grid(row=current_top_row, column=0, padx=(0, 5), pady=5, sticky="w")
        load_state_button = ctk.CTkButton(top_frame, text="加载状态 (.json)", command=self.load_app_state)
        load_state_button.grid(row=current_top_row, column=1, padx=(0, 10), pady=5, sticky="w")
        current_top_row += 1

        # 第二行：设置保存/加载
        save_all_button = ctk.CTkButton(top_frame, text="保存所有设置", command=self.save_all_configs)
        save_all_button.grid(row=current_top_row, column=0, padx=(0, 5), pady=5, sticky="w")
        load_all_button = ctk.CTkButton(top_frame, text="加载所有设置", command=self.load_all_configs)
        load_all_button.grid(row=current_top_row, column=1, padx=(0, 10), pady=5, sticky="w")
        current_top_row += 1

        # 第三行：提供商选择
        llm_provider_label = ctk.CTkLabel(top_frame, text="LLM:"); llm_provider_label.grid(row=current_top_row, column=0, padx=(0, 2), pady=5, sticky="w")
        llm_provider_menu = ctk.CTkOptionMenu(top_frame, width=90, values=["Google", "OpenAI"], variable=self.selected_llm_provider_var, command=self.on_llm_provider_change); llm_provider_menu.grid(row=current_top_row, column=1, padx=(0, 10), pady=5, sticky="w")
        img_provider_label = ctk.CTkLabel(top_frame, text="图片:"); img_provider_label.grid(row=current_top_row, column=2, padx=(10, 2), pady=5, sticky="w")
        img_provider_menu = ctk.CTkOptionMenu(top_frame, width=110, values=["SD WebUI", "ComfyUI"], variable=self.selected_image_provider_var, command=self.on_image_provider_change); img_provider_menu.grid(row=current_top_row, column=3, padx=(0, 10), pady=5, sticky="w")
        current_top_row += 1

        # 第四行：通知和外观
        notify_frame = ctk.CTkFrame(top_frame, fg_color="transparent") # 使用内部 Frame 组织
        notify_frame.grid(row=current_top_row, column=0, columnspan=2, pady=5, sticky="w")
        sound_notify_check = ctk.CTkCheckBox(notify_frame, text="提示音", variable=self.enable_sound_var); sound_notify_check.pack(side="left", padx=(0, 5))
        win_notify_check = ctk.CTkCheckBox(notify_frame, text="系统通知", variable=self.enable_win_notify_var); win_notify_check.pack(side="left", padx=(5, 10))
        appearance_label = ctk.CTkLabel(top_frame, text="外观:"); appearance_label.grid(row=current_top_row, column=2, padx=(10, 5), pady=5, sticky="w")
        appearance_menu = ctk.CTkOptionMenu(top_frame, width=90, values=["Light", "Dark", "System"], command=self.change_appearance_mode_event); appearance_menu.grid(row=current_top_row, column=3, padx=(0, 10), pady=5, sticky="w"); appearance_menu.set(ctk.get_appearance_mode())
        current_top_row += 1

        # 第五行：停止按钮
        # 逻辑备注: 创建停止按钮，但命令绑定需要在 workflow_tab 实例化后进行
        self.main_stop_button = ctk.CTkButton(top_frame, text="停止当前任务", state="disabled", fg_color="#d9534f", hover_color="#c9302c")
        self.main_stop_button.grid(row=current_top_row, column=0, columnspan=2, padx=(0, 5), pady=5, sticky="w")
        current_top_row += 1

        # 状态标签 (放在最后一行，跨越所有列)
        self.status_label = ctk.CTkLabel(top_frame, text="准备就绪", text_color="gray", anchor="e");
        self.status_label.grid(row=current_top_row, column=0, columnspan=4, padx=10, pady=5, sticky="ew")

        # --- 创建 TabView ---
        # 功能性备注: 保持不变
        self.tab_view = ctk.CTkTabview(self, anchor="nw")
        self.tab_view.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        self.tab_view.add("转换流程")
        self.tab_view.add("人物设定")
        self.tab_view.add("LLM 设置")
        self.tab_view.add("图片生成设置") # 统一图片设置 Tab
        self.tab_view.add("NAI 设置")
        self.tab_view.add("GPT-SoVITS 设置")
        self.tab_view.add("日志") # 添加日志 Tab

        # --- 实例化并放置每个标签页的内容 ---
        # 功能性备注: 保持不变
        try:
            logger.info("正在实例化 WorkflowTab..."); self.workflow_tab = WorkflowTab(master=self.tab_view.tab("转换流程"), config_manager=self.config_manager, api_helpers=self.api_helpers, utils=self.utils, sound_player=self.sound_player, app_instance=self); self.workflow_tab.pack(expand=True, fill="both", padx=5, pady=5)
            logger.info("正在实例化 ProfilesTab..."); self.profiles_tab = ProfilesTab(master=self.tab_view.tab("人物设定"), config_manager=self.config_manager, app_instance=self); self.profiles_tab.pack(expand=True, fill="both", padx=5, pady=5)
            logger.info("正在实例化 LLMConfigTab..."); self.llm_tab = LLMConfigTab(master=self.tab_view.tab("LLM 设置"), config_manager=self.config_manager, app_instance=self); self.llm_tab.pack(expand=True, fill="both", padx=5, pady=5)
            logger.info("正在实例化 ImageGenConfigTab..."); self.image_gen_tab = ImageGenConfigTab(master=self.tab_view.tab("图片生成设置"), config_manager=self.config_manager, app_instance=self); self.image_gen_tab.pack(expand=True, fill="both", padx=5, pady=5) # 新增
            logger.info("正在实例化 NAIConfigTab..."); self.nai_tab = NAIConfigTab(master=self.tab_view.tab("NAI 设置"), config_manager=self.config_manager, app_instance=self); self.nai_tab.pack(expand=True, fill="both", padx=5, pady=5)
            logger.info("正在实例化 GPTSoVITSConfigTab..."); self.gptsovits_tab = GPTSoVITSConfigTab(master=self.tab_view.tab("GPT-SoVITS 设置"), config_manager=self.config_manager, app_instance=self); self.gptsovits_tab.pack(expand=True, fill="both", padx=5, pady=5)
            logger.info("正在实例化 LoggingTab..."); self.logging_tab = LoggingTab(master=self.tab_view.tab("日志"), log_queue=logger_setup.log_queue, app_instance=self); self.logging_tab.pack(expand=True, fill="both", padx=5, pady=5) # 实例化日志 Tab
        except Exception as e:
            # 使用 logging 记录错误
            logger.exception(f"严重错误：实例化或放置标签页内容时出错: {e}")
            messagebox.showerror("界面构建错误", f"创建标签页内容时出错:\n{e}")

        # 逻辑备注: 在 workflow_tab 实例化后，绑定停止按钮的命令
        if hasattr(self, 'workflow_tab') and self.workflow_tab:
            self.main_stop_button.configure(command=self.workflow_tab.controller.stop_current_task)
        else:
            logger.error("错误：无法绑定停止按钮命令，WorkflowTab 未成功实例化。")
            self.main_stop_button.configure(state="disabled") # 禁用按钮

        self.tab_view.set("转换流程") # 默认显示

    # 功能性备注: deferred_initial_updates, change_appearance_mode_event, on_closing, on_llm_provider_change, on_image_provider_change 保持不变
    def deferred_initial_updates(self):
        """延迟调用的初始状态更新"""
        logger.info("执行延迟的初始 UI 更新...")
        try:
            if hasattr(self, 'workflow_tab') and self.workflow_tab.winfo_exists():
                logger.info("正在更新 WorkflowTab 的初始按钮状态...")
                self.workflow_tab.update_button_states()
            else:
                logger.warning("WorkflowTab 不存在，无法更新初始按钮状态。")
            if hasattr(self, 'llm_tab') and self.llm_tab.winfo_exists():
                self.llm_tab.on_provider_change(self.selected_llm_provider_var.get())
            if hasattr(self, 'image_gen_tab') and self.image_gen_tab.winfo_exists():
                self.image_gen_tab.on_provider_change(self.selected_image_provider_var.get()) # 更新图片 Tab 初始显示
        except Exception as e:
            logger.error(f"错误：执行延迟初始更新时出错: {e}", exc_info=True)
        logger.info("延迟更新完成。")

    def change_appearance_mode_event(self, new_appearance_mode: str):
        """切换应用的外观模式"""
        ctk.set_appearance_mode(new_appearance_mode)
        logger.info(f"外观模式已切换为: {new_appearance_mode}")
        # 逻辑备注: 外观模式改变后，需要重新加载并应用颜色配置
        if hasattr(self, 'logging_tab') and self.logging_tab.winfo_exists():
            self.logging_tab._load_and_apply_colors()

    def on_closing(self):
        """处理窗口关闭事件"""
        if messagebox.askokcancel("退出确认", "确定要退出应用程序吗？\n未保存的设置将会丢失。"):
            logger.info("正在关闭应用程序...")
            self.destroy()
        else:
            logger.info("取消退出。")

    def on_llm_provider_change(self, selected_provider):
        """当用户切换 LLM 提供商时调用"""
        logger.info(f"LLM 提供商已切换为: {selected_provider}")
        if hasattr(self, 'llm_tab') and self.llm_tab.winfo_exists():
            self.llm_tab.on_provider_change(selected_provider)
        if hasattr(self, 'workflow_tab') and self.workflow_tab.winfo_exists():
            self.workflow_tab.update_button_states()

    def on_image_provider_change(self, selected_provider):
        """当用户切换图片提供商时调用"""
        logger.info(f"图片提供商已切换为: {selected_provider}")
        if hasattr(self, 'image_gen_tab') and self.image_gen_tab.winfo_exists():
            self.image_gen_tab.on_provider_change(selected_provider) # 通知图片 Tab 更新显示
        if hasattr(self, 'workflow_tab') and self.workflow_tab.winfo_exists():
            self.workflow_tab.update_button_states()

    # --- 配置获取方法 ---
    # 功能性备注: get_global_llm_config, get_image_global_config, get_image_gen_shared_config, get_google_specific_config, get_openai_specific_config, get_nai_config, get_sd_config, get_comfyui_config, get_gptsovits_config, get_profiles_json 保持不变
    def get_global_llm_config(self):
        """获取全局 LLM 配置，确保从 UI 获取最新的调试开关状态和颜色配置"""
        # 功能性备注: 先从缓存加载基础配置
        config = self.llm_global_config.copy()
        # 功能性备注: 更新主窗口控制的变量
        config["enableSoundNotifications"] = self.enable_sound_var.get()
        config["enableWinNotifications"] = self.enable_win_notify_var.get()
        config["selected_provider"] = self.selected_llm_provider_var.get()
        # 功能性备注: 从 LLM Tab 获取最新的共享配置（包括调试开关）
        if hasattr(self, 'llm_tab') and self.llm_tab.winfo_exists():
             llm_data = self.llm_tab.get_config_data()
             shared_data = llm_data.get("shared", {})
             config.update(shared_data) # 用 UI 获取的值更新缓存副本
        # 功能性备注: 从 Logging Tab 获取最新的颜色配置
        if hasattr(self, 'logging_tab') and self.logging_tab.winfo_exists():
            color_data = self.logging_tab.get_color_config_data()
            config.update(color_data) # 用 UI 获取的颜色值更新缓存副本
        return config

    def get_image_global_config(self):
        """获取图片全局配置"""
        self.image_global_config["selected_image_provider"] = self.selected_image_provider_var.get()
        return self.image_global_config.copy()

    def get_image_gen_shared_config(self):
        """获取共享图片配置，确保从 UI 获取最新的调试开关状态"""
        config = self.image_gen_shared_config.copy()
        if hasattr(self, 'image_gen_tab') and self.image_gen_tab.winfo_exists():
            img_data = self.image_gen_tab.get_config_data()
            shared_data = img_data.get("shared", {})
            config.update(shared_data) # 用 UI 获取的值更新缓存副本
        return config

    def get_google_specific_config(self):
        """获取 Google 特定配置"""
        return self.google_config.copy()

    def get_openai_specific_config(self):
        """获取 OpenAI 特定配置"""
        return self.openai_config.copy()

    def get_nai_config(self):
        """获取 NAI 配置，确保从 UI 获取最新的调试开关状态"""
        config = self.nai_config.copy()
        if hasattr(self, 'nai_tab') and self.nai_tab.winfo_exists():
            nai_data = self.nai_tab.get_config_data()
            config.update(nai_data) # 用 UI 获取的值更新缓存副本
        return config

    def get_sd_config(self):
        """获取 SD WebUI 独立配置"""
        return self.sd_config.copy()

    def get_comfyui_config(self):
        """获取 ComfyUI 独立配置"""
        return self.comfyui_config.copy()

    def get_gptsovits_config(self):
        """获取 GPT-SoVITS 配置，确保从 UI 获取最新的调试开关状态"""
        config = self.gptsovits_config.copy()
        if hasattr(self, 'gptsovits_tab') and self.gptsovits_tab.winfo_exists():
            gsv_data = self.gptsovits_tab.get_config_data()
            config.update(gsv_data) # 用 UI 获取的值更新缓存副本
        return config

    def get_profiles_json(self):
        """获取人物设定用于 Prompt (JSON 字符串)"""
        if hasattr(self, 'profiles_tab') and self.profiles_tab.winfo_exists():
            try:
                _, json_string = self.profiles_tab.get_profiles_for_step2()
                return json_string
            except Exception as e:
                logger.error(f"错误：从 Profiles Tab 获取 JSON 时出错: {e}", exc_info=True)
                return None
        else:
            logger.error("错误：人物设定标签页不可用！")
            return None

    # --- 全局配置保存/加载 ---
    # 功能性备注: save_all_configs, load_all_configs 保持不变
    def save_all_configs(self):
        """收集所有配置 Tab 的数据并保存到对应的配置文件"""
        logger.info("正在保存所有设置...")
        self.status_label.configure(text="正在保存...", text_color="orange")
        self.update_idletasks()
        all_saved = True
        failed_types = []
        try:
            # LLM 配置
            llm_data = None
            if hasattr(self, 'llm_tab') and self.llm_tab.winfo_exists():
                try:
                    llm_data = self.llm_tab.get_config_data()
                except Exception as e:
                    logger.error(f"错误：获取 LLM 配置失败: {e}", exc_info=True)
                    all_saved = False; failed_types.append("LLM (获取)")
            else:
                all_saved = False; failed_types.append("LLM (Tab 不可用)")

            if llm_data:
                # 逻辑备注: 获取全局 LLM 配置，其中已包含颜色配置
                global_llm_data = self.get_global_llm_config()
                # 逻辑备注: 更新从 LLM Tab 获取的共享参数 (确保覆盖缓存中的旧值)
                global_llm_data.update(llm_data.get("shared", {}))
                # 逻辑备注: 更新主窗口控制的变量
                global_llm_data["selected_provider"] = self.selected_llm_provider_var.get()
                global_llm_data["enableSoundNotifications"] = self.enable_sound_var.get()
                global_llm_data["enableWinNotifications"] = self.enable_win_notify_var.get()

                if self.config_manager.save_config("llm_global", global_llm_data):
                    self.llm_global_config = global_llm_data # 更新缓存
                else:
                    all_saved = False; failed_types.append("LLM 全局")

                google_data = llm_data.get("google", {})
                if self.config_manager.save_config("google", google_data):
                    self.google_config = google_data # 更新缓存
                else:
                    all_saved = False; failed_types.append("Google 特定")

                openai_data = llm_data.get("openai", {})
                if self.config_manager.save_config("openai", openai_data):
                    self.openai_config = openai_data # 更新缓存
                else:
                    all_saved = False; failed_types.append("OpenAI 特定")

            # 图片生成配置
            img_data = None
            if hasattr(self, 'image_gen_tab') and self.image_gen_tab.winfo_exists():
                try:
                    img_data = self.image_gen_tab.get_config_data()
                except Exception as e:
                    logger.error(f"错误：获取图片生成配置失败: {e}", exc_info=True)
                    all_saved = False; failed_types.append("图片生成 (获取)")
            else:
                all_saved = False; failed_types.append("图片生成 (Tab 不可用)")

            if img_data:
                # 保存图片全局配置 (选择器)
                image_global_data = {"selected_image_provider": self.selected_image_provider_var.get()}
                if self.config_manager.save_config("image_global", image_global_data):
                    self.image_global_config = image_global_data # 更新缓存
                else:
                    all_saved = False; failed_types.append("图片全局")
                # 保存共享图片配置
                shared_img_data = img_data.get("shared", {})
                if self.config_manager.save_config("image_gen_shared", shared_img_data):
                    self.image_gen_shared_config = shared_img_data # 更新缓存
                else:
                    all_saved = False; failed_types.append("图片共享")
                # 保存 SD 独立配置
                sd_data = img_data.get("sd_webui", {})
                if self.config_manager.save_config("sd", sd_data):
                    self.sd_config = sd_data # 更新缓存
                else:
                    all_saved = False; failed_types.append("SD 独立")
                # 保存 ComfyUI 独立配置
                comfy_data = img_data.get("comfyui", {})
                if self.config_manager.save_config("comfyui", comfy_data):
                    self.comfyui_config = comfy_data # 更新缓存
                else:
                    all_saved = False; failed_types.append("ComfyUI 独立")

            # 其他配置 (NAI, GPT-SoVITS)
            other_config_map = { "nai": self.nai_tab, "gptsovits": self.gptsovits_tab }
            other_config_cache = { "nai": "nai_config", "gptsovits": "gptsovits_config" }
            for cfg_type, tab_instance in other_config_map.items():
                 data = None
                 if hasattr(self, tab_instance.__class__.__name__.lower()) and tab_instance.winfo_exists():
                     try:
                         data = tab_instance.get_config_data()
                     except Exception as e:
                         logger.error(f"错误: 获取 {cfg_type.upper()} 配置失败: {e}", exc_info=True)
                         failed_types.append(f"{cfg_type.upper()} (获取)")
                 else:
                     failed_types.append(f"{cfg_type.upper()} (Tab 不可用)")

                 if data is not None:
                     if self.config_manager.save_config(cfg_type, data):
                         setattr(self, other_config_cache[cfg_type], data) # 更新缓存
                     else:
                         all_saved = False; failed_types.append(cfg_type.upper())

            # 处理最终结果
            if all_saved:
                self.status_label.configure(text="所有设置已成功保存", text_color="green")
                logger.info("所有设置保存成功。")
            else:
                error_msg = f"部分设置保存失败: {', '.join(failed_types)}"
                self.status_label.configure(text=error_msg, text_color="orange")
                logger.warning(f"警告: {error_msg}")
                messagebox.showwarning("保存警告", f"{error_msg}", parent=self)
            self.after(5000, lambda: self.status_label.configure(text="", text_color="gray"))
        except Exception as e:
            logger.exception(f"保存所有配置时发生未预期的错误: {e}")
            messagebox.showerror("保存错误", f"保存配置时发生严重错误:\n{e}", parent=self)
            self.status_label.configure(text="保存出错!", text_color="red")
            self.after(5000, lambda: self.status_label.configure(text="", text_color="gray"))

    def load_all_configs(self):
        """从配置文件加载所有设置，并更新对应的 UI 标签页"""
        logger.info("请求加载所有设置...")
        if messagebox.askyesno("加载确认", "加载设置将覆盖当前所有标签页中的内容。\n确定要加载吗？", parent=self):
            logger.info("正在加载所有设置...")
            self.status_label.configure(text="正在加载...", text_color="orange")
            self.update_idletasks()
            load_errors = []
            try:
                # 加载所有配置到内存缓存
                self.llm_global_config = self.config_manager.load_config("llm_global")
                self.image_global_config = self.config_manager.load_config("image_global")
                self.image_gen_shared_config = self.config_manager.load_config("image_gen_shared")
                self.google_config = self.config_manager.load_config("google")
                self.openai_config = self.config_manager.load_config("openai")
                self.nai_config = self.config_manager.load_config("nai")
                self.sd_config = self.config_manager.load_config("sd")
                self.comfyui_config = self.config_manager.load_config("comfyui")
                self.gptsovits_config = self.config_manager.load_config("gptsovits")

                # 更新主应用的变量状态
                self.enable_sound_var.set(self.llm_global_config.get("enableSoundNotifications", True))
                self.enable_win_notify_var.set(self.llm_global_config.get("enableWinNotifications", True))
                self.selected_llm_provider_var.set(self.llm_global_config.get("selected_provider", "Google"))
                self.selected_image_provider_var.set(self.image_global_config.get("selected_image_provider", "SD WebUI"))

                # 更新所有 Tab UI
                # 逻辑备注: 添加 logging_tab 到需要更新的 Tab 列表
                tab_map = { "llm_tab": self.llm_tab, "image_gen_tab": self.image_gen_tab, "nai_tab": self.nai_tab, "gptsovits_tab": self.gptsovits_tab, "profiles_tab": self.profiles_tab, "logging_tab": self.logging_tab }
                for tab_name, tab_instance in tab_map.items():
                    if hasattr(self, tab_name) and tab_instance.winfo_exists():
                        try:
                            if tab_name == "profiles_tab": # Profiles Tab 特殊处理
                                 logger.info("正在重置 Profiles Tab...")
                                 tab_instance.character_profiles = {}
                                 tab_instance.loaded_filepath = None
                                 tab_instance._update_profile_selector() # 使用内部方法更新
                                 tab_instance.file_status_label.configure(text="配置已加载，请手动加载人物设定", text_color="gray")
                            elif tab_name == "logging_tab": # Logging Tab 特殊处理
                                logger.info("正在重新加载 Logging Tab 颜色...")
                                tab_instance._load_and_apply_colors() # 调用加载和应用颜色的方法
                            else:
                                 tab_instance.load_initial_config()
                        except Exception as e_load:
                            error_msg = f"{tab_name} UI 更新失败: {e_load}"
                            load_errors.append(error_msg)
                            logger.error(f"错误: 更新 {tab_name} UI 时出错: {e_load}", exc_info=True)
                    else:
                        logger.warning(f"警告: 标签页 {tab_name} 不存在或未初始化，跳过加载。")

                # 处理加载结果
                if not load_errors:
                    self.status_label.configure(text="所有设置已成功加载", text_color="blue")
                    logger.info("所有设置加载并更新 UI 完成。")
                else:
                    error_summary = f"加载完成，但部分界面更新失败: {'; '.join(load_errors)}"
                    logger.warning(f"警告: {error_summary}")
                    self.status_label.configure(text="部分加载失败", text_color="orange")
                    messagebox.showwarning("加载警告", f"{error_summary}", parent=self)
                self.deferred_initial_updates() # 触发必要的后续更新
                self.after(5000, lambda: self.status_label.configure(text="", text_color="gray"))
            except Exception as e:
                logger.exception(f"加载所有配置时发生未预期的错误: {e}")
                messagebox.showerror("加载错误", f"加载配置时发生严重错误:\n{e}", parent=self)
                self.status_label.configure(text="加载出错!", text_color="red")
                self.after(5000, lambda: self.status_label.configure(text="", text_color="gray"))
        else:
            logger.info("取消加载。")

    # --- 新增：保存/加载应用程序状态 ---
    # 功能性备注: save_app_state, load_app_state 保持不变
    def save_app_state(self):
        """保存当前应用程序的完整状态（文本、配置、设定）到 JSON 文件"""
        logger.info("请求保存应用程序状态...")
        self.status_label.configure(text="准备保存状态...", text_color="orange")
        self.update_idletasks()
        try:
            app_state = {}
            # 1. 获取 Workflow Tab 文本内容
            if hasattr(self, 'workflow_tab') and self.workflow_tab.winfo_exists():
                app_state['workflow_texts'] = self.workflow_tab.get_workflow_texts()
            else:
                messagebox.showerror("错误", "无法访问转换流程标签页，无法保存文本内容。", parent=self)
                logger.error("保存状态失败：无法访问 WorkflowTab。")
                return

            # 2. 获取 Profiles Tab 人物设定
            if hasattr(self, 'profiles_tab') and self.profiles_tab.winfo_exists():
                app_state['character_profiles'] = self.profiles_tab.get_profiles_data()
                app_state['profiles_loaded_filepath'] = self.profiles_tab.loaded_filepath # 保存加载的文件路径
            else:
                messagebox.showerror("错误", "无法访问人物设定标签页，无法保存人物设定。", parent=self)
                logger.error("保存状态失败：无法访问 ProfilesTab。")
                return

            # 3. 获取所有配置 Tab 的当前设置
            app_state['configs'] = {}
            # 逻辑备注: 添加 logging_tab 到获取配置的列表
            config_tabs = {
                "llm": self.llm_tab,
                "image_gen": self.image_gen_tab,
                "nai": self.nai_tab,
                "gptsovits": self.gptsovits_tab,
                "logging": self.logging_tab # 添加 logging_tab
            }
            for key, tab_instance in config_tabs.items():
                if hasattr(self, f"{key}_tab") and tab_instance.winfo_exists():
                    # 逻辑备注: logging_tab 需要调用不同的方法获取颜色配置
                    if key == "logging":
                        # 逻辑备注: 将颜色配置合并到 llm_global 配置中保存
                        if 'llm' not in app_state['configs']: app_state['configs']['llm'] = {}
                        if 'shared' not in app_state['configs']['llm']: app_state['configs']['llm']['shared'] = {}
                        # 逻辑备注: 确保 'shared' 存在后再更新
                        if isinstance(app_state['configs']['llm']['shared'], dict):
                            app_state['configs']['llm']['shared'].update(tab_instance.get_color_config_data())
                        else:
                            # 如果 'shared' 不是字典，则直接用颜色数据替换（可能覆盖其他共享设置，需谨慎）
                            app_state['configs']['llm']['shared'] = tab_instance.get_color_config_data()
                            logger.warning("警告：保存状态时，LLM 配置的 'shared' 部分结构异常，已用颜色配置覆盖。")
                    else:
                        app_state['configs'][key] = tab_instance.get_config_data()
                else:
                    messagebox.showerror("错误", f"无法访问 {key.upper()} 设置标签页，无法保存其配置。", parent=self)
                    logger.error(f"保存状态失败：无法访问 {key}_tab。")
                    return

            # 4. 获取 Workflow Tab 的 UI 状态
            if hasattr(self, 'workflow_tab') and self.workflow_tab.winfo_exists():
                app_state['workflow_ui_state'] = self.workflow_tab.get_workflow_ui_state()
            else:
                messagebox.showerror("错误", "无法访问转换流程标签页，无法保存其界面状态。", parent=self)
                logger.error("保存状态失败：无法访问 WorkflowTab (获取 UI 状态)。")
                return

            # 5. 获取主窗口的变量状态
            app_state['main_vars'] = {
                "enableSoundNotifications": self.enable_sound_var.get(),
                "enableWinNotifications": self.enable_win_notify_var.get(),
                "selected_llm_provider": self.selected_llm_provider_var.get(),
                "selected_image_provider": self.selected_image_provider_var.get()
            }

            # 6. 弹出保存对话框
            filepath = filedialog.asksaveasfilename(
                title="保存应用程序状态",
                defaultextension=".json",
                filetypes=[("JSON 状态文件", "*.json"), ("所有文件", "*.*")],
                initialfile="app_state.json",
                parent=self
            )
            if not filepath:
                logger.info("用户取消保存状态。")
                self.status_label.configure(text="取消保存状态", text_color="gray")
                self.after(3000, lambda: self.status_label.configure(text="", text_color="gray"))
                return

            # 7. 写入 JSON 文件
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(app_state, f, ensure_ascii=False, indent=4)

            logger.info(f"应用程序状态已成功保存到: {filepath}")
            self.status_label.configure(text=f"状态已保存: {os.path.basename(filepath)}", text_color="green")
            self.after(5000, lambda: self.status_label.configure(text="", text_color="gray"))

        except Exception as e:
            logger.exception(f"保存应用程序状态时发生错误: {e}")
            messagebox.showerror("保存状态错误", f"保存应用程序状态时发生错误:\n{e}", parent=self)
            self.status_label.configure(text="保存状态出错!", text_color="red")
            self.after(5000, lambda: self.status_label.configure(text="", text_color="gray"))

    def load_app_state(self):
        """从 JSON 文件加载应用程序的完整状态"""
        logger.info("请求加载应用程序状态...")
        if not messagebox.askyesno("加载确认", "加载状态将覆盖当前所有文本框、人物设定和配置。\n确定要加载吗？", parent=self):
            logger.info("用户取消加载状态。")
            return

        filepath = filedialog.askopenfilename(
            title="加载应用程序状态",
            filetypes=[("JSON 状态文件", "*.json"), ("所有文件", "*.*")],
            parent=self
        )
        if not filepath:
            logger.info("用户取消加载状态。")
            return

        logger.info(f"正在从 {filepath} 加载应用程序状态...")
        self.status_label.configure(text="正在加载状态...", text_color="orange")
        self.update_idletasks()
        load_errors = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                app_state = json.load(f)

            # --- 开始恢复状态 ---
            # 1. 恢复 Workflow Tab 文本
            if 'workflow_texts' in app_state and hasattr(self, 'workflow_tab') and self.workflow_tab.winfo_exists():
                try:
                    self.workflow_tab.set_workflow_texts(app_state['workflow_texts'])
                except Exception as e:
                    load_errors.append(f"恢复流程文本失败: {e}")
                    logger.error(f"恢复流程文本失败: {e}", exc_info=True)
            else:
                load_errors.append("未找到流程文本数据或标签页不可用")

            # 2. 恢复 Profiles Tab 人物设定
            if 'character_profiles' in app_state and hasattr(self, 'profiles_tab') and self.profiles_tab.winfo_exists():
                try:
                    self.profiles_tab.set_profiles_data(app_state['character_profiles'])
                    self.profiles_tab.loaded_filepath = app_state.get('profiles_loaded_filepath') # 恢复文件路径
                    filename = os.path.basename(self.profiles_tab.loaded_filepath) if self.profiles_tab.loaded_filepath else "未关联文件"
                    self.profiles_tab.file_status_label.configure(text=f"状态已加载 ({filename})", text_color="blue")
                except Exception as e:
                    load_errors.append(f"恢复人物设定失败: {e}")
                    logger.error(f"恢复人物设定失败: {e}", exc_info=True)
            else:
                load_errors.append("未找到人物设定数据或标签页不可用")

            # 3. 恢复配置 Tab 设置 (先更新缓存，再让 Tab 从缓存加载)
            if 'configs' in app_state:
                # LLM (包含颜色配置)
                if 'llm' in app_state['configs']:
                    llm_data = app_state['configs']['llm']
                    # 逻辑备注: 确保 llm_data['shared'] 是字典
                    shared_llm_data = llm_data.get('shared', {})
                    if not isinstance(shared_llm_data, dict):
                        logger.warning("警告：加载状态时，LLM 配置的 'shared' 部分不是字典，已忽略。")
                        shared_llm_data = {}
                    self.llm_global_config.update(shared_llm_data) # 更新共享和颜色
                    self.google_config.update(llm_data.get('google', {}))
                    self.openai_config.update(llm_data.get('openai', {}))
                    if hasattr(self, 'llm_tab') and self.llm_tab.winfo_exists():
                        try: self.llm_tab.load_initial_config()
                        except Exception as e: load_errors.append(f"更新 LLM 设置 UI 失败: {e}"); logger.error(f"更新 LLM 设置 UI 失败: {e}", exc_info=True)
                    else: load_errors.append("LLM 设置标签页不可用")
                    # 逻辑备注: 更新 Logging Tab 的颜色
                    if hasattr(self, 'logging_tab') and self.logging_tab.winfo_exists():
                        try: self.logging_tab._load_and_apply_colors()
                        except Exception as e: load_errors.append(f"更新日志颜色 UI 失败: {e}"); logger.error(f"更新日志颜色 UI 失败: {e}", exc_info=True)
                    else: load_errors.append("日志标签页不可用")
                # Image Gen
                if 'image_gen' in app_state['configs']:
                    img_data = app_state['configs']['image_gen']
                    self.image_gen_shared_config.update(img_data.get('shared', {}))
                    self.sd_config.update(img_data.get('sd_webui', {}))
                    self.comfyui_config.update(img_data.get('comfyui', {}))
                    if hasattr(self, 'image_gen_tab') and self.image_gen_tab.winfo_exists():
                        try: self.image_gen_tab.load_initial_config()
                        except Exception as e: load_errors.append(f"更新图片生成设置 UI 失败: {e}"); logger.error(f"更新图片生成设置 UI 失败: {e}", exc_info=True)
                    else: load_errors.append("图片生成设置标签页不可用")
                # NAI
                if 'nai' in app_state['configs']:
                    self.nai_config.update(app_state['configs']['nai'])
                    if hasattr(self, 'nai_tab') and self.nai_tab.winfo_exists():
                        try: self.nai_tab.load_initial_config()
                        except Exception as e: load_errors.append(f"更新 NAI 设置 UI 失败: {e}"); logger.error(f"更新 NAI 设置 UI 失败: {e}", exc_info=True)
                    else: load_errors.append("NAI 设置标签页不可用")
                # GPT-SoVITS
                if 'gptsovits' in app_state['configs']:
                    self.gptsovits_config.update(app_state['configs']['gptsovits'])
                    if hasattr(self, 'gptsovits_tab') and self.gptsovits_tab.winfo_exists():
                        try: self.gptsovits_tab.load_initial_config()
                        except Exception as e: load_errors.append(f"更新 GPT-SoVITS 设置 UI 失败: {e}"); logger.error(f"更新 GPT-SoVITS 设置 UI 失败: {e}", exc_info=True)
                    else: load_errors.append("GPT-SoVITS 设置标签页不可用")
            else:
                load_errors.append("未找到配置数据")

            # 4. 恢复 Workflow Tab UI 状态
            if 'workflow_ui_state' in app_state and hasattr(self, 'workflow_tab') and self.workflow_tab.winfo_exists():
                try:
                    self.workflow_tab.set_workflow_ui_state(app_state['workflow_ui_state'])
                except Exception as e:
                    load_errors.append(f"恢复流程界面状态失败: {e}")
                    logger.error(f"恢复流程界面状态失败: {e}", exc_info=True)
            else:
                load_errors.append("未找到流程界面状态数据或标签页不可用")

            # 5. 恢复主窗口变量状态
            if 'main_vars' in app_state:
                main_vars = app_state['main_vars']
                self.enable_sound_var.set(main_vars.get("enableSoundNotifications", True))
                self.enable_win_notify_var.set(main_vars.get("enableWinNotifications", True))
                self.selected_llm_provider_var.set(main_vars.get("selected_llm_provider", "Google"))
                self.selected_image_provider_var.set(main_vars.get("selected_image_provider", "SD WebUI"))
                # 触发 provider change 更新 UI 显示
                self.on_llm_provider_change(self.selected_llm_provider_var.get())
                self.on_image_provider_change(self.selected_image_provider_var.get())
            else:
                load_errors.append("未找到主窗口变量状态")

            # --- 处理加载结果 ---
            if not load_errors:
                self.status_label.configure(text=f"状态已从 {os.path.basename(filepath)} 加载", text_color="blue")
                logger.info("应用程序状态加载完成。")
            else:
                error_summary = f"状态加载完成，但出现问题: {'; '.join(load_errors)}"
                logger.warning(f"警告: {error_summary}")
                self.status_label.configure(text="状态加载部分失败", text_color="orange")
                messagebox.showwarning("加载警告", f"{error_summary}", parent=self)

            self.deferred_initial_updates() # 触发按钮状态等更新
            self.after(5000, lambda: self.status_label.configure(text="", text_color="gray"))

        except FileNotFoundError:
            messagebox.showerror("加载错误", f"状态文件未找到:\n{filepath}", parent=self)
            logger.error(f"加载状态失败：文件未找到: {filepath}")
            self.status_label.configure(text="加载状态失败: 文件未找到", text_color="red")
            self.after(5000, lambda: self.status_label.configure(text="", text_color="gray"))
        except json.JSONDecodeError as e:
            messagebox.showerror("加载错误", f"无法解析状态文件 (JSON 格式错误):\n{filepath}\n错误: {e}", parent=self)
            logger.error(f"加载状态失败：无法解析状态文件 {filepath}: {e}", exc_info=True)
            self.status_label.configure(text="加载状态失败: 文件格式错误", text_color="red")
            self.after(5000, lambda: self.status_label.configure(text="", text_color="gray"))
        except Exception as e:
            logger.exception(f"加载应用程序状态时发生错误: {e}")
            messagebox.showerror("加载状态错误", f"加载应用程序状态时发生错误:\n{e}", parent=self)
            self.status_label.configure(text="加载状态出错!", text_color="red")
            self.after(5000, lambda: self.status_label.configure(text="", text_color="gray"))

    # --- 新增：日志队列处理方法 ---
    # 功能性备注: _process_log_queue 保持不变
    def _process_log_queue(self):
        """定期检查日志队列并将日志显示在 UI 上"""
        try:
            # 检查日志 Tab 是否仍然有效
            if hasattr(self, 'logging_tab') and self.logging_tab and self.logging_tab.winfo_exists():
                # 处理队列中的所有当前日志记录
                while True:
                    try:
                        record = logger_setup.log_queue.get_nowait() # 从全局队列获取
                        level_name, message = record
                        self.logging_tab.display_log(level_name, message) # 调用 LoggingTab 的方法显示
                    except queue.Empty:
                        # 队列为空，跳出内部循环
                        break
                    except Exception as e:
                        # 处理单个日志记录时出错，记录错误但继续
                        # 使用 print 因为 logging 可能也出错了
                        print(f"处理日志队列记录时出错: {e}")
                        traceback.print_exc()
            else:
                # 如果日志 Tab 不存在，清空队列以防积压（可选）
                # print("日志 Tab 不存在，无法显示日志。")
                pass
        except Exception as e:
            # 处理检查队列本身或 Tab 存在性检查时的错误
            # 使用 print 因为 logging 可能也出错了
            print(f"检查日志队列时出错: {e}")
            traceback.print_exc()
        finally:
            # 无论如何，100ms 后再次安排检查
            self.after(100, self._process_log_queue)

    # --- 新增：控制台日志切换方法 ---
    # 功能性备注: control_console_logging 保持不变
    def control_console_logging(self, enable):
        """控制后台控制台日志的启用/禁用"""
        try:
            logger_setup.toggle_console_handler(enable) # 调用 logger_setup 中的函数
        except Exception as e:
            logger.error(f"切换控制台日志状态时出错: {e}", exc_info=True)


# --- 程序入口 ---
# 功能性备注: 保持不变
if __name__ == "__main__":
    # 确保目录存在 (使用 logging 记录)
    try:
        config_manager._ensure_config_dir()
        logging.info(f"配置目录 '{config_manager.CONFIG_DIR}' 已确认或创建。")
    except Exception as dir_e:
        logging.warning(f"警告：无法创建或访问配置目录 '{config_manager.CONFIG_DIR}': {dir_e}")
    try:
        DEBUG_LOG_DIR = Path("debug_logs") / "api_requests"
        DEBUG_LOG_DIR.mkdir(parents=True, exist_ok=True)
        logging.info(f"调试日志目录 '{DEBUG_LOG_DIR}' 已确认或创建。")
    except Exception as dir_e:
        logging.warning(f"警告：无法创建或访问调试日志目录 '{DEBUG_LOG_DIR}': {dir_e}")

    app = None
    try:
        # 在创建 App 实例前，日志系统已经通过 logger_setup 初始化
        logging.info("应用程序启动...")
        app = NovelConverterApp()
        app.mainloop()
    except Exception as main_e:
         # 使用 logging 记录主循环错误
         logging.critical(f"应用程序主循环中发生未捕获的严重错误: {main_e}", exc_info=True)
         try:
             # 尝试用 Tkinter 显示最终错误
             root = ctk.CTk(); root.withdraw(); messagebox.showerror("严重错误", f"应用程序遇到严重错误即将退出:\n{main_e}"); root.destroy()
         except: pass
         if app and app.winfo_exists():
             try: app.destroy()
             except Exception: pass # 忽略销毁错误
         sys.exit(1)
    logging.info("应用程序已正常退出。")