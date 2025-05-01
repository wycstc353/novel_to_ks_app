# ui/ui_helpers.py
import customtkinter as ctk
from tkinter import Toplevel, Text # 导入 Text 以便使用 Textbox
import logging # 导入日志模块

# 获取当前模块的 logger 实例
logger = logging.getLogger(__name__)

# 尝试导入帮助数据
try:
    from core.help_data import get_help_data
    HELP_DATA_LOADED = True
except ImportError:
    logger.warning("警告：无法从 core.help_data 导入帮助数据。帮助按钮将不可用。") # 使用 logging
    HELP_DATA_LOADED = False
    def get_help_data(config_type, param_key): return None # 定义一个空函数避免后续错误

def show_help_popup(config_type, param_key, button_widget):
    """
    显示包含参数帮助信息的弹出窗口，允许复制内容。

    Args:
        config_type (str): 配置类型 (如 'llm_global', 'sd')。
        param_key (str): 参数的内部键名。
        button_widget (ctk.CTkButton): 触发此弹窗的 '?' 按钮实例。
    """
    # 检查帮助数据是否加载
    if not HELP_DATA_LOADED:
        logger.error("错误：帮助数据未加载，无法显示帮助信息。") # 使用 logging
        return

    # 获取帮助信息
    help_info = get_help_data(config_type, param_key)

    # 如果未找到帮助信息，提供默认提示
    if not help_info:
        logger.error(f"错误：未找到配置类型 '{config_type}' 中参数 '{param_key}' 的帮助信息。") # 使用 logging
        help_info = {
            "name": f"{param_key} (未找到)",
            "key": param_key,
            "desc": "抱歉，该参数的详细帮助信息未找到。",
            "default": "N/A"
        }

    # 创建 Toplevel 窗口 (弹出窗口)
    popup = Toplevel(button_widget)
    popup.wm_overrideredirect(True) # 移除窗口边框和标题栏
    popup.attributes("-topmost", True) # 保持在最前

    # 使用 CTkFrame 作为内容容器，添加边框和圆角
    popup_frame = ctk.CTkFrame(popup, corner_radius=5, border_width=1)
    popup_frame.pack(padx=1, pady=1, fill="both", expand=True) # 让 Frame 填充

    # 显示标题
    title_label = ctk.CTkLabel(popup_frame, text=f"帮助: {help_info.get('name', param_key)}", font=ctk.CTkFont(weight="bold"))
    title_label.pack(pady=(5, 10), padx=10, anchor="w")

    # --- 使用 Textbox 显示可复制信息 ---
    info_textbox = ctk.CTkTextbox(
        popup_frame,
        wrap="word", # 自动换行
        height=150, # 初始高度，可根据内容调整
        border_width=0, # 无边框
        fg_color=popup_frame.cget("fg_color") # 背景色与 Frame 一致
    )
    info_textbox.pack(pady=5, padx=10, fill="x") # 填充宽度

    # 插入帮助内容到 Textbox
    info_textbox.insert("end", f"内部 Key: {help_info.get('key', 'N/A')}\n")
    info_textbox.insert("end", f"默认值: {help_info.get('default', 'N/A')}\n\n")
    info_textbox.insert("end", f"描述:\n{help_info.get('desc', '无描述。')}")

    # 设置为只读状态 (允许用户复制内容)
    info_textbox.configure(state="disabled")

    # 关闭按钮
    close_button = ctk.CTkButton(popup_frame, text="关闭", width=60, command=popup.destroy)
    close_button.pack(pady=(10, 10)) # 增加底部间距

    # --- 定位弹出窗口 ---
    # 确保按钮位置信息已更新
    button_widget.update_idletasks()
    btn_x = button_widget.winfo_rootx() # 按钮左上角 X 坐标 (屏幕)
    btn_y = button_widget.winfo_rooty() # 按钮左上角 Y 坐标 (屏幕)
    btn_height = button_widget.winfo_height() # 按钮高度

    # 更新弹出窗口尺寸信息
    popup.update_idletasks()
    popup_width = popup.winfo_width() # 弹出窗口宽度
    popup_height = popup.winfo_height() # 弹出窗口高度
    # 估算宽度，因为 Textbox 可能需要更多空间，设置最小宽度
    popup_width = max(popup_width, 350)

    # 计算弹出窗口的理想位置 (按钮下方)
    popup_x = btn_x
    popup_y = btn_y + btn_height + 2

    # 检查是否超出屏幕边界，并调整位置
    screen_width = popup.winfo_screenwidth()
    screen_height = popup.winfo_screenheight()
    if popup_x + popup_width > screen_width: # 如果右侧超出
        popup_x = screen_width - popup_width - 10 # 移到屏幕右边缘内
    if popup_y + popup_height > screen_height: # 如果下方超出
        popup_y = btn_y - popup_height - 2 # 移到按钮上方
    if popup_x < 0: popup_x = 10 # 防止左侧超出
    if popup_y < 0: popup_y = 10 # 防止上方超出

    # 设置弹出窗口的最终尺寸和位置
    popup.geometry(f"{popup_width}x{popup_height}+{popup_x}+{popup_y}")

    # 绑定事件：当弹出窗口失去焦点时自动关闭
    popup.bind("<FocusOut>", lambda e: popup.destroy())
    # 设置焦点到弹出窗口，以便 FocusOut 事件生效
    popup.focus_set()


def create_help_button(parent, config_type, param_key):
    """
    创建一个 '?' 按钮，点击时显示帮助信息。

    Args:
        parent: 父控件 (通常是包含参数控件的 Frame)。
        config_type (str): 配置类型。
        param_key (str): 参数的内部键名。

    Returns:
        ctk.CTkButton or None: 创建的帮助按钮实例，如果帮助数据未加载则返回 None。
    """
    # 检查帮助数据是否已加载
    if not HELP_DATA_LOADED:
        return None

    # 创建帮助按钮
    help_button = ctk.CTkButton(
        parent,
        text="?", # 按钮文字
        width=20, # 按钮宽度
        height=20, # 按钮高度
        corner_radius=10, # 圆角半径，使其看起来像圆形
        fg_color="gray", # 前景色 (背景色)
        hover_color="dim gray", # 鼠标悬停颜色
        # command 使用 lambda 捕获当前参数，并传递给 show_help_popup
        command=lambda ct=config_type, pk=param_key, btn=None: show_help_popup(ct, pk, btn)
    )
    # 再次配置 command，这次将按钮自身 (help_button) 传递给 lambda，以便 show_help_popup 获取按钮位置
    help_button.configure(command=lambda ct=config_type, pk=param_key, btn=help_button: show_help_popup(ct, pk, btn))
    return help_button