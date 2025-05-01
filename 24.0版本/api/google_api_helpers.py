# api/google_api_helpers.py
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

# 从同级目录导入通用代理获取函数
try:
    from .common_api_utils import _get_proxies
except ImportError as e:
    # 记录严重错误，因为代理功能会受限
    logger.critical(f"严重错误：无法从 .common_api_utils 导入 _get_proxies: {e}。代理功能可能受限。", exc_info=True)
    def _get_proxies(proxy_config):
        logger.warning("警告：_get_proxies 未能从 .common_api_utils 加载，将不使用代理。")
        return None

# --- Google Generative AI API 调用助手 ---

# 调试日志基础目录
DEBUG_LOG_DIR = Path("debug_logs") / "api_requests"
# Google API 默认基础 URL
GOOGLE_API_BASE = "https://generativelanguage.googleapis.com"

def _prepare_google_payload(prompt, temperature, max_output_tokens, top_p, top_k, safety_level="BLOCK_NONE"):
    """准备 Google API 请求的 payload (添加 topP, topK 和安全设置)"""
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    generation_config = {}
    # 安全地处理和验证生成参数
    if temperature is not None:
        try: temp_float = float(temperature); assert 0.0 <= temp_float <= 2.0; generation_config["temperature"] = temp_float
        except: logger.warning(f"警告: 无效的 temperature 值 '{temperature}'，将忽略。") # 记录无效值警告
    if max_output_tokens is not None:
         try: max_tokens_int = int(max_output_tokens); assert max_tokens_int > 0; generation_config["maxOutputTokens"] = max_tokens_int
         except: logger.warning(f"警告: 无效的 maxOutputTokens 值 '{max_output_tokens}'，将忽略。") # 记录无效值警告
    if top_p is not None:
        try: top_p_float = float(top_p); assert 0.0 <= top_p_float <= 1.0; generation_config["topP"] = top_p_float
        except: logger.warning(f"警告: 无效的 topP 值 '{top_p}'，将忽略。") # 记录无效值警告
    if top_k is not None:
        try: top_k_int = int(top_k); assert top_k_int >= 1; generation_config["topK"] = top_k_int
        except: logger.warning(f"警告: 无效的 topK 值 '{top_k}'，将忽略。") # 记录无效值警告
    if generation_config: payload["generationConfig"] = generation_config
    # 设置安全等级
    safety_settings = [ {"category": c, "threshold": safety_level} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
    payload["safetySettings"] = safety_settings
    return payload

def _handle_google_error_response(response, prompt_type):
    """处理 Google API 返回的错误响应"""
    status_code = response.status_code; error_msg = f"Google API 错误 ({prompt_type}, Status: {status_code})"
    try:
        error_json = response.json(); error_details = error_json.get('error', {})
        message = error_details.get('message', '')
        # 检查是否有 promptFeedback 导致的阻塞
        if fb := error_json.get('promptFeedback'):
            if reason := fb.get('blockReason'):
                ratings = fb.get('safetyRatings', []); details = "; ".join([f"{r.get('category','N/A').replace('HARM_CATEGORY_','')}:{r.get('probability','N/A')}" for r in ratings])
                message = f"Prompt 被阻止. 原因: {reason}. 详情: {details}"
        if not message: message = response.text # 如果没有具体错误消息，使用原始文本
        error_msg += f": {message}"
    except json.JSONDecodeError: error_msg += f": 无法解析错误响应: {response.text[:500]}..."
    except Exception as e: error_msg += f": 处理错误响应时发生意外错误: {e}. 原始响应: {response.text[:500]}..."
    logger.error(error_msg) # 记录错误日志
    return None, error_msg

def _save_debug_input(api_type, payload, prompt_type):
    """保存调试输入文件 (移除敏感信息)"""
    try:
        debug_save_dir = DEBUG_LOG_DIR / api_type.lower(); debug_save_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_identifier = re.sub(r'[\\/*?:"<>|\s\.]+', '_', prompt_type or "payload")
        filename = f"{timestamp}_{safe_identifier}.json"
        filepath = debug_save_dir / filename

        # 复制 payload 并移除敏感信息
        payload_to_save = copy.deepcopy(payload)
        # 对于 Google，暂时没有直接在 payload 中传递 API Key

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(payload_to_save, f, ensure_ascii=False, indent=4)
        # 使用 logger 记录保存信息
        logger.info(f"  [Debug Save] {api_type.upper()} 请求已保存到: {filepath}")
    except Exception as save_e:
        # 使用 logger 记录保存错误
        logger.error(f"错误：保存 {api_type.upper()} 请求调试文件时出错: {save_e}", exc_info=True)

def call_google_non_stream(api_key, api_base_url, model_name, prompt, temperature, max_output_tokens, top_p, top_k, prompt_type="Generic", proxy_config=None, save_debug=False):
    """调用 Google GenAI 非流式 API"""
    # 输入校验
    if not api_key or not api_base_url or not model_name:
        err_msg = f"错误 ({prompt_type}): API Key, Base URL 或 Model Name 不能为空。"
        logger.error(err_msg) # 记录错误
        return None, err_msg
    clean_base_url = api_base_url.rstrip('/')
    non_stream_endpoint = f"{clean_base_url}/v1beta/models/{model_name}:generateContent?key={api_key}"
    payload = _prepare_google_payload(prompt, temperature, max_output_tokens, top_p, top_k)
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    proxies = _get_proxies(proxy_config); response = None

    # 保存调试输入 (如果启用)
    if save_debug:
        _save_debug_input("google", payload, prompt_type)

    try:
        # 记录 API 调用信息 (隐藏 Key)
        logger.info(f"[Google API] 调用非流式 ({prompt_type}): {non_stream_endpoint.split('?')[0]}?key=HIDDEN")
        response = requests.post(non_stream_endpoint, headers=headers, json=payload, timeout=600, proxies=proxies)
        # 记录响应状态码
        logger.info(f"[Google API] 响应状态码: {response.status_code}")
        if response.status_code != 200:
            # 处理非 200 响应
            return _handle_google_error_response(response, prompt_type)
        # 处理成功响应
        try:
            response_json = response.json()
            # 检查 promptFeedback
            if fb := response_json.get('promptFeedback'):
                if reason := fb.get('blockReason'):
                    ratings = fb.get('safetyRatings', []); details = "; ".join([f"{r.get('category','N/A').replace('HARM_CATEGORY_','')}:{r.get('probability','N/A')}" for r in ratings])
                    error_msg = f"Google API 错误 ({prompt_type}): Prompt 被阻止. 原因: {reason}. 详情: {details}"; logger.error(error_msg); return None, error_msg
            # 检查 candidates
            if candidates := response_json.get('candidates'):
                 if candidates:
                      candidate = candidates[0]; finish_reason = candidate.get('finishReason')
                      # 检查非正常终止原因
                      if finish_reason and finish_reason not in ['STOP', 'MAX_TOKENS']:
                          ratings = candidate.get('safetyRatings', []); details = "; ".join([f"{r.get('category','N/A').replace('HARM_CATEGORY_','')}:{r.get('probability','N/A')}" for r in ratings])
                          warning_msg = f"Google API 警告/错误 ({prompt_type}): 生成中止. 原因: {finish_reason}. 详情: {details}"; logger.warning(warning_msg) # 记录警告
                          # 如果是安全原因，视为错误返回
                          if finish_reason == 'SAFETY': return None, warning_msg
                      # 提取内容
                      if content := candidate.get('content'):
                          if parts := content.get('parts'):
                              full_text = "".join(p.get('text', '') for p in parts); logger.info(f"[Google API] 非流式调用成功 ({prompt_type}).") # 记录成功
                              if finish_reason == 'MAX_TOKENS': logger.warning(f"警告 ({prompt_type})：输出可能因达到 Max Tokens 而被截断。") # 记录截断警告
                              return full_text, None
                          else: error_msg = f"Google API 错误 ({prompt_type}): 响应的 candidate content 中缺少 'parts'。"
                      else: error_msg = f"Google API 错误 ({prompt_type}): 响应的 candidate 中缺少 'content'。"
                 else: error_msg = f"Google API 错误 ({prompt_type}): 响应中 'candidates' 列表为空。"
            # 如果既没有 candidates 也没有 promptFeedback (阻塞)，则响应格式无效
            elif 'promptFeedback' not in response_json: error_msg = f"Google API 错误 ({prompt_type}): 响应格式无效，缺少 'candidates' 和 'promptFeedback'。"
            # 如果只有 promptFeedback 但未阻塞，也算异常
            else: error_msg = f"Google API 警告 ({prompt_type}): Prompt feedback 指示可能存在问题，但未返回任何候选结果。"
            logger.error(f"错误: {error_msg} Response: {response.text[:500]}...") # 记录错误
            return None, error_msg
        except json.JSONDecodeError as json_e: error_msg = f"Google API 错误 ({prompt_type}): 解析成功响应 JSON 失败: {json_e}. Status: {response.status_code}. Response: {response.text[:500]}..."; logger.error(error_msg); return None, error_msg
        except Exception as proc_e: error_msg = f"Google API 错误 ({prompt_type}): 处理成功响应时出错: {proc_e}"; logger.exception(error_msg); return None, error_msg # 使用 logger.exception 记录错误和 traceback
    # 处理网络和请求异常
    except requests.exceptions.ProxyError as proxy_e: proxy_url = proxies.get('http', 'N/A') if proxies else 'N/A'; error_msg = f"Google API 代理错误 ({prompt_type}): 无法连接到代理服务器 {proxy_url}. 错误: {proxy_e}"; logger.error(error_msg); return None, error_msg
    except requests.exceptions.SSLError as ssl_e: error_msg = f"Google API SSL 错误 ({prompt_type}): 建立安全连接失败. 错误: {ssl_e}"; logger.error(error_msg); return None, error_msg
    except requests.exceptions.Timeout: error_msg = f"Google API 网络错误 ({prompt_type}): 请求超时 (超过 600 秒)。"; logger.error(error_msg); return None, error_msg
    except requests.exceptions.RequestException as req_e:
        error_detail = str(req_e); status_code_info = f"Status: {response.status_code}" if response else "无响应"
        error_msg = f"Google API 网络/HTTP 错误 ({prompt_type}, {status_code_info}): {error_detail}"
        logger.error(error_msg) # 记录网络错误
        if response and response.text: logger.error(f"原始响应 (部分): {response.text[:500]}...") # 记录部分原始响应
        return None, error_msg
    except Exception as e: error_msg = f"Google API 调用时发生未预期的严重错误 ({prompt_type}): {e}"; logger.exception(error_msg); return None, error_msg # 使用 logger.exception

def stream_google_response(api_key, api_base_url, model_name, prompt, temperature, max_output_tokens, top_p, top_k, prompt_type="Generic", proxy_config=None, save_debug=False):
    """调用 Google GenAI 流式 API"""
    # 输入校验
    if not api_key or not api_base_url or not model_name:
        err_msg = f"错误 ({prompt_type}): API Key, Base URL 或 Model Name 不能为空。"
        logger.error(err_msg) # 记录错误
        yield "error", err_msg; return
    clean_base_url = api_base_url.rstrip('/')
    streaming_endpoint = f"{clean_base_url}/v1beta/models/{model_name}:streamGenerateContent?key={api_key}&alt=sse"
    payload = _prepare_google_payload(prompt, temperature, max_output_tokens, top_p, top_k)
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    proxies = _get_proxies(proxy_config); response = None

    # 保存调试输入 (如果启用)
    if save_debug:
        _save_debug_input("google", payload, f"{prompt_type}_stream")

    try:
        # 记录流式连接信息 (隐藏 Key)
        logger.info(f"[Google API Stream] 连接流 ({prompt_type}): {streaming_endpoint.split('?')[0]}?key=HIDDEN&alt=sse")
        response = requests.post(streaming_endpoint, headers=headers, json=payload, stream=True, timeout=600, proxies=proxies)
        # 记录响应状态码
        logger.info(f"[Google API Stream] 响应状态码: {response.status_code}")
        # 处理连接错误
        if response.status_code != 200:
            _, error_message = _handle_google_error_response(response, f"{prompt_type} Stream Connect"); yield "error", error_message; return
        # 检查 Content-Type
        content_type = response.headers.get('Content-Type', '')
        if 'text/event-stream' not in content_type:
             body = ""; error_message = f"Google API 流错误 ({prompt_type}): API 返回无效的 Content-Type: '{content_type}'."
             try: body = response.json().get('error',{}).get('message', response.text)
             except: body=response.text[:200]+"..."
             error_message += f" Body: {body}"; logger.error(error_message); yield "error", error_message; return

        # 处理事件流
        current_data = ""; logger.info(f"[Google API Stream] 开始接收事件流 ({prompt_type})...") # 记录流开始
        for line_bytes in response.iter_lines():
            if not line_bytes: # 空行表示一个事件结束
                if current_data:
                    try:
                        parsed_json = json.loads(current_data)
                        if isinstance(parsed_json, dict):
                            # 检查 API 错误
                            if err := parsed_json.get('error'): msg = err.get('message', '未知的 API 错误'); logger.error(f"Google API 流错误 ({prompt_type}): {msg}"); yield "error", f"API 错误: {msg}"; return
                            # 检查 Prompt Feedback 阻塞
                            elif fb := parsed_json.get('promptFeedback'):
                                if reason := fb.get('blockReason'): ratings = fb.get('safetyRatings', []); details = "; ".join([f"{r.get('category','N/A').replace('HARM_CATEGORY_','')}:{r.get('probability','N/A')}" for r in ratings]); block_msg = f"Prompt 被阻止 ({prompt_type}). 原因: {reason}. 详情: {details}"; logger.error(block_msg); yield "error", block_msg; return
                            # 处理正常的候选结果
                            elif candidates := parsed_json.get('candidates'):
                                if candidates:
                                    candidate = candidates[0]; text_chunk = ""
                                    # 提取文本块
                                    if content := candidate.get('content'):
                                        if parts := content.get('parts'): text_chunk = "".join(p.get('text', '') for p in parts)
                                    if text_chunk: yield "chunk", text_chunk # 返回数据块
                                    # 检查终止原因
                                    if finish_reason := candidate.get('finishReason'):
                                        if finish_reason != 'STOP':
                                            ratings = candidate.get('safetyRatings', []); details = "; ".join([f"{r.get('category','N/A').replace('HARM_CATEGORY_','')}:{r.get('probability','N/A')}" for r in ratings]); finish_msg = f"生成中止 ({prompt_type}). 原因: {finish_reason}. 详情: {details}"; logger.warning(f"警告: {finish_msg}"); yield "warning", finish_msg # 返回警告
                                            # 如果是安全原因，也发送 error 信号终止
                                            if finish_reason == 'SAFETY': yield "error", finish_msg; return
                                        elif finish_reason == 'MAX_TOKENS': yield "warning", f"输出可能因达到 Max Tokens ({max_output_tokens}) 而被截断。" # 返回截断警告
                            else: logger.warning(f"警告 ({prompt_type}): 收到未知结构的 JSON 数据: {current_data[:200]}...") # 记录未知结构警告
                    except json.JSONDecodeError as json_e: logger.error(f"错误 ({prompt_type}): 解析 SSE 数据块 JSON 失败: {json_e} - 数据: '{current_data[:200]}...'"); yield "error", f"收到无效的 JSON 数据: {current_data[:100]}..."; return # 返回解析错误
                    finally: current_data = "" # 重置当前事件数据
                continue # 处理下一个事件
            # 累积当前事件的数据行
            try:
                line = line_bytes.decode('utf-8')
                if line.startswith('data:'): current_data += line[len('data:'):].strip()
            except UnicodeDecodeError: logger.warning(f"警告 ({prompt_type}): 解码 SSE 行时出错，已跳过。原始字节: {line_bytes}"); continue # 记录解码错误
        # 循环正常结束
        logger.info(f"Google API 事件流处理完成 ({prompt_type})."); yield "done", f"{prompt_type} 处理完成。" # 返回完成信号
    # 处理网络和请求异常
    except requests.exceptions.ProxyError as proxy_e: proxy_url = proxies.get('http', 'N/A') if proxies else 'N/A'; error_msg = f"Google API 流代理错误 ({prompt_type}): 无法连接到代理 {proxy_url}. 错误: {proxy_e}"; logger.error(error_msg); yield "error", error_msg
    except requests.exceptions.SSLError as ssl_e: error_msg = f"Google API 流 SSL 错误 ({prompt_type}): {ssl_e}"; logger.error(error_msg); yield "error", error_msg
    except requests.exceptions.RequestException as req_e: error_msg = f"Google API 流网络/HTTP 错误 ({prompt_type}): {req_e}"; logger.error(error_msg); yield "error", error_msg
    except Exception as e: error_msg = f"处理 Google API 流时发生未预期的严重错误 ({prompt_type}): {e}"; logger.exception(error_msg); yield "error", error_msg # 使用 logger.exception
    finally:
        # 确保关闭响应流
        logger.info(f"Google API 流生成器退出 ({prompt_type}).") # 记录生成器退出
        if response:
            try: response.close(); logger.info(f"已关闭 Google API 响应流 ({prompt_type}).") # 记录流关闭
            except Exception as close_e: logger.warning(f"关闭 Google API 响应流时出错 ({prompt_type}): {close_e}") # 记录关闭错误

def get_google_models(api_key, api_base_url, proxy_config=None, save_debug=False):
    """
    调用 Google GenAI API 的 /models 端点获取可用模型列表。
    """
    # 输入校验
    if not api_key: err_msg = "错误 (Google Models): API Key 不能为空。"; logger.error(err_msg); return None, err_msg
    if not api_base_url: err_msg = "错误 (Google Models): API Base URL 不能为空。"; logger.error(err_msg); return None, err_msg

    endpoint = f"{api_base_url.rstrip('/')}/v1beta/models?key={api_key}"
    headers = {"Accept": "application/json"} # GET 请求通常只需要 Accept
    proxies = _get_proxies(proxy_config)
    response = None

    # 保存调试输入 (如果启用)
    if save_debug:
        debug_payload = {"request_type": "get_models", "url": endpoint.split('?')[0] + "?key=HIDDEN", "headers": headers}
        _save_debug_input("google", debug_payload, "GetModels")

    try:
        # 记录请求信息 (隐藏 Key)
        logger.info(f"[Google API] 获取模型列表: {endpoint.split('?')[0]}?key=HIDDEN")
        response = requests.get(endpoint, headers=headers, timeout=60, proxies=proxies) # 60秒超时
        # 记录响应状态码
        logger.info(f"[Google API] 获取模型响应状态码: {response.status_code}")

        if response.status_code == 200:
            try:
                response_json = response.json()
                # Google 格式是 {"models": [{"name": "models/xxx", ...}, ...]}
                if "models" in response_json and isinstance(response_json["models"], list):
                    model_ids = []
                    for item in response_json["models"]:
                        if name := item.get("name"):
                            if name.startswith("models/"):
                                model_ids.append(name.split('/')[-1]) # 提取 ID
                            else:
                                model_ids.append(name) # 如果格式不是 models/ 开头，直接使用
                    if model_ids:
                        logger.info(f"[Google API] 成功获取 {len(model_ids)} 个模型 ID。") # 记录成功获取
                        return sorted(model_ids), None # 返回排序后的模型 ID 列表
                    else:
                        error_msg = "Google API 错误: /models 响应成功，但 'models' 列表为空或不包含有效的模型名称。"
                else:
                    error_msg = "Google API 错误: /models 响应 JSON 结构无效 (缺少 'models' 列表)。"
                logger.error(f"{error_msg} Response: {response.text[:500]}...") # 记录错误
                return None, error_msg
            except json.JSONDecodeError as json_e:
                error_msg = f"Google API 错误: 解析 /models 响应 JSON 失败: {json_e}. Response: {response.text[:500]}..."
                logger.error(error_msg) # 记录 JSON 解析错误
                return None, error_msg
            except Exception as proc_e:
                error_msg = f"Google API 错误: 处理 /models 响应时出错: {proc_e}"
                logger.exception(error_msg) # 使用 logger.exception
                return None, error_msg
        else:
            # 处理非 200 错误
            _, error_message = _handle_google_error_response(response, "Get Models")
            # 特别处理 401/403，提示检查 Key 或 Base URL
            if response.status_code in [401, 403]:
                 error_message += " (请检查 API Key 和 API Base URL 是否正确，以及网络/代理设置)"
            return None, error_message

    # 处理网络和请求异常
    except requests.exceptions.ProxyError as proxy_e:
        proxy_url = proxies.get('http', 'N/A') if proxies else 'N/A'
        error_msg = f"Google API 获取模型代理错误: 无法连接到代理 {proxy_url}. 错误: {proxy_e}"
        logger.error(error_msg); return None, error_msg
    except requests.exceptions.SSLError as ssl_e:
        error_msg = f"Google API 获取模型 SSL 错误: {ssl_e}"
        logger.error(error_msg); return None, error_msg
    except requests.exceptions.Timeout:
        error_msg = f"Google API 获取模型网络错误: 请求超时 (超过 60 秒)。"
        logger.error(error_msg); return None, error_msg
    except requests.exceptions.RequestException as req_e:
        error_msg = f"Google API 获取模型网络/HTTP 错误: {req_e}"
        logger.error(error_msg); return None, error_msg
    except Exception as e:
        error_msg = f"Google API 获取模型时发生未预期的严重错误: {e}"
        logger.exception(error_msg); return None, error_msg # 使用 logger.exception