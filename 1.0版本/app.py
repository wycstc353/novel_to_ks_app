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
    import pygame
    try:
        pygame.mixer.init()
        PYGAME_AVAILABLE = True
        print("Pygame mixer initialized successfully.")
    except pygame.error as init_err:
        print(f"WARNING: Failed to initialize pygame mixer: {init_err}")
        print("         Check audio drivers/devices. Sound playback using pygame will be disabled.")
        PYGAME_AVAILABLE = False
except ImportError:
    print("WARNING: pygame library not found.")
    print("         Install it using: pip install pygame")
    print("         Sound notification will be disabled.")

# --- Global Config ---
CONFIG_FILENAME = "config.json"
app = Flask(__name__)

# --- Prompt Templates ---
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

KAG_CONVERSION_PROMPT_TEMPLATE = """
你是一个将【已格式化】的小说文本转换为 KiriKiri2 KAG (ks) 脚本格式的专家。
输入文本已经包含了说话人标记 `[名字]` 和心声标记 `*{{...}}*`。
严格按照以下规则进行转换，只输出 KAG 脚本代码，不要包含任何解释性文字或代码块标记。
专注于文本、对话、旁白和基本流程控制 `[p]`。
绝对不要生成任何与图像或声音相关的标签。
规则：
1.  识别说话人标记 `[名字]`：当遇到此标记时，将其理解为下一行对话的说话人。
2.  处理对话（`“...”` 或 `「...」`）：
    *   如果【前一行】是说话人标记 `[某名字]`，则输出：
        `[name]某名字[/name]`
        `对话内容（保留引号/括号）`
        `[p]`
    *   如果【前一行】不是说话人标记，则直接输出：
        `对话内容（保留引号/括号）`
        `[p]`
3.  识别心声/内心独白 `*{{...}}*`：将其转换为普通文本输出（去除标记本身），并在其后添加 `[p]`：
    `内心独白内容`
    `[p]`
4.  处理旁白/叙述：任何不符合上述对话或心声规则的、非空的文本行（除了说话人标记本身），都视为旁白输出，并在其后添加 `[p]`：
    `旁白内容`
    `[p]`
5.  忽略说话人标记本身：识别到的说话人标记 `[名字]` 仅用于判断下一行对话归属，标记本身【不应】出现在最终的 KAG 输出中。
6.  处理空行：忽略输入文本中的空行。
7.  结尾暂停：确保每个有效内容块（对话、心声、旁白）后面都有一个 `[p]`。
8.  输出格式：确保最终输出是纯净的 KAG 脚本文本。
现在，请将以下【已格式化】的文本转换为 KAG 脚本：
--- FORMATTED TEXT CHUNK START ---
{text_chunk}
--- FORMATTED TEXT CHUNK END ---
KAG Script Output:
"""

