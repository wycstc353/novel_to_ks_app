# workflow_tasks.py
"""
包含 WorkflowTab 后台任务的具体执行逻辑。
这些函数被设计为在单独的线程中运行。
"""
import re
import os
import time
import zipfile
import io
import base64
from pathlib import Path
import traceback

# 注意：这个文件需要能够访问 api_helpers 和 utils
# 可以通过参数传递实例，或者直接导入（如果它们是无状态的）
# 当前选择：让调用者 (WorkflowTab) 传递 api_helpers 实例
# utils 暂时只在 WorkflowTab 的 manual_replace_placeholders 中使用，不在此处需要

# --- LLM 相关任务 ---

def task_llm_preprocess(api_helpers, prompt_templates, llm_config, novel_text):
    """
    (非流式) 后台任务：调用 LLM 进行格式化。

    Args:
        api_helpers: api_helpers 模块的实例。
        prompt_templates: PromptTemplates 类的实例。
        llm_config (dict): LLM 配置字典。
        novel_text (str): 原始小说文本。

    Returns:
        tuple: (result: str or None, error: str or None)
    """
    print("执行后台任务：步骤一 - 格式化文本 (非流式)...")
    # 提取代理配置
    proxy_config = {k: llm_config.get(k) for k in ["use_proxy", "proxy_address", "proxy_port"]}
    # 构建 Prompt
    prompt = prompt_templates.PREPROCESSING_PROMPT_TEMPLATE.format(
        pre_instruction=llm_config.get('preInstruction',''),
        post_instruction=llm_config.get('postInstruction',''),
        text_chunk=novel_text
    )
    # 调用非流式 API 助手
    return api_helpers.call_google_non_stream(
        api_key=llm_config.get('apiKey'),
        api_base_url=llm_config.get('apiEndpoint'),
        model_name=llm_config.get('modelName'),
        prompt=prompt,
        temperature=llm_config.get('temperature'),
        max_output_tokens=llm_config.get('maxOutputTokens'),
        prompt_type="Preprocessing",
        proxy_config=proxy_config
    )

def task_llm_enhance(api_helpers, prompt_templates, llm_config, formatted_text, profiles_json):
    """
    (非流式) 后台任务：调用 LLM 添加提示词。

    Args:
        api_helpers: api_helpers 模块的实例。
        prompt_templates: PromptTemplates 类的实例。
        llm_config (dict): LLM 配置字典。
        formatted_text (str): 格式化后的文本。
        profiles_json (str): 人物设定 JSON 字符串。

    Returns:
        tuple: (result: str or None, error: str or None)
    """
    print("执行后台任务：步骤二 - 添加提示词 (非流式)...")
    # 检查人物设定 JSON 是否有效
    if profiles_json is None:
        return None, "错误: 缺少人物设定 JSON。"
    # 提取代理配置
    proxy_config = {k: llm_config.get(k) for k in ["use_proxy", "proxy_address", "proxy_port"]}
    # 构建 Prompt
    prompt = prompt_templates.PROMPT_ENHANCEMENT_TEMPLATE.format(
        pre_instruction=llm_config.get('preInstruction',''),
        post_instruction=llm_config.get('postInstruction',''),
        character_profiles_json=profiles_json,
        formatted_text_chunk=formatted_text
    )
    # 调用非流式 API 助手
    return api_helpers.call_google_non_stream(
        api_key=llm_config.get('apiKey'),
        api_base_url=llm_config.get('apiEndpoint'),
        model_name=llm_config.get('modelName'),
        prompt=prompt,
        temperature=llm_config.get('temperature'),
        max_output_tokens=llm_config.get('maxOutputTokens'),
        prompt_type="PromptEnhancement",
        proxy_config=proxy_config
    )

