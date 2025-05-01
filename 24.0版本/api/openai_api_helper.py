# api/openai_api_helper.py
import requests
import json
import traceback
import time
import os
import re
import copy
from pathlib import Path
import logging # 导入日志模块

# 获取当前模块的 logger 实例
logger = logging.getLogger(__name__)

# 尝试从同级目录导入通用代理获取函数
try:
    from .common_api_utils import _get_proxies
except ImportError as e:
    # 记录严重错误
    logger.critical(f"严重错误：无法从 .common_api_utils 导入 _get_proxies: {e}。代理功能可能受限。", exc_info=True)
    def _get_proxies(proxy_config):
        logger.warning("警告：_get_proxies 未能从 .common_api_utils 加载，将不使用代理。")
        return None

# --- OpenAI API 调用助手 ---

# OpenAI API 默认基础 URL (v1)
OPENAI_API_BASE = "https://api.openai.com/v1"
# 调试日志基础目录
DEBUG_LOG_DIR = Path("debug_logs") / "api_requests"

def _prepare_openai_payload(prompt, model_name, temperature, max_tokens, stream=False):
    """准备 OpenAI Chat Completions API 的请求体"""
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "stream": stream
    }
    # 添加可选参数，并记录无效值警告
    if temperature is not None:
        try: temp_float = float(temperature); assert 0.0 <= temp_float <= 2.0; payload["temperature"] = temp_float
        except: logger.warning(f"警告 (OpenAI): 无效 temperature '{temperature}'") # 记录警告
    if max_tokens is not None:
        try: max_tokens_int = int(max_tokens); assert max_tokens_int > 0; payload["max_tokens"] = max_tokens_int
        except: logger.warning(f"警告 (OpenAI): 无效 max_tokens '{max_tokens}'") # 记录警告
    return payload

def _get_openai_headers(api_key, custom_headers=None):
    """准备 OpenAI API 请求的 Headers"""
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    if isinstance(custom_headers, dict):
        headers.update(custom_headers)
        # 记录使用了自定义 Headers
        logger.info(f"[OpenAI API Helper] 使用了自定义 Headers: {list(custom_headers.keys())}")
    return headers

def _save_debug_input(api_type, payload, prompt_type, headers):
    """保存调试输入文件 (移除敏感信息)"""
    try:
        debug_save_dir = DEBUG_LOG_DIR / api_type.lower(); debug_save_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_identifier = re.sub(r'[\\/*?:"<>|\s\.]+', '_', prompt_type or "payload")
        filename = f"{timestamp}_{safe_identifier}.json"
        filepath = debug_save_dir / filename

        # 复制 payload 和 headers 并移除敏感信息
        payload_to_save = copy.deepcopy(payload)
        headers_to_save = copy.deepcopy(headers)

        # 移除 Authorization header (包含 API Key)
        if 'Authorization' in headers_to_save:
            headers_to_save['Authorization'] = "Bearer [HIDDEN]"
        # (可选) 检查自定义 headers 中是否有敏感信息

        data_to_save = {
            "payload": payload_to_save,
            "headers": headers_to_save # 保存清理后的 headers
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)
        # 使用 logger 记录保存信息
        logger.info(f"  [Debug Save] {api_type.upper()} 请求已保存到: {filepath}")
    except Exception as save_e:
        # 使用 logger 记录保存错误
        logger.error(f"错误：保存 {api_type.upper()} 请求调试文件时出错: {save_e}", exc_info=True)


