# api/sd_api_helper.py
"""
包含调用 Stable Diffusion WebUI API 的辅助函数。
"""
import requests
import json
import traceback
import base64

# --- Stable Diffusion WebUI API 调用助手 ---

def call_sd_webui_api(sd_webui_url, payload):
    """
    调用 Stable Diffusion WebUI 的 txt2img API。

    Args:
        sd_webui_url (str): SD WebUI 的基础 URL (例如 "http://127.0.0.1:7860")。
        payload (dict): 请求体 JSON 数据 (符合 SD WebUI API 要求)。

    Returns:
        tuple: (base64_image_list: list[str] or None, error_message: str or None)
               成功时 base64_image_list 是包含 Base64 编码图像字符串的列表，error_message 为 None。
               失败时 base64_image_list 为 None，error_message 包含错误信息。
               注意：列表中的 Base64 字符串可能包含 data URI 前缀 (如 'data:image/png;base64,...')，
                     调用方可能需要去除前缀再解码。
    """
    # --- 输入校验 ---
    if not sd_webui_url:
        return None, "错误: Stable Diffusion WebUI URL 不能为空。"

    # --- 准备请求 ---
    # 构建 txt2img API 端点 URL
    api_endpoint = f"{sd_webui_url.rstrip('/')}/sdapi/v1/txt2img"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    response = None
    # 注意：SD WebUI API 通常不需要代理，如果需要，可以在这里添加 proxy_config 参数和 _get_proxies 调用

    # --- 发送请求并处理响应 ---
    try:
        print(f"[SD API] 调用: {api_endpoint}")
        # 发送 POST 请求，设置较长超时时间 (例如 600 秒 = 10 分钟)
        response = requests.post(api_endpoint, headers=headers, json=payload, timeout=600) # proxies=proxies 如果需要代理
        print(f"[SD API] 响应状态码: {response.status_code}")

        # 检查 HTTP 状态码
        if response.status_code == 200:
            # 成功响应 (200 OK)
            try:
                response_json = response.json()
                # 检查响应中是否包含 'images' 列表且不为空
                if 'images' in response_json and isinstance(response_json['images'], list) and response_json['images']:
                    # 提取图像列表 (Base64 字符串)
                    image_list = response_json['images']
                    print(f"[SD API] 调用成功: 收到 {len(image_list)} 张图像数据 (Base64)。")
                    # 返回原始的 Base64 列表，让调用方处理前缀
                    return image_list, None
                else:
                    # 响应成功但没有图像数据
                    error_msg = "SD API 错误: 响应成功 (200 OK) 但未找到 'images' 列表或列表为空。"
                    print(f"{error_msg} Response: {response.text[:200]}...")
                    return None, error_msg
            except json.JSONDecodeError as json_e:
                 # 解析成功响应的 JSON 时出错
                 error_msg = f"SD API 错误: 解析成功响应 JSON 失败: {json_e}. Response: {response.text[:500]}..."
                 print(error_msg)
                 return None, error_msg
            except Exception as proc_e:
                 # 处理成功响应时发生其他错误
                 error_msg = f"SD API 错误: 处理成功响应时出错: {proc_e}"
                 print(f"错误: {error_msg}")
                 traceback.print_exc()
                 return None, error_msg
        else:
            # 处理非 200 的错误状态码
            error_msg = f"SD API 错误 (状态码: {response.status_code})"
            try:
                # 尝试解析 SD WebUI 返回的错误详情 ('detail' 或 'error' 字段)
                error_detail = response.json().get('detail', response.json().get('error', response.text))
                # 限制错误详情长度避免过长日志
                error_msg += f": {str(error_detail)[:500]}..."
            except:
                # 解析失败则直接用文本内容
                error_msg += f": {response.text[:500]}..."
            print(error_msg)
            return None, error_msg

    # --- 处理网络层面的异常 ---
    except requests.exceptions.Timeout:
        error_msg = f"SD API 网络错误: 请求超时 (超过 600 秒)。"
        print(error_msg)
        return None, error_msg
    except requests.exceptions.ConnectionError as conn_e:
         # 连接错误，通常是 URL 不对或 WebUI 未运行
         error_msg = f"SD API 连接错误: 无法连接到 WebUI 地址 '{api_endpoint}'. 请检查地址是否正确以及 WebUI 是否正在运行。错误: {conn_e}"
         print(error_msg)
         return None, error_msg
    except requests.exceptions.RequestException as req_e:
        # 其他 requests 异常
        error_msg = f"SD API 网络/HTTP 错误: {req_e}"
        print(error_msg)
        return None, error_msg
    except Exception as e:
        # 捕获其他所有意外错误
        error_msg = f"SD API 调用时发生未预期的严重错误: {e}"
        print(error_msg)
        traceback.print_exc()
        return None, error_msg
