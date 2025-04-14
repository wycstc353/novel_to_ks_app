# tasks/audio_generation_tasks.py
import re
import os
import time
from pathlib import Path
import traceback
import hashlib
import codecs
import random
import copy # 导入 copy

# 语言代码到中文名称的映射
LANG_CODE_TO_NAME = {
    "zh": "中文", "en": "英语", "ja": "日语", "all_zh": "中英混合",
    "all_ja": "日英混合", "all_yue": "粤英混合", "all_ko": "韩英混合",
    "yue": "粤语", "ko": "韩语", "auto": "多语种混合", "auto_yue": "多语种混合(粤语)"
}

# 调试日志基础目录 (如果需要保存调试输入)
DEBUG_LOG_DIR = Path("debug_logs") / "api_requests"

def task_generate_audio(api_helpers, gptsovits_config, kag_script, audio_prefix, generation_options, save_debug=False):
    """
    后台任务：解析 KAG 脚本中的语音任务，调用 GPT-SoVITS API 生成音频，
    并在成功后取消对应 @playse 标签的注释。
    """
    print(f"执行语音生成后台任务 (GPT-SoVITS)... Options: {generation_options}, Save Debug: {save_debug}")

    # 从配置中获取基础信息
    api_url = gptsovits_config.get("apiUrl")
    model_name = gptsovits_config.get("model_name")
    save_dir = gptsovits_config.get("audioSaveDir")
    voice_map = gptsovits_config.get("character_voice_map", {})
    # 从配置中获取所有生成参数
    gen_params = {k: gptsovits_config.get(k) for k in [
        "how_to_cut", "top_k", "top_p", "temperature", "audio_dl_url",
        "batch_size", "batch_threshold", "split_bucket", "speed_facter",
        "fragment_interval", "parallel_infer", "repetition_penalty", "seed"
    ]}
    scope = generation_options.get('scope', 'all')
    specific_placeholder = generation_options.get('specific_speakers', '').strip()

    # 检查基础配置
    if not api_url or not save_dir or not model_name:
        return None, "错误：GPT-SoVITS 配置不完整 (缺少 API URL、模型名称或保存目录)。"
    if scope == 'specific' and not specific_placeholder:
         return {"message": "错误：未指定有效的语音文件名占位符。", "details": [], "modified_script": kag_script}, None
    if scope == 'specific':
        print(f"目标语音文件名占位符: '{specific_placeholder}'")

    # 解析 KAG 脚本中的语音生成任务 (对话或心声)
    pattern = re.compile(
        r"^\s*(;?\s*@playse\s+storage=\"(PLACEHOLDER_.*?)\".*?;\s*name=\"(.*?)\")\s*$\n\s*(?:「(.*?)」|\（(.*?)\）)\[p\]",
        re.MULTILINE | re.IGNORECASE
    )
    all_tasks = []
    print("[Audio Gen] 开始解析 KAG 脚本寻找语音任务 (对话和心声)...")
    speaker_audio_counters = {}
    for match in pattern.finditer(kag_script):
        playse_line = match.group(1).strip()
        original_placeholder = match.group(2).strip()
        speaker_name = match.group(3).strip()
        dialogue_content = match.group(4); monologue_content = match.group(5)
        text_to_speak = ""
        if dialogue_content is not None: text_to_speak = dialogue_content.strip()
        elif monologue_content is not None: text_to_speak = monologue_content.strip()

        if playse_line.startswith(';') and text_to_speak:
            sanitized_speaker_name = re.sub(r'[\\/*?:"<>|\s\.]+', '_', speaker_name)
            if not sanitized_speaker_name: print(f"警告: 跳过无效说话人名称的任务: {speaker_name}"); continue
            placeholder_match = re.match(r'PLACEHOLDER_(.*?)_(\d+)\.wav', original_placeholder)
            if placeholder_match: base_name = placeholder_match.group(1); index = int(placeholder_match.group(2)); actual_filename = f"{audio_prefix}{base_name}_{index}.wav"
            else: print(f"警告: 语音占位符格式不符 '{original_placeholder}'，尝试使用计数器生成文件名。"); speaker_audio_counters[sanitized_speaker_name] = speaker_audio_counters.get(sanitized_speaker_name, 0) + 1; index = speaker_audio_counters[sanitized_speaker_name]; actual_filename = f"{audio_prefix}{sanitized_speaker_name}_{index}.wav"
            task_data = {"speaker": speaker_name, "sanitized_speaker": sanitized_speaker_name, "dialogue": text_to_speak, "commented_playse_line": playse_line, "actual_filename": actual_filename, "line_index": match.start(), "original_placeholder": original_placeholder}
            all_tasks.append(task_data)
        elif not playse_line.startswith(';'): print(f"提示: 跳过已取消注释的语音任务: {playse_line}")
        elif not text_to_speak: print(f"警告: 找到注释的 @playse 行，但未能提取有效的对话或心声文本。 Playse 行: {playse_line}")

    print(f"[Audio Gen] 解析完成，共找到 {len(all_tasks)} 个潜在语音任务。")

    # 根据文件名占位符筛选任务
    tasks_to_run = []
    if scope == 'all': tasks_to_run = all_tasks
    elif scope == 'specific':
        tasks_to_run = [t for t in all_tasks if t['original_placeholder'] == specific_placeholder]
        if not tasks_to_run: print(f"警告: 未在 KAG 脚本中找到与指定占位符 '{specific_placeholder}' 完全匹配的待处理任务。"); return {"message": f"未在脚本中找到指定的待处理占位符任务: '{specific_placeholder}'", "details": [], "modified_script": kag_script}, None
        else: print(f"找到匹配占位符的任务: {tasks_to_run[0]['speaker']} - {tasks_to_run[0]['dialogue'][:20]}..."); tasks_to_run = tasks_to_run[:1]

    if not tasks_to_run: return {"message": "未找到需要执行的有效语音生成任务。", "details": [], "modified_script": kag_script}, None

    tag = "[Audio Gen]"; count = len(tasks_to_run); print(f"{tag} 准备执行 {count} 个语音任务。")

    # 检查和准备音频保存目录
    base_save_path = Path(save_dir)
    try: base_save_path.mkdir(parents=True, exist_ok=True); test_file = base_save_path / f".write_test_{os.getpid()}"; test_file.touch(); test_file.unlink(); print(f"{tag} 音频将保存到: {base_save_path.resolve()}")
    except Exception as e: error_msg = f"错误：音频保存目录 '{save_dir}' 处理失败 (无法创建或写入): {e}"; print(error_msg); return None, error_msg

    # 初始化计数器和日志
    generated_count = 0; failed_count = 0; results_log = []; lines_to_uncomment_map = {}

    # 获取 API 调用函数
    try: call_gptsovits_api = api_helpers.call_gptsovits_api
    except AttributeError:
        try: from api.gptsovits_api_helper import call_gptsovits_api
        except ImportError: return None, "错误：找不到 GPT-SoVITS API 调用函数 (call_gptsovits_api)。"

    # 循环处理每个任务
    for i, task in enumerate(tasks_to_run):
        speaker = task['speaker']; dialogue = task['dialogue']; actual_filename = task['actual_filename']
        commented_line = task['commented_playse_line']; target_path = base_save_path.joinpath(actual_filename).resolve()
        print(f"\n--- {tag} {i+1}/{count}: 处理任务 for '{speaker}' -> '{actual_filename}' ---"); print(f"    文本: {dialogue[:50]}...")
        ref_wav_path_for_api = None; prompt_text_for_api = ""; prompt_language_code = "zh"; text_language_code = "zh"; task_error_msg = None

        # 获取该角色的语音配置
        voice_config = voice_map.get(speaker)
        # 如果找不到配置，直接跳过，不计为失败
        if not voice_config or not isinstance(voice_config, dict):
            skip_msg = f"提示: 跳过任务，因为未在语音映射中找到说话人 '{speaker}' 的有效配置。"
            print(f"  {tag} {skip_msg}")
            results_log.append(skip_msg) # 记录跳过信息
            continue # 直接进入下一次循环
        else:
            # 处理 map 和 random 模式
            mode = voice_config.get("mode", "map"); prompt_language_code = voice_config.get("prompt_language", "zh"); text_language_code = voice_config.get("text_language", "zh")
            # --- 修改：修正随机模式逻辑 ---
            if mode == "random":
                char_random_folder_str = voice_config.get("refer_wav_path", "")
                char_random_folder_path = Path(char_random_folder_str) if char_random_folder_str else None
                print(f"    [随机模式] 查找文件夹: '{char_random_folder_path}'")
                if not char_random_folder_path or not char_random_folder_path.is_dir():
                    task_error_msg = f"随机模式错误：角色 '{speaker}' 未配置有效随机文件夹路径或路径无效。"
                else:
                    try:
                        wav_files = list(char_random_folder_path.glob("*.wav"))
                        if not wav_files:
                            task_error_msg = f"随机模式错误：在文件夹 '{char_random_folder_path}' 中未找到任何 .wav 文件。"
                        else:
                            # 1. 随机选择一个 WAV 文件
                            chosen_wav_path = random.choice(wav_files)
                            ref_wav_path_for_api = str(chosen_wav_path.resolve())
                            print(f"      > 随机选中 WAV: {chosen_wav_path.name}")

                            # 2. 根据选中的 WAV 文件名查找对应的文本文件
                            wav_filename_stem = chosen_wav_path.stem # 获取不带扩展名的文件名
                            corresponding_text_path = None
                            # 优先查找 .lab 文件
                            lab_path = char_random_folder_path / f"{wav_filename_stem}.lab"
                            if lab_path.is_file():
                                corresponding_text_path = lab_path
                            else:
                                # 如果没有 .lab，再查找 .txt 文件
                                txt_path = char_random_folder_path / f"{wav_filename_stem}.txt"
                                if txt_path.is_file():
                                    corresponding_text_path = txt_path

                            # 3. 检查是否找到了对应的文本文件
                            if corresponding_text_path:
                                print(f"      > 找到对应 Text: {corresponding_text_path.name}")
                                # 4. 读取对应的文本文件内容
                                try:
                                    try:
                                        with codecs.open(corresponding_text_path, 'r', encoding='utf-8') as f_text:
                                            prompt_text_for_api = f_text.read().strip()
                                    except UnicodeDecodeError:
                                        print(f"      > UTF-8 读取失败，尝试 GBK: {corresponding_text_path.name}")
                                        with codecs.open(corresponding_text_path, 'r', encoding='gbk', errors='ignore') as f_text:
                                            prompt_text_for_api = f_text.read().strip()
                                    print(f"      > 读取对应文本 ({corresponding_text_path.suffix}): {prompt_text_for_api[:30]}...")
                                except Exception as read_e:
                                    task_error_msg = f"随机模式错误：读取文本文件 '{corresponding_text_path.name}' 失败: {read_e}"
                            else:
                                # 如果找不到对应的文本文件
                                task_error_msg = f"随机模式错误：未能为选中的音频 '{chosen_wav_path.name}' 找到对应的 .lab 或 .txt 文件。"
                    except Exception as random_find_e:
                        task_error_msg = f"随机模式错误：查找或处理文件时出错: {random_find_e}"
                        traceback.print_exc()
            # --- 修改结束 ---
            elif mode == "map":
                print(f"    [映射模式] 使用 '{speaker}' 的配置...")
                ref_wav_path_for_api = voice_config.get("refer_wav_path"); prompt_text_for_api = voice_config.get("prompt_text")
                if not ref_wav_path_for_api or not prompt_text_for_api: task_error_msg = f"映射模式错误：说话人 '{speaker}' 的语音映射配置不完整 (缺少参考路径或文本)。"
                elif not Path(ref_wav_path_for_api).is_file(): task_error_msg = f"映射模式错误：配置的参考音频文件不存在或无效: '{ref_wav_path_for_api}'"
                else: print(f"      > 使用配置: WAV='{ref_wav_path_for_api}', Text='{prompt_text_for_api[:30]}...', PromptLang='{prompt_language_code}', TextLang='{text_language_code}'")
            else: task_error_msg = f"错误：说话人 '{speaker}' 配置了未知的模式 '{mode}'。"

        # 如果在处理模式时出错，记录失败并跳过
        if task_error_msg: log_msg = f"失败: {actual_filename} (for {speaker}) - {task_error_msg}"; print(f"  {tag} {log_msg}"); results_log.append(log_msg); failed_count += 1; continue

        # 将语言代码转换为 API 需要的语言名称
        prompt_language_name = LANG_CODE_TO_NAME.get(prompt_language_code, "中文"); text_language_name = LANG_CODE_TO_NAME.get(text_language_code, "中文")
        print(f"    > 转换语言代码: Prompt='{prompt_language_code}'->'{prompt_language_name}', Text='{text_language_code}'->'{text_language_name}'")

        # 构建传递给 API 助手的 payload
        payload = {
            "refer_wav_path": ref_wav_path_for_api, "prompt_text": prompt_text_for_api, "prompt_language": prompt_language_name,
            "text": dialogue, "text_language": text_language_name, "model_name": model_name,
            "how_to_cut": gen_params.get("how_to_cut", "按标点符号切"), "top_k": gen_params.get("top_k", 10), "top_p": gen_params.get("top_p", 1.0),
            "temperature": gen_params.get("temperature", 1.0), "audio_dl_url": gen_params.get("audio_dl_url", ""),
            "batch_size": gen_params.get("batch_size", 1), "batch_threshold": gen_params.get("batch_threshold", 0.75),
            "split_bucket": gen_params.get("split_bucket", True), "speed_facter": gen_params.get("speed_facter", 1.0),
            "fragment_interval": gen_params.get("fragment_interval", 0.3), "parallel_infer": gen_params.get("parallel_infer", True),
            "repetition_penalty": gen_params.get("repetition_penalty", 1.35), "seed": gen_params.get("seed", -1), "media_type": "wav"
        }

        # 保存调试输入
        if save_debug:
            try:
                api_type = "GPTSoVITS"; debug_save_dir = DEBUG_LOG_DIR / api_type.lower(); debug_save_dir.mkdir(parents=True, exist_ok=True)
                timestamp = time.strftime("%Y%m%d_%H%M%S"); safe_identifier = re.sub(r'[\\/*?:"<>|\s\.]+', '_', actual_filename or "payload"); filename = f"{timestamp}_{safe_identifier}.json"; filepath = debug_save_dir / filename
                payload_to_save = copy.deepcopy(payload); payload_to_save["refer_wav_path"] = "[Local Path Removed]"
                with open(filepath, 'w', encoding='utf-8') as f: json.dump(payload_to_save, f, ensure_ascii=False, indent=4)
                print(f"  [Debug Save] GPT-SoVITS 请求已保存到: {filepath}")
            except Exception as save_e: print(f"错误：保存 GPT-SoVITS 请求调试文件时出错: {save_e}"); traceback.print_exc()

        # 调用 API 生成音频
        api_call_error_msg = None; success = False; api_error = None
        try:
            print(f"  {tag} 调用 GPT-SoVITS API (URL: {api_url})...")
            print(f"  {tag} 准备发送的 audio_dl_url: '{payload.get('audio_dl_url')}'") # 打印确认
            success, api_error = call_gptsovits_api(api_url, payload, str(target_path), save_debug_inputs=False, identifier=actual_filename)
        except Exception as api_e: api_call_error_msg = f"调用 API 时发生意外错误: {api_e}"; traceback.print_exc(); success = False

        # 检查 API 调用结果
        if success is False and api_call_error_msg is None: api_call_error_msg = api_error or "未知 API 错误"

        # 处理最终结果
        if api_call_error_msg: log_msg = f"失败: {actual_filename} (for {speaker}) - {api_call_error_msg}"; print(f"  {tag} {log_msg}"); results_log.append(log_msg); failed_count += 1; continue
        else: log_msg = f"成功: {actual_filename} (for {speaker}) 已生成并保存。"; print(f"  {tag} {log_msg}"); results_log.append(log_msg); generated_count += 1; uncommented_line = commented_line.replace(task['original_placeholder'], actual_filename).lstrip(';').lstrip(); lines_to_uncomment_map[commented_line] = uncommented_line

        time.sleep(0.5) # 循环间延时

    # --- 所有任务处理完毕，修改 KAG 脚本 ---
    print(f"{tag} 所有任务处理完毕，准备修改 KAG 脚本，取消 {len(lines_to_uncomment_map)} 个成功任务的注释...")
    modified_script_lines = []; uncommented_count = 0
    for line in kag_script.splitlines():
        trimmed_line = line.strip()
        if trimmed_line in lines_to_uncomment_map: replacement_line = lines_to_uncomment_map[trimmed_line]; modified_script_lines.append(replacement_line); print(f"  > 取消注释并更新文件名: {replacement_line}"); uncommented_count += 1
        else: modified_script_lines.append(line)
    modified_script = "\n".join(modified_script_lines)
    print(f"{tag} KAG 脚本修改完成，共取消注释 {uncommented_count} 个语音标签。")

    # --- 返回最终结果 ---
    final_message = f"GPT-SoVITS 语音生成完成。成功: {generated_count}, 失败: {failed_count}."
    print(final_message)
    return {"message": final_message, "details": results_log, "modified_script": modified_script}, None