# --- Reusable Streaming Helper (with Corrected Finally Block) ---
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
        print(f"Connecting to stream ({prompt_type}): {streaming_endpoint.split('?')[0]}?key=HIDDEN&alt=sse")
        response = requests.post(streaming_endpoint, headers=headers, json=payload, stream=True, timeout=300)
        response.raise_for_status()
        current_data = ""
        for line_bytes in response.iter_lines():
            if not line_bytes:
                if current_data:
                    try:
                        sse_data_json = json.loads(current_data)
                        print(f"--- Processing Parsed JSON ({prompt_type}): ---"); pprint.pprint(sse_data_json); print("--- End Processing JSON ---")
                        if 'promptFeedback' in sse_data_json: block_reason = sse_data_json['promptFeedback'].get('blockReason', 'Unknown'); error_message = f"Input prompt blocked ({prompt_type}). Reason: {block_reason}."; print(error_message); error_payload = json.dumps({"type": "error", "message": error_message}); yield f"event: error\ndata: {error_payload}\n\n"; return
                        if 'error' in sse_data_json: error_message = sse_data_json['error'].get('message', f'Unknown API error ({prompt_type}).'); print(error_message); error_payload = json.dumps({"type": "error", "message": f"API Error: {error_message}"}); yield f"event: error\ndata: {error_payload}\n\n"; return
                        if 'candidates' in sse_data_json and len(sse_data_json['candidates']) > 0:
                             candidate = sse_data_json['candidates'][0]
                             print(f"--- Candidate Object ({prompt_type}): ---"); pprint.pprint(candidate); print("--- End Candidate Object ---")
                             if 'content' in candidate and 'parts' in candidate['content'] and len(candidate['content']['parts']) > 0:
                                 print(f"--- Parts List ({prompt_type}): ---"); pprint.pprint(candidate['content']['parts']); print("--- End Parts List ---")
                                 text_chunk = candidate['content']['parts'][0].get('text', '')
                                 if text_chunk: print(f"--- Yielding Text Chunk ({prompt_type}): [{text_chunk}]"); chunk_payload = json.dumps({"type": "chunk", "content": text_chunk}); yield f"data: {chunk_payload}\n\n"
                                 else: print(f"--- Extracted Text Chunk is EMPTY ({prompt_type}) ---")
                             finish_reason = candidate.get('finishReason')
                             if finish_reason and finish_reason != 'STOP': print(f"Stream Warning ({prompt_type}): Finish Reason: {finish_reason}"); warn_payload = json.dumps({"type": "warning", "message": f"Generation stopped: {finish_reason}"}); yield f"event: warning\ndata: {warn_payload}\n\n"
                    except json.JSONDecodeError as json_e: print(f"Error parsing accumulated JSON data ({prompt_type}): {json_e} - Data: {current_data}"); error_payload = json.dumps({"type": "error", "message": f"Invalid JSON block received: {current_data[:100]}..."}); yield f"event: error\ndata: {error_payload}\n\n"
                    current_data = ""
                continue
            try: line = line_bytes.decode('utf-8')
            except UnicodeDecodeError: print(f"Warning: Skipping line due to decode error: {line_bytes}"); continue
            if line.startswith('data:'): current_data += line[5:].strip()
        if current_data:
             print(f"Processing remaining data after stream end: {current_data}")
             try:
                 sse_data_json = json.loads(current_data)
                 print(f"--- Processing Final Parsed JSON ({prompt_type}): ---"); pprint.pprint(sse_data_json); print("--- End Processing Final JSON ---")
                 if 'promptFeedback' in sse_data_json: block_reason = sse_data_json['promptFeedback'].get('blockReason', 'Unknown'); error_message = f"Input prompt blocked ({prompt_type}). Reason: {block_reason}."; print(error_message); error_payload = json.dumps({"type": "error", "message": error_message}); yield f"event: error\ndata: {error_payload}\n\n"; return
                 if 'error' in sse_data_json: error_message = sse_data_json['error'].get('message', f'Unknown API error ({prompt_type}).'); print(error_message); error_payload = json.dumps({"type": "error", "message": f"API Error: {error_message}"}); yield f"event: error\ndata: {error_payload}\n\n"; return
                 if 'candidates' in sse_data_json and len(sse_data_json['candidates']) > 0:
                      candidate = sse_data_json['candidates'][0]
                      print(f"--- Final Candidate Object ({prompt_type}): ---"); pprint.pprint(candidate); print("--- End Final Candidate Object ---")
                      if 'content' in candidate and 'parts' in candidate['content'] and len(candidate['content']['parts']) > 0:
                          print(f"--- Final Parts List ({prompt_type}): ---"); pprint.pprint(candidate['content']['parts']); print("--- End Final Parts List ---")
                          text_chunk = candidate['content']['parts'][0].get('text', '')
                          if text_chunk: print(f"--- Yielding Final Text Chunk ({prompt_type}): [{text_chunk}]"); chunk_payload = json.dumps({"type": "chunk", "content": text_chunk}); yield f"data: {chunk_payload}\n\n"
                          else: print(f"--- Extracted Final Text Chunk is EMPTY ({prompt_type}) ---")
                      finish_reason = candidate.get('finishReason')
                      if finish_reason and finish_reason != 'STOP': print(f"Final Stream Warning ({prompt_type}): Finish Reason: {finish_reason}"); warn_payload = json.dumps({"type": "warning", "message": f"Generation stopped: {finish_reason}"}); yield f"event: warning\ndata: {warn_payload}\n\n"
             except json.JSONDecodeError as json_e: print(f"Error parsing final accumulated JSON data ({prompt_type}): {json_e} - Data: {current_data}"); error_payload = json.dumps({"type": "error", "message": f"Invalid final JSON block: {current_data[:100]}..."}); yield f"event: error\ndata: {error_payload}\n\n"
        print(f"Google API stream processing logic finished ({prompt_type}).")
    except requests.exceptions.RequestException as e:
        print(f"Error during API streaming request ({prompt_type}): {e}")
        error_detail = str(e)
        if e.response is not None:
            try: json_error = e.response.json(); error_detail = json_error.get('error', {}).get('message', e.response.text)
            except json.JSONDecodeError: error_detail = e.response.text
        error_payload = json.dumps({"type": "error", "message": f"Network/Request Error ({prompt_type}): {error_detail}"}); yield f"event: error\ndata: {error_payload}\n\n"; traceback.print_exc()
    except Exception as e:
        print(f"Unexpected error processing stream ({prompt_type}): {e}")
        error_payload = json.dumps({"type": "error", "message": f"Internal Server Error during streaming ({prompt_type}): {e}"}); yield f"event: error\ndata: {error_payload}\n\n"; traceback.print_exc()
    # --- CORRECTED Finally Block ---
    finally:
        print(f"Stream generator exiting ({prompt_type}).")
        if response: # Check if response object exists before trying to close
            try:
                # Attempt to close the underlying connection
                response.close()
                print("Closed Google API response stream.")
            except Exception as close_err:
                # Log if closing fails, but don't crash
                print(f"Error closing Google API response stream ({prompt_type}): {close_err}")
    # --- End of Correction ---


