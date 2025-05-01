# core/logger_setup.py
import logging
import queue
import sys
import customtkinter as ctk # 需要导入以获取主题颜色
# 功能性备注: 导入 colorama 用于控制台颜色
import colorama
# 功能性备注: 导入 config_manager 以读取颜色配置
from . import config_manager

# --- 全局日志队列 ---
# 功能性备注: 用于在不同线程和模块之间安全地传递日志记录
log_queue = queue.Queue()

# --- 自定义日志处理器：将日志放入队列 ---
class QueueHandler(logging.Handler):
    """
    一个自定义的日志处理器，它将日志记录放入一个指定的队列中，
    而不是直接输出到控制台或文件。
    """
    def __init__(self, log_queue):
        # 功能性备注: 初始化父类 Handler
        super().__init__()
        # 功能性备注: 保存日志队列的引用
        self.log_queue = log_queue

    def emit(self, record):
        """
        处理传入的日志记录。
        格式化记录，并将级别名称和格式化后的消息放入队列。
        """
        try:
            # 功能性备注: 格式化日志记录为字符串
            msg = self.format(record)
            # 功能性备注: 将日志级别名称和格式化后的消息作为一个元组放入队列
            # 功能性备注: 使用 levelname 而不是 levelno，方便前端直接使用字符串判断
            self.log_queue.put((record.levelname, msg))
        except Exception:
            # 功能性备注: 如果在处理过程中发生异常，则报告错误
            self.handleError(record)

# --- 功能性备注: 自定义 Formatter 添加颜色 ---
class ColoredFormatter(logging.Formatter):
    """自定义日志格式化器，根据日志级别添加 colorama 颜色代码。"""

    # 功能性备注: 构造函数，接收颜色配置字典
    def __init__(self, fmt=None, datefmt=None, style='%', colors=None):
        super().__init__(fmt, datefmt, style)
        # 功能性备注: 存储颜色配置，提供默认值
        self.colors = colors or {
            logging.DEBUG: colorama.Style.DIM + colorama.Fore.CYAN, # 默认 DIM CYAN
            logging.INFO: colorama.Fore.GREEN,                     # 默认 GREEN
            logging.WARNING: colorama.Fore.YELLOW,                  # 默认 YELLOW
            logging.ERROR: colorama.Fore.RED,                       # 默认 RED
            logging.CRITICAL: colorama.Style.BRIGHT + colorama.Fore.RED # 默认 BRIGHT RED
        }

    # 功能性备注: 重写 format 方法
    def format(self, record):
        # 功能性备注: 获取原始格式化消息
        log_msg = super().format(record)
        # 功能性备注: 根据日志级别获取颜色代码
        color_prefix = self.colors.get(record.levelno, colorama.Style.RESET_ALL) # 找不到则重置颜色
        # 功能性备注: 添加颜色前缀和重置后缀
        # 逻辑备注: colorama.init(autoreset=True) 会自动在打印后重置，所以后缀不是必须的，但加上更保险
        return f"{color_prefix}{log_msg}{colorama.Style.RESET_ALL}"

# --- 全局变量，用于存储控制台处理器引用 ---
# 功能性备注: 允许之后动态修改控制台输出的级别或启用/禁用
_console_handler = None

