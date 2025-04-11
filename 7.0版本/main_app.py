# main_app.py
import customtkinter as ctk
from tkinter import messagebox
import threading # 虽然主要在 Tab 中使用，但主应用可能需要了解线程状态
import queue     # 虽然主要在 Tab 中使用
import os        # 用于路径操作 (例如获取文件名)
import sys       # 用于退出程序等系统操作
import json      # 用于处理 JSON 数据
import traceback # 用于打印详细错误信息

# --- 导入自定义模块 (使用绝对导入) ---
try:
    from core import config_manager
    from api import api_helpers # Facade
    from core import utils
    from core import sound_player
    from core.prompts import PromptTemplates # 从 prompts.py 导入
    # 导入新的 API 助手和任务模块 (虽然主程序不直接用，但确保它们能被加载)
    from api import google_api_helpers
    from api import nai_api_helper
    from api import sd_api_helper
    from api import gptsovits_api_helper # 新增
    from tasks import workflow_tasks
    from tasks import image_generation_tasks
    from tasks import audio_generation_tasks # 新增
    from api import common_api_utils # 新增
except ImportError as e:
    print(f"严重错误：无法导入核心模块或 prompts.py: {e}")
    print("请确保所有 .py 文件已移动到正确的子目录 (api, core, tasks) 且包含 __init__.py。")
    try:
        root = ctk.CTk()
        root.withdraw()
        messagebox.showerror("启动错误", f"无法加载核心模块: {e}\n请检查项目文件结构。程序即将退出。")
        root.destroy()
    except Exception as msg_e:
        print(f"无法显示错误消息框: {msg_e}")
    sys.exit(1)

# --- 导入 UI 标签页类 (使用绝对导入) ---
try:
    from ui.llm_config_tab import LLMConfigTab
    from ui.nai_config_tab import NAIConfigTab
    from ui.sd_config_tab import SDConfigTab
    from ui.profiles_tab import ProfilesTab
    from ui.workflow_tab import WorkflowTab
    from ui.gptsovits_config_tab import GPTSoVITSConfigTab # 新增导入
except ImportError as e:
    print(f"严重错误：无法导入 UI 标签页模块: {e}")
    print("请确保 'ui' 文件夹存在于项目根目录下，并且包含所需的 .py 文件和 __init__.py。")
    try:
        root = ctk.CTk()
        root.withdraw()
        messagebox.showerror("启动错误", f"无法加载界面模块: {e}\n请检查项目文件结构。程序即将退出。")
        root.destroy()
    except Exception as msg_e:
        print(f"无法显示错误消息框: {msg_e}")
    sys.exit(1)