# --- Helper to play sound using pygame.mixer ---
def play_sound_async(sound_path):
    if not PYGAME_AVAILABLE: print("[Sound Disabled] Pygame unavailable or mixer failed to initialize."); return
    if not sound_path or not isinstance(sound_path, str): print(f"Invalid sound path: {sound_path}"); return
    if not os.path.exists(sound_path): print(f"Sound file not found: {sound_path}"); return
    def target():
        try:
            if not pygame.mixer.get_init(): pygame.mixer.init() # Try to init if not already
            if not pygame.mixer.get_init(): print("Error: Failed to initialize mixer. Cannot play sound."); return
            print(f"Attempting to load sound with pygame: {sound_path}"); sound = pygame.mixer.Sound(sound_path)
            print(f"Sound loaded. Attempting to play..."); sound.play(); print(f"Started playing sound via pygame: {sound_path}")
        except pygame.error as e: print(f"Pygame Error playing sound ({sound_path}): {e}"); traceback.print_exc()
        except Exception as e: print(f"Unexpected error during pygame sound playback ({sound_path}): {e}"); traceback.print_exc()
    thread = threading.Thread(target=target); thread.daemon = True; thread.start()

# --- Flask Routes ---
@app.route('/')
def index(): return render_template('index.html')

@app.route('/save_config', methods=['POST'])
def save_config_api():
    if not request.is_json: return jsonify({"error": "请求必须是 JSON 格式"}), 415
    data = request.get_json();
    if not data: return jsonify({"error": "无效的请求数据"}), 400
    config_to_save = { 'apiKey': data.get('apiKey', ''), 'apiEndpoint': data.get('apiEndpoint', ''), 'modelName': data.get('modelName', ''), 'temperature': data.get('temperature', None), 'maxOutputTokens': data.get('maxOutputTokens', None), 'successSoundPath': data.get('successSoundPath', ''), 'failureSoundPath': data.get('failureSoundPath', '') }
    try:
        with open(CONFIG_FILENAME, 'w', encoding='utf-8') as f: json.dump(config_to_save, f, ensure_ascii=False, indent=4)
        print(f"配置已保存到 {CONFIG_FILENAME}"); return jsonify({"message": "参数已成功保存到服务器文件。"}), 200
    except Exception as e: print(f"保存配置时发生错误: {e}"); traceback.print_exc(); return jsonify({"error": f"保存配置失败: {e}"}), 500

@app.route('/load_config', methods=['GET'])
def load_config_api():
    if not os.path.exists(CONFIG_FILENAME): print(f"配置文件 {CONFIG_FILENAME} 未找到。"); return jsonify({}), 200
    try:
        with open(CONFIG_FILENAME, 'r', encoding='utf-8') as f: config_data = json.load(f)
        print(f"配置已从 {CONFIG_FILENAME} 加载。"); return jsonify(config_data), 200
    except Exception as e: print(f"加载配置时发生错误: {e}"); traceback.print_exc(); return jsonify({"error": f"加载配置失败: {e}"}), 500

