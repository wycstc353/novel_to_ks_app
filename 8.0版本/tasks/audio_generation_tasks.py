# tasks/audio_generation_tasks.py
"""
包含使用 GPT-SoVITS 生成语音的后台任务逻辑。
"""
import re
import os
import time
from pathlib import Path
import traceback
import hashlib # 用于生成基于对话内容的哈希，使文件名更稳定

# 注意：这个文件需要能够访问 api_helpers (或 gptsovits_api_helper)
# 调用者 (WorkflowTab) 会传递 api_helpers 实例

def task_generate_audio(api_helpers, gptsovits_config, kag_script, audio_prefix, generation_options):
    """
    后台任务：解析 KAG 脚本中的语音任务，调用 GPT-SoVITS API 生成音频，
    并在成功后取消对应 @playse 标签的注释。

    Args:
        api_helpers: api_helpers 模块的实例 (包含所有 API 调用函数)。
        gptsovits_config (dict): GPT-SoVITS 配置字典。
        kag_script (str): 包含注释掉的语音任务的 KAG 脚本。
        audio_prefix (str): 音频文件名前缀。
        generation_options (dict): 生成选项，包括 scope, specific_speakers。

    Returns:
        tuple: (result_dict, error_message)
               result_dict 包含 message, details, modified_script。
               error_message 在发生严重错误时返回。
    """
    print(f"执行语音生成后台任务 (GPT-SoVITS)... Options: {generation_options}")

    # --- 解析配置和选项 ---
    api_url = gptsovits_config.get("apiUrl")
    save_dir = gptsovits_config.get("audioSaveDir")
    voice_map = gptsovits_config.get("character_voice_map", {})
    default_params = {k: gptsovits_config.get(k) for k in ["how_to_cut", "top_k", "top_p", "temperature", "ref_free"]}

    scope = generation_options.get('scope', 'all') # 'all' 或 'specific'
    specific_speakers_str = generation_options.get('specific_speakers', '') # 逗号分隔的说话人名称字符串
    # n_samples 对语音意义不大，暂时忽略

    if not api_url or not save_dir:
        return None, "错误：GPT-SoVITS 配置不完整 (缺少 API URL 或保存目录)。"
    if not voice_map:
        return None, "错误：人物语音映射为空，请在 GPT-SoVITS 设置中配置。"

    # 处理指定说话人
    target_speakers = set()
    if scope == 'specific':
        target_speakers = set(s.strip() for s in specific_speakers_str.split(',') if s.strip())
        if not target_speakers:
            return {"message": "错误：未指定有效的说话人名称。", "details": [], "modified_script": kag_script}, None
        print(f"目标说话人: {target_speakers}")

    # --- 解析 KAG 脚本中的语音生成任务 ---
    # 正则表达式匹配注释掉的 @playse 标签和紧随其后的对话行
    # ; @playse storage="PLACEHOLDER_名字_序号.wav" buf=0 ; name="名字"
    # 「对话内容」[p]
    pattern = re.compile(
        r"^\s*"                                           # 行首空白
        r"(;?\s*@playse\s+storage=\"(.*?)\".*?;\s*name=\"(.*?)\")" # 捕获组1: 整个 @playse 行 (可能带分号); 捕获组2: 文件名占位符; 捕获组3: 说话人名称
        r"\s*$\n\s*"                                      # 行尾空白, 换行, 下一行行首空白
        r"「(.*?)」",                                     # 捕获组4: 对话内容 (不含引号)
        re.MULTILINE | re.IGNORECASE
    )

    all_tasks = []
    print("[Audio Gen] 开始解析 KAG 脚本寻找语音任务...")
    # 使用字典跟踪每个说话人的序号
    speaker_audio_counters = {}

    # 第一次遍历：收集所有任务并分配序号
    for match in pattern.finditer(kag_script):
        playse_line = match.group(1).strip()
        filename_placeholder = match.group(2).strip() # PLACEHOLDER_名字_序号.wav
        speaker_name = match.group(3).strip()
        dialogue_text = match.group(4).strip()

        # 检查是否是注释掉的任务
        if playse_line.startswith(';'):
            # 清理说话人名称，移除或替换非法字符
            sanitized_speaker_name = re.sub(r'[\\/*?:"<>|\s\.]+', '_', speaker_name)
            if not sanitized_speaker_name:
                print(f"警告: 跳过无效说话人名称的任务: {speaker_name}")
                continue

            # 计算序号
            speaker_audio_counters[sanitized_speaker_name] = speaker_audio_counters.get(sanitized_speaker_name, 0) + 1
            index = speaker_audio_counters[sanitized_speaker_name]

            # 生成实际文件名
            actual_filename = f"{audio_prefix}{sanitized_speaker_name}_{index}.wav"

            task_data = {
                "speaker": speaker_name, # 保留原始名称用于查找映射
                "dialogue": dialogue_text,
                "commented_playse_line": playse_line, # 原始注释行
                "actual_filename": actual_filename, # 实际要生成的文件名
                "line_index": match.start() # 记录匹配开始位置，用于后续替换
            }
            all_tasks.append(task_data)
        else:
             # 如果 @playse 行没有被注释，说明可能已经生成过了，跳过
             print(f"提示: 跳过已取消注释的语音任务: {playse_line}")


    print(f"[Audio Gen] 解析完成，共找到 {len(all_tasks)} 个潜在语音任务。")

    # --- 筛选需要执行的任务 ---
    tasks_to_run = []
    if scope == 'all':
        tasks_to_run = all_tasks
    else: # scope == 'specific'
        tasks_to_run = [t for t in all_tasks if t['speaker'] in target_speakers]
        found_specific_speakers = {t['speaker'] for t in tasks_to_run}
        missing_speakers = target_speakers - found_specific_speakers
        if missing_speakers:
            print(f"警告: 指定的说话人在 KAG 脚本中未找到对应任务: {', '.join(missing_speakers)}")
        if not tasks_to_run:
            return {"message": f"未在脚本中找到指定的有效说话人任务: {specific_speakers_str}", "details": [], "modified_script": kag_script}, None

    if not tasks_to_run:
        return {"message": "未找到需要执行的有效语音生成任务。", "details": [], "modified_script": kag_script}, None

    print(f"[Audio Gen] 准备执行 {len(tasks_to_run)} 个语音任务。")

    # --- 准备保存路径 ---
    base_save_path = Path(save_dir)
    try:
        base_save_path.mkdir(parents=True, exist_ok=True)
        test_file = base_save_path / f".write_test_{os.getpid()}"
        test_file.touch()
        test_file.unlink()
        print(f"[Audio Gen] 音频将保存到: {base_save_path.resolve()}")
    except Exception as e:
        error_msg = f"错误：音频保存目录 '{save_dir}' 处理失败 (无法创建或写入): {e}"
        print(error_msg)
        return None, error_msg

    # --- 循环执行任务 ---
    generated_count = 0
    failed_count = 0
    results_log = []
    lines_to_uncomment_map = {} # 存储需要取消注释的行 {原始行: 替换后的行}

    # 导入 GPT-SoVITS API 调用函数 (假设已添加到 api_helpers facade 或单独的文件)
    try:
        # 尝试从 api_helpers facade 导入
        call_gptsovits_api = api_helpers.call_gptsovits_api
    except AttributeError:
        # 如果 facade 中没有，尝试直接导入（如果创建了单独的文件）
        try:
            from api.gptsovits_api_helper import call_gptsovits_api
        except ImportError:
            return None, "错误：找不到 GPT-SoVITS API 调用函数 (call_gptsovits_api)。"


    for i, task in enumerate(tasks_to_run):
        speaker = task['speaker']
        dialogue = task['dialogue']
        actual_filename = task['actual_filename']
        commented_line = task['commented_playse_line']
        target_path = base_save_path.joinpath(actual_filename).resolve()

        print(f"--- [Audio Gen] {i+1}/{len(tasks_to_run)}: 处理任务 for '{speaker}' -> '{actual_filename}' ---")
        print(f"    对话: {dialogue[:50]}...")

        # 查找语音映射
        voice_config = voice_map.get(speaker)
        if not voice_config:
            log_msg = f"失败: 说话人 '{speaker}' 未在语音映射中找到配置。"
            print(f"  [Audio Gen] {log_msg}")
            results_log.append(log_msg)
            failed_count += 1
            continue # 跳过此任务

        # --- 构建 API Payload ---
        payload = {
            "refer_wav_path": voice_config.get("refer_wav_path"),
            "prompt_text": voice_config.get("prompt_text"),
            "prompt_language": voice_config.get("prompt_language"),
            "text": dialogue,
            "text_language": voice_config.get("prompt_language"), # 默认使用参考语言作为目标语言
            **default_params # 合并默认生成参数
        }

        # 检查必需参数是否存在
        if not all([payload["refer_wav_path"], payload["prompt_text"], payload["prompt_language"]]):
            log_msg = f"失败: 说话人 '{speaker}' 的语音映射配置不完整 (缺少参考路径/文本/语言)。"
            print(f"  [Audio Gen] {log_msg}")
            results_log.append(log_msg)
            failed_count += 1
            continue

        # --- 调用 API ---
        task_error_msg = None
        try:
            print(f"  [Audio Gen] 调用 GPT-SoVITS API (URL: {api_url})...")
            # 调用 API 函数，传递输出文件路径
            success, api_error = call_gptsovits_api(api_url, payload, str(target_path))
            if not success:
                task_error_msg = api_error or "未知 API 错误"
            # 短暂延迟
            time.sleep(0.2)

        except Exception as api_e:
            task_error_msg = f"调用 API 时发生意外错误: {api_e}"
            traceback.print_exc()

        # --- 记录结果 ---
        if task_error_msg:
            log_msg = f"失败: {actual_filename} (for {speaker}) - {task_error_msg}"
            print(f"  [Audio Gen] {log_msg}")
            results_log.append(log_msg)
            failed_count += 1
        else:
            log_msg = f"成功: {actual_filename} (for {speaker}) 已生成并保存。"
            print(f"  [Audio Gen] {log_msg}")
            results_log.append(log_msg)
            generated_count += 1
            # 准备替换注释行
            # 将原始注释行中的占位符文件名替换为实际文件名，并去掉开头的分号
            uncommented_line = commented_line.replace(
                re.search(r'storage="(.*?)"', commented_line).group(1), # 找到占位符文件名
                actual_filename # 替换为实际文件名
            ).lstrip(';').lstrip() # 去掉分号和前导空格
            lines_to_uncomment_map[commented_line] = uncommented_line # 存储映射关系

    # --- 修改 KAG 脚本 (取消注释) ---
    print(f"[Audio Gen] 准备修改 KAG 脚本，取消 {len(lines_to_uncomment_map)} 个成功任务的注释...")
    modified_script_lines = []
    uncommented_count = 0
    for line in kag_script.splitlines():
        trimmed_line = line.strip()
        # 检查当前行是否是需要取消注释的原始行
        if trimmed_line in lines_to_uncomment_map:
            replacement_line = lines_to_uncomment_map[trimmed_line]
            modified_script_lines.append(replacement_line)
            print(f"  > 取消注释并更新文件名: {replacement_line}")
            uncommented_count += 1
        else:
            modified_script_lines.append(line)

    modified_script = "\n".join(modified_script_lines)
    print(f"[Audio Gen] KAG 脚本修改完成，共取消注释 {uncommented_count} 个语音标签。")

    # --- 返回最终结果 ---
    final_message = f"GPT-SoVITS 语音生成完成。成功: {generated_count}, 失败: {failed_count}."
    print(final_message)
    return {
        "message": final_message,
        "details": results_log,
        "modified_script": modified_script
    }, None