class NovelConverterApp(ctk.CTk):
    """主应用程序类，负责创建窗口、管理标签页和协调模块"""
    def __init__(self):
        super().__init__()

        self.title("小说转 KAG 工具 (模块化版)")
        self.geometry("1200x850") # 稍微增加高度以容纳新选项
        self.minsize(1000, 650) # 稍微增加最小高度
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        # --- 初始化核心模块实例 ---
        self.config_manager = config_manager
        self.api_helpers = api_helpers # Facade
        self.utils = utils
        self.sound_player = sound_player

        # --- 实例化 Prompt 模板 (从 prompts.py 导入) ---
        self.prompt_templates = PromptTemplates()

        # --- 加载初始配置 ---
        try:
            print("正在加载初始配置...")
            self.llm_config = self.config_manager.load_config("llm_global")
            self.nai_config = self.config_manager.load_config("nai")
            self.sd_config = self.config_manager.load_config("sd")
            self.gptsovits_config = self.config_manager.load_config("gptsovits") # 新增加载
            print("初始配置加载完成。")
        except Exception as e:
             print(f"严重错误：加载初始配置时发生错误: {e}")
             traceback.print_exc()
             messagebox.showerror("配置加载错误", f"加载配置文件时出错:\n{e}\n将使用默认设置。")
             self.llm_config = config_manager.DEFAULT_LLM_GLOBAL_CONFIG.copy()
             self.nai_config = config_manager.DEFAULT_NAI_CONFIG.copy()
             self.sd_config = config_manager.DEFAULT_SD_CONFIG.copy()
             self.gptsovits_config = config_manager.DEFAULT_GPTSOVITS_CONFIG.copy() # 新增默认

        # --- 创建主界面 ---
        try:
            print("正在构建主界面...")
            self.build_main_ui() # 实例化所有 Tab
            print("主界面构建完成。")
            # 延迟调用初始状态更新，确保所有 Tab 都已创建
            self.after(10, self.deferred_initial_updates)
        except Exception as e:
             print(f"严重错误：构建主界面时发生错误: {e}")
             traceback.print_exc()
             messagebox.showerror("界面构建错误", f"创建主界面时出错:\n{e}\n程序即将退出。")
             self.quit()


    def build_main_ui(self):
        """构建主窗口的 UI 布局"""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # --- 顶部操作栏 ---
        top_frame = ctk.CTkFrame(self, height=40, fg_color="transparent")
        top_frame.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="ew")
        save_all_button = ctk.CTkButton(top_frame, text="保存所有设置", command=self.save_all_configs)
        save_all_button.pack(side="left", padx=(0, 10), pady=5)
        load_all_button = ctk.CTkButton(top_frame, text="加载所有设置", command=self.load_all_configs)
        load_all_button.pack(side="left", padx=10, pady=5)
        appearance_label = ctk.CTkLabel(top_frame, text="外观:")
        appearance_label.pack(side="left", padx=(20, 5), pady=5)
        appearance_menu = ctk.CTkOptionMenu(top_frame, values=["Light", "Dark", "System"], command=self.change_appearance_mode_event)
        appearance_menu.pack(side="left", pady=5)
        appearance_menu.set(ctk.get_appearance_mode())
        self.status_label = ctk.CTkLabel(top_frame, text="准备就绪", text_color="gray", anchor="e")
        self.status_label.pack(side="right", padx=10, pady=5, fill="x", expand=True)

        # --- 创建 TabView ---
        self.tab_view = ctk.CTkTabview(self, anchor="nw")
        self.tab_view.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        self.tab_view.add("转换流程")
        self.tab_view.add("人物设定")
        self.tab_view.add("LLM 与全局设置")
        self.tab_view.add("NAI 设置")
        self.tab_view.add("SD WebUI 设置")
        self.tab_view.add("GPT-SoVITS 设置") # 新增标签页

        # --- 实例化并放置每个标签页的内容 ---
        try:
            print("正在实例化 WorkflowTab...")
            self.workflow_tab = WorkflowTab(master=self.tab_view.tab("转换流程"), config_manager=self.config_manager, api_helpers=self.api_helpers, utils=self.utils, sound_player=self.sound_player, app_instance=self)
            self.workflow_tab.pack(expand=True, fill="both", padx=5, pady=5)

            print("正在实例化 ProfilesTab...")
            self.profiles_tab = ProfilesTab(master=self.tab_view.tab("人物设定"), config_manager=self.config_manager, app_instance=self)
            self.profiles_tab.pack(expand=True, fill="both", padx=5, pady=5)

            print("正在实例化 LLMConfigTab...")
            self.llm_tab = LLMConfigTab(master=self.tab_view.tab("LLM 与全局设置"), config_manager=self.config_manager, app_instance=self)
            self.llm_tab.pack(expand=True, fill="both", padx=5, pady=5)

            print("正在实例化 NAIConfigTab...")
            self.nai_tab = NAIConfigTab(master=self.tab_view.tab("NAI 设置"), config_manager=self.config_manager, app_instance=self)
            self.nai_tab.pack(expand=True, fill="both", padx=5, pady=5)

            print("正在实例化 SDConfigTab...")
            self.sd_tab = SDConfigTab(master=self.tab_view.tab("SD WebUI 设置"), config_manager=self.config_manager, app_instance=self)
            self.sd_tab.pack(expand=True, fill="both", padx=5, pady=5)

            # 新增：实例化 GPTSoVITSConfigTab
            print("正在实例化 GPTSoVITSConfigTab...")
            self.gptsovits_tab = GPTSoVITSConfigTab(master=self.tab_view.tab("GPT-SoVITS 设置"), config_manager=self.config_manager, app_instance=self)
            self.gptsovits_tab.pack(expand=True, fill="both", padx=5, pady=5)

        except Exception as e:
             print(f"严重错误：实例化或放置标签页内容时出错: {e}")
             traceback.print_exc()
             messagebox.showerror("界面构建错误", f"创建标签页内容时出错:\n{e}")

        self.tab_view.set("转换流程")

    def deferred_initial_updates(self):
        """在主 UI 构建完成后延迟调用的方法，用于初始状态更新"""
        print("执行延迟的初始 UI 更新...")
        try:
            if hasattr(self, 'workflow_tab') and self.workflow_tab.winfo_exists():
                print("正在更新 WorkflowTab 的初始按钮状态...")
                self.workflow_tab.update_button_states()
            else:
                print("警告: WorkflowTab 不存在，无法更新初始按钮状态。")
        except Exception as e:
            print(f"错误：执行延迟初始更新时出错: {e}")
            traceback.print_exc()
        print("延迟更新完成。")

    def change_appearance_mode_event(self, new_appearance_mode: str):
        """切换亮色/暗色/系统模式"""
        ctk.set_appearance_mode(new_appearance_mode)
        print(f"外观模式已切换为: {new_appearance_mode}")

    def on_closing(self):
        """处理窗口关闭事件"""
        if messagebox.askokcancel("退出确认", "确定要退出应用程序吗？\n未保存的设置将会丢失。"):
            print("正在关闭应用程序...")
            self.destroy()
        else:
            print("取消退出。")

    # --- 配置获取方法 ---
    def get_llm_config(self):
        """获取最新的 LLM 配置数据"""
        if hasattr(self, 'llm_tab') and self.llm_tab.winfo_exists():
            try: return self.llm_tab.get_config_data()
            except Exception as e: print(f"错误：从 LLM Tab 获取配置时出错: {e}"); traceback.print_exc(); messagebox.showerror("配置错误", f"无法从 LLM 设置标签页获取配置:\n{e}", parent=self); print("警告: 返回内存中缓存的 LLM 配置。"); return self.llm_config
        else: print("错误: LLM 配置标签页不可用！"); messagebox.showerror("内部错误", "无法访问 LLM 配置标签页。", parent=self); print("警告: 返回内存中缓存的 LLM 配置。"); return self.llm_config

    def get_nai_config(self):
        """获取最新的 NAI 配置数据"""
        if hasattr(self, 'nai_tab') and self.nai_tab.winfo_exists():
            try: return self.nai_tab.get_config_data()
            except Exception as e: print(f"错误：从 NAI Tab 获取配置时出错: {e}"); traceback.print_exc(); messagebox.showerror("配置错误", f"无法从 NAI 设置标签页获取配置:\n{e}", parent=self); print("警告: 返回内存中缓存的 NAI 配置。"); return self.nai_config
        else: print("错误: NAI 配置标签页不可用！(在 get_nai_config 调用时)"); messagebox.showerror("内部错误", "无法访问 NAI 配置标签页。", parent=self); print("警告: 返回内存中缓存的 NAI 配置。"); return self.nai_config

    def get_sd_config(self):
        """获取最新的 SD 配置数据"""
        if hasattr(self, 'sd_tab') and self.sd_tab.winfo_exists():
            try: return self.sd_tab.get_config_data()
            except Exception as e: print(f"错误：从 SD Tab 获取配置时出错: {e}"); traceback.print_exc(); messagebox.showerror("配置错误", f"无法从 SD 设置标签页获取配置:\n{e}", parent=self); print("警告: 返回内存中缓存的 SD 配置。"); return self.sd_config
        else: print("错误: SD 配置标签页不可用！(在 get_sd_config 调用时)"); messagebox.showerror("内部错误", "无法访问 SD 配置标签页。", parent=self); print("警告: 返回内存中缓存的 SD 配置。"); return self.sd_config

    # 新增：获取 GPT-SoVITS 配置
    def get_gptsovits_config(self):
        """获取最新的 GPT-SoVITS 配置数据"""
        if hasattr(self, 'gptsovits_tab') and self.gptsovits_tab.winfo_exists():
            try: return self.gptsovits_tab.get_config_data()
            except Exception as e: print(f"错误：从 GPT-SoVITS Tab 获取配置时出错: {e}"); traceback.print_exc(); messagebox.showerror("配置错误", f"无法从 GPT-SoVITS 设置标签页获取配置:\n{e}", parent=self); print("警告: 返回内存中缓存的 GPT-SoVITS 配置。"); return self.gptsovits_config
        else: print("错误: GPT-SoVITS 配置标签页不可用！"); messagebox.showerror("内部错误", "无法访问 GPT-SoVITS 配置标签页。", parent=self); print("警告: 返回内存中缓存的 GPT-SoVITS 配置。"); return self.gptsovits_config

    def get_profiles_json(self):
         """获取 Profiles Tab 中的人物设定 JSON 字符串"""
         if hasattr(self, 'profiles_tab') and self.profiles_tab.winfo_exists():
              try: return self.profiles_tab.get_profiles_json()
              except Exception as e: print(f"错误：从 Profiles Tab 获取 JSON 时发生意外错误: {e}"); traceback.print_exc(); messagebox.showerror("内部错误", f"获取人物设定 JSON 时发生意外错误:\n{e}", parent=self); return None
         else: print("错误：人物设定标签页不可用！"); messagebox.showerror("内部错误", "无法访问人物设定标签页。", parent=self); return None

    # --- 全局配置保存/加载 ---
    def save_all_configs(self):
        """收集所有配置 Tab 的数据并保存到对应的配置文件"""
        print("正在保存所有设置...")
        self.status_label.configure(text="正在保存...", text_color="orange"); self.update_idletasks()
        all_saved = True; failed_types = []
        try:
            # LLM/全局
            llm_data = self.get_llm_config()
            if llm_data is not None:
                if self.config_manager.save_config("llm_global", llm_data): self.llm_config = llm_data
                else: all_saved = False; failed_types.append("LLM/全局")
            else: all_saved = False; failed_types.append("LLM/全局 (获取失败)")
            # NAI
            nai_data = self.get_nai_config()
            if nai_data is not None:
                if self.config_manager.save_config("nai", nai_data): self.nai_config = nai_data
                else: all_saved = False; failed_types.append("NAI")
            else: all_saved = False; failed_types.append("NAI (获取失败)")
            # SD
            sd_data = self.get_sd_config()
            if sd_data is not None:
                if self.config_manager.save_config("sd", sd_data): self.sd_config = sd_data
                else: all_saved = False; failed_types.append("SD")
            else: all_saved = False; failed_types.append("SD (获取失败)")
            # GPT-SoVITS (新增)
            gptsv_data = self.get_gptsovits_config()
            if gptsv_data is not None:
                if self.config_manager.save_config("gptsovits", gptsv_data): self.gptsovits_config = gptsv_data
                else: all_saved = False; failed_types.append("GPT-SoVITS")
            else: all_saved = False; failed_types.append("GPT-SoVITS (获取失败)")


            if all_saved: self.status_label.configure(text="所有设置已成功保存", text_color="green"); print("所有设置保存成功。")
            else: error_msg = f"部分设置保存失败: {', '.join(failed_types)}"; self.status_label.configure(text=error_msg, text_color="orange"); print(f"警告: {error_msg}"); messagebox.showwarning("保存警告", f"{error_msg}\n请检查控制台日志获取详细信息。", parent=self)
            self.after(5000, lambda: self.status_label.configure(text="", text_color="gray"))
        except Exception as e: print(f"保存所有配置时发生未预期的错误: {e}"); traceback.print_exc(); messagebox.showerror("保存错误", f"保存配置时发生严重错误:\n{e}", parent=self); self.status_label.configure(text="保存出错!", text_color="red"); self.after(5000, lambda: self.status_label.configure(text="", text_color="gray"))

    def load_all_configs(self):
        """从配置文件加载所有设置，并更新对应的 UI 标签页"""
        print("请求加载所有设置...")
        if messagebox.askyesno("加载确认", "加载设置将覆盖当前所有标签页中的内容（除了人物设定列表）。\n确定要加载吗？", parent=self):
            print("正在加载所有设置..."); self.status_label.configure(text="正在加载...", text_color="orange"); self.update_idletasks()
            load_errors = []
            try:
                # LLM/全局
                llm_loaded = self.config_manager.load_config("llm_global"); self.llm_config = llm_loaded
                try:
                    if hasattr(self, 'llm_tab') and self.llm_tab.winfo_exists(): self.llm_tab.load_initial_config()
                    else: raise RuntimeError("LLM Tab 不存在")
                except Exception as e_llm: load_errors.append(f"LLM Tab UI 更新失败: {e_llm}"); print(f"错误: 更新 LLM Tab UI 时出错: {e_llm}"); traceback.print_exc()
                # NAI
                nai_loaded = self.config_manager.load_config("nai"); self.nai_config = nai_loaded
                try:
                    if hasattr(self, 'nai_tab') and self.nai_tab.winfo_exists(): self.nai_tab.load_initial_config()
                    else: raise RuntimeError("NAI Tab 不存在")
                except Exception as e_nai: load_errors.append(f"NAI Tab UI 更新失败: {e_nai}"); print(f"错误: 更新 NAI Tab UI 时出错: {e_nai}"); traceback.print_exc()
                # SD
                sd_loaded = self.config_manager.load_config("sd"); self.sd_config = sd_loaded
                try:
                    if hasattr(self, 'sd_tab') and self.sd_tab.winfo_exists(): self.sd_tab.load_initial_config()
                    else: raise RuntimeError("SD Tab 不存在")
                except Exception as e_sd: load_errors.append(f"SD Tab UI 更新失败: {e_sd}"); print(f"错误: 更新 SD Tab UI 时出错: {e_sd}"); traceback.print_exc()
                # GPT-SoVITS (新增)
                gptsv_loaded = self.config_manager.load_config("gptsovits"); self.gptsovits_config = gptsv_loaded
                try:
                    if hasattr(self, 'gptsovits_tab') and self.gptsovits_tab.winfo_exists(): self.gptsovits_tab.load_initial_config()
                    else: raise RuntimeError("GPT-SoVITS Tab 不存在")
                except Exception as e_gptsv: load_errors.append(f"GPT-SoVITS Tab UI 更新失败: {e_gptsv}"); print(f"错误: 更新 GPT-SoVITS Tab UI 时出错: {e_gptsv}"); traceback.print_exc()

                # 重置 Profiles Tab (保持不变)
                if hasattr(self, 'profiles_tab') and self.profiles_tab.winfo_exists():
                     try: print("正在重置 Profiles Tab..."); self.profiles_tab.character_profiles = {}; self.profiles_tab.loaded_filepath = None; self.profiles_tab.render_profiles_list(); self.profiles_tab.file_status_label.configure(text="配置已加载，请手动加载人物设定文件", text_color="gray")
                     except Exception as e_prof: load_errors.append(f"Profiles Tab 重置失败: {e_prof}"); print(f"错误: 重置 Profiles Tab 时出错: {e_prof}"); traceback.print_exc()

                if not load_errors: self.status_label.configure(text="所有设置已成功加载", text_color="blue"); print("所有设置加载并更新 UI 完成。")
                else: error_summary = f"加载完成，但部分界面更新失败: {'; '.join(load_errors)}"; print(f"警告: {error_summary}"); self.status_label.configure(text="部分加载失败", text_color="orange"); messagebox.showwarning("加载警告", f"{error_summary}\n请检查控制台日志获取详细信息。", parent=self)
                self.deferred_initial_updates() # 更新按钮状态
                self.after(5000, lambda: self.status_label.configure(text="", text_color="gray"))
            except Exception as e: print(f"加载所有配置时发生未预期的错误: {e}"); traceback.print_exc(); messagebox.showerror("加载错误", f"加载配置时发生严重错误:\n{e}", parent=self); self.status_label.configure(text="加载出错!", text_color="red"); self.after(5000, lambda: self.status_label.configure(text="", text_color="gray"))

# --- 程序入口 ---
if __name__ == "__main__":
    print("应用程序启动...")
    try: config_manager._ensure_config_dir(); print(f"配置目录 '{config_manager.CONFIG_DIR}' 已确认或创建。")
    except Exception as dir_e: print(f"警告：无法创建或访问配置目录 '{config_manager.CONFIG_DIR}': {dir_e}")
    app = None
    try: app = NovelConverterApp(); app.mainloop()
    except Exception as main_e:
         print(f"应用程序主循环中发生未捕获的严重错误: {main_e}"); traceback.print_exc()
         try: root = ctk.CTk(); root.withdraw(); messagebox.showerror("严重错误", f"应用程序遇到严重错误即将退出:\n{main_e}"); root.destroy()
         except: pass
         if app and app.winfo_exists():
             try: app.destroy()
             except: pass
         sys.exit(1)
    print("应用程序已正常退出。")