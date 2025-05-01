# tasks/audio_generation_tasks.py
import re # 功能性备注: 导入正则表达式模块
import os # 功能性备注: 导入操作系统模块
import time # 功能性备注: 导入时间模块
from pathlib import Path # 功能性备注: 导入 Path 对象
import copy # 导入 copy
import json # 导入 json
import codecs # 功能性备注: 导入 codecs 模块，用于文件编码
import random # 功能性备注: 导入 random 模块
import hashlib # 功能性备注: 导入 hashlib 模块
import logging # 功能性备注: 导入日志模块

# 功能性备注: 获取当前模块的 logger 实例
logger = logging.getLogger(__name__)

# 语言代码到中文名称的映射
LANG_CODE_TO_NAME = {
    "zh": "中文", "en": "英语", "ja": "日语", "all_zh": "中英混合",
    "all_ja": "日英混合", "all_yue": "粤英混合", "all_ko": "韩英混合",
    "yue": "粤语", "ko": "韩语", "auto": "多语种混合", "auto_yue": "多语种混合(粤语)"
}

# 调试日志基础目录 (如果需要保存调试输入)
DEBUG_LOG_DIR = Path("debug_logs") / "api_requests"

def task_generate_audio(api_helpers, gptsovits_config, kag_script, audio_prefix, generation_options, stop_event=None): # 功能性备注: 添加 stop_event 参数
    """
    后台任务：解析 KAG 脚本中的语音任务，调用 GPT-SoVITS API 生成音频，
    并在成功后取消对应 @playse 标签的注释。
    """
    # --- 获取调试开关 ---
    save_debug = gptsovits_config.get('saveGsvDebugInputs', False)
    logger.info(f"执行语音生成后台任务 (GPT-SoVITS)... Options: {generation_options}, Save Debug: {save_debug}")

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
    scope = generation_options.get('scope', 'all') # 逻辑修改: 默认值改为 'all' 或根据 UI 默认值调整
    specific_placeholder = generation_options.get('specific_speakers', '').strip()

    # 检查基础配置
    if not api_url or not save_dir or not model_name:
        err_msg = "错误：GPT-SoVITS 配置不完整 (缺少 API URL、模型名称或保存目录)。"
        logger.error(err_msg)
        return None, err_msg
    if scope == 'specific' and not specific_placeholder:
         err_msg = "错误：未指定有效的语音文件名占位符。"
         logger.error(err_msg)
         return {"message": err_msg, "details": [], "modified_script": kag_script}, None
    if scope == 'specific':
        logger.info(f"目标语音文件名占位符: '{specific_placeholder}'")

    # --- 解析 KAG 脚本中的语音生成任务 (逻辑修改: 识别注释和非注释标签) ---
    # 逻辑修改: 正则表达式捕获可选的分号，并记录是否被注释
    # Group 1: 完整的 @playse 行 (带或不带分号)
    # Group 2: 可选的分号 (表示被注释)
    # Group 3: @playse 标签内容 (不含分号)
    # Group 4: storage 中的占位符文件名
    # Group 5: name 属性中的说话人名字
    # Group 6: 对话内容 (「...」)
    # Group 7: 心声内容 (（...）)
    pattern = re.compile(
        r"^\s*((;?)(\s*@playse\s+storage=\"(PLACEHOLDER_.*?)\".*?;\s*name=\"(.*?)\"))\s*$\n\s*(?:「(.*?)」|\（(.*?)\）)\[p\]",
        re.MULTILINE | re.IGNORECASE
    )
    all_tasks = []
    logger.info("[Audio Gen] 开始解析 KAG 脚本寻找语音任务 (包括已生成和未生成的)...")
    speaker_audio_counters = {}
    for match in pattern.finditer(kag_script):
        full_playse_line = match.group(1).strip() # 完整的 @playse 行 (带或不带分号)
        is_commented = match.group(2) == ";" # 检查是否有分号
        playse_tag_content = match.group(3).strip() # 不含分号的 @playse 标签内容
        original_placeholder = match.group(4).strip()
        speaker_name = match.group(5).strip()
        dialogue_content = match.group(6); monologue_content = match.group(7)
        text_to_speak = ""
        if dialogue_content is not None: text_to_speak = dialogue_content.strip()
        elif monologue_content is not None: text_to_speak = monologue_content.strip()

        if text_to_speak: # 只要有文本就记录任务
            sanitized_speaker_name = re.sub(r'[\\/*?:"<>|\s\.]+', '_', speaker_name)
            if not sanitized_speaker_name: logger.warning(f"跳过无效说话人名称的任务: {speaker_name}"); continue
            placeholder_match = re.match(r'PLACEHOLDER_(.*?)_(\d+)\.wav', original_placeholder)
            if placeholder_match: base_name = placeholder_match.group(1); index = int(placeholder_match.group(2)); actual_filename = f"{audio_prefix}{base_name}_{index}.wav"
            else: logger.warning(f"语音占位符格式不符 '{original_placeholder}'，尝试使用计数器生成文件名。"); speaker_audio_counters[sanitized_speaker_name] = speaker_audio_counters.get(sanitized_speaker_name, 0) + 1; index = speaker_audio_counters[sanitized_speaker_name]; actual_filename = f"{audio_prefix}{sanitized_speaker_name}_{index}.wav"
            task_data = {
                "speaker": speaker_name,
                "sanitized_speaker": sanitized_speaker_name,
                "dialogue": text_to_speak,
                "full_playse_line": full_playse_line, # 存储完整的行 (带或不带分号)
                "playse_tag_content": playse_tag_content, # 存储不带分号的内容
                "actual_filename": actual_filename,
                "line_index": match.start(),
                "original_placeholder": original_placeholder,
                "is_commented": is_commented # 存储原始注释状态
            }
            all_tasks.append(task_data)
            logger.debug(f"  解析到语音任务: Speaker='{speaker_name}', File='{actual_filename}', Commented={is_commented}") # 功能性备注 (调试)
        elif not text_to_speak:
            logger.warning(f"找到 @playse 行，但未能提取有效的对话或心声文本。 Playse 行: {full_playse_line}")

    logger.info(f"[Audio Gen] 解析完成，共找到 {len(all_tasks)} 个潜在语音任务。")

    # --- 筛选需要执行的任务 (逻辑修改: 根据新的 scope) ---
    tasks_to_run = []
    if scope == 'all':
        tasks_to_run = all_tasks
    elif scope == 'uncommented': # 新增：未生成 (即被注释的)
        tasks_to_run = [t for t in all_tasks if t['is_commented']]
    elif scope == 'commented': # 新增：已生成 (即未被注释的)
        tasks_to_run = [t for t in all_tasks if not t['is_commented']]
    elif scope == 'specific':
        tasks_to_run = [t for t in all_tasks if t['original_placeholder'] == specific_placeholder]
        if not tasks_to_run: logger.warning(f"未在 KAG 脚本中找到与指定占位符 '{specific_placeholder}' 匹配的任务。"); return {"message": f"未在脚本中找到指定的占位符任务: '{specific_placeholder}'", "details": [], "modified_script": kag_script}, None
        else: logger.info(f"找到匹配占位符的任务: {tasks_to_run[0]['speaker']} - {tasks_to_run[0]['dialogue'][:20]}..."); tasks_to_run = tasks_to_run[:1] # 指定模式只处理第一个匹配项

    if not tasks_to_run:
        logger.info(f"根据范围 '{scope}' 未找到需要执行的有效语音生成任务。") # 功能性备注
        return {"message": f"根据范围 '{scope}' 未找到需要执行的有效语音生成任务。", "details": [], "modified_script": kag_script}, None
    logger.info(f"[Audio Gen] 根据范围 '{scope}' 筛选后，准备执行 {len(tasks_to_run)} 个任务。") # 功能性备注

    tag = "[Audio Gen]"; count = len(tasks_to_run); logger.info(f"{tag} 准备执行 {count} 个语音任务。")

    # 检查和准备音频保存目录
    base_save_path = Path(save_dir)
    try: base_save_path.mkdir(parents=True, exist_ok=True); test_file = base_save_path / f".write_test_{os.getpid()}"; test_file.touch(); test_file.unlink(); logger.info(f"{tag} 音频将保存到: {base_save_path.resolve()}")
    except Exception as e: error_msg = f"错误：音频保存目录 '{save_dir}' 处理失败 (无法创建或写入): {e}"; logger.exception(error_msg); return None, error_msg

    # 初始化计数器和日志
    generated_count = 0; failed_count = 0; results_log = []; lines_to_uncomment_map = {}

    # 获取 API 调用函数
    try: call_gptsovits_api = api_helpers.call_gptsovits_api
    except AttributeError:
        try: from api.gptsovits_api_helper import call_gptsovits_api
        except ImportError as e: err_msg = f"错误：找不到 GPT-SoVITS API 调用函数 (call_gptsovits_api)。ImportError: {e}"; logger.critical(err_msg); return None, err_msg

    # 循环处理每个任务
    for i, task in enumerate(tasks_to_run):
        # 逻辑备注: 在处理每个任务前检查停止信号
        if stop_event and stop_event.is_set():
            logger.info(f"任务在处理第 {i+1} 个语音任务之前被停止。") # 功能性备注
            task_error_msg = "任务被用户停止"
            break # 功能性备注: 跳出循环

        speaker = task['speaker']; dialogue = task['dialogue']; actual_filename = task['actual_filename']
        full_line = task['full_playse_line']; target_path = base_save_path.joinpath(actual_filename).resolve()
        logger.info(f"\n--- {tag} {i+1}/{count}: 处理任务 for '{speaker}' -> '{actual_filename}' (原始状态: {'已注释' if task['is_commented'] else '未注释'}) ---"); logger.info(f"    文本: {dialogue[:50]}...")
        ref_wav_path_for_api = None; prompt_text_for_api = ""; prompt_language_code = "zh"; text_language_code = "zh"; task_error_msg = None

        # 获取该角色的语音配置
        voice_config = voice_map.get(speaker)
        # 如果找不到配置，直接跳过，不计为失败
        if not voice_config or not isinstance(voice_config, dict):
            skip_msg = f"提示: 跳过任务，因为未在语音映射中找到说话人 '{speaker}' 的有效配置。"
            logger.warning(f"  {tag} {skip_msg}")
            results_log.append(skip_msg) # 记录跳过信息
            continue # 直接进入下一次循环
        else:
            # 处理 map 和 random 模式
            mode = voice_config.get("mode", "map"); prompt_language_code = voice_config.get("prompt_language", "zh"); text_language_code = voice_config.get("text_language", "zh")
            if mode == "random":
                char_random_folder_str = voice_config.get("refer_wav_path", "")
                char_random_folder_path = Path(char_random_folder_str) if char_random_folder_str else None
                logger.info(f"    [随机模式] 查找文件夹: '{char_random_folder_path}'")
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
                            logger.info(f"      > 随机选中 WAV: {chosen_wav_path.name}")

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
                                logger.info(f"      > 找到对应 Text: {corresponding_text_path.name}")
                                # 4. 读取对应的文本文件内容
                                try:
                                    try:
                                        with codecs.open(corresponding_text_path, 'r', encoding='utf-8') as f_text:
                                            prompt_text_for_api = f_text.read().strip()
                                    except UnicodeDecodeError:
                                        logger.warning(f"      > UTF-8 读取失败，尝试 GBK: {corresponding_text_path.name}")
                                        with codecs.open(corresponding_text_path, 'r', encoding='gbk', errors='ignore') as f_text:
                                            prompt_text_for_api = f_text.read().strip()
                                    logger.info(f"      > 读取对应文本 ({corresponding_text_path.suffix}): {prompt_text_for_api[:30]}...")
                                except Exception as read_e:
                                    task_error_msg = f"随机模式错误：读取文本文件 '{corresponding_text_path.name}' 失败: {read_e}"
                            else:
                                # 如果找不到对应的文本文件
                                task_error_msg = f"随机模式错误：未能为选中的音频 '{chosen_wav_path.name}' 找到对应的 .lab 或 .txt 文件。"
                    except Exception as random_find_e:
                        task_error_msg = f"随机模式错误：查找或处理文件时出错: {random_find_e}"
                        logger.exception(task_error_msg) # 使用 logger.exception 记录 traceback
            elif mode == "map":
                logger.info(f"    [映射模式] 使用 '{speaker}' 的配置...")
                ref_wav_path_for_api = voice_config.get("refer_wav_path"); prompt_text_for_api = voice_config.get("prompt_text")
                if not ref_wav_path_for_api or not prompt_text_for_api: task_error_msg = f"映射模式错误：说话人 '{speaker}' 的语音映射配置不完整 (缺少参考路径或文本)。"
                elif not Path(ref_wav_path_for_api).is_file(): task_error_msg = f"映射模式错误：配置的参考音频文件不存在或无效: '{ref_wav_path_for_api}'"
                else: logger.info(f"      > 使用配置: WAV='{ref_wav_path_for_api}', Text='{prompt_text_for_api[:30]}...', PromptLang='{prompt_language_code}', TextLang='{text_language_code}'")
            else: task_error_msg = f"错误：说话人 '{speaker}' 配置了未知的模式 '{mode}'。"

        # 如果在处理模式时出错，记录失败并跳过
        if task_error_msg: log_msg = f"失败: {actual_filename} (for {speaker}) - {task_error_msg}"; logger.error(f"  {tag} {log_msg}"); results_log.append(log_msg); failed_count += 1; continue

        # 将语言代码转换为 API 需要的语言名称
        prompt_language_name = LANG_CODE_TO_NAME.get(prompt_language_code, "中文"); text_language_name = LANG_CODE_TO_NAME.get(text_language_code, "中文")
        logger.info(f"    > 转换语言代码: Prompt='{prompt_language_code}'->'{prompt_language_name}', Text='{text_language_code}'->'{text_language_name}'")

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

        # 调用 API 生成音频
        api_call_error_msg = None; success = False; api_error = None
        try:
            # 逻辑备注: 在调用 API 前检查停止信号
            if stop_event and stop_event.is_set():
                logger.info(f"任务在调用 API for '{actual_filename}' 之前被停止。") # 功能性备注
                task_error_msg = "任务被用户停止"
                break # 功能性备注: 跳出循环

            logger.info(f"  {tag} 调用 GPT-SoVITS API (URL: {api_url})...")
            logger.debug(f"  {tag} 准备发送的 audio_dl_url: '{payload.get('audio_dl_url')}'") # 打印确认
            # 传递 save_debug 标志
            success, api_error = call_gptsovits_api(api_url, payload, str(target_path), save_debug_inputs=save_debug, identifier=actual_filename)

            # 逻辑备注: 在 API 调用后检查停止信号
            if stop_event and stop_event.is_set():
                logger.info(f"任务在 GPT-SoVITS API 调用后被停止，结果将被丢弃。") # 功能性备注
                task_error_msg = "任务被用户停止"
                break # 功能性备注: 跳出循环

        except Exception as api_e: api_call_error_msg = f"调用 API 时发生意外错误: {api_e}"; logger.exception(api_call_error_msg); success = False

        # 检查 API 调用结果
        if success is False and api_call_error_msg is None: api_call_error_msg = api_error or "未知 API 错误"

        # 处理最终结果
        if api_call_error_msg: log_msg = f"失败: {actual_filename} (for {speaker}) - {api_call_error_msg}"; logger.error(f"  {tag} {log_msg}"); results_log.append(log_msg); failed_count += 1; continue
        else:
            log_msg = f"成功: {actual_filename} (for {speaker}) 已生成并保存。"; logger.info(f"  {tag} {log_msg}"); results_log.append(log_msg); generated_count += 1;
            # 逻辑修改: 只有当任务原本是被注释的时候，才记录下来以便取消注释
            if task['is_commented']:
                uncommented_line = task['playse_tag_content'].replace(task['original_placeholder'], actual_filename) # 使用不带分号的内容
                lines_to_uncomment_map[task['full_playse_line']] = uncommented_line # 使用带分号的完整行作为 key

        time.sleep(0.5) # 循环间延时

    # --- 所有任务处理完毕，修改 KAG 脚本 ---
    logger.info(f"{tag} 所有任务处理完毕，准备修改 KAG 脚本，取消 {len(lines_to_uncomment_map)} 个成功任务的注释...") # 功能性备注
    modified_script_lines = []; uncommented_count = 0
    for line in kag_script.splitlines():
        trimmed_line = line.strip()
        # 逻辑修改: 使用带分号的完整行来匹配需要取消注释的行
        if trimmed_line in lines_to_uncomment_map:
            replacement_line = lines_to_uncomment_map[trimmed_line];
            modified_script_lines.append(replacement_line);
            logger.info(f"  > 取消注释并更新文件名: {replacement_line}");
            uncommented_count += 1
        else:
            modified_script_lines.append(line)
    modified_script = "\n".join(modified_script_lines)
    logger.info(f"{tag} KAG 脚本修改完成，共取消注释 {uncommented_count} 个语音标签。")

    # --- 返回最终结果 ---
    final_message = f"GPT-SoVITS 语音生成完成。成功: {generated_count}, 失败: {failed_count}."
    if task_error_msg == "任务被用户停止": # 逻辑备注: 如果是用户停止，修改最终消息
        final_message = f"GPT-SoVITS 语音生成任务被用户停止。成功任务: {generated_count}, 中断/失败任务: {failed_count + (len(tasks_to_run) - generated_count - failed_count)}."
    logger.info(final_message)
    return {"message": final_message, "details": results_log, "modified_script": modified_script}, None