def task_llm_convert_to_kag(api_helpers, prompt_templates, llm_config, enhanced_text):
    """
    (非流式) 后台任务：调用 LLM 转换 KAG。

    Args:
        api_helpers: api_helpers 模块的实例。
        prompt_templates: PromptTemplates 类的实例。
        llm_config (dict): LLM 配置字典。
        enhanced_text (str): 包含提示词标记的文本。

    Returns:
        tuple: (result: str or None, error: str or None)
    """
    print("执行后台任务：步骤三 - 转换 KAG (非流式)...")
    # 提取代理配置
    proxy_config = {k: llm_config.get(k) for k in ["use_proxy", "proxy_address", "proxy_port"]}
    # 构建 Prompt
    prompt = prompt_templates.KAG_CONVERSION_PROMPT_TEMPLATE.format(
        pre_instruction=llm_config.get('preInstruction',''),
        post_instruction=llm_config.get('postInstruction',''),
        text_chunk=enhanced_text
    )
    # 调用非流式 API 助手获取脚本主体
    script_body, error = api_helpers.call_google_non_stream(
        api_key=llm_config.get('apiKey'),
        api_base_url=llm_config.get('apiEndpoint'),
        model_name=llm_config.get('modelName'),
        prompt=prompt,
        temperature=llm_config.get('temperature'),
        max_output_tokens=llm_config.get('maxOutputTokens'),
        prompt_type="KAGConversion",
        proxy_config=proxy_config
    )
    # 如果调用出错，直接返回错误
    if error:
        return None, error
    else:
        # 成功获取脚本主体，添加 KAG 脚本尾部
        # 注意：根据 KAG 模板，LLM 可能已经生成了 *start，这里不再添加
        # header = "*start\n"
        footer = "\n\n@s ; Script End" # KAG 脚本结束标签和注释
        final_script = (script_body or "") + footer # 组合最终脚本
        return final_script, None # 返回最终脚本和 None (表示无错误)


# --- 图片生成任务 ---

