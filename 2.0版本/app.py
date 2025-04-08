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

# --- Pygame Sound Playback Setup ---
PYGAME_AVAILABLE = False
try:
    # 尝试导入并初始化 pygame.mixer 用于声音播放
    import pygame
    try:
        pygame.mixer.init()
        PYGAME_AVAILABLE = True
        print("Pygame mixer 初始化成功。")
    except pygame.error as init_err:
        print(f"警告：无法初始化 pygame mixer: {init_err}")
        print("         请检查音频驱动/设备。使用 pygame 的声音播放功能将被禁用。")
        PYGAME_AVAILABLE = False
except ImportError:
    print("警告：未找到 pygame 库。")
    print("         请使用 'pip install pygame' 安装。")
    print("         声音通知功能将被禁用。")

# --- 全局配置 ---
CONFIG_FILENAME = "config.json" # 服务器配置（API Key等）文件名
app = Flask(__name__)

# --- Prompt Templates ---

# 步骤一：格式化原始小说文本
PREPROCESSING_PROMPT_TEMPLATE = """
你是一个小说文本格式化助手。请仔细阅读以下原始小说文本。
你的任务是【仅仅】添加结构化标记，【不要】改变原文内容或生成任何 KAG 脚本代码。
严格遵循以下规则：
1.  **识别说话人:** 如果通过上下文或直接提示（如“XXX说：”、“XXX问道：”）能明确判断出某句对话（通常在中文引号 `“...”` 或日文括号 `「...」` 内）的说话人，请在该对话行的【正上方】添加一行标记，格式为 `[说话人名字]`。
2.  **识别心声/内心独白:** 如果某段文字明显是角色的内心想法（通常没有引号，可能伴有“他想”、“她觉得”等提示，或者就是独立的思考句），请用 `*{{...}}*` 将其【完整地】包裹起来。确保开始和结束标记都存在。
3.  **保留原文:** 除了添加上述两种标记外，【完全保留】原文的所有文字、标点和换行符。不要删除、修改或添加任何其他内容。不要进行任何翻译或解释。
4.  **输出格式:** 直接输出带有标记的文本。不要包含任何代码块标记或额外的解释。
现在，请格式化以下文本：
--- RAW NOVEL TEXT START ---
{text_chunk}
--- RAW NOVEL TEXT END ---
Formatted Text Output:
"""

# 步骤二：根据人物设定和上下文【生成并添加】NAI 提示词标记
PROMPT_ENHANCEMENT_TEMPLATE = """
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
    *   如果只有正面或负面提示词（基础+动态），另一部分留空，但**必须保留分隔符 `|`**。例如: `[NAI:爱丽丝|1girl, blonde hair, smiling, classroom background||low quality, text]` 或 `[NAI:鲍勃|standing, looking serious|||worst quality]`。
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

Enhanced Text Output with Generated Prompts:
"""


