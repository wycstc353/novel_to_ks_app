# api_helpers.py
import requests
import json
import traceback
import base64
from pathlib import Path
import time # 用于添加延迟

# --- Google Generative AI API 调用助手 ---

def _prepare_google_payload(prompt, temperature, max_output_tokens, safety_level="BLOCK_NONE"):
    """
    准备 Google API 请求的 payload (内容、生成配置、安全设置)。

    Args:
        prompt (str): 输入的提示文本.
        temperature (float or None): 温度参数.
        max_output_tokens (int or None): 最大输出 Token 数.
        safety_level (str): 安全设置阈值 (如 "BLOCK_NONE", "BLOCK_ONLY_HIGH").

    Returns:
        dict: 构建好的请求体 payload 字典。
    """
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    # 配置生成参数
    generation_config = {}
    if temperature is not None:
        try:
            temp_float = float(temperature)
            # Google API 允许 0.0 到 2.0 (根据最新文档确认)
            if 0.0 <= temp_float <= 2.0:
                generation_config["temperature"] = temp_float
            else:
                print(f"警告: Temperature {temp_float} 超出 Google API 允许范围 [0.0, 2.0]，将忽略此参数。")
        except (ValueError, TypeError):
            print(f"警告: 无效的 temperature 值 '{temperature}'，将忽略此参数。")
    if max_output_tokens is not None:
         try:
             max_tokens_int = int(max_output_tokens)
             if max_tokens_int > 0:
                 generation_config["maxOutputTokens"] = max_tokens_int
             else:
                 print(f"警告: maxOutputTokens {max_tokens_int} 必须大于 0，将忽略此参数。")
         except (ValueError, TypeError):
             print(f"警告: 无效的 maxOutputTokens 值 '{max_output_tokens}'，将忽略此参数。")

    if generation_config:
        payload["generationConfig"] = generation_config

    # 配置安全设置 (常用的四类)
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": safety_level},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": safety_level},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": safety_level},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": safety_level},
    ]
    payload["safetySettings"] = safety_settings

    return payload

def _get_proxies(proxy_config):
    """
    根据传入的代理配置字典，返回适用于 requests 库的 proxies 字典。
    能自动识别 Google 和 NAI 的代理配置键。

    Args:
        proxy_config (dict or None): 包含代理设置的字典。
            Google: {"use_proxy": bool, "proxy_address": str, "proxy_port": str}
            NAI: {"nai_use_proxy": bool, "nai_proxy_address": str, "nai_proxy_port": str}

    Returns:
        dict or None: requests 库使用的 proxies 字典，或 None (如果不使用代理)。
    """
    proxies = None
    use_key = "use_proxy" # 默认 Google API 的 key
    addr_key = "proxy_address"
    port_key = "proxy_port"

    # 检查是否是 NAI 的代理配置键存在
    if proxy_config and "nai_use_proxy" in proxy_config:
        use_key = "nai_use_proxy"
        addr_key = "nai_proxy_address"
        port_key = "nai_proxy_port"
        api_name = "NAI"
    else:
        api_name = "Google"

    # 检查是否启用代理，并且地址和端口有效
    if proxy_config and proxy_config.get(use_key) and proxy_config.get(addr_key) and proxy_config.get(port_key):
        addr = proxy_config[addr_key]
        port = proxy_config[port_key]
        # 确保地址和端口不为空字符串
        if addr and port:
            # 构建代理 URL (假设是 HTTP 代理)
            # 注意：如果代理需要认证，格式会更复杂 (http://user:pass@host:port)
            url = f"http://{addr}:{port}"
            proxies = {"http": url, "https": url} # 同时为 http 和 https 设置代理
            print(f"[{api_name} API Helper] 使用代理: {url}")
        else:
            print(f"[{api_name} API Helper] 代理已启用但地址或端口为空，将不使用代理。")
    else:
        print(f"[{api_name} API Helper] 未配置或未启用代理。")
    return proxies

