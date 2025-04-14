# api/nai_api_helper.py
"""
包含调用 NovelAI API 的辅助函数。
"""
import requests
import traceback
import time # 用于添加延迟

# 从新的 common_api_utils 导入代理获取函数 (使用相对导入)
try:
    from .common_api_utils import _get_proxies
except ImportError as e:
    print(f"严重错误：无法从 .common_api_utils 导入 _get_proxies: {e}。代理功能可能受限。")
    # 提供一个备用函数，防止完全崩溃
    def _get_proxies(proxy_config):
        print("警告：_get_proxies 未能从 .common_api_utils 加载，将不使用代理。")
        return None

# --- NovelAI API 调用助手 ---
NAI_API_BASE = "https://api.novelai.net" # NAI API 基础 URL

def call_novelai_image_api(api_key, payload, proxy_config=None):
    """
    调用 NovelAI 图像生成 API (/ai/generate-image)。

    Args:
        api_key (str): NovelAI API Key.
        payload (dict): 请求体 JSON 数据 (符合 NAI API 要求)。
        proxy_config (dict or None): NAI 专用的代理配置字典。
            键应为 "nai_use_proxy", "nai_proxy_address", "nai_proxy_port"。

    Returns:
        tuple: (image_data_bytes: bytes or None, error_message: str or None)
               成功时 image_data_bytes 是返回的 Zip 文件内容 (bytes)，error_message 为 None。
               失败时 image_data_bytes 为 None，error_message 包含错误信息。
    """
    # --- 输入校验 ---
    if not api_key:
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

    # --- 发送请求并处理响应 ---
    try:
        print(f"[NAI API] 调用: {api_endpoint}")
        # 发送 POST 请求，超时时间设为 300 秒 (5 分钟)
        response = requests.post(api_endpoint, headers=headers, json=payload, timeout=300, proxies=proxies)
        print(f"[NAI API] 响应状态码: {response.status_code}")

        # 检查 HTTP 状态码
        if response.status_code == 200:
            # 成功响应 (200 OK)
            content_type = response.headers.get('Content-Type', '').lower()
            # 检查 Content-Type 是否是预期的 Zip
            if 'application/zip' in content_type:
                print(f"[NAI API] 调用成功: 收到图像数据 (Zip)。")
                return response.content, None # 返回 Zip 文件内容的 bytes
            else:
                # 如果 Content-Type 不对，可能是 API 返回了错误信息 (即使状态码是 200)
                error_msg = f"NAI API 错误: 收到非预期的 Content-Type '{content_type}' (状态码 200 OK)."
                try:
                    # 尝试解析可能的 JSON 错误体
                    error_msg += f" Body: {response.json().get('message', response.text)}"
                except:
                    error_msg += f" Body: {response.text[:200]}..."
                print(error_msg)
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
            print(error_msg)
            return None, error_msg

    # --- 处理网络层面的异常 ---
    except requests.exceptions.ProxyError as proxy_e:
        proxy_url = proxies.get('http', 'N/A') if proxies else 'N/A'
        error_msg = f"NAI API 代理错误: 无法连接到代理 {proxy_url}. 错误: {proxy_e}"
        print(error_msg)
        return None, error_msg
    except requests.exceptions.Timeout:
        error_msg = f"NAI API 网络错误: 请求超时 (超过 300 秒)。"
        print(error_msg)
        return None, error_msg
    except requests.exceptions.RequestException as req_e:
        error_msg = f"NAI API 网络/HTTP 错误: {req_e}"
        print(error_msg)
        return None, error_msg
    except Exception as e:
        error_msg = f"NAI API 调用时发生未预期的严重错误: {e}"
        print(error_msg)
        traceback.print_exc()
        return None, error_msg