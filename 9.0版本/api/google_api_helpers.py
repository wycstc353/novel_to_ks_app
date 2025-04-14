# api/google_api_helpers.py
import requests
import json
import traceback
import time

# 从 common_api_utils 导入代理获取函数
try:
    from .common_api_utils import _get_proxies
except ImportError as e:
    print(f"严重错误：无法从 .common_api_utils 导入 _get_proxies: {e}。代理功能可能受限。")
    def _get_proxies(proxy_config): print("警告：_get_proxies 未能从 .common_api_utils 加载，将不使用代理。"); return None

# --- Google Generative AI API 调用助手 ---

def _prepare_google_payload(prompt, temperature, max_output_tokens, top_p, top_k, safety_level="BLOCK_NONE"):
    """准备 Google API 请求的 payload (添加 topP, topK)"""
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    generation_config = {}
    if temperature is not None:
        try: temp_float = float(temperature); assert 0.0 <= temp_float <= 2.0; generation_config["temperature"] = temp_float
        except: print(f"警告: 无效的 temperature 值 '{temperature}'，将忽略。")
    if max_output_tokens is not None:
         try: max_tokens_int = int(max_output_tokens); assert max_tokens_int > 0; generation_config["maxOutputTokens"] = max_tokens_int
         except: print(f"警告: 无效的 maxOutputTokens 值 '{max_output_tokens}'，将忽略。")
    if top_p is not None:
        try: top_p_float = float(top_p); assert 0.0 <= top_p_float <= 1.0; generation_config["topP"] = top_p_float
        except: print(f"警告: 无效的 topP 值 '{top_p}'，将忽略。")
    if top_k is not None:
        try: top_k_int = int(top_k); assert top_k_int >= 1; generation_config["topK"] = top_k_int
        except: print(f"警告: 无效的 topK 值 '{top_k}'，将忽略。")
    if generation_config: payload["generationConfig"] = generation_config
    safety_settings = [ {"category": c, "threshold": safety_level} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
    payload["safetySettings"] = safety_settings
    return payload

def _handle_google_error_response(response, prompt_type):
    """处理 Google API 返回的错误响应"""
    status_code = response.status_code; error_msg = f"Google API 错误 ({prompt_type}, Status: {status_code})"
    try:
        error_json = response.json(); error_details = error_json.get('error', {})
        message = error_details.get('message', '')
        if fb := error_json.get('promptFeedback'):
            if reason := fb.get('blockReason'):
                ratings = fb.get('safetyRatings', []); details = "; ".join([f"{r.get('category','N/A').replace('HARM_CATEGORY_','')}:{r.get('probability','N/A')}" for r in ratings])
                message = f"Prompt 被阻止. 原因: {reason}. 详情: {details}"
        if not message: message = response.text
        error_msg += f": {message}"
    except json.JSONDecodeError: error_msg += f": 无法解析错误响应: {response.text[:500]}..."
    except Exception as e: error_msg += f": 处理错误响应时发生意外错误: {e}. 原始响应: {response.text[:500]}..."
    print(error_msg); return None, error_msg

def call_google_non_stream(api_key, api_base_url, model_name, prompt, temperature, max_output_tokens, top_p, top_k, prompt_type="Generic", proxy_config=None):
    """调用 Google GenAI 非流式 API"""
    if not api_key or not api_base_url or not model_name: return None, f"错误 ({prompt_type}): API Key, Base URL 或 Model Name 不能为空。"
    clean_base_url = api_base_url.rstrip('/')
    non_stream_endpoint = f"{clean_base_url}/v1beta/models/{model_name}:generateContent?key={api_key}"
    payload = _prepare_google_payload(prompt, temperature, max_output_tokens, top_p, top_k)
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    proxies = _get_proxies(proxy_config); response = None
    try:
        print(f"[Google API] 调用非流式 ({prompt_type}): {non_stream_endpoint.split('?')[0]}?key=HIDDEN")
        response = requests.post(non_stream_endpoint, headers=headers, json=payload, timeout=600, proxies=proxies)
        print(f"[Google API] 响应状态码: {response.status_code}")
        if response.status_code != 200: return _handle_google_error_response(response, prompt_type)
        try:
            response_json = response.json()
            if fb := response_json.get('promptFeedback'):
                if reason := fb.get('blockReason'):
                    ratings = fb.get('safetyRatings', []); details = "; ".join([f"{r.get('category','N/A').replace('HARM_CATEGORY_','')}:{r.get('probability','N/A')}" for r in ratings])
                    error_msg = f"Google API 错误 ({prompt_type}): Prompt 被阻止. 原因: {reason}. 详情: {details}"; print(error_msg); return None, error_msg
            if candidates := response_json.get('candidates'):
                 if candidates:
                      candidate = candidates[0]; finish_reason = candidate.get('finishReason')
                      if finish_reason and finish_reason not in ['STOP', 'MAX_TOKENS']:
                          ratings = candidate.get('safetyRatings', []); details = "; ".join([f"{r.get('category','N/A').replace('HARM_CATEGORY_','')}:{r.get('probability','N/A')}" for r in ratings])
                          warning_msg = f"Google API 警告/错误 ({prompt_type}): 生成中止. 原因: {finish_reason}. 详情: {details}"; print(warning_msg)
                          if finish_reason == 'SAFETY': return None, warning_msg
                      if content := candidate.get('content'):
                          if parts := content.get('parts'):
                              full_text = "".join(p.get('text', '') for p in parts); print(f"[Google API] 非流式调用成功 ({prompt_type}).")
                              if finish_reason == 'MAX_TOKENS': print(f"警告 ({prompt_type})：输出可能因达到 Max Tokens 而被截断。")
                              return full_text, None
                          else: error_msg = f"Google API 错误 ({prompt_type}): 响应的 candidate content 中缺少 'parts'。"
                      else: error_msg = f"Google API 错误 ({prompt_type}): 响应的 candidate 中缺少 'content'。"
                 else: error_msg = f"Google API 错误 ({prompt_type}): 响应中 'candidates' 列表为空。"
            elif 'promptFeedback' not in response_json: error_msg = f"Google API 错误 ({prompt_type}): 响应格式无效，缺少 'candidates' 和 'promptFeedback'。"
            else: error_msg = f"Google API 警告 ({prompt_type}): Prompt feedback 指示可能存在问题，但未返回任何候选结果。"
            print(f"错误: {error_msg} Response: {response.text[:500]}..."); return None, error_msg
        except json.JSONDecodeError as json_e: error_msg = f"Google API 错误 ({prompt_type}): 解析成功响应 JSON 失败: {json_e}. Status: {response.status_code}. Response: {response.text[:500]}..."; print(error_msg); return None, error_msg
        except Exception as proc_e: error_msg = f"Google API 错误 ({prompt_type}): 处理成功响应时出错: {proc_e}"; print(f"错误: {error_msg}"); traceback.print_exc(); return None, error_msg
    except requests.exceptions.ProxyError as proxy_e: proxy_url = proxies.get('http', 'N/A') if proxies else 'N/A'; error_msg = f"Google API 代理错误 ({prompt_type}): 无法连接到代理服务器 {proxy_url}. 错误: {proxy_e}"; print(error_msg); return None, error_msg
    except requests.exceptions.SSLError as ssl_e: error_msg = f"Google API SSL 错误 ({prompt_type}): 建立安全连接失败. 错误: {ssl_e}"; print(error_msg); return None, error_msg
    except requests.exceptions.Timeout: error_msg = f"Google API 网络错误 ({prompt_type}): 请求超时 (超过 600 秒)。"; print(error_msg); return None, error_msg
    except requests.exceptions.RequestException as req_e:
        error_detail = str(req_e); status_code_info = f"Status: {response.status_code}" if response else "无响应"
        error_msg = f"Google API 网络/HTTP 错误 ({prompt_type}, {status_code_info}): {error_detail}"
        print(error_msg)
        if response and response.text:
            print(f"原始响应 (部分): {response.text[:500]}...")
        return None, error_msg
    except Exception as e: error_msg = f"Google API 调用时发生未预期的严重错误 ({prompt_type}): {e}"; print(error_msg); traceback.print_exc(); return None, error_msg

def stream_google_response(api_key, api_base_url, model_name, prompt, temperature, max_output_tokens, top_p, top_k, prompt_type="Generic", proxy_config=None):
    """调用 Google GenAI 流式 API"""
    if not api_key or not api_base_url or not model_name: yield "error", f"错误 ({prompt_type}): API Key, Base URL 或 Model Name 不能为空。"; return
    clean_base_url = api_base_url.rstrip('/')
    streaming_endpoint = f"{clean_base_url}/v1beta/models/{model_name}:streamGenerateContent?key={api_key}&alt=sse"
    payload = _prepare_google_payload(prompt, temperature, max_output_tokens, top_p, top_k)
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    proxies = _get_proxies(proxy_config); response = None
    try:
        print(f"[Google API Stream] 连接流 ({prompt_type}): {streaming_endpoint.split('?')[0]}?key=HIDDEN&alt=sse")
        response = requests.post(streaming_endpoint, headers=headers, json=payload, stream=True, timeout=600, proxies=proxies)
        print(f"[Google API Stream] 响应状态码: {response.status_code}")
        if response.status_code != 200: _, error_message = _handle_google_error_response(response, f"{prompt_type} Stream Connect"); yield "error", error_message; return
        content_type = response.headers.get('Content-Type', '')
        if 'text/event-stream' not in content_type:
             body = ""; error_message = f"Google API 流错误 ({prompt_type}): API 返回无效的 Content-Type: '{content_type}'."
             try: body = response.json().get('error',{}).get('message', response.text)
             except: body=response.text[:200]+"..."
             error_message += f" Body: {body}"; print(error_message); yield "error", error_message; return

        current_data = ""; print(f"[Google API Stream] 开始接收事件流 ({prompt_type})...")
        for line_bytes in response.iter_lines():
            if not line_bytes:
                if current_data:
                    try:
                        parsed_json = json.loads(current_data)
                        if isinstance(parsed_json, dict):
                            if err := parsed_json.get('error'): msg = err.get('message', '未知的 API 错误'); print(f"Google API 流错误 ({prompt_type}): {msg}"); yield "error", f"API 错误: {msg}"; return
                            elif fb := parsed_json.get('promptFeedback'):
                                if reason := fb.get('blockReason'): ratings = fb.get('safetyRatings', []); details = "; ".join([f"{r.get('category','N/A').replace('HARM_CATEGORY_','')}:{r.get('probability','N/A')}" for r in ratings]); block_msg = f"Prompt 被阻止 ({prompt_type}). 原因: {reason}. 详情: {details}"; print(block_msg); yield "error", block_msg; return
                            elif candidates := parsed_json.get('candidates'):
                                if candidates:
                                    candidate = candidates[0]; text_chunk = ""
                                    if content := candidate.get('content'):
                                        if parts := content.get('parts'): text_chunk = "".join(p.get('text', '') for p in parts)
                                    if text_chunk: yield "chunk", text_chunk
                                    if finish_reason := candidate.get('finishReason'):
                                        if finish_reason != 'STOP':
                                            ratings = candidate.get('safetyRatings', []); details = "; ".join([f"{r.get('category','N/A').replace('HARM_CATEGORY_','')}:{r.get('probability','N/A')}" for r in ratings]); finish_msg = f"生成中止 ({prompt_type}). 原因: {finish_reason}. 详情: {details}"; print(f"警告: {finish_msg}"); yield "warning", finish_msg
                                            if finish_reason == 'SAFETY': yield "error", finish_msg; return
                                        elif finish_reason == 'MAX_TOKENS': yield "warning", f"输出可能因达到 Max Tokens ({max_output_tokens}) 而被截断。"
                            else: print(f"警告 ({prompt_type}): 收到未知结构的 JSON 数据: {current_data[:200]}...")
                    except json.JSONDecodeError as json_e: print(f"错误 ({prompt_type}): 解析 SSE 数据块 JSON 失败: {json_e} - 数据: '{current_data[:200]}...'"); yield "error", f"收到无效的 JSON 数据: {current_data[:100]}..."; return
                    finally: current_data = ""
                continue
            try:
                line = line_bytes.decode('utf-8')
                if line.startswith('data:'): current_data += line[len('data:'):].strip()
            except UnicodeDecodeError: print(f"警告 ({prompt_type}): 解码 SSE 行时出错，已跳过。原始字节: {line_bytes}"); continue
        print(f"Google API 事件流处理完成 ({prompt_type})."); yield "done", f"{prompt_type} 处理完成。"
    except requests.exceptions.ProxyError as proxy_e: proxy_url = proxies.get('http', 'N/A') if proxies else 'N/A'; error_msg = f"Google API 流代理错误 ({prompt_type}): 无法连接到代理 {proxy_url}. 错误: {proxy_e}"; print(error_msg); yield "error", error_msg
    except requests.exceptions.SSLError as ssl_e: error_msg = f"Google API 流 SSL 错误 ({prompt_type}): {ssl_e}"; print(error_msg); yield "error", error_msg
    except requests.exceptions.RequestException as req_e: error_msg = f"Google API 流网络/HTTP 错误 ({prompt_type}): {req_e}"; print(error_msg); yield "error", error_msg
    except Exception as e: error_msg = f"处理 Google API 流时发生未预期的严重错误 ({prompt_type}): {e}"; print(error_msg); traceback.print_exc(); yield "error", error_msg
    finally:
        # --- 修正 finally 块的缩进 ---
        print(f"Google API 流生成器退出 ({prompt_type}).")
        if response:
            try:
                response.close()
                print(f"已关闭 Google API 响应流 ({prompt_type}).")
            except Exception as close_e:
                print(f"关闭 Google API 响应流时出错 ({prompt_type}): {close_e}")
        # --- 修正结束 ---