def _handle_google_error_response(response, prompt_type):
    """
    处理 Google API 返回的错误响应 (非 200 OK 或响应体中包含错误信息)。

    Args:
        response: requests 的响应对象。
        prompt_type (str): 用于日志记录的任务类型标识。

    Returns:
        tuple: (None, error_message: str) 总是返回 None 和错误消息字符串。
    """
    status_code = response.status_code
    error_msg = f"Google API 错误 ({prompt_type}, Status: {status_code})" # 基础错误信息

    try:
        # 尝试解析 JSON 格式的错误响应体
        error_json = response.json()
        error_details = error_json.get('error', {})
        message = error_details.get('message', '') # 获取 'message' 字段

        # 检查是否有更具体的 'promptFeedback' 中的阻止原因
        if 'promptFeedback' in error_json and error_json['promptFeedback'].get('blockReason'):
            reason = error_json['promptFeedback']['blockReason']
            ratings = error_json['promptFeedback'].get('safetyRatings', [])
            # 格式化安全评分详情
            details = "; ".join([
                f"{r.get('category','N/A').replace('HARM_CATEGORY_','')}:{r.get('probability','N/A')}"
                for r in ratings
            ])
            message = f"Prompt 被阻止. 原因: {reason}. 详情: {details}"
        elif not message: # 如果 'message' 字段为空或不存在
            message = response.text # 使用原始响应文本作为错误信息

        error_msg += f": {message}" # 将具体错误信息附加到基础信息后

    except json.JSONDecodeError:
        # 如果响应体不是有效的 JSON
        error_msg += f": 无法解析错误响应: {response.text[:500]}..." # 显示部分原始响应
    except Exception as e:
        # 处理解析过程中可能出现的其他异常
        error_msg += f": 处理错误响应时发生意外错误: {e}. 原始响应: {response.text[:500]}..."

    print(error_msg) # 打印最终的错误消息
    return None, error_msg # 返回 None 表示结果，和错误消息