def task_generate_images(api_helpers, api_type, config, kag_script, generation_options):
    """
    后台任务：解析 KAG 脚本中的任务，调用 NAI 或 SD API 生成图片，
    并在成功后取消对应 image 标签的注释（保留提示词注释）。

    Args:
        api_helpers: api_helpers 模块的实例。
        api_type (str): "NAI" 或 "SD"。
        config (dict): 对应 API 的配置字典。
        kag_script (str): 包含注释掉的图片任务的 KAG 脚本。
        generation_options (dict): 生成选项，包括 scope, specific_files, n_samples。

    Returns:
        tuple: (result_dict, error_message)
               result_dict 包含 message, details, modified_script。
               error_message 在发生严重错误时返回。
    """
    print(f"执行图片生成后台任务 ({api_type})... Options: {generation_options}")
    # 解析生成选项
    scope = generation_options.get('scope', 'all') # 'all' 或 'specific'
    specific_files_str = generation_options.get('specific_files', '') # 逗号分隔的文件名字符串
    n_samples = generation_options.get('n_samples', 1) # 每个任务生成几张图
    n_samples = max(1, n_samples) # 确保至少生成1张

    # 如果是指定文件模式，处理文件名列表
    target_files = set()
    if scope == 'specific':
        target_files = set(f.strip() for f in specific_files_str.split(',') if f.strip())
        if not target_files:
            return {"message": f"错误：未指定有效的文件名。", "details": [], "modified_script": kag_script}, None

    # --- 解析 KAG 脚本中的图片生成任务 ---
    pattern = re.compile(
        r"^\s*"
        r"(;\s*NAI Prompt for\s*(.*?):\s*"
        r"Positive=\[(.*?)\]\s*"
        r"(?:Negative=\[(.*?)\])?)"
        r"\s*$\n\s*"
        r"(;\[image\s+storage=\"(.*?)\".*?\])",
        re.MULTILINE | re.IGNORECASE
    )

    all_tasks = []
    print(f"[{api_type} Gen] 开始解析 KAG 脚本寻找任务...")
    for match in pattern.finditer(kag_script):
        comment_line = match.group(1).strip() if match.group(1) else ""
        name = match.group(2).strip() if match.group(2) else "Unknown"
        positive = match.group(3).strip() if match.group(3) else ""
        negative = match.group(4).strip() if match.group(4) else ""
        commented_image_line = match.group(5).strip() if match.group(5) else ""
        filename = match.group(6).strip() if match.group(6) else ""

        if positive and filename and commented_image_line.startswith(';'):
            task_data = {
                "name": name, "positive": positive, "negative": negative,
                "filename": filename, "comment_line": comment_line,
                "commented_image_line": commented_image_line
            }
            all_tasks.append(task_data)
        else:
            print(f"警告 ({api_type}): 跳过无效或格式不匹配的任务。文件名: '{filename}', 注释图片行: '{commented_image_line[:50]}...'")

    print(f"[{api_type} Gen] 解析完成，共找到 {len(all_tasks)} 个潜在任务。")

    # --- 筛选需要执行的任务 ---
    tasks_to_run = []
    if scope == 'all':
        tasks_to_run = all_tasks
    else: # scope == 'specific'
        tasks_to_run = [t for t in all_tasks if t['filename'] in target_files]
        found_specific_files = {t['filename'] for t in tasks_to_run}
        missing_files = target_files - found_specific_files
        if missing_files:
            print(f"警告 ({api_type}): 指定的文件在 KAG 脚本中未找到对应任务: {', '.join(missing_files)}")
        if not tasks_to_run:
            return {"message": f"未在脚本中找到指定的有效任务文件: {specific_files_str}", "details": [], "modified_script": kag_script}, None

    if not tasks_to_run:
        return {"message": "未找到需要执行的有效图片生成任务。", "details": [], "modified_script": kag_script}, None

    print(f"[{api_type} Gen] 准备执行 {len(tasks_to_run)} 个任务。")

    # --- 准备 API 配置和保存路径 ---
    base_save_path = None
    api_key = None
    api_url = None
    nai_proxy_config = None

    if api_type == "NAI":
        api_key = config.get('naiApiKey')
        save_dir = config.get('naiImageSaveDir')
        if not api_key or not save_dir:
            return None, f"错误：NAI 配置不完整 (缺少 API Key 或保存目录)。"
        base_save_path = Path(save_dir)
        nai_proxy_config = {
            "nai_use_proxy": config.get("nai_use_proxy"),
            "nai_proxy_address": config.get("nai_proxy_address"),
            "nai_proxy_port": config.get("nai_proxy_port")
        }
    elif api_type == "SD":
        api_url = config.get('sdWebUiUrl')
        save_dir = config.get('sdImageSaveDir')
        if not api_url or not save_dir:
            return None, f"错误：SD 配置不完整 (缺少 WebUI URL 或保存目录)。"
        base_save_path = Path(save_dir)
    else:
        return None, f"错误：未知的 API 类型 '{api_type}'"

    try:
        base_save_path.mkdir(parents=True, exist_ok=True)
        test_file = base_save_path / f".write_test_{os.getpid()}"
        test_file.touch()
        test_file.unlink()
        print(f"[{api_type} Gen] 图片将保存到: {base_save_path.resolve()}")
    except Exception as e:
        error_msg = f"错误：图片保存目录 '{save_dir}' 处理失败 (无法创建或写入): {e}"
        print(error_msg)
        return None, error_msg

    # --- 循环执行任务 ---
    generated_count = 0
    failed_count = 0
    results_log = []
    lines_to_uncomment = set()

    for i, task in enumerate(tasks_to_run):
        print(f"--- [{api_type} Gen] {i+1}/{len(tasks_to_run)}: 处理任务 '{task['filename']}' (请求生成 {n_samples} 张) ---")
        filename_base, file_ext = os.path.splitext(task['filename'])
        file_ext = file_ext if file_ext else ".png"
        all_samples_successful = True
        task_error_msg = None
        image_data_list = []

        # --- 调用 API ---
        if api_type == "NAI":
            payload = {
                "action": "generate", "input": task['positive'], "model": config.get('naiModel'),
                "parameters": {
                    "width": 1024, "height": 1024, "scale": config.get('naiScale'),
                    "sampler": config.get('naiSampler'), "steps": config.get('naiSteps'),
                    "seed": config.get('naiSeed'), "n_samples": n_samples,
                    "ucPreset": config.get('naiUcPreset'), "qualityToggle": config.get('naiQualityToggle'),
                    "negative_prompt": task['negative']
                }
            }
            zip_data, task_error_msg = api_helpers.call_novelai_image_api(
                api_key, payload, proxy_config=nai_proxy_config
            )
            time.sleep(1)

            if zip_data and not task_error_msg:
                try:
                    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
                        print(f"  [NAI Gen] 解压 Zip 文件 ({len(zf.infolist())} 个文件)...")
                        extracted_count = 0
                        for img_info in zf.infolist():
                            if not img_info.is_dir() and img_info.filename.lower().endswith('.png') and extracted_count < n_samples:
                                print(f"    > 提取图片: {img_info.filename}")
                                image_data_list.append(zf.read(img_info.filename))
                                extracted_count += 1
                    if len(image_data_list) != n_samples:
                        print(f"警告: NAI 返回的 Zip 中 PNG 图片数量 ({len(image_data_list)}) 与请求数量 ({n_samples}) 不符!")
                    if not image_data_list:
                        task_error_msg = "错误: 从 NAI 返回的 Zip 文件中未能提取到任何 PNG 图片。"
                except zipfile.BadZipFile:
                    task_error_msg = "错误: NAI 返回的不是有效的 Zip 文件。"
                except Exception as zip_e:
                    task_error_msg = f"错误: 解压 NAI Zip 文件失败: {zip_e}"
                    traceback.print_exc()
            elif not task_error_msg:
                 task_error_msg = "错误: NAI API 调用成功但未返回数据。"

        elif api_type == "SD":
            final_positive = task['positive']
            add_pos = config.get('sdAdditionalPositivePrompt', '')
            if add_pos: final_positive += f", {add_pos}"
            final_negative = task['negative']
            add_neg = config.get('sdAdditionalNegativePrompt', '')
            if add_neg: final_negative = f"{final_negative}, {add_neg}" if final_negative else add_neg

            payload = {
                "prompt": final_positive.strip(', '), "negative_prompt": final_negative.strip(', '),
                "sampler_name": config.get('sdSampler'), "steps": config.get('sdSteps'),
                "cfg_scale": config.get('sdCfgScale'), "width": config.get('sdWidth'),
                "height": config.get('sdHeight'), "seed": config.get('sdSeed'),
                "restore_faces": config.get('sdRestoreFaces'), "tiling": config.get('sdTiling'),
                "n_iter": n_samples, "batch_size": 1
            }
            base64_image_list, task_error_msg = api_helpers.call_sd_webui_api(api_url, payload)
            time.sleep(0.2)

            if base64_image_list and not task_error_msg:
                if len(base64_image_list) != n_samples:
                     print(f"警告: SD API 返回图片数量 ({len(base64_image_list)}) 与请求数量 ({n_samples}) 不符!")
                for idx, b64_img in enumerate(base64_image_list):
                    if idx >= n_samples: break
                    try:
                        if isinstance(b64_img, str) and ',' in b64_img:
                            b64_img_data = b64_img.split(',', 1)[-1]
                        else:
                            b64_img_data = b64_img
                        image_data_list.append(base64.b64decode(b64_img_data))
                    except Exception as dec_e:
                        task_error_msg = f"错误: Base64 解码失败 (图片 {idx+1}): {dec_e}"
                        image_data_list = []
                        break
            elif not task_error_msg:
                task_error_msg = "错误: SD API 调用成功但未返回任何图片数据。"

        # --- 保存图片 ---
        if task_error_msg:
            all_samples_successful = False
            print(f"  [{api_type} Gen] API 调用或数据处理失败: {task_error_msg}")
        else:
            for sample_idx, img_data in enumerate(image_data_list):
                current_filename = f"{filename_base}_{sample_idx+1}{file_ext}" if n_samples > 1 else task['filename']
                try:
                    safe_filename = re.sub(r'[\\/:"*?<>|]', '_', current_filename)
                    target_path = base_save_path.joinpath(safe_filename).resolve()
                    if '..' in safe_filename or not target_path.is_relative_to(base_save_path.resolve()):
                        raise ValueError("检测到无效的文件名或路径穿越尝试。")
                    if target_path.suffix.lower() != '.png':
                        target_path = target_path.with_suffix('.png')
                        print(f"    > 修正文件后缀为 .png: {target_path.name}")
                    print(f"  [{api_type} Gen] 保存图片 {sample_idx+1}/{len(image_data_list)} -> {target_path}")
                    with open(target_path, 'wb') as f:
                        f.write(img_data)
                except Exception as save_e:
                    task_error_msg = f"错误: 保存图片 '{current_filename}' 到 '{target_path}' 时出错: {save_e}"
                    print(f"  [{api_type} Gen] 严重错误: {task_error_msg}")
                    traceback.print_exc()
                    all_samples_successful = False
                    break

        # --- 记录任务结果 ---
        if all_samples_successful:
            generated_count += 1
            log_msg = f"成功: {task['filename']} (生成 {len(image_data_list)}/{n_samples} 张并保存)"
            results_log.append(log_msg)
            print(f"  [{api_type} Gen] 任务成功: {log_msg}")
            lines_to_uncomment.add(task['commented_image_line'])
        else:
            failed_count += 1
            log_msg = f"失败 ({api_type}): {task['filename']} - {task_error_msg or '未知错误'}"
            results_log.append(log_msg)
            print(f"  [{api_type} Gen] 任务失败: {log_msg}")

    # --- 修改 KAG 脚本 (取消注释) ---
    print(f"[{api_type} Gen] 准备修改 KAG 脚本，取消 {len(lines_to_uncomment)} 个成功任务的注释...")
    modified_script_lines = []
    uncommented_count = 0
    for line in kag_script.splitlines():
        trimmed_line = line.strip()
        if trimmed_line in lines_to_uncomment:
            uncommented_line = line.lstrip(';').lstrip()
            modified_script_lines.append(uncommented_line)
            print(f"  > 取消注释: {uncommented_line}")
            uncommented_count += 1
        else:
            modified_script_lines.append(line)

    modified_script = "\n".join(modified_script_lines)
    print(f"[{api_type} Gen] KAG 脚本修改完成，共取消注释 {uncommented_count} 个图片标签。")

    # --- 返回最终结果 ---
    final_message = f"{api_type} 图片生成完成。成功任务: {generated_count}, 失败任务: {failed_count}."
    print(final_message)
    return {
        "message": final_message,
        "details": results_log,
        "modified_script": modified_script
    }, None