# 步骤三：将带有提示词标记的文本转换为 KAG 脚本 (修正花括号转义)
KAG_CONVERSION_PROMPT_TEMPLATE = """
你是一个将【已格式化并包含 NAI 提示词标记】的小说文本转换为 KiriKiri2 KAG (ks) 脚本格式的专家。
输入文本已经包含了说话人标记 `[名字]`、心声标记 `*{{...}}*` 以及 NAI 提示词标记 `[NAI:名字|正面|负面]`。
严格按照以下规则进行转换，只输出 KAG 脚本代码，不要包含任何解释性文字或代码块标记。
专注于文本、对话、旁白和基本流程控制 `[p]`。
绝对不要生成任何与图像或声音相关的 KAG 标签（除了我们规则中定义的注释）。

规则：
1.  **处理 NAI 提示词标记 `[NAI:名字|正面|负面]`**: 当遇到此标记时，将其转换为 KAG 注释行，格式为：
    `; NAI Prompt for {{名字}}: Positive=[{{正面}}] Negative=[{{负面}}]` # <<< 修改在这里：使用了双花括号进行转义
    该注释行应出现在由该提示词引导的人物对话或动作之前。标记本身【不应】出现在最终的 KAG 输出中。
2.  **识别说话人标记 `[名字]`**: 当遇到此标记时，将其理解为下一行对话的说话人。标记本身【不应】出现在最终的 KAG 输出中。
3.  **处理对话（`“...”` 或 `「...」`）**:
    *   如果【前一行】是说话人标记 `[某名字]`，则输出：
        `[name]某名字[/name]`
        `对话内容（保留引号/括号）`
        `[p]`
    *   如果【前一行】不是说话人标记（例如是旁白或 NAI 注释后），则直接输出：
        `对话内容（保留引号/括号）`
        `[p]`
4.  **识别心声/内心独白 `*{{...}}*`**: 将其转换为普通文本输出（去除标记本身），并在其后添加 `[p]`：
    `内心独白内容`
    `[p]`
5.  **处理旁白/叙述**: 任何不符合上述 NAI 标记、对话或心声规则的、非空的文本行（除了说话人标记本身），都视为旁白输出，并在其后添加 `[p]`：
    `旁白内容`
    `[p]`
6.  **忽略空行**: 忽略输入文本中的空行。
7.  **结尾暂停**: 确保每个有效内容块（NAI 注释后的对话/旁白、普通对话、心声、旁白）后面都有一个 `[p]`（除了 NAI 注释本身后面不需要独立的 `[p]`）。
8.  **顺序**: NAI 注释应紧邻其关联的人物对话/动作之前。
9.  **输出格式**: 确保最终输出是纯净的 KAG 脚本文本。

现在，请将以下【已包含 NAI 标记的格式化文本】转换为 KAG 脚本：
--- ENHANCED FORMATTED TEXT CHUNK START ---
{text_chunk}
--- ENHANCED FORMATTED TEXT CHUNK END ---

KAG Script Output:
"""