def call_google_non_stream(api_key, api_base_url, model_name, prompt, temperature, max_output_tokens, prompt_type="Generic", proxy_config=None):
    """
    调用 Google GenAI 非流式 API (generateContent)。

    Args:
        api_key (str): Google API Key.
        api_base_url (str): API 端点基础 URL.
        model_name (str): 模型名称 (e.g., "gemini-1.5-flash-latest").
        prompt (str): 输入的提示文本.
        temperature (float or None): 温度参数.
        max_output_tokens (int or None): 最大输出 Token 数.
        prompt_type (str): 用于日志记录的任务类型标识.
        proxy_config (dict or None): 代理配置字典.

    Returns:
        tuple: (result_text: str or None, error_message: str or None)
               成功时 result_text 是生成的文本，error_message 为 None。
               失败时 result_text 为 None，error_message 包含错误信息。
    """
    # --- 输入校验 ---
    if not api_key or not api_base_url or not model_name:
        return None, f"错误 ({prompt_type}): API Key, Base URL 或 Model Name 不能为空。"

    # --- 准备请求 ---
    clean_base_url = api_base_url.rstrip('/')
    # 构建非流式 API 端点 URL
    non_stream_endpoint = f"{clean_base_url}/v1beta/models/{model_name}:generateContent?key={api_key}"
    # 准备请求体 payload (使用辅助函数)
    payload = _prepare_google_payload(prompt, temperature, max_output_tokens)
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    # 获取代理设置 (使用辅助函数)
    proxies = _get_proxies(proxy_config)
    response = None # 初始化响应变量

    # --- 发送请求并处理响应 ---
    try:
        print(f"[Google API] 调用非流式 ({prompt_type}): {non_stream_endpoint.split('?')[0]}?key=HIDDEN")
        # 发送 POST 请求，设置超时时间 (例如 600 秒 = 10 分钟)
        response = requests.post(non_stream_endpoint, headers=headers, json=payload, timeout=600, proxies=proxies)
        print(f"[Google API] 响应状态码: {response.status_code}")

        # 检查 HTTP 状态码
        if response.status_code != 200:
            # 如果状态码不是 200 OK，调用错误处理函数
            return _handle_google_error_response(response, prompt_type)

        # --- 解析成功的响应 (200 OK) ---
        try:
            response_json = response.json()

            # 1. 检查 Prompt Feedback 是否有阻止信息
            if fb := response_json.get('promptFeedback'):
                if reason := fb.get('blockReason'):
                    ratings = fb.get('safetyRatings', [])
                    details = "; ".join([f"{r.get('category','N/A').replace('HARM_CATEGORY_','')}:{r.get('probability','N/A')}" for r in ratings])
                    error_msg = f"Google API 错误 ({prompt_type}): Prompt 被阻止. 原因: {reason}. 详情: {details}"
                    print(error_msg)
                    return None, error_msg # Prompt 被阻止，返回错误

            # 2. 检查 Candidates (候选结果)
            if candidates := response_json.get('candidates'):
                 if candidates: # 确保 candidates 列表不为空
                      candidate = candidates[0] # 通常只关心第一个候选结果
                      finish_reason = candidate.get('finishReason')

                      # 检查生成中止原因
                      if finish_reason and finish_reason not in ['STOP', 'MAX_TOKENS']:
                          ratings = candidate.get('safetyRatings', [])
                          details = "; ".join([f"{r.get('category','N/A').replace('HARM_CATEGORY_','')}:{r.get('probability','N/A')}" for r in ratings])
                          warning_msg = f"Google API 警告/错误 ({prompt_type}): 生成中止. 原因: {finish_reason}. 详情: {details}"
                          print(warning_msg)
                          # 如果是因为安全原因中止，视为错误返回
                          if finish_reason == 'SAFETY':
                              return None, warning_msg

                      # 提取生成的文本内容
                      if content := candidate.get('content'):
                          if parts := content.get('parts'):
                              # 拼接所有 part 的文本
                              full_text = "".join(p.get('text', '') for p in parts)
                              print(f"[Google API] 非流式调用成功 ({prompt_type}).")
                              # 如果是因为达到 Max Tokens 而停止，打印警告
                              if finish_reason == 'MAX_TOKENS':
                                  print(f"警告 ({prompt_type})：输出可能因达到 Max Tokens 而被截断。")
                              return full_text, None # 成功获取文本，返回结果
                          else:
                              error_msg = f"Google API 错误 ({prompt_type}): 响应的 candidate content 中缺少 'parts'。"
                      else:
                          error_msg = f"Google API 错误 ({prompt_type}): 响应的 candidate 中缺少 'content'。"
                 else:
                     # candidates 列表为空
                     error_msg = f"Google API 错误 ({prompt_type}): 响应中 'candidates' 列表为空。"
            # 3. 如果既没有 candidates 也没有 promptFeedback (异常情况)
            elif 'promptFeedback' not in response_json:
                 error_msg = f"Google API 错误 ({prompt_type}): 响应格式无效，缺少 'candidates' 和 'promptFeedback'。"
            # 4. 只有 promptFeedback 没有 candidates
            else:
                 error_msg = f"Google API 警告 ({prompt_type}): Prompt feedback 指示可能存在问题，但未返回任何候选结果。"

            # 如果执行到这里，说明未能成功提取文本
            print(f"错误: {error_msg} Response: {response.text[:500]}...")
            return None, error_msg

        except json.JSONDecodeError as json_e:
            # 解析成功响应的 JSON 时出错
            error_msg = f"Google API 错误 ({prompt_type}): 解析成功响应 JSON 失败: {json_e}. Status: {response.status_code}. Response: {response.text[:500]}..."
            print(error_msg)
            return None, error_msg
        except Exception as proc_e:
            # 处理成功响应时发生其他错误
            error_msg = f"Google API 错误 ({prompt_type}): 处理成功响应时出错: {proc_e}"
            print(f"错误: {error_msg}")
            traceback.print_exc()
            return None, error_msg

    # --- 处理网络层面的异常 ---
    except requests.exceptions.ProxyError as proxy_e:
        proxy_url = proxies.get('http', 'N/A') if proxies else 'N/A'
        error_msg = f"Google API 代理错误 ({prompt_type}): 无法连接到代理服务器 {proxy_url}. 错误: {proxy_e}"
        print(error_msg)
        return None, error_msg
    except requests.exceptions.SSLError as ssl_e:
        error_msg = f"Google API SSL 错误 ({prompt_type}): 建立安全连接失败. 错误: {ssl_e}"
        print(error_msg)
        return None, error_msg
    except requests.exceptions.Timeout:
        error_msg = f"Google API 网络错误 ({prompt_type}): 请求超时 (超过 600 秒)。"
        print(error_msg)
        return None, error_msg
    except requests.exceptions.RequestException as req_e:
        # 处理其他 requests 库可能抛出的异常 (如连接错误、DNS错误等)
        error_detail = str(req_e)
        status_code_info = f"Status: {response.status_code}" if response else "无响应"
        error_msg = f"Google API 网络/HTTP 错误 ({prompt_type}, {status_code_info}): {error_detail}"
        print(error_msg)
        if response and response.text: print(f"原始响应 (部分): {response.text[:500]}...")
        return None, error_msg
    except Exception as e:
        # 捕获其他所有意外错误
        error_msg = f"Google API 调用时发生未预期的严重错误 ({prompt_type}): {e}"
        print(error_msg)
        traceback.print_exc()
        return None, error_msg