def call_openai_non_stream(api_key, api_base_url, model_name, prompt, temperature, max_tokens, custom_headers=None, proxy_config=None, save_debug=False, prompt_type="Generic"):
    """调用 OpenAI Chat Completions 非流式 API"""
    # 输入校验
    if not api_key: err_msg = "错误 (OpenAI): API Key 不能为空。"; logger.error(err_msg); return None, err_msg
    if not api_base_url: api_base_url = OPENAI_API_BASE
    if not model_name: err_msg = "错误 (OpenAI): 模型名称不能为空。"; logger.error(err_msg); return None, err_msg

    endpoint = f"{api_base_url.rstrip('/')}/chat/completions"
    headers = _get_openai_headers(api_key, custom_headers)
    payload = _prepare_openai_payload(prompt, model_name, temperature, max_tokens, stream=False)
    proxies = _get_proxies(proxy_config)
    response = None

    # 保存调试输入 (如果启用)
    if save_debug:
        _save_debug_input("openai", payload, prompt_type, headers)

    try:
        # 记录 API 调用信息
        logger.info(f"[OpenAI API] 调用非流式: {endpoint}")
        response = requests.post(endpoint, headers=headers, json=payload, timeout=600, proxies=proxies)
        # 记录响应状态码
        logger.info(f"[OpenAI API] 响应状态码: {response.status_code}")

        if response.status_code == 200:
            try:
                response_json = response.json()
                # 检查响应结构
                if "choices" in response_json and isinstance(response_json["choices"], list) and len(response_json["choices"]) > 0:
                    first_choice = response_json["choices"][0]
                    if "message" in first_choice and "content" in first_choice["message"]:
                        result_text = first_choice["message"]["content"]
                        finish_reason = first_choice.get("finish_reason", "unknown")
                        # 记录成功和终止原因
                        logger.info(f"[OpenAI API] 非流式调用成功. Finish Reason: {finish_reason}")
                        if finish_reason == "length": logger.warning(f"警告 (OpenAI): 输出可能因达到 Max Tokens ({max_tokens}) 而被截断。") # 记录截断警告
                        elif finish_reason != "stop": logger.warning(f"警告 (OpenAI): 非预期的终止原因: {finish_reason}") # 记录其他终止原因警告
                        return result_text, None
                    else: error_msg = "OpenAI API 错误: 响应 JSON 结构无效 (缺少 message.content)。"
                else: error_msg = "OpenAI API 错误: 响应 JSON 结构无效 (缺少 choices 列表或列表为空)。"
                logger.error(f"{error_msg} Response: {response.text[:500]}...") # 记录结构错误
                return None, error_msg
            except json.JSONDecodeError as json_e: error_msg = f"OpenAI API 错误: 解析成功响应 JSON 失败: {json_e}. Response: {response.text[:500]}..."; logger.error(error_msg); return None, error_msg # 记录 JSON 解析错误
            except Exception as proc_e: error_msg = f"OpenAI API 错误: 处理成功响应时出错: {proc_e}"; logger.exception(error_msg); return None, error_msg # 使用 logger.exception
        else:
            # 处理非 200 错误
            error_msg = f"OpenAI API 错误 (状态码: {response.status_code})"
            try: error_detail = response.json().get('error', {}).get('message', response.text)
            except: error_detail = response.text
            error_msg += f": {str(error_detail)[:500]}..."; logger.error(error_msg); return None, error_msg # 记录 API 错误

    # 处理网络和请求异常
    except requests.exceptions.ProxyError as proxy_e: proxy_url = proxies.get('http', 'N/A') if proxies else 'N/A'; error_msg = f"OpenAI API 代理错误: 无法连接到代理 {proxy_url}. 错误: {proxy_e}"; logger.error(error_msg); return None, error_msg
    except requests.exceptions.SSLError as ssl_e: error_msg = f"OpenAI API SSL 错误: 建立安全连接失败. 错误: {ssl_e}"; logger.error(error_msg); return None, error_msg
    except requests.exceptions.Timeout: error_msg = f"OpenAI API 网络错误: 请求超时 (超过 600 秒)。"; logger.error(error_msg); return None, error_msg
    except requests.exceptions.RequestException as req_e:
        error_detail = str(req_e)
        status_code_info = f"Status: {response.status_code}" if response else "无响应"
        error_msg = f"OpenAI API 网络/HTTP 错误 ({status_code_info}): {error_detail}"
        logger.error(error_msg) # 记录网络错误
        if response and response.text:
            logger.error(f"原始响应 (部分): {response.text[:500]}...") # 记录部分原始响应
        return None, error_msg
    except Exception as e: error_msg = f"OpenAI API 调用时发生未预期的严重错误: {e}"; logger.exception(error_msg); return None, error_msg # 使用 logger.exception

