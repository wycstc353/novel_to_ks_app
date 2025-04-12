# api/api_helpers.py
"""
API 助手模块 (Facade)。
导入并重新导出各个具体 API 的助手函数。
通用函数 _get_proxies 已移至 common_api_utils.py。
"""

# --- 导入具体的 API 助手模块 (使用相对导入) ---
# 使用 try-except 块增加启动时的健壮性
try:
    from .google_api_helpers import call_google_non_stream, stream_google_response
except ImportError as e:
    print(f"错误：无法从 .google_api_helpers 导入: {e}")
    # 定义占位符函数，以便程序可以继续运行（但功能会受限）
    def call_google_non_stream(*args, **kwargs): return None, "错误: Google API 助手未加载"
    def stream_google_response(*args, **kwargs): yield "error", "错误: Google API 助手未加载"

try:
    from .nai_api_helper import call_novelai_image_api
except ImportError as e:
    print(f"错误：无法从 .nai_api_helper 导入: {e}")
    def call_novelai_image_api(*args, **kwargs): return None, "错误: NAI API 助手未加载"

try:
    from .sd_api_helper import call_sd_webui_api
except ImportError as e:
    print(f"错误：无法从 .sd_api_helper 导入: {e}")
    def call_sd_webui_api(*args, **kwargs): return None, "错误: SD API 助手未加载"

# 新增：导入 GPT-SoVITS API 助手
try:
    from .gptsovits_api_helper import call_gptsovits_api
except ImportError as e:
    print(f"错误：无法从 .gptsovits_api_helper 导入: {e}")
    def call_gptsovits_api(*args, **kwargs): return False, "错误: GPT-SoVITS API 助手未加载"


# --- 重新导出导入的函数，保持接口一致性 ---
# 这使得其他模块仍然可以写 from api.api_helpers import call_google_non_stream 等
__all__ = [
    'call_google_non_stream',
    'stream_google_response',
    'call_novelai_image_api',
    'call_sd_webui_api',
    'call_gptsovits_api', # 新增导出
    # '_get_proxies' 不再由此模块提供
]