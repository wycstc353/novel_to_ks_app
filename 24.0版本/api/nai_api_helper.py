# api/nai_api_helper.py
import requests
import traceback
import time
import json
import re
import copy
from pathlib import Path
import logging # 导入日志模块

# 获取当前模块的 logger 实例
logger = logging.getLogger(__name__)

# 从新的 common_api_utils 导入代理获取函数 (使用相对导入)
try:
    from .common_api_utils import _get_proxies
except ImportError as e:
    # 记录严重错误
    logger.critical(f"严重错误：无法从 .common_api_utils 导入 _get_proxies: {e}。代理功能可能受限。", exc_info=True)
    def _get_proxies(proxy_config):
        logger.warning("警告：_get_proxies 未能从 .common_api_utils 加载，将不使用代理。")
        return None

# --- NovelAI API 调用助手 ---
NAI_API_BASE = "https://api.novelai.net" # NAI API 基础 URL
# 调试日志基础目录
DEBUG_LOG_DIR = Path("debug_logs") / "api_requests"

def _save_debug_input(api_type, payload, identifier):
    """保存调试输入文件 (移除敏感信息)"""
    try:
        debug_save_dir = DEBUG_LOG_DIR / api_type.lower(); debug_save_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_identifier = re.sub(r'[\\/*?:"<>|\s\.]+', '_', identifier or "payload")
        filename = f"{timestamp}_{safe_identifier}.json"
        filepath = debug_save_dir / filename

        # 复制 payload 并移除敏感信息
        payload_to_save = copy.deepcopy(payload)
        # 移除图片 base64 数据
        if 'parameters' in payload_to_save:
            if 'image' in payload_to_save['parameters']:
                payload_to_save['parameters']['image'] = "[Base64 Image Data Removed]"
            if 'mask' in payload_to_save['parameters']:
                payload_to_save['parameters']['mask'] = "[Base64 Mask Data Removed]"

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(payload_to_save, f, ensure_ascii=False, indent=4)
        # 使用 logger 记录保存信息
        logger.info(f"  [Debug Save] {api_type.upper()} 请求已保存到: {filepath}")
    except Exception as save_e:
        # 使用 logger 记录保存错误
        logger.error(f"错误：保存 {api_type.upper()} 请求调试文件时出错: {save_e}", exc_info=True)


def call_novelai_image_api(api_key, payload, proxy_config=None, save_debug=False):
    """
    调用 NovelAI 图像生成 API (/ai/generate-image)。
    """
    # --- 输入校验 ---
    if not api_key:
        logger.error("错误: NovelAI API Key 不能为空。") # 记录错误
        return None, "错误: NovelAI API Key 不能为空。"

    # --- 准备请求 ---
    headers = {
        "Authorization": f"Bearer {api_key}", # API Key 通过 Bearer Token 传递
        "Content-Type": "application/json",
        "Accept": "application/zip" # NAI v3 返回 Zip 文件
    }
    api_endpoint = f"{NAI_API_BASE}/ai/generate-image"
    # 获取 NAI 专用的代理设置 (使用辅助函数)
    proxies = _get_proxies(proxy_config)
    response = None

    # 保存调试输入 (如果启用)
    if save_debug:
        # NAI 的 API Key 在 Header 中，所以不需要从 payload 移除
        _save_debug_input("nai", payload, "generate-image")

    # --- 发送请求并处理响应 ---
    try:
        logger.info(f"调用 NAI API: {api_endpoint}") # 记录信息
        # 发送 POST 请求，超时时间设为 300 秒 (5 分钟)
        response = requests.post(api_endpoint, headers=headers, json=payload, timeout=300, proxies=proxies)
        logger.info(f"NAI API 响应状态码: {response.status_code}") # 记录信息

        # 检查 HTTP 状态码
        if response.status_code == 200:
            # 成功响应 (200 OK)
            content_type = response.headers.get('Content-Type', '').lower()
            # 检查 Content-Type 是否是预期的 Zip
            if 'application/zip' in content_type:
                logger.info(f"NAI API 调用成功: 收到图像数据 (Zip)。") # 记录信息
                return response.content, None # 返回 Zip 文件内容的 bytes
            else:
                # 如果 Content-Type 不对，可能是 API 返回了错误信息 (即使状态码是 200)
                error_msg = f"NAI API 错误: 收到非预期的 Content-Type '{content_type}' (状态码 200 OK)."
                try:
                    # 尝试解析可能的 JSON 错误体
                    error_msg += f" Body: {response.json().get('message', response.text)}"
                except:
                    error_msg += f" Body: {response.text[:200]}..."
                logger.error(error_msg) # 记录错误
                return None, error_msg
        else:
            # 处理非 200 的错误状态码
            error_msg = f"NAI API 错误 (状态码: {response.status_code})"
            try:
                # 尝试解析 JSON 错误信息
                error_msg += f": {response.json().get('message', response.text)}"
            except:
                # 解析失败则直接用文本内容
                error_msg += f": {response.text[:500]}..."
            logger.error(error_msg) # 记录错误
            return None, error_msg

    # --- 处理网络层面的异常 ---
    except requests.exceptions.ProxyError as proxy_e:
        proxy_url = proxies.get('http', 'N/A') if proxies else 'N/A'
        error_msg = f"NAI API 代理错误: 无法连接到代理 {proxy_url}. 错误: {proxy_e}"
        logger.error(error_msg) # 记录错误
        return None, error_msg
    except requests.exceptions.Timeout:
        error_msg = f"NAI API 网络错误: 请求超时 (超过 300 秒)。"
        logger.error(error_msg) # 记录错误
        return None, error_msg
    except requests.exceptions.RequestException as req_e:
        error_msg = f"NAI API 网络/HTTP 错误: {req_e}"
        logger.error(error_msg) # 记录错误
        return None, error_msg
    except Exception as e:
        error_msg = f"NAI API 调用时发生未预期的严重错误: {e}"
        logger.exception(error_msg) # 使用 logger.exception
        return None, error_msg