# app.py
import os
import re
import json
import time
import requests
from flask import Flask, request, jsonify, render_template, Response, stream_with_context
import traceback
import pprint
import threading
import base64
from pathlib import Path

# --- Pygame Sound Playback Setup ---
PYGAME_AVAILABLE = False
try: # 检查 pygame 导入
    import pygame
    try: # 检查 mixer 初始化
        pygame.mixer.init()
        PYGAME_AVAILABLE = True
        print("Pygame mixer 初始化成功。")
    except pygame.error as init_err: # mixer 初始化失败
        print(f"警告：无法初始化 pygame mixer: {init_err}")
        print("         请检查音频驱动/设备。使用 pygame 的声音播放功能将被禁用。")
        PYGAME_AVAILABLE = False
except ImportError: # pygame 导入失败
    print("警告：未找到 pygame 库。")
    print("         请使用 'pip install pygame' 安装。")
    print("         声音通知功能将被禁用。")

# --- 全局配置 ---
CONFIG_FILENAME = "config.json"
app = Flask(__name__)

# --- Prompt Templates ---
# [Templates 不变]
PREPROCESSING_PROMPT_TEMPLATE = """
**任务：根据上下文指令格式化文本**
请仔细阅读【上下文指令】和【原始小说文本】。
你的核心任务是：在【充分理解上下文指令】的前提下，对【原始小说文本】进行格式化，【仅】添加以下两种标记：
1.  `[说话人名字]`：添加到能确定说话人的对话行上方。
2.  `*{{...}}*`：包裹角色的内心想法。
**【格式化时严格禁止】：**
*   禁止生成任何新的文本内容。
*   禁止修改或删除原始文本的任何字符。
*   禁止添加规则之外的任何标记。
*   禁止进行任何解释或评论。
**--- 上下文指令 ---**
{pre_instruction}
{post_instruction}
**--- 指令结束 ---**
**--- 原始小说文本 ---**
{text_chunk}
**--- 文本结束 ---**
请根据以上所有信息，输出带有标记的格式化文本：
"""
PROMPT_ENHANCEMENT_TEMPLATE = """
{pre_instruction}
你是一个高级小说处理助手，擅长理解上下文并生成符合场景的 NAI (NovelAI) 图像生成风格提示词。
你的任务是：阅读【已格式化文本】，参考【人物基础设定】，并在特定人物的对话或重要动作【之前】，智能地生成并添加 NAI 提示词标记。
输入包含两部分：
1.  【已格式化文本】：包含 `[名字]` 说话人标记和 `*{{...}}*` 心声标记的文本。这是主要的上下文来源。
2.  【人物基础设定】：一个 JSON 字符串，格式为 `{{"人物名字1": {{"positive": "基础正面提示词", "negative": "基础负面提示词"}}, "人物名字2": {{...}} }}`。这些是每个角色**固定不变**的提示词。
严格遵循以下规则进行处理：
1.  **分析上下文**: 当遇到说话人标记 `[名字]` 时，仔细阅读该标记**之后**的几行文本（对话、动作描述等），理解当前场景、人物的情绪、动作和环境。
2.  **查找基础设定**: 在【人物基础设定】中查找当前说话人 `[名字]` 对应的基础提示词（positive 和 negative）。
3.  **动态生成提示词**: 基于你对当前上下文的理解（步骤 1），以及人物的基础设定（步骤 2），为当前场景**动态生成**额外的、描述性的 NAI 提示词。这些动态提示词应该反映：
    *   人物的**当前情绪**（例如：`smiling`, `angry`, `crying`, `blushing`）
    *   人物的**主要动作或姿态**（例如：`raising hand`, `pointing forward`, `sitting on chair`, `leaning on wall`）
    *   **关键的场景元素或光照**（例如：`classroom background`, `night`, `window light`, ` dimly lit`）
    *   **与其他角色的互动**（如果适用，例如：`looking at other`, `holding hands with ...`）
4.  **组合提示词**:
    *   将**基础正面提示词**和**动态生成的正面提示词**组合起来，用逗号 `,` 分隔。
    *   将**基础负面提示词**和**动态生成的负面提示词**（如果需要生成额外的负面词，通常较少）组合起来，用逗号 `,` 分隔。
5.  **添加标记**: 在识别到的 `[名字]` 标记行的【正上方】，添加一个新的标记行，格式为：`[NAI:{{名字}}|{{组合后的正面提示词}}|{{组合后的负面提示词}}]`。
    *   确保使用**双花括号 `{{ }}`** 包裹占位符名称，以防止 Python 格式化错误。
    *   如果某个角色的基础设定为空，并且根据上下文也无法生成有意义的动态提示词，则**不要**为该角色添加 `[NAI:...]` 标记。
    *   如果只有正面或负面提示词（基础+动态），另一部分留空，但**必须保留分隔符 `|`**。
6.  **处理心声/旁白**: 不要为心声 `*{{...}}*` 或普通旁白添加 `[NAI:...]` 标记。
7.  **保留原文和原有标记**: 除了按规则添加包含【组合后提示词】的 `[NAI:...]` 标记外，必须【完整保留】输入文本中的所有其他内容。
8.  **输出格式**: 直接输出带有新增标记的文本。不要包含任何代码块标记或额外的解释。
现在，请根据以下【人物基础设定】和【已格式化文本】的上下文，智能地生成并添加 NAI 提示词标记：
--- CHARACTER BASE PROFILES (JSON) ---
{character_profiles_json}
--- CHARACTER BASE PROFILES END ---
--- FORMATTED TEXT START ---
{formatted_text_chunk}
--- FORMATTED TEXT END ---
{post_instruction}
Enhanced Text Output with Generated Prompts:
"""
KAG_CONVERSION_PROMPT_TEMPLATE = """
{pre_instruction}
你是一个将【已格式化并包含 NAI 提示词标记】的小说文本转换为 KiriKiri2 KAG (ks) 脚本格式的专家。
输入文本已经包含了说话人标记 `[名字]`、心声标记 `*{{...}}*` 以及 NAI 提示词标记 `[NAI:名字|正面|负面]`。
严格按照以下规则进行转换，只输出 KAG 脚本代码，不要包含任何解释性文字或代码块标记。
专注于文本、对话、旁白和基本流程控制 `[p]`。
绝对不要生成任何与图像或声音相关的 KAG 标签（除了我们规则中定义的注释和【图片占位符】）。
规则：
1.  **处理 NAI 提示词标记 `[NAI:名字|正面|负面]`**: 当遇到此标记时，将其转换为 KAG 注释行，格式为：
    `; NAI Prompt for {{名字}}: Positive=[{{正面}}] Negative=[{{负面}}]`
    该注释行应出现在由该提示词引导的人物对话或动作之前。标记本身【不应】出现在最终的 KAG 输出中。
    **【重要】**：在该注释行的【正下方、紧接着的下一行】，添加一个**图片占位符**，格式为：
    `[INSERT_IMAGE_HERE:{{名字}}]`
    其中 `{{名字}}` 必须与 NAI 标记中的名字完全一致。
2.  **识别说话人标记 `[名字]`**: 当遇到此标记时，将其理解为下一行对话的说话人。标记本身【不应】出现在最终的 KAG 输出中。
3.  **处理对话（`“...”` 或 `「...」`）**:
    *   如果【前一行】是说话人标记 `[某名字]`，则输出：
        `[name]某名字[/name]`
        `对话内容（保留引号/括号）`
        `[p]`
    *   如果【前一行】不是说话人标记，则直接输出：
        `对话内容（保留引号/括号）`
        `[p]`
4.  **识别心声/内心独白 `*{{...}}*`**: 将其转换为普通文本输出（去除标记本身），并在其后添加 `[p]`：
    `内心独白内容`
    `[p]`
5.  **处理旁白/叙述**: 任何不符合上述 NAI 标记、图片占位符、对话或心声规则的、非空的文本行（除了说话人标记本身），都视为旁白输出，并在其后添加 `[p]`：
    `旁白内容`
    `[p]`
6.  **忽略空行**: 忽略输入文本中的空行。
7.  **结尾暂停**: 确保每个有效内容块（图片占位符、对话、心声、旁白）后面都有一个 `[p]`。对话、心声、旁白自带 `[p]` 即可。
8.  **顺序**: NAI 注释、图片占位符应紧邻其关联的人物对话/动作之前。
9.  **输出格式**: 确保最终输出是纯净的 KAG 脚本文本，包含 NAI 注释和图片占位符。
现在，请将以下【已包含 NAI 标记的格式化文本】转换为 KAG 脚本：
--- ENHANCED FORMATTED TEXT CHUNK START ---
{text_chunk}
--- ENHANCED FORMATTED TEXT CHUNK END ---
{post_instruction}
KAG Script Output with Image Placeholders:
"""