# --- 日志系统设置函数 ---
def setup_logging(console_level=logging.INFO):
    """
    配置全局日志系统。
    设置根 logger，添加队列处理器和带颜色的控制台处理器。
    """
    global _console_handler # 声明使用全局变量

    # 功能性备注: 初始化 colorama
    colorama.init(autoreset=True)

    # 功能性备注: 获取根 logger
    root_logger = logging.getLogger()
    # 功能性备注: 设置根 logger 处理的最低级别为 DEBUG，以捕获所有级别的日志
    root_logger.setLevel(logging.DEBUG)

    # --- 功能性备注: 清理现有的处理器 (防止重复添加) ---
    # 功能性备注: 在重新配置时移除旧的处理器，避免日志重复输出
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        handler.close() # 关闭处理器释放资源

    # --- 功能性备注: 创建基础日志格式化器 (不含颜色) ---
    log_formatter_basic = logging.Formatter(
        '%(asctime)s - %(levelname)-8s - [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # --- 功能性备注: 配置队列处理器 ---
    # 功能性备注: 创建 QueueHandler 实例，使用全局的 log_queue
    queue_handler = QueueHandler(log_queue)
    # 功能性备注: 设置日志级别为 DEBUG，确保所有日志都进入队列，由前端决定显示哪些
    queue_handler.setLevel(logging.DEBUG)
    # 功能性备注: 为队列处理器设置基础格式化器
    queue_handler.setFormatter(log_formatter_basic)
    # 功能性备注: 将队列处理器添加到根 logger
    root_logger.addHandler(queue_handler)

    # --- 功能性备注: 加载控制台颜色配置 ---
    console_colors_config = {}
    try:
        # 逻辑备注: 假设颜色配置存储在 llm_global_config 中
        config = config_manager.load_config("llm_global")
        # 逻辑备注: 将配置中的颜色名称 (或代码) 映射到 colorama 对象
        color_map = {
            "RESET": colorama.Style.RESET_ALL, "NORMAL": colorama.Style.NORMAL,
            "DIM": colorama.Style.DIM, "BRIGHT": colorama.Style.BRIGHT,
            "BLACK": colorama.Fore.BLACK, "RED": colorama.Fore.RED, "GREEN": colorama.Fore.GREEN,
            "YELLOW": colorama.Fore.YELLOW, "BLUE": colorama.Fore.BLUE, "MAGENTA": colorama.Fore.MAGENTA,
            "CYAN": colorama.Fore.CYAN, "WHITE": colorama.Fore.WHITE,
            "BRIGHT_BLACK": colorama.Fore.BLACK + colorama.Style.BRIGHT, # 示例组合
            "BRIGHT_RED": colorama.Fore.RED + colorama.Style.BRIGHT,
            "BRIGHT_GREEN": colorama.Fore.GREEN + colorama.Style.BRIGHT,
            "BRIGHT_YELLOW": colorama.Fore.YELLOW + colorama.Style.BRIGHT,
            "BRIGHT_BLUE": colorama.Fore.BLUE + colorama.Style.BRIGHT,
            "BRIGHT_MAGENTA": colorama.Fore.MAGENTA + colorama.Style.BRIGHT,
            "BRIGHT_CYAN": colorama.Fore.CYAN + colorama.Style.BRIGHT,
            "BRIGHT_WHITE": colorama.Fore.WHITE + colorama.Style.BRIGHT,
        }
        # 逻辑备注: 映射配置值到 colorama 代码
        # 逻辑备注: 新增 - 尝试将十六进制颜色转为 ANSI (简化版，仅前景色)
        def hex_to_colorama(hex_code, default_color):
            if not isinstance(hex_code, str) or not hex_code.startswith('#'):
                # 如果不是有效的十六进制，尝试按名称查找
                return color_map.get(hex_code.upper(), default_color)
            try:
                # 简化转换：只处理基本颜色，更复杂的需要 colorama 扩展或直接用 ANSI
                r = int(hex_code[1:3], 16)
                g = int(hex_code[3:5], 16)
                b = int(hex_code[5:7], 16)
                # 简单映射到最接近的 colorama 颜色 (非常粗略)
                if r > 180 and g < 100 and b < 100: return colorama.Fore.RED
                if g > 180 and r < 100 and b < 100: return colorama.Fore.GREEN
                if b > 180 and r < 100 and g < 100: return colorama.Fore.BLUE
                if r > 180 and g > 180 and b < 100: return colorama.Fore.YELLOW
                if r > 180 and b > 180 and g < 100: return colorama.Fore.MAGENTA
                if g > 180 and b > 180 and r < 100: return colorama.Fore.CYAN
                if r > 180 and g > 180 and b > 180: return colorama.Fore.WHITE
                if r < 70 and g < 70 and b < 70: return colorama.Fore.BLACK # Dim gray as black
                # 其他情况返回默认
                return default_color
            except:
                return default_color

        console_colors_config = {
            logging.DEBUG: hex_to_colorama(config.get("console_log_color_debug", "DIM"), colorama.Style.DIM + colorama.Fore.CYAN),
            logging.INFO: hex_to_colorama(config.get("console_log_color_info", "GREEN"), colorama.Fore.GREEN),
            logging.WARNING: hex_to_colorama(config.get("console_log_color_warning", "YELLOW"), colorama.Fore.YELLOW),
            logging.ERROR: hex_to_colorama(config.get("console_log_color_error", "RED"), colorama.Fore.RED),
            logging.CRITICAL: hex_to_colorama(config.get("console_log_color_critical", "BRIGHT_RED"), colorama.Style.BRIGHT + colorama.Fore.RED),
        }
        logging.info("成功加载控制台颜色配置。")
    except Exception as e:
        logging.warning(f"加载控制台颜色配置失败，将使用默认颜色: {e}", exc_info=True)
        # 逻辑备注: 加载失败时，console_colors_config 会为空，ColoredFormatter 会使用其内部默认值

    # --- 功能性备注: 配置带颜色的控制台处理器 ---
    # 功能性备注: 创建 StreamHandler 实例，输出到标准错误流 (通常是控制台)
    _console_handler = logging.StreamHandler(sys.stderr)
    # 功能性备注: 设置控制台处理器的日志级别 (可以动态调整)
    _console_handler.setLevel(console_level)
    # 功能性备注: 创建并设置带颜色的格式化器
    colored_formatter = ColoredFormatter(
        '%(asctime)s - %(levelname)-8s - [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        colors=console_colors_config # 传递加载的颜色配置
    )
    _console_handler.setFormatter(colored_formatter)
    # 功能性备注: 将控制台处理器添加到根 logger
    root_logger.addHandler(_console_handler)

    # 功能性备注: 记录一条信息，表示日志系统已配置完成
    root_logger.info("日志系统初始化完成。队列和带颜色的控制台处理器已添加。")

# --- 控制函数：修改控制台日志级别 ---
def set_console_log_level(level):
    """
    动态修改控制台处理器的日志级别。
    Args:
        level: logging 模块定义的日志级别 (例如 logging.INFO, logging.DEBUG)。
    """
    if _console_handler:
        # 功能性备注: 检查传入的级别是否有效
        if isinstance(level, int) and level in [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL]:
            # 功能性备注: 设置控制台处理器的级别
            _console_handler.setLevel(level)
            # 功能性备注: 记录级别变更信息
            logging.info(f"控制台日志级别已设置为: {logging.getLevelName(level)}")
        else:
            # 功能性备注: 记录无效级别警告
            logging.warning(f"尝试设置无效的控制台日志级别: {level}")
    else:
        # 功能性备注: 记录处理器未找到警告
        logging.warning("控制台处理器未初始化，无法设置级别。")

# --- 控制函数：启用/禁用控制台处理器 ---
def toggle_console_handler(enable):
    """
    动态启用或禁用控制台日志输出。
    Args:
        enable (bool): True 表示启用，False 表示禁用。
    """
    global _console_handler # 声明使用全局变量
    root_logger = logging.getLogger()
    if enable:
        # 功能性备注: 如果要启用，并且当前没有控制台处理器，则重新创建并添加
        if not _console_handler:
            # 逻辑备注: 重新启用时，需要重新加载配置并创建带颜色的处理器
            setup_logging() # 重新调用 setup 来创建和添加
            logging.info("控制台日志处理器已重新创建并启用。") # setup_logging 内部会记录
        elif _console_handler not in root_logger.handlers:
            # 功能性备注: 如果处理器存在但未添加到 logger，则添加回去
            root_logger.addHandler(_console_handler)
            logging.info("控制台日志处理器已重新启用。")
        else:
            # 功能性备注: 如果已启用，则无需操作
            logging.debug("控制台日志处理器已处于启用状态。")
    else:
        # 功能性备注: 如果要禁用，并且当前有控制台处理器
        if _console_handler and _console_handler in root_logger.handlers:
            # 功能性备注: 从根 logger 中移除处理器
            root_logger.removeHandler(_console_handler)
            # 功能性备注: 关闭处理器释放资源 (可选，但推荐)
            # _console_handler.close()
            # _console_handler = None # 可以选择置空引用
            logging.info("控制台日志处理器已禁用。")
        else:
            # 功能性备注: 如果已禁用或处理器不存在，则无需操作
            logging.debug("控制台日志处理器已处于禁用状态或不存在。")