# --- 可重用的流式响应助手 ---
def stream_google_response(api_key, api_base_url, model_name, prompt, temperature, max_output_tokens, prompt_type="Generic"):
    clean_base_url = api_base_url.rstrip('/')
    streaming_endpoint = f"{clean_base_url}/v1beta/models/{model_name}:streamGenerateContent?key={api_key}&alt=sse"
    generation_config = {}
    if temperature is not None: generation_config["temperature"] = temperature
    if max_output_tokens is not None: generation_config["maxOutputTokens"] = max_output_tokens
    payload = { "contents": [{"parts": [{"text": prompt}]}], **({"generationConfig": generation_config} if generation_config else {}) }
    headers = {"Content-Type": "application/json"}
    response = None
    try:
        print(f"连接流 ({prompt_type}): {streaming_endpoint.split('?')[0]}?key=HIDDEN&alt=sse")
        response = requests.post(streaming_endpoint, headers=headers, json=payload, stream=True, timeout=300)
        response.raise_for_status()
        current_data = ""
        for line_bytes in response.iter_lines():
            if not line_bytes:
                if current_data:
                    try:
                        sse_data_json = json.loads(current_data)
                        # print(f"--- 处理解析的 JSON ({prompt_type}): ---"); pprint.pprint(sse_data_json); print("--- 结束处理 JSON ---")
                        if 'promptFeedback' in sse_data_json: block_reason = sse_data_json['promptFeedback'].get('blockReason', 'Unknown'); error_message = f"输入 prompt 被阻止 ({prompt_type}). 原因: {block_reason}."; print(error_message); error_payload = json.dumps({"type": "error", "message": error_message}); yield f"event: error\ndata: {error_payload}\n\n"; return
                        if 'error' in sse_data_json: error_message = sse_data_json['error'].get('message', f'未知的 API 错误 ({prompt_type}).'); print(error_message); error_payload = json.dumps({"type": "error", "message": f"API 错误: {error_message}"}); yield f"event: error\ndata: {error_payload}\n\n"; return
                        if 'candidates' in sse_data_json and len(sse_data_json['candidates']) > 0:
                             candidate = sse_data_json['candidates'][0]
                             if 'content' in candidate and 'parts' in candidate['content'] and len(candidate['content']['parts']) > 0:
                                 text_chunk = candidate['content']['parts'][0].get('text', '')
                                 if text_chunk: chunk_payload = json.dumps({"type": "chunk", "content": text_chunk}); yield f"data: {chunk_payload}\n\n"
                             finish_reason = candidate.get('finishReason')
                             if finish_reason and finish_reason != 'STOP': print(f"流警告 ({prompt_type}): 结束原因: {finish_reason}"); warn_payload = json.dumps({"type": "warning", "message": f"生成停止: {finish_reason}"}); yield f"event: warning\ndata: {warn_payload}\n\n"
                    except json.JSONDecodeError as json_e: print(f"解析累积的 JSON 数据时出错 ({prompt_type}): {json_e} - 数据: {current_data}"); error_payload = json.dumps({"type": "error", "message": f"收到无效的 JSON 块: {current_data[:100]}..."}); yield f"event: error\ndata: {error_payload}\n\n"
                    current_data = ""
                continue
            try: line = line_bytes.decode('utf-8')
            except UnicodeDecodeError: print(f"警告: 因解码错误跳过行: {line_bytes}"); continue
            if line.startswith('data:'): current_data += line[5:].strip()
        if current_data:
             # print(f"处理流结束后剩余的数据: {current_data}")
             try:
                 sse_data_json = json.loads(current_data)
                 if 'promptFeedback' in sse_data_json: block_reason = sse_data_json['promptFeedback'].get('blockReason', 'Unknown'); error_message = f"输入 prompt 被阻止 ({prompt_type}). 原因: {block_reason}."; print(error_message); error_payload = json.dumps({"type": "error", "message": error_message}); yield f"event: error\ndata: {error_payload}\n\n"; return
                 if 'error' in sse_data_json: error_message = sse_data_json['error'].get('message', f'未知的 API 错误 ({prompt_type}).'); print(error_message); error_payload = json.dumps({"type": "error", "message": f"API 错误: {error_message}"}); yield f"event: error\ndata: {error_payload}\n\n"; return
                 if 'candidates' in sse_data_json and len(sse_data_json['candidates']) > 0:
                      candidate = sse_data_json['candidates'][0]
                      if 'content' in candidate and 'parts' in candidate['content'] and len(candidate['content']['parts']) > 0:
                          text_chunk = candidate['content']['parts'][0].get('text', '')
                          if text_chunk: chunk_payload = json.dumps({"type": "chunk", "content": text_chunk}); yield f"data: {chunk_payload}\n\n"
                      finish_reason = candidate.get('finishReason')
                      if finish_reason and finish_reason != 'STOP': print(f"最终流警告 ({prompt_type}): 结束原因: {finish_reason}"); warn_payload = json.dumps({"type": "warning", "message": f"Generation stopped: {finish_reason}"}); yield f"event: warning\ndata: {warn_payload}\n\n"
             except json.JSONDecodeError as json_e: print(f"解析最终累积的 JSON 数据时出错 ({prompt_type}): {json_e} - 数据: {current_data}"); error_payload = json.dumps({"type": "error", "message": f"无效的最终 JSON 块: {current_data[:100]}..."}); yield f"event: error\ndata: {error_payload}\n\n"
        print(f"Google API 流处理逻辑完成 ({prompt_type}).")
    except requests.exceptions.RequestException as e:
        print(f"API 流请求期间出错 ({prompt_type}): {e}")
        error_detail = str(e)
        if e.response is not None:
            try: json_error = e.response.json(); error_detail = json_error.get('error', {}).get('message', e.response.text)
            except json.JSONDecodeError: error_detail = e.response.text
        error_payload = json.dumps({"type": "error", "message": f"网络/请求错误 ({prompt_type}): {error_detail}"}); yield f"event: error\ndata: {error_payload}\n\n"; traceback.print_exc()
    except Exception as e:
        print(f"处理流时发生意外错误 ({prompt_type}): {e}")
        error_payload = json.dumps({"type": "error", "message": f"流处理期间内部服务器错误 ({prompt_type}): {e}"}); yield f"event: error\ndata: {error_payload}\n\n"; traceback.print_exc()
    finally:
        print(f"流生成器退出 ({prompt_type}).")
        if response:
            try:
                response.close()
                print("已关闭 Google API 响应流。")
            except Exception as close_err:
                print(f"关闭 Google API 响应流时出错 ({prompt_type}): {close_err}")