def stream_google_response(api_key, api_base_url, model_name, prompt, temperature, max_output_tokens, prompt_type="Generic", proxy_config=None):
    """
    调用 Google GenAI 流式 API (streamGenerateContent)，并产生事件。

    Yields:
        tuple: (status: str, data: str or dict)
               status 可以是 "chunk" (文本块), "error" (错误信息),
               "warning" (警告信息), "done" (完成消息)。
               data 包含对应状态的数据。
    """
    # --- 输入校验 ---
    if not api_key or not api_base_url or not model_name:
        yield "error", f"错误 ({prompt_type}): API Key, Base URL 或 Model Name 不能为空。"
        return

    # --- 准备请求 ---
    clean_base_url = api_base_url.rstrip('/')
    # 构建流式 API 端点 URL (包含 alt=sse 参数，表示 Server-Sent Events)
    streaming_endpoint = f"{clean_base_url}/v1beta/models/{model_name}:streamGenerateContent?key={api_key}&alt=sse"
    # 准备请求体 payload
    payload = _prepare_google_payload(prompt, temperature, max_output_tokens)
    # 流式请求需要特定的 Accept header
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    # 获取代理设置
    proxies = _get_proxies(proxy_config)
    response = None # 初始化响应变量

    # --- 发送请求并处理流式响应 ---
    try:
        print(f"[Google API Stream] 连接流 ({prompt_type}): {streaming_endpoint.split('?')[0]}?key=HIDDEN&alt=sse")
        # 发送 POST 请求，启用 stream=True，设置超时
        response = requests.post(streaming_endpoint, headers=headers, json=payload, stream=True, timeout=600, proxies=proxies)
        print(f"[Google API Stream] 响应状态码: {response.status_code}")

        # 检查 HTTP 状态码
        if response.status_code != 200:
            # 如果连接时就返回错误状态码，处理错误并终止
            _, error_message = _handle_google_error_response(response, f"{prompt_type} Stream Connect")
            yield "error", error_message
            return

        # 检查 Content-Type 是否为 SSE
        content_type = response.headers.get('Content-Type', '')
        if 'text/event-stream' not in content_type:
             # 如果 Content-Type 不对，尝试读取错误信息并终止
             body = ""
             error_message = f"Google API 流错误 ({prompt_type}): API 返回无效的 Content-Type: '{content_type}'."
             try:
                 body = response.json().get('error',{}).get('message', response.text)
             except:
                 body=response.text[:200]+"..."
             error_message += f" Body: {body}"
             print(error_message)
             yield "error", error_message
             return

        # --- 处理 SSE 事件流 ---
        current_data = "" # 用于累积一个事件的 data: 行内容
        print(f"[Google API Stream] 开始接收事件流 ({prompt_type})...")
        # 使用 iter_lines() 迭代响应内容 (按行读取)
        for line_bytes in response.iter_lines():
            # SSE 事件以空行分隔
            if not line_bytes:
                # 遇到空行，表示一个事件结束
                if current_data:
                    # 如果累积了数据，尝试解析这个事件
                    try:
                        # print(f"  [Stream Debug] Received data block: {current_data}") # 调试日志
                        parsed_json = json.loads(current_data) # 解析 JSON

                        # 检查解析后的 JSON 是否为字典
                        if isinstance(parsed_json, dict):
                            # --- 检查错误 ---
                            if err := parsed_json.get('error'):
                                msg = err.get('message', '未知的 API 错误')
                                print(f"Google API 流错误 ({prompt_type}): {msg}")
                                yield "error", f"API 错误: {msg}"
                                return # 发生错误，停止处理

                            # --- 检查 Prompt Feedback ---
                            elif fb := parsed_json.get('promptFeedback'):
                                if reason := fb.get('blockReason'):
                                    ratings = fb.get('safetyRatings', [])
                                    details = "; ".join([f"{r.get('category','N/A').replace('HARM_CATEGORY_','')}:{r.get('probability','N/A')}" for r in ratings])
                                    block_msg = f"Prompt 被阻止 ({prompt_type}). 原因: {reason}. 详情: {details}"
                                    print(block_msg)
                                    yield "error", block_msg
                                    return # Prompt 被阻止，停止处理

                            # --- 检查 Candidates ---
                            elif candidates := parsed_json.get('candidates'):
                                if candidates:
                                    candidate = candidates[0]
                                    text_chunk = ""
                                    # 提取文本块
                                    if content := candidate.get('content'):
                                        if parts := content.get('parts'):
                                            text_chunk = "".join(p.get('text', '') for p in parts)

                                    # 如果有文本块，产生 "chunk" 事件
                                    if text_chunk:
                                        yield "chunk", text_chunk

                                    # 检查生成中止原因
                                    if finish_reason := candidate.get('finishReason'):
                                        # 如果不是正常停止 (STOP)
                                        if finish_reason != 'STOP':
                                            ratings = candidate.get('safetyRatings', [])
                                            details = "; ".join([f"{r.get('category','N/A').replace('HARM_CATEGORY_','')}:{r.get('probability','N/A')}" for r in ratings])
                                            finish_msg = f"生成中止 ({prompt_type}). 原因: {finish_reason}. 详情: {details}"
                                            print(f"警告: {finish_msg}")
                                            # 产生 "warning" 事件
                                            yield "warning", finish_msg
                                            # 如果是安全原因中止，也产生 "error" 事件并停止
                                            if finish_reason == 'SAFETY':
                                                yield "error", finish_msg
                                                return # 安全中止，停止处理
                                        # 如果是 MAX_TOKENS，也视为一种警告/提示
                                        elif finish_reason == 'MAX_TOKENS':
                                             yield "warning", f"输出可能因达到 Max Tokens ({max_output_tokens}) 而被截断。"
                                        # 如果是 STOP，表示正常结束，不需要额外处理，等待流结束即可

                            # --- 未知结构 ---
                            else:
                                print(f"警告 ({prompt_type}): 收到未知结构的 JSON 数据: {current_data[:200]}...")
                                # yield "warning", f"收到未知 JSON 结构: {current_data[:100]}..."

                    except json.JSONDecodeError as json_e:
                        # 解析当前事件的 JSON 失败
                        print(f"错误 ({prompt_type}): 解析 SSE 数据块 JSON 失败: {json_e} - 数据: '{current_data[:200]}...'")
                        yield "error", f"收到无效的 JSON 数据: {current_data[:100]}..."
                        # 考虑是否要 return，取决于是否希望忽略错误继续处理后续事件
                        # return # 决定：解析错误时终止流处理
                    finally:
                        # 重置累积的数据，准备接收下一个事件
                        current_data = ""
                # 如果是空行且没有累积数据，则忽略
                continue

            # --- 处理非空行 (通常是 data: 行) ---
            try:
                # 解码行数据 (假设是 utf-8)
                line = line_bytes.decode('utf-8')
                # 如果行以 "data:" 开头，提取后面的内容并累加到 current_data
                if line.startswith('data:'):
                    current_data += line[len('data:'):].strip()
                # 可以忽略其他类型的 SSE 行，如 "event:", "id:", ":" (注释)
            except UnicodeDecodeError:
                # 如果解码失败
                print(f"警告 ({prompt_type}): 解码 SSE 行时出错，已跳过。原始字节: {line_bytes}")
                continue # 继续处理下一行

        # --- 流正常结束 (循环结束) ---
        print(f"Google API 事件流处理完成 ({prompt_type}).")
        yield "done", f"{prompt_type} 处理完成。"

    # --- 处理网络层面的异常 ---
    except requests.exceptions.ProxyError as proxy_e:
        proxy_url = proxies.get('http', 'N/A') if proxies else 'N/A'
        error_msg = f"Google API 流代理错误 ({prompt_type}): 无法连接到代理 {proxy_url}. 错误: {proxy_e}"
        print(error_msg)
        yield "error", error_msg
    except requests.exceptions.SSLError as ssl_e:
        error_msg = f"Google API 流 SSL 错误 ({prompt_type}): {ssl_e}"
        print(error_msg)
        yield "error", error_msg
    except requests.exceptions.RequestException as req_e:
        error_msg = f"Google API 流网络/HTTP 错误 ({prompt_type}): {req_e}"
        print(error_msg)
        yield "error", error_msg
    except Exception as e:
        # 捕获处理流过程中的其他所有意外错误
        error_msg = f"处理 Google API 流时发生未预期的严重错误 ({prompt_type}): {e}"
        print(error_msg)
        traceback.print_exc()
        yield "error", error_msg
    finally:
        # --- 确保关闭响应流 ---
        print(f"Google API 流生成器退出 ({prompt_type}).")
        if response:
            try:
                response.close() # 关闭连接，释放资源
                print(f"已关闭 Google API 响应流 ({prompt_type}).")
            except Exception as close_e:
                print(f"关闭 Google API 响应流时出错 ({prompt_type}): {close_e}")


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