def stream_openai_response(api_key, api_base_url, model_name, prompt, temperature, max_tokens, custom_headers=None, proxy_config=None, save_debug=False, prompt_type="Generic"):
    """调用 OpenAI Chat Completions 流式 API"""
    # 输入校验
    if not api_key: err_msg = "错误 (OpenAI): API Key 不能为空。"; logger.error(err_msg); yield "error", err_msg; return
    if not api_base_url: api_base_url = OPENAI_API_BASE
    if not model_name: err_msg = "错误 (OpenAI): 模型名称不能为空。"; logger.error(err_msg); yield "error", err_msg; return

    endpoint = f"{api_base_url.rstrip('/')}/chat/completions"
    headers = _get_openai_headers(api_key, custom_headers)
    payload = _prepare_openai_payload(prompt, model_name, temperature, max_tokens, stream=True)
    proxies = _get_proxies(proxy_config)
    response = None

    # 保存调试输入 (如果启用)
    if save_debug:
        _save_debug_input("openai", payload, f"{prompt_type}_stream", headers)

    try:
        # 记录流式连接信息
        logger.info(f"[OpenAI API Stream] 连接流: {endpoint}")
        response = requests.post(endpoint, headers=headers, json=payload, stream=True, timeout=600, proxies=proxies)
        # 记录响应状态码
        logger.info(f"[OpenAI API Stream] 响应状态码: {response.status_code}")

        if response.status_code != 200:
            # 处理连接时的错误
            error_msg = f"OpenAI API 流错误 (连接阶段, 状态码: {response.status_code})"
            try: error_detail = response.json().get('error', {}).get('message', response.text)
            except: error_detail = response.text
            error_msg += f": {str(error_detail)[:500]}..."; logger.error(error_msg); yield "error", error_msg; return

        # 记录流开始
        logger.info(f"[OpenAI API Stream] 开始接收事件流...")
        finish_reason = None
        for line_bytes in response.iter_lines():
            if line_bytes:
                try:
                    line = line_bytes.decode('utf-8')
                    if line.startswith('data: '):
                        json_str = line[len('data: '):].strip()
                        if json_str == '[DONE]': break # 正常结束循环
                        try:
                            chunk_json = json.loads(json_str)
                            if "choices" in chunk_json and len(chunk_json["choices"]) > 0:
                                delta = chunk_json["choices"][0].get("delta", {})
                                content_chunk = delta.get("content")
                                if content_chunk: yield "chunk", content_chunk # 返回文本块
                                if chunk_json["choices"][0].get("finish_reason"): finish_reason = chunk_json["choices"][0].get("finish_reason")
                        except json.JSONDecodeError: logger.warning(f"警告 (OpenAI Stream): 解析 SSE 数据块 JSON 失败: '{json_str[:100]}...'"); yield "warning", f"收到无效的 JSON 数据块: {json_str[:100]}..." # 记录解析警告
                        except Exception as proc_e: logger.warning(f"警告 (OpenAI Stream): 处理 SSE 数据块时出错: {proc_e}"); yield "warning", f"处理数据块时出错: {proc_e}" # 记录处理警告
                except UnicodeDecodeError: logger.warning(f"警告 (OpenAI Stream): 解码 SSE 行时出错，已跳过。原始字节: {line_bytes}"); continue # 记录解码警告

        # 循环结束后检查 finish_reason
        logger.info(f"OpenAI API 事件流处理完成. Finish Reason: {finish_reason}") # 记录完成和原因
        if finish_reason == "length": yield "warning", f"输出可能因达到 Max Tokens ({max_tokens}) 而被截断。" # 返回截断警告
        elif finish_reason and finish_reason != "stop": yield "warning", f"非预期的终止原因: {finish_reason}" # 返回其他终止原因警告
        yield "done", "OpenAI 流处理完成。" # 返回完成信号

    # 处理网络和请求异常
    except requests.exceptions.ProxyError as proxy_e: proxy_url = proxies.get('http', 'N/A') if proxies else 'N/A'; error_msg = f"OpenAI API 流代理错误: 无法连接到代理 {proxy_url}. 错误: {proxy_e}"; logger.error(error_msg); yield "error", error_msg
    except requests.exceptions.SSLError as ssl_e: error_msg = f"OpenAI API 流 SSL 错误: {ssl_e}"; logger.error(error_msg); yield "error", error_msg
    except requests.exceptions.RequestException as req_e: error_msg = f"OpenAI API 流网络/HTTP 错误: {req_e}"; logger.error(error_msg); yield "error", error_msg
    except Exception as e: error_msg = f"处理 OpenAI API 流时发生未预期的严重错误: {e}"; logger.exception(error_msg); yield "error", error_msg # 使用 logger.exception
    finally:
        # 记录生成器退出
        logger.info(f"OpenAI API 流生成器退出.")
        if response:
            try: response.close(); logger.info("已关闭 OpenAI API 响应流.") # 记录流关闭
            except Exception as close_e: logger.warning(f"关闭 OpenAI API 响应流时出错: {close_e}") # 记录关闭错误