# --- 异步播放声音助手 ---
def play_sound_async(sound_path):
    if not PYGAME_AVAILABLE: print("[声音禁用] Pygame 不可用或 mixer 初始化失败。"); return
    if not sound_path or not isinstance(sound_path, str): print(f"无效的声音路径: {sound_path}"); return
    if not os.path.exists(sound_path): print(f"声音文件未找到: {sound_path}"); return
    def target():
        try:
            if not pygame.mixer.get_init(): pygame.mixer.init() # 如果未初始化，则尝试初始化
            if not pygame.mixer.get_init(): print("错误：无法初始化 mixer。无法播放声音。"); return
            print(f"尝试使用 pygame 加载声音: {sound_path}"); sound = pygame.mixer.Sound(sound_path)
            print(f"声音已加载。尝试播放..."); sound.play(); print(f"开始通过 pygame 播放声音: {sound_path}")
        except pygame.error as e: print(f"播放声音时出现 Pygame 错误 ({sound_path}): {e}"); traceback.print_exc()
        except Exception as e: print(f"播放 pygame 声音时出现意外错误 ({sound_path}): {e}"); traceback.print_exc()
    thread = threading.Thread(target=target); thread.daemon = True; thread.start()

# --- Flask 路由 ---
@app.route('/')
def index():
    # 渲染主页面
    return render_template('index.html')

@app.route('/save_config', methods=['POST'])
def save_config_api():
    # 保存服务器配置（API Key, URL, 模型, 声音路径等）到 config.json
    if not request.is_json: return jsonify({"error": "请求必须是 JSON 格式"}), 415
    data = request.get_json();
    if not data: return jsonify({"error": "无效的请求数据"}), 400
    config_to_save = {
        'apiKey': data.get('apiKey', ''),
        'apiEndpoint': data.get('apiEndpoint', ''),
        'modelName': data.get('modelName', ''),
        'temperature': data.get('temperature', None),
        'maxOutputTokens': data.get('maxOutputTokens', None),
        'successSoundPath': data.get('successSoundPath', ''),
        'failureSoundPath': data.get('failureSoundPath', '')
    }
    try:
        with open(CONFIG_FILENAME, 'w', encoding='utf-8') as f:
            json.dump(config_to_save, f, ensure_ascii=False, indent=4)
        print(f"配置已保存到 {CONFIG_FILENAME}");
        return jsonify({"message": "参数已成功保存到服务器文件。"}), 200
    except Exception as e:
        print(f"保存配置时发生错误: {e}"); traceback.print_exc();
        return jsonify({"error": f"保存配置失败: {e}"}), 500

