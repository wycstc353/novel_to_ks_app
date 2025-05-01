# api/sd_api_helper.py
import requests
import json
import traceback
import base64
import time
import re
import copy
from pathlib import Path
import logging # 导入日志模块

# 获取当前模块的 logger 实例
logger = logging.getLogger(__name__)

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
        if 'init_images' in payload_to_save:
            payload_to_save['init_images'] = ["[Base64 Image Data Removed]"] * len(payload_to_save['init_images'])
        if 'mask' in payload_to_save:
            payload_to_save['mask'] = "[Base64 Mask Data Removed]"
        # 移除 alwayson_scripts 中的图片数据 (如果存在)
        if 'alwayson_scripts' in payload_to_save and isinstance(payload_to_save['alwayson_scripts'], dict):
            for script_name, script_args in payload_to_save['alwayson_scripts'].items():
                 if isinstance(script_args, dict) and 'args' in script_args and isinstance(script_args['args'], list):
                     for i, arg in enumerate(script_args['args']):
                         # 简单检查是否可能是 base64 字符串 (长度和内容)
                         if isinstance(arg, str) and len(arg) > 100 and ('/' in arg or '+' in arg or '=' in arg):
                             script_args['args'][i] = f"[Potential Base64 Data Removed in {script_name}]"

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(payload_to_save, f, ensure_ascii=False, indent=4)
        # 使用 logger 记录保存信息
        logger.info(f"  [Debug Save] {api_type.upper()} 请求已保存到: {filepath}")
    except Exception as save_e:
        # 使用 logger 记录保存错误
        logger.error(f"错误：保存 {api_type.upper()} 请求调试文件时出错: {save_e}", exc_info=True)

# --- Stable Diffusion WebUI API 调用助手 ---

def call_sd_webui_api(sd_webui_url, endpoint_suffix, payload, save_debug=False):
    """
    调用 Stable Diffusion WebUI 的指定 API 端点。
    """
    # --- 输入校验 ---
    if not sd_webui_url:
        logger.error("错误: Stable Diffusion WebUI URL 不能为空。") # 记录错误
        return None, "错误: Stable Diffusion WebUI URL 不能为空。"
    if not endpoint_suffix or not endpoint_suffix.startswith('/'):
        logger.error(f"错误: 无效的 API 端点后缀 '{endpoint_suffix}'。") # 记录错误
        return None, f"错误: 无效的 API 端点后缀 '{endpoint_suffix}'。"

    # --- 准备请求 ---
    api_endpoint = f"{sd_webui_url.rstrip('/')}{endpoint_suffix}"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    response = None

    # 保存调试输入 (如果启用)
    if save_debug:
        _save_debug_input("sd", payload, endpoint_suffix.strip('/'))

    # --- 发送请求并处理响应 ---
    try:
        logger.info(f"调用 SD API: {api_endpoint}") # 记录信息
        response = requests.post(api_endpoint, headers=headers, json=payload, timeout=600) # proxies=proxies 如果需要代理
        logger.info(f"SD API 响应状态码: {response.status_code}") # 记录信息

        # 检查 HTTP 状态码
        if response.status_code == 200:
            try:
                response_json = response.json()
                # 检查响应中是否包含 'images' 列表且不为空
                if 'images' in response_json and isinstance(response_json['images'], list) and response_json['images']:
                    image_list = response_json['images']
                    logger.info(f"SD API 调用成功: 收到 {len(image_list)} 张图像数据 (Base64)。") # 记录信息
                    return image_list, None
                else:
                    error_msg = f"SD API 错误 ({endpoint_suffix}): 响应成功 (200 OK) 但未找到 'images' 列表或列表为空。"
                    logger.error(f"{error_msg} Response: {response.text[:200]}...") # 记录错误
                    return None, error_msg
            except json.JSONDecodeError as json_e:
                 error_msg = f"SD API 错误 ({endpoint_suffix}): 解析成功响应 JSON 失败: {json_e}. Response: {response.text[:500]}..."
                 logger.error(error_msg) # 记录错误
                 return None, error_msg
            except Exception as proc_e:
                 error_msg = f"SD API 错误 ({endpoint_suffix}): 处理成功响应时出错: {proc_e}"
                 logger.exception(error_msg) # 使用 logger.exception
                 return None, error_msg
        else:
            # 处理非 200 的错误状态码
            error_msg = f"SD API 错误 ({endpoint_suffix}, 状态码: {response.status_code})"
            try:
                error_detail = response.json().get('detail', response.json().get('error', response.text))
                error_msg += f": {str(error_detail)[:500]}..."
            except:
                error_msg += f": {response.text[:500]}..."
            logger.error(error_msg) # 记录错误
            return None, error_msg

    # --- 处理网络层面的异常 ---
    except requests.exceptions.Timeout:
        error_msg = f"SD API 网络错误 ({endpoint_suffix}): 请求超时 (超过 600 秒)。"
        logger.error(error_msg) # 记录错误
        return None, error_msg
    except requests.exceptions.ConnectionError as conn_e:
         error_msg = f"SD API 连接错误 ({endpoint_suffix}): 无法连接到 WebUI 地址 '{api_endpoint}'. 请检查地址是否正确以及 WebUI 是否正在运行。错误: {conn_e}"
         logger.error(error_msg) # 记录错误
         return None, error_msg
    except requests.exceptions.RequestException as req_e:
        error_msg = f"SD API 网络/HTTP 错误 ({endpoint_suffix}): {req_e}"
        logger.error(error_msg) # 记录错误
        return None, error_msg
    except Exception as e:
        error_msg = f"SD API 调用 ({endpoint_suffix}) 时发生未预期的严重错误: {e}"
        logger.exception(error_msg) # 使用 logger.exception
        return None, error_msg