# --- Google API 调用助手 (*** 再次修正所有 try/except 语法 ***) ---

def stream_google_response(api_key, api_base_url, model_name, prompt, temperature, max_output_tokens, prompt_type="Generic"):
    clean_base_url = api_base_url.rstrip('/')
    streaming_endpoint = f"{clean_base_url}/v1beta/models/{model_name}:streamGenerateContent?key={api_key}&alt=sse"
    generation_config = {}
    if temperature is not None: generation_config["temperature"] = temperature
    if max_output_tokens is not None: generation_config["maxOutputTokens"] = max_output_tokens
    safety_settings = [ {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}, {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"}, {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"}, {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"} ]
    payload = { "contents": [{"parts": [{"text": prompt}]}], "safetySettings": safety_settings, **({"generationConfig": generation_config} if generation_config else {}) }
    headers = {"Content-Type": "application/json"}
    response = None
    try: # 外层 try: 处理 requests 调用和 HTTP 错误
        print(f"连接流 ({prompt_type}): {streaming_endpoint.split('?')[0]}?key=HIDDEN&alt=sse")
        response = requests.post(streaming_endpoint, headers=headers, json=payload, stream=True, timeout=600)
        response.raise_for_status() # 检查 4xx/5xx 错误
        content_type = response.headers.get('Content-Type', '')

        # 检查 Content-Type
        if 'application/json' in content_type:
            # 如果是 JSON，尝试解析错误信息
            try: # 内层 try: 处理 JSON 解析
                error_json = response.json()
                error_message = error_json.get('error', {}).get('message', f'API 返回 JSON 错误 ({prompt_type}).')
                print(f"错误: {error_message}")
                error_payload = json.dumps({"type": "error", "message": f"API 错误: {error_message}"})
                yield f"event: error\ndata: {error_payload}\n\n"
                return
            except json.JSONDecodeError: # 如果 JSON 解析失败
                error_message = f"API 返回无效 JSON ({prompt_type}). 状态码: {response.status_code}"
                print(error_message)
                error_payload = json.dumps({"type": "error", "message": error_message})
                yield f"event: error\ndata: {error_payload}\n\n"
                return
        elif 'text/event-stream' not in content_type:
            # 如果不是 SSE 也不是 JSON
            error_message = f"API 返回无效 Content-Type: {content_type} ({prompt_type})."
            print(error_message)
            error_payload = json.dumps({"type": "error", "message": error_message})
            yield f"event: error\ndata: {error_payload}\n\n"
            return

        # --- 循环处理 SSE 流 ---
        current_data = ""
        for line_bytes in response.iter_lines():
            if not line_bytes: # 消息结束标记
                if current_data:
                    parsed_json = None
                    try: # 内层 try: 处理 JSON 解析和内容提取
                        parsed_json = json.loads(current_data)
                        # print(f"Parsed SSE Data ({prompt_type}):", parsed_json) # Verbose debug

                        # --- 处理解析后的 JSON ---
                        if isinstance(parsed_json, dict) and 'error' in parsed_json:
                             error_message = parsed_json['error'].get('message', f'未知 API 错误 ({prompt_type}).')
                             print(f"API 流错误 ({prompt_type}): {error_message}")
                             error_payload = json.dumps({"type": "error", "message": f"API 错误: {error_message}"})
                             yield f"event: error\ndata: {error_payload}\n\n"
                             return # 终止

                        elif isinstance(parsed_json, dict) and 'promptFeedback' in parsed_json:
                             block_reason = parsed_json['promptFeedback'].get('blockReason', 'Unknown')
                             block_message = f"Prompt 被阻止 ({prompt_type}). 原因: {block_reason}."
                             ratings_details = parsed_json['promptFeedback'].get('safetyRatings', [])
                             if ratings_details: block_message += " Details: " + "; ".join([f"{r.get('category', 'N/A').replace('HARM_CATEGORY_', '')}={r.get('probability', 'N/A')}" for r in ratings_details])
                             print(block_message)
                             error_payload = json.dumps({"type": "error", "message": block_message})
                             yield f"event: error\ndata: {error_payload}\n\n"
                             return # 终止

                        elif isinstance(parsed_json, dict) and 'candidates' in parsed_json and parsed_json['candidates']:
                             candidate = parsed_json['candidates'][0]
                             text_chunk = ""
                             if 'content' in candidate and 'parts' in candidate['content'] and candidate['content']['parts']:
                                 text_chunk = candidate['content']['parts'][0].get('text', '')
                             if text_chunk:
                                 chunk_payload = json.dumps({"type": "chunk", "content": text_chunk})
                                 yield f"data: {chunk_payload}\n\n"

                             finish_reason = candidate.get('finishReason')
                             if finish_reason and finish_reason != 'STOP':
                                 finish_message = f"生成中止 ({prompt_type}). 原因: {finish_reason}."
                                 ratings_details = candidate.get('safetyRatings', [])
                                 if ratings_details: finish_message += " Details: " + "; ".join([f"{r.get('category', 'N/A').replace('HARM_CATEGORY_', '')}={r.get('probability', 'N/A')}" for r in ratings_details])
                                 print(f"警告: {finish_message}")
                                 warn_payload = json.dumps({"type": "warning", "message": finish_message})
                                 yield f"event: warning\ndata: {warn_payload}\n\n"
                                 if finish_reason == 'SAFETY':
                                      error_payload = json.dumps({"type": "error", "message": finish_message})
                                      yield f"event: error\ndata: {error_payload}\n\n"
                                      return # 终止
                        # else:
                        #     print(f"警告: 未识别的 SSE JSON 结构 ({prompt_type}): {current_data}")
                        # --- 成功处理结束 ---

                    except json.JSONDecodeError as json_e: # 捕获 JSON 解析错误
                        print(f"JSON 解析错误 ({prompt_type}): {json_e} - 数据: '{current_data}'")
                        try: # 内内层 try: 尝试发送错误到前端
                            error_payload = json.dumps({"type": "error", "message": f"收到无效 JSON: {current_data[:100]}..."})
                            yield f"event: error\ndata: {error_payload}\n\n"
                        except Exception as yield_err: # 如果发送失败
                            print(f"发送 JSON 解析错误失败 ({prompt_type}): {yield_err}")
                    # finally 块移出，current_data 总在下面重置

                current_data = "" # 在消息处理完后重置
                continue # 继续处理下一行

            # 解码并累积数据
            try: # 内层 try: 处理 decode
                line = line_bytes.decode('utf-8')
                if line.startswith('data:'):
                    current_data += line[len('data:'):].strip()
            except UnicodeDecodeError: # 处理解码错误
                print(f"警告: 解码错误跳过行 ({prompt_type}): {line_bytes}")
                continue

        # 处理流结束后可能残留的数据
        if current_data:
            print(f"警告: 流结束后有未处理数据 ({prompt_type}): '{current_data}'")

        print(f"Google API 流处理逻辑完成 ({prompt_type}).")

    # --- 外层异常处理 ---
    except requests.exceptions.Timeout:
        print(f"API 请求超时 ({prompt_type})")
        error_payload = json.dumps({"type": "error", "message": f"请求超时 ({prompt_type})."})
        yield f"event: error\ndata: {error_payload}\n\n"
    except requests.exceptions.RequestException as e:
        print(f"API 流请求出错 ({prompt_type}): {e}")
        error_detail = str(e); status_code = "N/A"
        if e.response is not None:
            status_code = e.response.status_code
            try: # 内层 try: 解析错误响应体
                json_error = e.response.json()
                error_detail = json_error.get('error', {}).get('message', e.response.text);
            except json.JSONDecodeError: # 如果无法解析
                error_detail = e.response.text if e.response.text else str(e)
        error_message = f"网络/请求错误 (状态码: {status_code}, 类型: {prompt_type}): {error_detail}"; print(error_message); error_payload = json.dumps({"type": "error", "message": error_message}); yield f"event: error\ndata: {error_payload}\n\n"; traceback.print_exc()
    except Exception as e:
        print(f"处理流时发生意外错误 ({prompt_type}): {e}"); error_payload = json.dumps({"type": "error", "message": f"流处理内部错误 ({prompt_type}): {str(e)}"}); yield f"event: error\ndata: {error_payload}\n\n"; traceback.print_exc()
    finally:
        print(f"流生成器退出 ({prompt_type}).")
        if response:
            try: # 内层 try: 关闭 response
                response.close()
                print(f"已关闭 Google API 响应流 ({prompt_type}).")
            except Exception as ce: # 捕获关闭异常
                print(f"关闭响应流出错 ({prompt_type}): {ce}")

# --- 非流式调用助手 (*** 再次核查所有 try/except 语法 ***) ---
def call_google_non_stream(api_key, api_base_url, model_name, prompt, temperature, max_output_tokens, prompt_type="Generic"):
    clean_base_url = api_base_url.rstrip('/')
    non_stream_endpoint = f"{clean_base_url}/v1beta/models/{model_name}:generateContent?key={api_key}"
    generation_config = {}
    if temperature is not None: generation_config["temperature"] = temperature
    if max_output_tokens is not None: generation_config["maxOutputTokens"] = max_output_tokens
    safety_settings = [ {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}, {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"}, {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"}, {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"} ]
    payload = { "contents": [{"parts": [{"text": prompt}]}], "safetySettings": safety_settings, **({"generationConfig": generation_config} if generation_config else {}) }
    headers = {"Content-Type": "application/json"}
    response = None # 初始化 response

    try: # 外层 try: 处理 requests 调用和 HTTP 错误
        print(f"调用非流式 API ({prompt_type}): {non_stream_endpoint.split('?')[0]}?key=HIDDEN")
        response = requests.post(non_stream_endpoint, headers=headers, json=payload, timeout=600)
        response.raise_for_status() # 检查 HTTP 错误

        # --- 在 try 块内部处理响应解析 ---
        try: # 内层 try: 处理 JSON 解析
            response_json = response.json()

            # --- 处理解析后的 JSON ---
            if 'promptFeedback' in response_json:
                block_reason = response_json['promptFeedback'].get('blockReason', 'Unknown')
                block_message = f"输入 prompt 被阻止 ({prompt_type}). 原因: {block_reason}."
                ratings_details = response_json['promptFeedback'].get('safetyRatings', [])
                if ratings_details: block_message += " Details: " + "; ".join([f"{r.get('category', 'N/A').replace('HARM_CATEGORY_', '')}={r.get('probability', 'N/A')}" for r in ratings_details])
                print(f"错误: {block_message}")
                return None, block_message # 返回错误

            if 'candidates' in response_json and response_json['candidates']:
                candidate = response_json['candidates'][0]
                finish_reason = candidate.get('finishReason')
                if finish_reason and finish_reason not in ['STOP', 'MAX_TOKENS']:
                    finish_message = f"生成中止 ({prompt_type}). 原因: {finish_reason}."
                    ratings_details = candidate.get('safetyRatings', [])
                    if ratings_details: finish_message += " Details: " + "; ".join([f"{r.get('category', 'N/A').replace('HARM_CATEGORY_', '')}={r.get('probability', 'N/A')}" for r in ratings_details])
                    print(f"警告/错误: {finish_message}")
                    if finish_reason == 'SAFETY': return None, finish_message # 返回安全错误

                if 'content' in candidate and 'parts' in candidate['content'] and candidate['content']['parts']:
                    full_text = "".join(part.get('text', '') for part in candidate['content']['parts'])
                    print(f"非流式 API 调用成功 ({prompt_type})。")
                    if finish_reason == 'MAX_TOKENS': print(f"警告：输出可能因达到 Max Tokens ({max_output_tokens}) 而被截断。")
                    return full_text, None # 成功返回
                else:
                    error_msg = f"API 响应中缺少有效内容部分 ({prompt_type})."
                    print(f"错误: {error_msg}")
                    return None, error_msg
            else:
                # 如果没有 candidates 也没有 promptFeedback
                if 'promptFeedback' not in response_json:
                     error_msg = f"API 响应格式无效，缺少 candidates ({prompt_type}). Response: {response.text[:500]}..." # 打印部分原始响应
                     print(f"错误: {error_msg}")
                     return None, error_msg
                else: # 只有 promptFeedback
                     return None, "Prompt feedback indicated an issue."
            # --- JSON 处理结束 ---

        except json.JSONDecodeError as json_e: # 捕获 JSON 解析错误
            error_msg = f"解析非流式 API 响应 JSON 时出错 ({prompt_type}): {json_e}. Response text: {response.text[:500]}..."
            print(error_msg)
            return None, error_msg
        # --- 内层 try 结束 ---

    # --- 外层异常处理 ---
    except requests.exceptions.Timeout:
        error_msg = f"非流式 API 请求超时 ({prompt_type})."
        print(error_msg)
        return None, error_msg
    except requests.exceptions.RequestException as e:
        error_detail = str(e); status_code = "N/A"
        if e.response is not None:
            status_code = e.response.status_code
            try: # 内层 try: 解析错误响应体
                json_error = e.response.json()
                error_detail = json_error.get('error', {}).get('message', e.response.text);
            except json.JSONDecodeError: # 如果无法解析
                error_detail = e.response.text if e.response.text else str(e)
        error_msg = f"非流式 API 网络/请求错误 (状态码: {status_code}, 类型: {prompt_type}): {error_detail}"
        print(error_msg); traceback.print_exc()
        return None, error_msg
    except Exception as e:
        error_msg = f"处理非流式 API 响应时发生意外错误 ({prompt_type}): {e}"
        print(error_msg); traceback.print_exc()
        return None, error_msg
    # finally 块在这里不是必需的，因为 response 变量的作用域仅在此函数内

# --- 异步播放声音助手 ---
# [Code unchanged]
def play_sound_async(sound_path):
    if not PYGAME_AVAILABLE: print("[声音禁用] Pygame 不可用或 mixer 初始化失败。"); return
    if not sound_path or not isinstance(sound_path, str): print(f"无效的声音路径: {sound_path}"); return
    if not os.path.exists(sound_path): print(f"声音文件未找到: {sound_path}"); return
    def target():
        try: # try: 处理 pygame 调用
            if not pygame.mixer.get_init(): pygame.mixer.init()
            if not pygame.mixer.get_init(): print("错误：无法初始化 mixer。无法播放声音。"); return
            print(f"尝试使用 pygame 加载声音: {sound_path}"); sound = pygame.mixer.Sound(sound_path)
            print(f"声音已加载。尝试播放..."); sound.play(); print(f"开始通过 pygame 播放声音: {sound_path}")
        except pygame.error as e: print(f"播放声音时出现 Pygame 错误 ({sound_path}): {e}"); traceback.print_exc()
        except Exception as e: print(f"播放 pygame 声音时出现意外错误 ({sound_path}): {e}"); traceback.print_exc()
    thread = threading.Thread(target=target); thread.daemon = True; thread.start()

# --- Flask 路由 ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/save_config', methods=['POST'])
def save_config_api():
    if not request.is_json: return jsonify({"error": "请求必须是 JSON 格式"}), 415
    data = request.get_json()
    if not data: return jsonify({"error": "无效的请求数据"}), 400
    config_to_save = {
        'apiKey': data.get('apiKey', ''), 'apiEndpoint': data.get('apiEndpoint', ''), 'modelName': data.get('modelName', ''),
        'temperature': data.get('temperature', None), 'maxOutputTokens': data.get('maxOutputTokens', None),
        'successSoundPath': data.get('successSoundPath', ''), 'failureSoundPath': data.get('failureSoundPath', ''),
        'preInstruction': data.get('preInstruction', ''), 'postInstruction': data.get('postInstruction', ''),
        'saveDebugInputs': data.get('saveDebugInputs', False), 'enableStreaming': data.get('enableStreaming', True),
        'naiApiKey': data.get('naiApiKey', ''), 'naiImageSaveDir': data.get('naiImageSaveDir', ''), 'naiModel': data.get('naiModel', 'nai-diffusion-3'), 'naiSampler': data.get('naiSampler', 'k_euler'),
        'naiSteps': data.get('naiSteps', 28), 'naiScale': data.get('naiScale', 7.0), 'naiSeed': data.get('naiSeed', -1), 'naiUcPreset': data.get('naiUcPreset', 0), 'naiQualityToggle': data.get('naiQualityToggle', True)
    }
    try: # try: 处理文件写入和路径检查
        save_dir = config_to_save.get('naiImageSaveDir')
        if save_dir:
            path = Path(save_dir)
            if not path.exists(): print(f"警告: NAI 图片保存目录 '{save_dir}' 不存在。将在生成时尝试创建。")
            elif not path.is_dir(): print(f"警告: NAI 图片保存目录 '{save_dir}' 不是一个目录。")
        with open(CONFIG_FILENAME, 'w', encoding='utf-8') as f:
            json.dump(config_to_save, f, ensure_ascii=False, indent=4)
        print(f"配置已保存到 {CONFIG_FILENAME}")
        return jsonify({"message": "参数与设置已成功保存。"}), 200
    except Exception as e: # 捕获所有保存相关的错误
        print(f"保存配置时发生错误: {e}"); traceback.print_exc()
        return jsonify({"error": f"保存配置失败: {e}"}), 500

@app.route('/load_config', methods=['GET'])
def load_config_api():
    default_config = { 'apiKey': '', 'apiEndpoint': '', 'modelName': '', 'temperature': None, 'maxOutputTokens': None, 'successSoundPath': '', 'failureSoundPath': '', 'preInstruction': '', 'postInstruction': '', 'saveDebugInputs': False, 'enableStreaming': True, 'naiApiKey': '', 'naiImageSaveDir': '', 'naiModel': 'nai-diffusion-3', 'naiSampler': 'k_euler', 'naiSteps': 28, 'naiScale': 7.0, 'naiSeed': -1, 'naiUcPreset': 0, 'naiQualityToggle': True }
    if not os.path.exists(CONFIG_FILENAME):
        print(f"配置文件 {CONFIG_FILENAME} 未找到。")
        return jsonify(default_config), 200
    try: # try: 处理文件读取和 JSON 解析
        with open(CONFIG_FILENAME, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        final_config = {**default_config, **config_data}
        # 类型修正
        for key in ['naiSteps', 'naiUcPreset', 'naiSeed']:
            if key in final_config and isinstance(final_config[key], (str, float)):
                try: final_config[key] = int(final_config[key])
                except (ValueError, TypeError): final_config[key] = default_config[key]
        if 'naiScale' in final_config and isinstance(final_config['naiScale'], str):
            try: final_config['naiScale'] = float(final_config['naiScale'])
            except (ValueError, TypeError): final_config['naiScale'] = default_config['naiScale']
        for key_bool in ['naiQualityToggle', 'saveDebugInputs', 'enableStreaming']:
             if key_bool in final_config and not isinstance(final_config[key_bool], bool):
                  final_config[key_bool] = str(final_config[key_bool]).lower() == 'true'

        print(f"配置已从 {CONFIG_FILENAME} 加载。")
        return jsonify(final_config), 200
    except Exception as e: # 捕获加载和解析错误
        print(f"加载配置时发生错误: {e}"); traceback.print_exc()
        return jsonify({"error": f"加载配置失败: {e}"}), 500

@app.route('/play_sound', methods=['POST'])
def play_sound_api():
    if not PYGAME_AVAILABLE: return jsonify({"message": "声音在服务器上被禁用。"}), 202
    if not request.is_json: return jsonify({"error": "请求必须是 JSON 格式"}), 415
    data = request.get_json()
    if not data: return jsonify({"error": "无效的请求数据"}), 400
    status = data.get('status')
    if status not in ['success', 'failure']: return jsonify({"error": "无效的状态"}), 400
    config_data = {}
    if os.path.exists(CONFIG_FILENAME):
        try: # try: 处理配置文件读取
            with open(CONFIG_FILENAME, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
        except Exception as e: # 只记录错误，不中断播放
            print(f"加载配置以播放声音时出错: {e}")
            traceback.print_exc()
    sound_path = config_data.get('successSoundPath') if status == 'success' else config_data.get('failureSoundPath')
    if sound_path:
        play_sound_async(sound_path)
        return jsonify({"message": f"尝试播放 {status} 声音。"}), 202
    else:
        print(f"未为以下状态配置声音路径: {status}")
        return jsonify({"message": f"未配置 {status} 声音路径。"}), 202

# --- API 端点 ---
def validate_common_params(data):
    errors = []
    api_key = data.get('api_key'); api_base_url = data.get('api_base_url'); model_name = data.get('model_name')
    if not api_key: errors.append("缺少 API Key");
    if not api_base_url: errors.append("缺少 API Base URL");
    elif not api_base_url.startswith("https://"): errors.append("无效的 API Base URL (应以 https:// 开头)")
    if not model_name: errors.append("缺少 Model Name")
    try: # try: 处理数字转换
        raw_temp = data.get('temperature'); temperature = float(raw_temp) if raw_temp is not None and raw_temp != '' else None
        if temperature is not None and (temperature < 0 or temperature > 2): errors.append("Temperature 必须在 0 到 2 之间")
        raw_max_tokens = data.get('max_output_tokens'); max_output_tokens = int(raw_max_tokens) if raw_max_tokens is not None and raw_max_tokens != '' else None
        if max_output_tokens is not None and max_output_tokens < 1: errors.append("Max Output Tokens 必须大于 0")
    except (ValueError, TypeError) as e: errors.append(f"无效的数字参数格式: {e}")
    if errors: return False, ", ".join(errors), None, None
    return True, "", temperature, max_output_tokens

# --- 流式 API 端点 ---
@app.route('/preprocess_stream', methods=['POST'])
def preprocess_stream_api():
    if not request.is_json: return jsonify({"error": "请求必须是 JSON 格式"}), 415
    data = request.get_json();
    if not data: return jsonify({"error": "无效的请求数据"}), 400
    is_valid, error_msg, temperature, max_output_tokens = validate_common_params(data);
    if not is_valid: return jsonify({"error": error_msg}), 400
    api_key = data['api_key']; api_base_url = data['api_base_url']; model_name = data['model_name']
    novel_text = data.get('novel_text'); pre_instruction = data.get('pre_instruction', ''); post_instruction = data.get('post_instruction', '')
    if not novel_text: return jsonify({"error": "缺少 Novel Text"}), 400
    try: # try: 格式化 prompt
        preprocess_prompt = PREPROCESSING_PROMPT_TEMPLATE.format(pre_instruction=pre_instruction, post_instruction=post_instruction, text_chunk=novel_text)
    except Exception as format_error:
        print(f"格式化 Preprocessing Prompt 时出错: {format_error}")
        return jsonify({"error": f"服务器内部错误：格式化失败。错误: {format_error}"}), 500
    print("\n--- Final Preprocessing Prompt to LLM (Step 1 - Partial, with instructions) ---")
    print(preprocess_prompt[:1000] + ("..." if len(preprocess_prompt) > 1000 else ""))
    print("--- End Final Prompt (Step 1) ---\n")
    def generate_preprocess_sse():
        header_payload = json.dumps({"type": "header", "content": "; Preprocessing Started (Streaming)...\n"}); yield f"data: {header_payload}\n\n"
        yield from stream_google_response(api_key, api_base_url, model_name, preprocess_prompt, temperature, max_output_tokens, prompt_type="Preprocessing")
        footer_payload = json.dumps({"type": "footer", "content": "\n; Preprocessing Finished."}); yield f"data: {footer_payload}\n\n"
    return Response(stream_with_context(generate_preprocess_sse()), mimetype='text/event-stream')

@app.route('/enhance_stream', methods=['POST'])
def enhance_stream_api():
    if not request.is_json: return jsonify({"error": "请求必须是 JSON 格式"}), 415
    data = request.get_json();
    if not data: return jsonify({"error": "无效的请求数据"}), 400
    is_valid, error_msg, temperature, max_output_tokens = validate_common_params(data);
    if not is_valid: return jsonify({"error": error_msg}), 400
    api_key = data['api_key']; api_base_url = data['api_base_url']; model_name = data['model_name']
    formatted_text = data.get('formatted_text'); character_profiles_str = data.get('character_profiles_json')
    pre_instruction = data.get('pre_instruction', ''); post_instruction = data.get('post_instruction', '')
    if not formatted_text: return jsonify({"error": "缺少 Formatted Text"}), 400
    if not character_profiles_str: return jsonify({"error": "缺少 Character Profiles"}), 400
    try: # try: 解析 JSON
        json.loads(character_profiles_str)
    except json.JSONDecodeError: return jsonify({"error": "无效的人物设定 JSON 格式。"}), 400
    try: # try: 格式化 prompt
        enhancement_prompt = PROMPT_ENHANCEMENT_TEMPLATE.format(pre_instruction=pre_instruction, character_profiles_json=character_profiles_str, formatted_text_chunk=formatted_text, post_instruction=post_instruction)
    except Exception as format_error:
        print(f"格式化 Enhancement Prompt 时出错: {format_error}")
        return jsonify({"error": f"服务器内部错误：格式化失败。错误: {format_error}"}), 500
    def generate_enhancement_sse():
        header_payload = json.dumps({"type": "header", "content": "; Prompt Enhancement Started (Streaming)...\n"}); yield f"data: {header_payload}\n\n"
        yield from stream_google_response(api_key, api_base_url, model_name, enhancement_prompt, temperature, max_output_tokens, prompt_type="PromptEnhancement")
        footer_payload = json.dumps({"type": "footer", "content": "\n; Prompt Enhancement Finished."}); yield f"data: {footer_payload}\n\n"
    return Response(stream_with_context(generate_enhancement_sse()), mimetype='text/event-stream')

@app.route('/convert_stream', methods=['POST'])
def convert_stream_api():
     if not request.is_json: return jsonify({"error": "请求必须是 JSON 格式"}), 415
     data = request.get_json()
     if not data: return jsonify({"error": "无效的请求数据"}), 400
     is_valid, error_msg, temperature, max_output_tokens = validate_common_params(data);
     if not is_valid: return jsonify({"error": error_msg}), 400
     api_key = data['api_key']; api_base_url = data['api_base_url']; model_name = data['model_name']
     enhanced_text = data.get('enhanced_text'); pre_instruction = data.get('pre_instruction', ''); post_instruction = data.get('post_instruction', '')
     if not enhanced_text: return jsonify({"error": "缺少 Enhanced Text"}), 400
     try: # try: 格式化 prompt
         kag_conversion_prompt = KAG_CONVERSION_PROMPT_TEMPLATE.format(pre_instruction=pre_instruction, text_chunk=enhanced_text, post_instruction=post_instruction)
     except Exception as format_error:
         print(f"格式化 KAG Conversion Prompt 时出错: {format_error}")
         return jsonify({"error": f"服务器内部错误：格式化失败。错误: {format_error}"}), 500
     def generate_convert_sse():
        header_content = "; Generated KAG script (Streaming)\n"; header_content += "; ...\n\n"; header_content += "*start\n";
        header_payload = json.dumps({"type": "header", "content": header_content}); yield f"data: {header_payload}\n\n"
        yield from stream_google_response( api_key, api_base_url, model_name, kag_conversion_prompt, temperature, max_output_tokens, prompt_type="KAG Conversion" )
        footer_content = "\n@s ; Script End"; footer_payload = json.dumps({"type": "footer", "content": footer_content}); yield f"data: {footer_payload}\n\n"
     return Response(stream_with_context(generate_convert_sse()), mimetype='text/event-stream')

# --- 非流式 API 端点 ---
@app.route('/preprocess_nostream', methods=['POST'])
def preprocess_nostream_api():
    if not request.is_json: return jsonify({"error": "请求必须是 JSON 格式"}), 415
    data = request.get_json()
    if not data: return jsonify({"error": "无效的请求数据"}), 400
    is_valid, error_msg, temperature, max_output_tokens = validate_common_params(data)
    if not is_valid: return jsonify({"error": error_msg}), 400
    api_key = data['api_key']; api_base_url = data['api_base_url']; model_name = data['model_name']
    novel_text = data.get('novel_text'); pre_instruction = data.get('pre_instruction', ''); post_instruction = data.get('post_instruction', '')
    if not novel_text: return jsonify({"error": "缺少 Novel Text"}), 400
    try: # try: 格式化 prompt
        preprocess_prompt = PREPROCESSING_PROMPT_TEMPLATE.format(pre_instruction=pre_instruction, post_instruction=post_instruction, text_chunk=novel_text)
    except Exception as format_error:
        print(f"格式化 Preprocessing Prompt 时出错: {format_error}")
        return jsonify({"error": f"服务器内部错误：格式化失败。错误: {format_error}"}), 500

    print(f"\n--- Calling Non-Streaming API for Preprocessing ---")
    full_text, error = call_google_non_stream(api_key, api_base_url, model_name, preprocess_prompt, temperature, max_output_tokens, prompt_type="Preprocessing (NoStream)")
    print(f"--- Non-Streaming Call Finished ---")
    if error: return jsonify({"error": error}), 500
    else: return jsonify({"result": full_text, "status": "success"})

@app.route('/enhance_nostream', methods=['POST'])
def enhance_nostream_api():
    if not request.is_json: return jsonify({"error": "请求必须是 JSON 格式"}), 415
    data = request.get_json()
    if not data: return jsonify({"error": "无效的请求数据"}), 400
    is_valid, error_msg, temperature, max_output_tokens = validate_common_params(data)
    if not is_valid: return jsonify({"error": error_msg}), 400
    api_key = data['api_key']; api_base_url = data['api_base_url']; model_name = data['model_name']
    formatted_text = data.get('formatted_text'); character_profiles_str = data.get('character_profiles_json')
    pre_instruction = data.get('pre_instruction', ''); post_instruction = data.get('post_instruction', '')
    if not formatted_text: return jsonify({"error": "缺少 Formatted Text"}), 400
    if not character_profiles_str: return jsonify({"error": "缺少 Character Profiles"}), 400
    try: # try: 解析 JSON
        json.loads(character_profiles_str)
    except json.JSONDecodeError: return jsonify({"error": "无效的人物设定 JSON 格式。"}), 400
    try: # try: 格式化 prompt
        enhancement_prompt = PROMPT_ENHANCEMENT_TEMPLATE.format(pre_instruction=pre_instruction, character_profiles_json=character_profiles_str, formatted_text_chunk=formatted_text, post_instruction=post_instruction)
    except Exception as format_error:
        print(f"格式化 Enhancement Prompt 时出错: {format_error}")
        return jsonify({"error": f"服务器内部错误：格式化失败。错误: {format_error}"}), 500

    print(f"\n--- Calling Non-Streaming API for Enhancement ---")
    full_text, error = call_google_non_stream(api_key, api_base_url, model_name, enhancement_prompt, temperature, max_output_tokens, prompt_type="Enhancement (NoStream)")
    print(f"--- Non-Streaming Call Finished ---")
    if error: return jsonify({"error": error}), 500
    else: return jsonify({"result": full_text, "status": "success"})

@app.route('/convert_nostream', methods=['POST'])
def convert_nostream_api():
     if not request.is_json: return jsonify({"error": "请求必须是 JSON 格式"}), 415
     data = request.get_json()
     if not data: return jsonify({"error": "无效的请求数据"}), 400
     is_valid, error_msg, temperature, max_output_tokens = validate_common_params(data)
     if not is_valid: return jsonify({"error": error_msg}), 400
     api_key = data['api_key']; api_base_url = data['api_base_url']; model_name = data['model_name']
     enhanced_text = data.get('enhanced_text'); pre_instruction = data.get('pre_instruction', ''); post_instruction = data.get('post_instruction', '')
     if not enhanced_text: return jsonify({"error": "缺少 Enhanced Text"}), 400
     try: # try: 格式化 prompt
         kag_conversion_prompt = KAG_CONVERSION_PROMPT_TEMPLATE.format(pre_instruction=pre_instruction, text_chunk=enhanced_text, post_instruction=post_instruction)
     except Exception as format_error:
         print(f"格式化 KAG Conversion Prompt 时出错: {format_error}")
         return jsonify({"error": f"服务器内部错误：格式化失败。错误: {format_error}"}), 500

     print(f"\n--- Calling Non-Streaming API for KAG Conversion ---")
     full_text, error = call_google_non_stream(api_key, api_base_url, model_name, kag_conversion_prompt, temperature, max_output_tokens, prompt_type="KAG Conversion (NoStream)")
     print(f"--- Non-Streaming Call Finished ---")
     if error: return jsonify({"error": error}), 500
     else:
         header = "*start\n"; footer = "\n@s ; Script End"
         final_script = header + full_text + footer
         return jsonify({"result": final_script, "status": "success"})

# [generate_images_api - 使用修正后的 try/with]
NAI_API_BASE = "https://api.novelai.net"
def call_novelai_image_api(api_key, payload):
    headers = { "Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "Accept": "application/json" }
    api_endpoint = f"{NAI_API_BASE}/ai/generate-image"
    try: # try: 处理 requests 调用
        print(f"  调用 NovelAI API: {api_endpoint}")
        response = requests.post(api_endpoint, headers=headers, json=payload, timeout=300)
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '').lower()
            if 'application/zip' in content_type or 'application/octet-stream' in content_type: print(f"  成功: 收到图像数据 (Content-Type: {content_type})"); return response.content, None
            elif 'application/json' in content_type:
                 try: error_json = response.json(); error_msg = f"NovelAI 返回意外 JSON (200 OK): {error_json.get('message', response.text)}"; print(f"  错误: {error_msg}"); return None, error_msg
                 except json.JSONDecodeError: error_msg = f"NovelAI 返回非预期 Content-Type (200 OK): {content_type}"; print(f"  错误: {error_msg}"); return None, error_msg
            else: error_msg = f"NovelAI 返回非预期 Content-Type (200 OK): {content_type}"; print(f"  错误: {error_msg}"); return None, error_msg
        else:
            error_msg = f"NovelAI API 错误 (状态码: {response.status_code})";
            try: error_json = response.json(); error_msg += f": {error_json.get('message', response.text)}"
            except json.JSONDecodeError: error_msg += f": {response.text}"
            print(f"  错误: {error_msg}"); return None, error_msg
    except requests.exceptions.RequestException as e: error_msg = f"调用 NovelAI API 时网络错误: {e}"; print(f"  错误: {error_msg}"); return None, error_msg
    except Exception as e: error_msg = f"调用 NovelAI API 时意外错误: {e}"; print(f"  错误: {error_msg}"); traceback.print_exc(); return None, error_msg

@app.route('/generate_images', methods=['POST'])
def generate_images_api():
    if not request.is_json: return jsonify({"error": "请求必须是 JSON 格式"}), 415
    data = request.get_json()
    if not data: return jsonify({"error": "无效的请求数据"}), 400
    kag_script = data.get('kag_script')
    if not kag_script: return jsonify({"error": "缺少 KAG 脚本内容"}), 400
    config = {};
    if os.path.exists(CONFIG_FILENAME):
        try: # *** 再次确认这里的 try/with 结构正确 ***
            with open(CONFIG_FILENAME, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception as e: # 捕获文件读取或 JSON 解析错误
            print(f"加载配置出错: {e}")
            return jsonify({"error": f"无法加载服务器配置: {e}"}), 500
    else:
        return jsonify({"error": "服务器配置文件未找到。"}), 500

    nai_api_key = config.get('naiApiKey'); nai_save_dir_str = config.get('naiImageSaveDir'); nai_model = config.get('naiModel', 'nai-diffusion-3'); nai_sampler = config.get('naiSampler', 'k_euler'); nai_steps = int(config.get('naiSteps', 28)); nai_scale = float(config.get('naiScale', 7.0)); nai_seed = int(config.get('naiSeed', -1)); nai_uc_preset = int(config.get('naiUcPreset', 0)); nai_quality_toggle = bool(config.get('naiQualityToggle', True))
    if not nai_api_key: return jsonify({"error": "配置中缺少 NovelAI API Key。"}), 400
    if not nai_save_dir_str: return jsonify({"error": "配置中缺少 NovelAI 图片保存目录。"}), 400

    try: # try: 处理路径验证
        base_save_path = Path(nai_save_dir_str).resolve(strict=True) # strict=True 确保路径存在
        if not base_save_path.is_dir(): return jsonify({"error": f"图片保存路径 '{nai_save_dir_str}' 不是有效目录。"}), 400
        if not os.access(base_save_path, os.W_OK): return jsonify({"error": f"服务器对图片保存目录 '{nai_save_dir_str}' 无写入权限。"}), 403
    except FileNotFoundError: return jsonify({"error": f"图片保存路径 '{nai_save_dir_str}' 不存在。"}), 400
    except Exception as path_e: return jsonify({"error": f"验证图片保存路径时出错: {path_e}"}), 500

    pattern = re.compile(r";\s*NAI Prompt for\s*(.*?):\s*Positive=\[(.*?)\]\s*(?:Negative=\[(.*?)\])?\s*\n\s*\[image storage=\"(.*?)\".*?\]", re.DOTALL)
    tasks = [];
    for match in pattern.finditer(kag_script):
        name = match.group(1).strip() if match.group(1) else "Unknown"; positive = match.group(2).strip() if match.group(2) else ""; negative = match.group(3).strip() if match.group(3) else ""; filename = match.group(4).strip() if match.group(4) else ""; full_comment = match.group(0).split('\n')[0]
        if positive and filename: tasks.append({ "name": name, "positive": positive, "negative": negative, "filename": filename, "comment_line": full_comment })
        else: print(f"警告: 跳过无效匹配项 - Positive 或 Filename 为空。匹配: {match.group(0)[:100]}...")
    if not tasks: return jsonify({"message": "未找到有效的 NAI Prompt 注释和图片标签对。", "modified_script": kag_script}), 200

    print(f"解析到 {len(tasks)} 个图片生成任务。"); generated_count = 0; failed_count = 0; results_log = []; successful_comments_to_remove = set()

    for i, task in enumerate(tasks):
        print(f"--- 开始生成图片 {i+1}/{len(tasks)}: {task['filename']} ---"); filename = task['filename']; pos_prompt = task['positive']; neg_prompt = task['negative']
        payload = { "action": "generate", "input": pos_prompt, "model": nai_model, "parameters": { "width": 1024, "height": 1024, "scale": nai_scale, "sampler": nai_sampler, "steps": nai_steps, "seed": nai_seed, "n_samples": 1, "ucPreset": nai_uc_preset, "qualityToggle": nai_quality_toggle, "negative_prompt": neg_prompt } }
        image_data, error_msg = call_novelai_image_api(nai_api_key, payload)
        if image_data and not error_msg:
            try: # try: 处理路径安全和文件写入
                safe_filename_str = re.sub(r'[\\/]', '_', filename);
                if '..' in safe_filename_str: raise ValueError("检测到无效文件名 '..'")
                target_path = base_save_path.joinpath(safe_filename_str).resolve()
                if not target_path.is_relative_to(base_save_path): raise SecurityError(f"尝试写入基础保存目录之外: {target_path}")
                if not target_path.suffix.lower() == '.png': target_path = target_path.with_suffix('.png'); print(f"  注意: 文件名后缀强制设为 .png")
                print(f"  保存图片到: {target_path}")
                with open(target_path, 'wb') as f: # 使用 with 确保文件关闭
                    f.write(image_data)
                generated_count += 1; results_log.append(f"成功: {filename}"); successful_comments_to_remove.add(task['comment_line']); print(f"  成功保存图片: {filename}")
            except (IOError, ValueError, SecurityError, Exception) as save_err: # 捕获保存错误
                failed_count += 1; err_detail = f"保存图片 '{filename}' 时出错: {save_err}"; print(f"  错误: {err_detail}"); results_log.append(f"失败 (保存错误): {filename} - {err_detail}")
        else: failed_count += 1; results_log.append(f"失败 (API错误): {filename} - {error_msg}"); print(f"  生成失败: {error_msg}")
        print(f"--- 完成图片 {i+1}/{len(tasks)} ---"); time.sleep(0.5)

    modified_script_lines = []; original_lines = kag_script.splitlines();
    for line in original_lines:
        trimmed_line = line.strip()
        if trimmed_line in successful_comments_to_remove: print(f"移除注释: {trimmed_line}"); continue
        else: modified_script_lines.append(line)
    modified_script = "\n".join(modified_script_lines)

    final_message = f"图片生成完成。成功: {generated_count}, 失败: {failed_count}."
    print(final_message); print("详细日志:\n" + "\n".join(results_log))
    return jsonify({ "message": final_message, "details": results_log, "modified_script": modified_script }), 200

# --- 运行 Flask 应用 ---
if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000, threaded=True)