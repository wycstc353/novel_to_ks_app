# api/api_helpers.py
"""
API 助手模块 (Facade)。
导入并重新导出各个具体 API 的助手函数。
"""
import logging # 导入日志模块

# 获取当前模块的 logger 实例
logger = logging.getLogger(__name__)

# --- 导入 Google API 助手 ---
try:
    from .google_api_helpers import call_google_non_stream, stream_google_response, get_google_models
except ImportError as e:
    # 记录导入错误
    logger.critical(f"错误：无法从 .google_api_helpers 导入: {e}", exc_info=True)
    # 定义占位函数，返回错误信息
    def call_google_non_stream(*args, **kwargs): return None, "错误: Google API 助手未加载"
    def stream_google_response(*args, **kwargs): yield "error", "错误: Google API 助手未加载"
    def get_google_models(*args, **kwargs): return None, "错误: Google API 助手未加载"

# --- 导入 NAI API 助手 ---
try:
    from .nai_api_helper import call_novelai_image_api
except ImportError as e:
    logger.critical(f"错误：无法从 .nai_api_helper 导入: {e}", exc_info=True)
    def call_novelai_image_api(*args, **kwargs): return None, "错误: NAI API 助手未加载"

# --- 导入 SD API 助手 ---
try:
    from .sd_api_helper import call_sd_webui_api
except ImportError as e:
    logger.critical(f"错误：无法从 .sd_api_helper 导入: {e}", exc_info=True)
    def call_sd_webui_api(*args, **kwargs): return None, "错误: SD API 助手未加载"

# --- 导入 ComfyUI API 助手 ---
try:
    from .comfyui_api_helper import call_comfyui_api
except ImportError as e:
    logger.critical(f"错误：无法从 .comfyui_api_helper 导入: {e}", exc_info=True)
    def call_comfyui_api(*args, **kwargs): return None, "错误: ComfyUI API 助手未加载"

# --- 导入 GPT-SoVITS API 助手 ---
try:
    from .gptsovits_api_helper import call_gptsovits_api
except ImportError as e:
    logger.critical(f"错误：无法从 .gptsovits_api_helper 导入: {e}", exc_info=True)
    def call_gptsovits_api(*args, **kwargs): return False, "错误: GPT-SoVITS API 助手未加载"

# --- 导入 OpenAI API 助手 ---
try:
    from .openai_api_helper import call_openai_non_stream, stream_openai_response, get_openai_models
except ImportError as e:
    logger.critical(f"错误：无法从 .openai_api_helper 导入: {e}", exc_info=True)
    def call_openai_non_stream(*args, **kwargs): return None, "错误: OpenAI API 助手未加载"
    def stream_openai_response(*args, **kwargs): yield "error", "错误: OpenAI API 助手未加载"
    def get_openai_models(*args, **kwargs): return None, "错误: OpenAI API 助手未加载"


# --- 重新导出导入的函数 ---
# 这使得其他模块可以通过 from api import api_helpers 来访问所有 API 函数
__all__ = [
    'call_google_non_stream',
    'stream_google_response',
    'get_google_models',
    'call_novelai_image_api',
    'call_sd_webui_api',
    'call_comfyui_api', # 导出 ComfyUI 助手
    'call_gptsovits_api',
    'call_openai_non_stream',
    'stream_openai_response',
    'get_openai_models',
]