def get_openai_models(api_key, api_base_url, custom_headers=None, proxy_config=None, save_debug=False):
    """调用 OpenAI API (或兼容反代) 的 /models 端点获取可用模型列表。"""
    # 输入校验
    if not api_key: err_msg = "错误 (OpenAI): API Key 不能为空。"; logger.error(err_msg); return None, err_msg
    if not api_base_url: api_base_url = OPENAI_API_BASE

    endpoint = f"{api_base_url.rstrip('/')}/models"
    headers = _get_openai_headers(api_key, custom_headers)
    headers["Accept"] = "application/json"
    if "Content-Type" in headers: del headers["Content-Type"] # GET 请求不需要 Content-Type

    proxies = _get_proxies(proxy_config)
    response = None

    # 保存调试输入 (如果启用)
    if save_debug:
        debug_payload = {"request_type": "get_models", "url": endpoint, "headers": {k: v for k, v in headers.items() if k.lower() != 'authorization'}} # 移除 Authorization
        _save_debug_input("openai", debug_payload, "GetModels", headers) # Pass original headers for removal inside

    try:
        # 记录请求信息
        logger.info(f"[OpenAI API] 获取模型列表: {endpoint}")
        response = requests.get(endpoint, headers=headers, timeout=60, proxies=proxies) # 60秒超时
        # 记录响应状态码
        logger.info(f"[OpenAI API] 获取模型响应状态码: {response.status_code}")

        if response.status_code == 200:
            try:
                response_json = response.json()
                # OpenAI 官方格式是 {"object": "list", "data": [{"id": "model-id", ...}, ...]}
                if "data" in response_json and isinstance(response_json["data"], list):
                    model_ids = [item.get("id") for item in response_json["data"] if item.get("id")]
                    if model_ids:
                        logger.info(f"[OpenAI API] 成功获取 {len(model_ids)} 个模型 ID。") # 记录成功获取
                        return sorted(model_ids), None # 返回排序后的模型 ID 列表
                    else: error_msg = "OpenAI API 错误: /models 响应成功，但 'data' 列表为空或不包含有效的模型 ID。"
                else: error_msg = "OpenAI API 错误: /models 响应 JSON 结构无效 (缺少 'data' 列表)。"
                logger.error(f"{error_msg} Response: {response.text[:500]}...") # 记录结构错误
                return None, error_msg
            except json.JSONDecodeError as json_e: error_msg = f"OpenAI API 错误: 解析 /models 响应 JSON 失败: {json_e}. Response: {response.text[:500]}..."; logger.error(error_msg); return None, error_msg # 记录 JSON 解析错误
            except Exception as proc_e: error_msg = f"OpenAI API 错误: 处理 /models 响应时出错: {proc_e}"; logger.exception(error_msg); return None, error_msg # 使用 logger.exception
        else:
            # 处理非 200 错误
            error_msg = f"OpenAI API 获取模型错误 (状态码: {response.status_code})"
            try: error_detail = response.json().get('error', {}).get('message', response.text)
            except: error_detail = response.text
            error_msg += f": {str(error_detail)[:500]}..."
            logger.error(error_msg) # 记录 API 错误
            if response.status_code in [401, 403]: error_msg += " (请检查 API Key 和 API Base URL 是否正确，以及网络/代理设置)"
            return None, error_msg

    # 处理网络和请求异常
    except requests.exceptions.ProxyError as proxy_e: proxy_url = proxies.get('http', 'N/A') if proxies else 'N/A'; error_msg = f"OpenAI API 获取模型代理错误: 无法连接到代理 {proxy_url}. 错误: {proxy_e}"; logger.error(error_msg); return None, error_msg
    except requests.exceptions.SSLError as ssl_e: error_msg = f"OpenAI API 获取模型 SSL 错误: {ssl_e}"; logger.error(error_msg); return None, error_msg
    except requests.exceptions.Timeout: error_msg = f"OpenAI API 获取模型网络错误: 请求超时 (超过 60 秒)。"; logger.error(error_msg); return None, error_msg
    except requests.exceptions.RequestException as req_e: error_msg = f"OpenAI API 获取模型网络/HTTP 错误: {req_e}"; logger.error(error_msg); return None, error_msg
    except Exception as e: error_msg = f"OpenAI API 获取模型时发生未预期的严重错误: {e}"; logger.exception(error_msg); return None, error_msg # 使用 logger.exception