@app.route('/play_sound', methods=['POST'])
def play_sound_api():
    if not PYGAME_AVAILABLE: return jsonify({"message": "Sound is disabled on the server."}), 202
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
            print(f"Error loading config for sound playback: {e}"); traceback.print_exc()
    sound_path = config_data.get('successSoundPath') if status == 'success' else config_data.get('failureSoundPath')
    if sound_path: play_sound_async(sound_path); return jsonify({"message": f"Attempting to play {status} sound."}), 202
    else: print(f"No sound path configured for: {status}"); return jsonify({"message": f"未配置 {status} 声音路径。"}), 202

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
    if not api_base_url.startswith("https://"): return jsonify({"error": "无效的 API Base URL"}), 400
    full_input_text_parts = [];
    if pre_novel_text: full_input_text_parts.append(pre_novel_text)
    if novel_text: full_input_text_parts.append(novel_text)
    if post_novel_text: full_input_text_parts.append(post_novel_text)
    full_input_text = "\n\n".join(full_input_text_parts).strip()
    if not full_input_text: return jsonify({"error": "组合后的输入文本为空。"}), 400
    try: preprocess_prompt = PREPROCESSING_PROMPT_TEMPLATE.format(text_chunk=full_input_text)
    except Exception as format_error: print(f"格式化 Preprocessing Prompt 时出错: {format_error}"); return jsonify({"error": f"服务器内部错误：格式化 Preprocessing Prompt 失败。错误: {format_error}"}), 500
    def generate_preprocess_sse():
        header_payload = json.dumps({"type": "header", "content": "; Preprocessing Started...\n"}); yield f"data: {header_payload}\n\n"
        yield from stream_google_response( api_key, api_base_url, model_name, preprocess_prompt, temperature, max_output_tokens, prompt_type="Preprocessing" )
        footer_payload = json.dumps({"type": "footer", "content": "\n; Preprocessing Finished."}); yield f"data: {footer_payload}\n\n"
    return Response(generate_preprocess_sse(), mimetype='text/event-stream')

@app.route('/convert_stream', methods=['POST'])
def convert_stream_api():
     if not request.is_json: return jsonify({"error": "请求必须是 JSON 格式"}), 415
     data = request.get_json();
     if not data: return jsonify({"error": "无效的请求数据"}), 400
     api_key = data.get('api_key'); api_base_url = data.get('api_base_url'); model_name = data.get('model_name'); structured_text = data.get('structured_text')
     try:
         raw_temp = data.get('temperature'); temperature = float(raw_temp) if raw_temp is not None else None;
         if temperature is not None and (temperature < 0 or temperature > 2): temperature = None
         raw_max_tokens = data.get('max_output_tokens'); max_output_tokens = int(raw_max_tokens) if raw_max_tokens is not None else None;
         if max_output_tokens is not None and max_output_tokens < 1: max_output_tokens = None
     except (ValueError, TypeError) as e: return jsonify({"error": f"无效的数字参数格式: {e}"}), 400
     if not all([api_key, api_base_url, model_name, structured_text]): return jsonify({"error": "缺少 API Key, Base URL, Model Name, 或 Structured Text"}), 400
     if not api_base_url.startswith("https://"): return jsonify({"error": "无效的 API Base URL"}), 400
     try: kag_conversion_prompt = KAG_CONVERSION_PROMPT_TEMPLATE.format(text_chunk=structured_text)
     except Exception as format_error: print(f"格式化 KAG Conversion Prompt 时出错: {format_error}"); return jsonify({"error": f"服务器内部错误：格式化 KAG Conversion Prompt 失败。错误: {format_error}"}), 500
     def generate_convert_sse():
        header_content = "; Generated KAG script (Streaming)\n"; header_content += f"; Params: Temp={temperature}, MaxOutput={max_output_tokens}\n"; header_content += "; Focuses on text conversion, manual addition of visuals/audio needed.\n\n"; header_content += "*start\n"; header_payload = json.dumps({"type": "header", "content": header_content}); yield f"data: {header_payload}\n\n"
        yield from stream_google_response( api_key, api_base_url, model_name, kag_conversion_prompt, temperature, max_output_tokens, prompt_type="KAG Conversion" )
        footer_content = "\n@s ; Script End"; footer_payload = json.dumps({"type": "footer", "content": footer_content}); yield f"data: {footer_payload}\n\n"
     return Response(generate_convert_sse(), mimetype='text/event-stream')

# --- 运行 Flask 应用 ---
if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000, threaded=True)