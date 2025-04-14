# api/api_helpers.py
"""
API 助手模块 (Facade)。
导入并重新导出各个具体 API 的助手函数。
"""

# --- 导入具体的 API 助手模块 ---
try:
    from .google_api_helpers import call_google_non_stream, stream_google_response
except ImportError as e:
    print(f"错误：无法从 .google_api_helpers 导入: {e}")
    # --- 修正：将占位符函数定义放到独立行 ---
    def call_google_non_stream(*args, **kwargs):
        return None, "错误: Google API 助手未加载"
    def stream_google_response(*args, **kwargs):
        yield "error", "错误: Google API 助手未加载"
    # --- 修正结束 ---

try:
    from .nai_api_helper import call_novelai_image_api
except ImportError as e:
    print(f"错误：无法从 .nai_api_helper 导入: {e}")
    def call_novelai_image_api(*args, **kwargs):
        return None, "错误: NAI API 助手未加载"

try:
    from .sd_api_helper import call_sd_webui_api
except ImportError as e:
    print(f"错误：无法从 .sd_api_helper 导入: {e}")
    def call_sd_webui_api(*args, **kwargs):
        return None, "错误: SD API 助手未加载"

try:
    from .gptsovits_api_helper import call_gptsovits_api
except ImportError as e:
    print(f"错误：无法从 .gptsovits_api_helper 导入: {e}")
    def call_gptsovits_api(*args, **kwargs):
        return False, "错误: GPT-SoVITS API 助手未加载"


# --- 重新导出导入的函数 ---
__all__ = [
    'call_google_non_stream', # 注意：签名已更新，需要传递 top_p, top_k
    'stream_google_response', # 注意：签名已更新，需要传递 top_p, top_k
    'call_novelai_image_api',
    'call_sd_webui_api',
    'call_gptsovits_api',
]