# ui/logging_tab.py
import customtkinter as ctk
from tkinter import BooleanVar, Text # Text 用于 CTkTextbox
import logging # 需要导入 logging 以便使用级别常量
import traceback # 导入 traceback 用于打印错误详情
# 功能性备注: 导入颜色选择对话框 (如果需要实现 UI 选择器)
from tkinter import colorchooser # 功能性备注: 导入实际的颜色选择器

class LoggingTab(ctk.CTkFrame):
    """
    用于显示应用程序日志并提供过滤控制的 UI 标签页。
    """
    def __init__(self, master, log_queue, app_instance):
        # 功能性备注: 初始化父类 Frame
        super().__init__(master, fg_color="transparent")
        # 功能性备注: 保存日志队列和主应用程序实例的引用
        self.log_queue = log_queue
        self.app = app_instance

        # --- UI 状态变量 ---
        # 功能性备注: 用于控制是否显示对应级别的日志
        self.show_debug_var = BooleanVar(value=True)
        self.show_info_var = BooleanVar(value=True)
        self.show_warning_var = BooleanVar(value=True)
        self.show_error_var = BooleanVar(value=True)
        # 功能性备注: 用于控制是否启用后台控制台日志输出
        self.enable_console_log_var = BooleanVar(value=True) # 默认启用

        # --- 功能性备注: 存储从配置加载的颜色 (或默认值) ---
        self.ui_log_colors = {}
        self.console_log_colors = {} # 存储控制台颜色配置，供保存用

        # --- 构建 UI 界面 ---
        self.build_ui()

        # --- 功能性备注: 加载颜色配置并应用到 UI ---
        self._load_and_apply_colors()

    def _load_and_apply_colors(self):
        """加载颜色配置并应用到 UI 日志标签"""
        # 功能性备注: 尝试从全局配置加载颜色设置
        # 逻辑备注: 这里假设颜色配置存储在 llm_global_config 中
        config = self.app.get_global_llm_config() # 获取包含颜色设置的配置

        # 功能性备注: 为 UI 日志设置颜色，提供默认值
        self.ui_log_colors = {
            "DEBUG": config.get("ui_log_color_debug", "#ADD8E6"), # 浅蓝色
            "INFO": config.get("ui_log_color_info", "#3CB371"),   # 中绿色
            "WARNING": config.get("ui_log_color_warning", "orange"),
            "ERROR": config.get("ui_log_color_error", "#ff5f5f"),
            "CRITICAL": config.get("ui_log_color_critical", "#ff0000")
        }
        # 功能性备注: 为控制台日志加载颜色配置 (仅用于保存，不在此处应用)
        self.console_log_colors = {
            "DEBUG": config.get("console_log_color_debug", "DIM"), # 使用 colorama 名称
            "INFO": config.get("console_log_color_info", "RESET"),
            "WARNING": config.get("console_log_color_warning", "YELLOW"),
            "ERROR": config.get("console_log_color_error", "RED"),
            "CRITICAL": config.get("console_log_color_critical", "BRIGHT_RED")
        }

        # 功能性备注: 应用 UI 日志颜色
        try:
            for level, color in self.ui_log_colors.items():
                self.log_display.tag_config(level, foreground=color)
            logging.info("UI 日志颜色已根据配置应用。")
        except Exception as e:
            logging.error(f"错误：配置日志颜色标签时出错: {e}", exc_info=True)
            traceback.print_exc()

    def build_ui(self):
        """构建日志标签页的界面元素"""
        # 功能性备注: 配置主网格布局，让日志显示区域可扩展
        self.grid_rowconfigure(3, weight=1) # 逻辑修改: 增加颜色设置行，日志行改为 3
        self.grid_columnconfigure(0, weight=1)

        # --- 功能性备注: 添加说明文字 ---
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="ew")
        # 逻辑修改: 更改说明文字颜色为红色，字体加大
        info_label = ctk.CTkLabel(info_frame, text="颜色设置说明：界面日志颜色修改后立即生效；控制台日志颜色修改后需重启程序才能生效。",
                                  font=ctk.CTkFont(size=13, weight="bold"), # 逻辑修改: 字体加大
                                  text_color="red", # 逻辑修改: 颜色改为红色
                                  wraplength=self.winfo_width()-40) # 自动换行
        info_label.pack(fill="x", padx=5, pady=2)

        # --- 控制栏 Frame ---
        # 功能性备注: 包含过滤复选框、控制台开关和清空按钮
        control_frame = ctk.CTkFrame(self, fg_color="transparent")
        control_frame.grid(row=1, column=0, padx=10, pady=(5, 5), sticky="ew") # 逻辑修改: 行号改为 1

        # 功能性备注: 日志级别过滤复选框
        filter_label = ctk.CTkLabel(control_frame, text="显示级别:")
        filter_label.pack(side="left", padx=(0, 5))
        debug_check = ctk.CTkCheckBox(control_frame, text="Debug", variable=self.show_debug_var)
        debug_check.pack(side="left", padx=5)
        info_check = ctk.CTkCheckBox(control_frame, text="Info", variable=self.show_info_var)
        info_check.pack(side="left", padx=5)
        warning_check = ctk.CTkCheckBox(control_frame, text="Warning", variable=self.show_warning_var)
        warning_check.pack(side="left", padx=5)
        error_check = ctk.CTkCheckBox(control_frame, text="Error", variable=self.show_error_var)
        error_check.pack(side="left", padx=(5, 20))

        # 功能性备注: 控制台日志开关
        console_check = ctk.CTkCheckBox(control_frame, text="启用控制台日志", variable=self.enable_console_log_var, command=self.toggle_console_logging)
        console_check.pack(side="left", padx=5)

        # 功能性备注: 清空日志按钮 (放置在右侧)
        clear_button = ctk.CTkButton(control_frame, text="清空日志", width=80, command=self.clear_logs)
        clear_button.pack(side="right", padx=5)

        # --- 功能性备注: 颜色选择器区域 ---
        # 逻辑备注: 添加用于放置颜色选择按钮的框架
        color_picker_frame = ctk.CTkFrame(self)
        color_picker_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew") # 逻辑修改: 行号改为 2
        color_picker_frame.grid_columnconfigure((1, 3, 5, 7, 9), weight=1) # 让按钮后的标签扩展

        # 功能性备注: 为每个级别添加 UI 和控制台颜色选择按钮 (示例)
        levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        current_color_row = 0
        # UI 颜色按钮
        ui_color_label = ctk.CTkLabel(color_picker_frame, text="UI 颜色:", font=ctk.CTkFont(weight="bold"))
        ui_color_label.grid(row=current_color_row, column=0, padx=5, pady=5, sticky="w")
        for i, level in enumerate(levels):
            btn = ctk.CTkButton(color_picker_frame, text=level, width=70,
                                command=lambda lvl=level: self._pick_color(lvl, "ui"))
            btn.grid(row=current_color_row, column=i*2 + 1, padx=5, pady=5, sticky="w")
            # 功能性备注: 添加一个标签显示当前颜色 (可选)
            color_display = ctk.CTkLabel(color_picker_frame, text="", width=20, height=20, fg_color=self.ui_log_colors.get(level, "gray"))
            color_display.grid(row=current_color_row, column=i*2 + 2, padx=(0, 5), pady=5, sticky="w")
            setattr(self, f"ui_color_display_{level.lower()}", color_display) # 保存引用以便更新
        current_color_row += 1
        # 控制台颜色按钮
        console_color_label = ctk.CTkLabel(color_picker_frame, text="控制台:", font=ctk.CTkFont(weight="bold"))
        console_color_label.grid(row=current_color_row, column=0, padx=5, pady=5, sticky="w")
        for i, level in enumerate(levels):
            btn = ctk.CTkButton(color_picker_frame, text=level, width=70,
                                command=lambda lvl=level: self._pick_color(lvl, "console"))
            btn.grid(row=current_color_row, column=i*2 + 1, padx=5, pady=5, sticky="w")
            # 功能性备注: 添加一个标签显示当前配置的颜色名称 (可选)
            color_name_label = ctk.CTkLabel(color_picker_frame, text=f"({self.console_log_colors.get(level, '默认')})", font=ctk.CTkFont(size=10))
            color_name_label.grid(row=current_color_row, column=i*2 + 2, padx=(0, 5), pady=5, sticky="w")
            setattr(self, f"console_color_name_label_{level.lower()}", color_name_label) # 保存引用以便更新

        # --- 日志显示文本框 ---
        # 功能性备注: 使用 CTkTextbox 显示日志，初始状态为禁用编辑
        self.log_display = ctk.CTkTextbox(self, wrap="word", state="disabled")
        self.log_display.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="nsew") # 逻辑修改: 行号改为 3

    # --- 功能性备注: 颜色选择器回调函数 ---
    def _pick_color(self, level, target_type):
        """弹出颜色选择器并处理选择结果"""
        # 逻辑备注: 调用颜色选择器
        # 逻辑备注: 获取当前颜色作为初始颜色
        initial_color = None
        if target_type == "ui":
            initial_color = self.ui_log_colors.get(level)
        # 逻辑备注: 控制台颜色可能不是标准颜色值，暂时不设置初始颜色
        # else:
        #     initial_color = self.console_log_colors.get(level) # 这可能不是有效的颜色值

        # 功能性备注: 弹出颜色选择对话框
        color_code_tuple = colorchooser.askcolor(title=f"选择 {target_type.upper()} {level} 颜色", initialcolor=initial_color, parent=self)
        color_code = color_code_tuple[1] if color_code_tuple else None # 获取十六进制颜色 (#rrggbb)

        if color_code:
            logging.info(f"用户为 {target_type.upper()} {level} 选择了新颜色: {color_code}")
            if target_type == "ui":
                self._update_ui_color_config(level, color_code)
            elif target_type == "console":
                # 逻辑备注: 对于控制台，我们保存十六进制值，logger_setup 负责映射
                # 逻辑备注: 或者这里可以尝试映射到 colorama 名称，但会更复杂
                self._update_console_color_config(level, color_code) # 保存十六进制值
        else:
            logging.info(f"用户取消为 {target_type.upper()} {level} 选择颜色。")

    def _update_ui_color_config(self, level, color_code):
        """实时更新 UI 日志颜色并保存到缓存"""
        logging.info(f"UI 颜色更新: {level} -> {color_code}")
        self.ui_log_colors[level] = color_code # 功能性备注: 更新内部字典
        try:
            # 功能性备注: 实时应用到日志框
            self.log_display.tag_config(level, foreground=color_code)
            # 功能性备注: 更新颜色显示标签 (如果存在)
            display_label = getattr(self, f"ui_color_display_{level.lower()}", None)
            if display_label and display_label.winfo_exists():
                display_label.configure(fg_color=color_code)
            # 逻辑备注: 更新内存缓存 (llm_global_config)
            config_key = f"ui_log_color_{level.lower()}"
            if hasattr(self.app, 'llm_global_config'):
                self.app.llm_global_config[config_key] = color_code
                logging.info(f"UI 颜色配置 '{config_key}' 已更新到内存缓存。")
            else:
                logging.warning("警告：无法访问主应用的 llm_global_config 来更新 UI 颜色缓存。")
        except Exception as e:
            logging.error(f"更新 UI 颜色时出错: {e}", exc_info=True)

    def _update_console_color_config(self, level, color_code):
        """更新控制台颜色配置到缓存 (不立即生效)"""
        logging.info(f"控制台颜色配置更新 (下次启动生效): {level} -> {color_code}")
        # 逻辑备注: 直接保存十六进制颜色值到缓存
        self.console_log_colors[level] = color_code # 功能性备注: 更新内部字典
        # 逻辑备注: 更新内存缓存 (llm_global_config)
        config_key = f"console_log_color_{level.lower()}"
        if hasattr(self.app, 'llm_global_config'):
            self.app.llm_global_config[config_key] = color_code # 保存十六进制值
            logging.info(f"控制台颜色配置 '{config_key}' 已更新到内存缓存。")
            # 功能性备注: 更新控制台颜色名称显示标签 (显示保存的值)
            name_label = getattr(self, f"console_color_name_label_{level.lower()}", None)
            if name_label and name_label.winfo_exists():
                name_label.configure(text=f"({color_code})") # 显示保存的颜色代码
        else:
            logging.warning("警告：无法访问主应用的 llm_global_config 来更新控制台颜色缓存。")

    def display_log(self, level_name, message):
        """
        将从队列中获取的日志消息显示在文本框中。
        根据复选框状态过滤，并应用颜色。
        Args:
            level_name (str): 日志级别名称 (例如 "INFO", "WARNING")。
            message (str): 格式化后的日志消息。
        """
        # 功能性备注: 检查控件是否存在
        if not self or not self.winfo_exists() or not hasattr(self, 'log_display') or not self.log_display.winfo_exists():
            return

        # --- 功能性备注: 根据级别和复选框状态决定是否显示 ---
        should_display = False
        if level_name == "DEBUG" and self.show_debug_var.get():
            should_display = True
        elif level_name == "INFO" and self.show_info_var.get():
            should_display = True
        elif level_name == "WARNING" and self.show_warning_var.get():
            should_display = True
        elif level_name in ["ERROR", "CRITICAL"] and self.show_error_var.get(): # ERROR 和 CRITICAL 共用一个开关
            should_display = True

        # 功能性备注: 如果需要显示
        if should_display:
            try:
                # 功能性备注: 临时启用文本框进行编辑
                self.log_display.configure(state="normal")
                # 功能性备注: 在末尾插入日志消息，并应用对应级别的颜色标签
                self.log_display.insert("end", message + "\n", level_name)
                # 功能性备注: 自动滚动到文本框末尾
                self.log_display.see("end")
                # 功能性备注: 重新禁用文本框编辑
                self.log_display.configure(state="disabled")

            except Exception as e:
                # 功能性备注: 捕获在更新文本框时可能发生的错误
                print(f"错误：更新日志显示时出错: {e}")
                traceback.print_exc()
                # 功能性备注: 尝试恢复文本框状态
                try:
                    if self.log_display.winfo_exists(): # 再次检查是否存在
                        self.log_display.configure(state="disabled")
                except:
                    pass # 忽略恢复状态时的错误

    def clear_logs(self):
        """清空日志显示文本框的内容"""
        # 功能性备注: 检查控件是否存在
        if not self or not self.winfo_exists() or not hasattr(self, 'log_display') or not self.log_display.winfo_exists():
            return
        try:
            # 功能性备注: 启用编辑 -> 删除所有内容 -> 禁用编辑
            self.log_display.configure(state="normal")
            self.log_display.delete("1.0", "end")
            self.log_display.configure(state="disabled")
            logging.info("前台日志显示已清空。") # 记录清空操作
        except Exception as e:
            # 功能性备注: 捕获清空时的错误
            print(f"错误：清空日志时出错: {e}")
            traceback.print_exc()

    def toggle_console_logging(self):
        """
        当“启用控制台日志”复选框状态改变时调用。
        通知主应用程序或日志设置模块更新控制台处理器的状态。
        """
        # 功能性备注: 获取复选框的当前状态
        enable = self.enable_console_log_var.get()
        try:
            # 功能性备注: 调用主应用程序中用于控制控制台日志的方法
            if hasattr(self.app, 'control_console_logging'):
                self.app.control_console_logging(enable)
            else:
                # 功能性备注: 如果主程序没有该方法，尝试直接调用 logger_setup 中的函数
                from core import logger_setup # 导入日志设置模块
                logger_setup.toggle_console_handler(enable)
        except Exception as e:
            # 功能性备注: 捕获调用控制函数时的错误
            print(f"错误：切换控制台日志状态时出错: {e}")
            traceback.print_exc()

    # --- 功能性备注: 获取颜色配置的方法 (供 main_app 保存用) ---
    def get_color_config_data(self):
        """返回当前 UI 和控制台的颜色配置"""
        # 逻辑备注: 返回从 UI 或缓存中获取的颜色设置
        # 逻辑备注: 确保 key 与 config_manager 中定义的一致
        return {
            "ui_log_color_debug": self.ui_log_colors.get("DEBUG", "#ADD8E6"),
            "ui_log_color_info": self.ui_log_colors.get("INFO", "#3CB371"),
            "ui_log_color_warning": self.ui_log_colors.get("WARNING", "orange"),
            "ui_log_color_error": self.ui_log_colors.get("ERROR", "#ff5f5f"),
            "ui_log_color_critical": self.ui_log_colors.get("CRITICAL", "#ff0000"),
            "console_log_color_debug": self.console_log_colors.get("DEBUG", "DIM"),
            "console_log_color_info": self.console_log_colors.get("INFO", "RESET"),
            "console_log_color_warning": self.console_log_colors.get("WARNING", "YELLOW"),
            "console_log_color_error": self.console_log_colors.get("ERROR", "RED"),
            "console_log_color_critical": self.console_log_colors.get("CRITICAL", "BRIGHT_RED"),
        }