@app.route('/load_config', methods=['GET'])
def load_config_api():
    # 从 config.json 加载服务器配置
    if not os.path.exists(CONFIG_FILENAME):
        print(f"配置文件 {CONFIG_FILENAME} 未找到。");
        return jsonify({}), 200
    try:
        with open(CONFIG_FILENAME, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        print(f"配置已从 {CONFIG_FILENAME} 加载。");
        return jsonify(config_data), 200
    except Exception as e:
        print(f"加载配置时发生错误: {e}"); traceback.print_exc();
        return jsonify({"error": f"加载配置失败: {e}"}), 500

@app.route('/play_sound', methods=['POST'])
def play_sound_api():
    # 请求播放成功或失败的声音
    if not PYGAME_AVAILABLE: return jsonify({"message": "声音在服务器上被禁用。"}), 202
    if not request.is_json: return jsonify({"error": "请求必须是 JSON 格式"}), 415
    data = request.get_json();
    if not data: return jsonify({"error": "无效的请求数据"}), 400
    status = data.get('status');
    if status not in ['success', 'failure']: return jsonify({"error": "无效的状态"}), 400
    config_data = {};
    if os.path.exists(CONFIG_FILENAME):
        try:
            with open(CONFIG_FILENAME, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
        except Exception as e:
            print(f"加载配置以播放声音时出错: {e}"); traceback.print_exc()
    sound_path = config_data.get('successSoundPath') if status == 'success' else config_data.get('failureSoundPath')
    if sound_path:
        play_sound_async(sound_path);
        return jsonify({"message": f"尝试播放 {status} 声音。"}), 202
    else:
        print(f"未为以下状态配置声音路径: {status}");
        return jsonify({"message": f"未配置 {status} 声音路径。"}), 202

# 步骤一 API：预处理原始文本
@app.route('/preprocess_stream', methods=['POST'])
def preprocess_stream_api():
    if not request.is_json: return jsonify({"error": "请求必须是 JSON 格式"}), 415
    data = request.get_json();
    if not data: return jsonify({"error": "无效的请求数据"}), 400
    api_key = data.get('api_key'); api_base_url = data.get('api_base_url'); model_name = data.get('model_name'); novel_text = data.get('novel_text'); pre_novel_text = data.get('pre_novel_text', ''); post_novel_text = data.get('post_novel_text', '')
    try:
        raw_temp = data.get('temperature'); temperature = float(raw_temp) if raw_temp is not None else None;
        if temperature is not None and (temperature < 0 or temperature > 2): temperature = None
        raw_max_tokens = data.get('max_output_tokens'); max_output_tokens = int(raw_max_tokens) if raw_max_tokens is not None else None;
        if max_output_tokens is not None and max_output_tokens < 1: max_output_tokens = None
    except (ValueError, TypeError) as e: return jsonify({"error": f"无效的数字参数格式: {e}"}), 400
    if not all([api_key, api_base_url, model_name, novel_text]): return jsonify({"error": "缺少 API Key, Base URL, Model Name, 或 Novel Text"}), 400
    if not api_base_url.startswith("https://"): return jsonify({"error": "无效的 API Base URL (应以 https:// 开头)"}), 400
    full_input_text_parts = [];
    if pre_novel_text: full_input_text_parts.append(pre_novel_text)
    if novel_text: full_input_text_parts.append(novel_text)
    if post_novel_text: full_input_text_parts.append(post_novel_text)
    full_input_text = "\n\n".join(full_input_text_parts).strip()
    if not full_input_text: return jsonify({"error": "组合后的输入文本为空。"}), 400
    try:
        preprocess_prompt = PREPROCESSING_PROMPT_TEMPLATE.format(text_chunk=full_input_text)
    except Exception as format_error:
        print(f"格式化 Preprocessing Prompt 时出错: {format_error}");
        return jsonify({"error": f"服务器内部错误：格式化 Preprocessing Prompt 失败。错误: {format_error}"}), 500
    def generate_preprocess_sse():
        header_payload = json.dumps({"type": "header", "content": "; Preprocessing Started...\n"}); yield f"data: {header_payload}\n\n"
        yield from stream_google_response( api_key, api_base_url, model_name, preprocess_prompt, temperature, max_output_tokens, prompt_type="Preprocessing" )
        footer_payload = json.dumps({"type": "footer", "content": "\n; Preprocessing Finished."}); yield f"data: {footer_payload}\n\n"
    return Response(generate_preprocess_sse(), mimetype='text/event-stream')

# 步骤二 API：添加 NAI 提示词
@app.route('/enhance_with_prompts_stream', methods=['POST'])
def enhance_with_prompts_stream_api():
    if not request.is_json: return jsonify({"error": "请求必须是 JSON 格式"}), 415
    data = request.get_json();
    if not data: return jsonify({"error": "无效的请求数据"}), 400
    api_key = data.get('api_key'); api_base_url = data.get('api_base_url'); model_name = data.get('model_name'); formatted_text = data.get('formatted_text'); character_profiles_str = data.get('character_profiles_json');
    try:
        raw_temp = data.get('temperature'); temperature = float(raw_temp) if raw_temp is not None else None;
        if temperature is not None and (temperature < 0 or temperature > 2): temperature = None
        raw_max_tokens = data.get('max_output_tokens'); max_output_tokens = int(raw_max_tokens) if raw_max_tokens is not None else None;
        if max_output_tokens is not None and max_output_tokens < 1: max_output_tokens = None
    except (ValueError, TypeError) as e: return jsonify({"error": f"无效的数字参数格式: {e}"}), 400
    if not all([api_key, api_base_url, model_name, formatted_text, character_profiles_str]): return jsonify({"error": "缺少 API Key, Base URL, Model Name, Formatted Text, 或 Character Profiles"}), 400
    if not api_base_url.startswith("https://"): return jsonify({"error": "无效的 API Base URL (应以 https:// 开头)"}), 400
    try:
        json.loads(character_profiles_str) # 简单验证 JSON
    except json.JSONDecodeError: return jsonify({"error": "无效的人物设定 JSON 格式。"}), 400
    try:
        # *** 使用修正后的 PROMPT_ENHANCEMENT_TEMPLATE ***
        enhancement_prompt = PROMPT_ENHANCEMENT_TEMPLATE.format(
            character_profiles_json=character_profiles_str,
            formatted_text_chunk=formatted_text
        )
    except Exception as format_error:
        # 捕捉并返回具体的格式化错误
        print(f"格式化 Prompt Enhancement Prompt 时出错: {format_error}");
        # 将 format_error 直接包含在返回的 JSON 中，方便前端显示
        return jsonify({"error": f"服务器内部错误：格式化 Prompt Enhancement Prompt 失败。错误: {format_error}"}), 500
    def generate_enhancement_sse():
        header_payload = json.dumps({"type": "header", "content": "; Prompt Enhancement Started...\n"}); yield f"data: {header_payload}\n\n"
        yield from stream_google_response( api_key, api_base_url, model_name, enhancement_prompt, temperature, max_output_tokens, prompt_type="PromptEnhancement" )
        footer_payload = json.dumps({"type": "footer", "content": "\n; Prompt Enhancement Finished."}); yield f"data: {footer_payload}\n\n"
    return Response(generate_enhancement_sse(), mimetype='text/event-stream')


# 步骤三 API：转换为 KAG 脚本
@app.route('/convert_stream', methods=['POST'])
def convert_stream_api():
     if not request.is_json: return jsonify({"error": "请求必须是 JSON 格式"}), 415
     data = request.get_json();
     if not data: return jsonify({"error": "无效的请求数据"}), 400
     api_key = data.get('api_key'); api_base_url = data.get('api_base_url'); model_name = data.get('model_name'); enhanced_text = data.get('enhanced_text'); # 输入是 enhanced_text
     try:
         raw_temp = data.get('temperature'); temperature = float(raw_temp) if raw_temp is not None else None;
         if temperature is not None and (temperature < 0 or temperature > 2): temperature = None
         raw_max_tokens = data.get('max_output_tokens'); max_output_tokens = int(raw_max_tokens) if raw_max_tokens is not None else None;
         if max_output_tokens is not None and max_output_tokens < 1: max_output_tokens = None
     except (ValueError, TypeError) as e: return jsonify({"error": f"无效的数字参数格式: {e}"}), 400
     if not all([api_key, api_base_url, model_name, enhanced_text]): return jsonify({"error": "缺少 API Key, Base URL, Model Name, 或 Enhanced Text"}), 400
     if not api_base_url.startswith("https://"): return jsonify({"error": "无效的 API Base URL (应以 https:// 开头)"}), 400
     try:
         kag_conversion_prompt = KAG_CONVERSION_PROMPT_TEMPLATE.format(text_chunk=enhanced_text)
     except Exception as format_error:
         print(f"格式化 KAG Conversion Prompt 时出错: {format_error}");
         return jsonify({"error": f"服务器内部错误：格式化 KAG Conversion Prompt 失败。错误: {format_error}"}), 500
     def generate_convert_sse():
        header_content = "; Generated KAG script (Streaming)\n"; header_content += "; Includes NAI prompt comments where applicable.\n"; header_content += "; Manual addition of visuals/audio/effects needed.\n\n"; header_content += "*start\n";
        header_payload = json.dumps({"type": "header", "content": header_content}); yield f"data: {header_payload}\n\n"
        yield from stream_google_response( api_key, api_base_url, model_name, kag_conversion_prompt, temperature, max_output_tokens, prompt_type="KAG Conversion" )
        footer_content = "\n@s ; Script End"; footer_payload = json.dumps({"type": "footer", "content": footer_content}); yield f"data: {footer_payload}\n\n"
     return Response(generate_convert_sse(), mimetype='text/event-stream')

# --- 运行 Flask 应用 ---
if __name__ == '__main__':
    # 使用 threaded=True 处理并发请求
    app.run(debug=True, host='127.0.0.1', port=5000, threaded=True)