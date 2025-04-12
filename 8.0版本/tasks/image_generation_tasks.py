# tasks/image_generation_tasks.py
"""
包含图片生成后台任务的具体执行逻辑 (NAI 和 SD)。
"""
import re
import os
import time
import zipfile
import io
import base64
from pathlib import Path
import traceback

# 注意：这个文件需要能够访问 api_helpers 模块
# 调用者 (WorkflowTab) 会传递 api_helpers 实例

def task_generate_images(api_helpers, api_type, config, kag_script, generation_options):
    """
    后台任务：解析 KAG 脚本中的任务，调用 NAI 或 SD API 生成图片，
    并在成功后取消对应 image 标签的注释（保留提示词注释）。

    Args:
        api_helpers: api_helpers 模块的实例 (包含所有 API 调用函数)。
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
    # 正则表达式匹配提示词注释和紧随其后的注释掉的 image 标签
    # 注意：这里匹配的是手动替换后的注释掉的 image 标签，而不是占位符
    pattern = re.compile(
        r"^\s*"                                      # 行首空白
        r"(;\s*NAI Prompt for\s*(.*?):\s*"           # 捕获组1: 整个提示词注释行; 捕获组2: 名字
        r"Positive=\[(.*?)\]\s*"                     # 捕获组3: 正向提示
        r"(?:Negative=\[(.*?)\])?)"                  # 捕获组4: 负向提示 (可选)
        r"\s*$\n\s*"                                 # 行尾空白, 换行, 下一行行首空白
        r"(;\[image\s+storage=\"(.*?)\".*?\])",      # 捕获组5: 整个注释掉的 image 行; 捕获组6: 文件名
        re.MULTILINE | re.IGNORECASE                 # 多行匹配，忽略大小写
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

        # 确保提取到必要信息，并且 image 行确实是被注释掉的
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
        # 提取 NAI 代理配置
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

    # 检查保存目录是否可写
    try:
        base_save_path.mkdir(parents=True, exist_ok=True)
        # 尝试创建一个临时文件来测试写入权限
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
    lines_to_uncomment = set() # 存储需要取消注释的原始 image 行

    for i, task in enumerate(tasks_to_run):
        print(f"--- [{api_type} Gen] {i+1}/{len(tasks_to_run)}: 处理任务 '{task['filename']}' (请求生成 {n_samples} 张) ---")
        filename_base, file_ext = os.path.splitext(task['filename'])
        file_ext = file_ext if file_ext else ".png" # 确保有后缀，默认为 png
        all_samples_successful = True # 标记当前任务的所有样本是否都成功
        task_error_msg = None # 存储当前任务的错误信息
        image_data_list = [] # 存储当前任务获取到的图像数据 (bytes)

        # --- 调用 API ---
        if api_type == "NAI":
            # 构建 NAI API 请求体
            payload = {
                "action": "generate",
                "input": task['positive'],
                "model": config.get('naiModel'), # 从配置获取模型
                "parameters": {
                    "width": 1024, # NAI v3 常用尺寸
                    "height": 1024,
                    "scale": config.get('naiScale'),
                    "sampler": config.get('naiSampler'),
                    "steps": config.get('naiSteps'),
                    "seed": config.get('naiSeed'),
                    "n_samples": n_samples, # 请求生成 n_samples 张
                    "ucPreset": config.get('naiUcPreset'),
                    "qualityToggle": config.get('naiQualityToggle'),
                    "negative_prompt": task['negative']
                    # 可以根据需要添加更多 NAI 参数
                }
            }
            # 调用 NAI API 助手 (通过 api_helpers 实例)
            zip_data, task_error_msg = api_helpers.call_novelai_image_api(
                api_key, payload, proxy_config=nai_proxy_config # 传递代理配置
            )
            # 添加短暂延迟，避免过于频繁请求
            time.sleep(1)

            # 处理 NAI 返回的 Zip 数据
            if zip_data and not task_error_msg:
                try:
                    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
                        print(f"  [NAI Gen] 解压 Zip 文件 ({len(zf.infolist())} 个文件)...")
                        extracted_count = 0
                        for img_info in zf.infolist():
                            # 只处理非目录的 png 文件，且不超过请求数量
                            if not img_info.is_dir() and img_info.filename.lower().endswith('.png') and extracted_count < n_samples:
                                print(f"    > 提取图片: {img_info.filename}")
                                image_data_list.append(zf.read(img_info.filename))
                                extracted_count += 1
                        # 检查提取到的图片数量是否符合预期
                        if len(image_data_list) != n_samples:
                            print(f"警告: NAI 返回的 Zip 中 PNG 图片数量 ({len(image_data_list)}) 与请求数量 ({n_samples}) 不符!")
                        # 如果一张图片都没提取到
                        if not image_data_list:
                            task_error_msg = "错误: 从 NAI 返回的 Zip 文件中未能提取到任何 PNG 图片。"
                except zipfile.BadZipFile:
                    task_error_msg = "错误: NAI 返回的不是有效的 Zip 文件。"
                except Exception as zip_e:
                    task_error_msg = f"错误: 解压 NAI Zip 文件失败: {zip_e}"
                    traceback.print_exc()
            elif not task_error_msg:
                 # API 调用成功但没返回数据
                 task_error_msg = "错误: NAI API 调用成功但未返回数据。"

        elif api_type == "SD":
            # 组合基础提示词和全局附加提示词
            final_positive = task['positive']
            add_pos = config.get('sdAdditionalPositivePrompt', '')
            if add_pos: final_positive += f", {add_pos}"
            final_negative = task['negative']
            add_neg = config.get('sdAdditionalNegativePrompt', '')
            if add_neg: final_negative = f"{final_negative}, {add_neg}" if final_negative else add_neg

            # 构建 SD WebUI API 请求体
            payload = {
                "prompt": final_positive.strip(', '), # 去除可能多余的逗号和空格
                "negative_prompt": final_negative.strip(', '),
                "sampler_name": config.get('sdSampler'),
                "steps": config.get('sdSteps'),
                "cfg_scale": config.get('sdCfgScale'),
                "width": config.get('sdWidth'),
                "height": config.get('sdHeight'),
                "seed": config.get('sdSeed'),
                "restore_faces": config.get('sdRestoreFaces'),
                "tiling": config.get('sdTiling'),
                "n_iter": n_samples, # n_iter 控制生成批次数，相当于样本数
                "batch_size": 1 # 每次生成一张
                # 可以根据需要添加更多 SD API 参数，如 override_settings 等
            }
            # 调用 SD WebUI API 助手 (通过 api_helpers 实例)
            base64_image_list, task_error_msg = api_helpers.call_sd_webui_api(api_url, payload)
            # 添加短暂延迟
            time.sleep(0.2)

            # 处理 SD 返回的 Base64 图像列表
            if base64_image_list and not task_error_msg:
                # 检查返回数量
                if len(base64_image_list) != n_samples:
                     print(f"警告: SD API 返回图片数量 ({len(base64_image_list)}) 与请求数量 ({n_samples}) 不符!")
                # 解码 Base64
                for idx, b64_img in enumerate(base64_image_list):
                    if idx >= n_samples: break # 只处理请求数量的图片
                    try:
                        # 检查并去除可能的 data URI 前缀 (如 'data:image/png;base64,')
                        if isinstance(b64_img, str) and ',' in b64_img:
                            b64_img_data = b64_img.split(',', 1)[-1]
                        else:
                            b64_img_data = b64_img # 假设已经是纯 Base64 数据
                        # 解码并添加到列表
                        image_data_list.append(base64.b64decode(b64_img_data))
                    except Exception as dec_e:
                        task_error_msg = f"错误: Base64 解码失败 (图片 {idx+1}): {dec_e}"
                        image_data_list = [] # 解码失败则清空列表，标记任务失败
                        break # 停止处理后续图片
            elif not task_error_msg:
                # API 调用成功但没返回图像数据
                task_error_msg = "错误: SD API 调用成功但未返回任何图片数据。"

        # --- 保存图片 ---
        if task_error_msg:
            # 如果 API 调用或数据处理失败
            all_samples_successful = False
            print(f"  [{api_type} Gen] API 调用或数据处理失败: {task_error_msg}")
        else:
            # 循环保存每个样本
            for sample_idx, img_data in enumerate(image_data_list):
                # 如果生成多张，文件名添加序号 (e.g., image_1.png, image_2.png)
                current_filename = f"{filename_base}_{sample_idx+1}{file_ext}" if n_samples > 1 else task['filename']
                try:
                    # 清理文件名中的非法字符，替换为空格或下划线等
                    safe_filename = re.sub(r'[\\/:"*?<>|]', '_', current_filename)
                    # 构建完整的目标路径
                    target_path = base_save_path.joinpath(safe_filename).resolve()

                    # 安全检查：防止路径穿越或写入非预期目录
                    if '..' in safe_filename or not target_path.is_relative_to(base_save_path.resolve()):
                        raise ValueError("检测到无效的文件名或路径穿越尝试。")

                    # 确保文件后缀是 .png (API 可能返回其他格式，但我们强制保存为 png)
                    if target_path.suffix.lower() != '.png':
                        target_path = target_path.with_suffix('.png')
                        print(f"    > 修正文件后缀为 .png: {target_path.name}")

                    print(f"  [{api_type} Gen] 保存图片 {sample_idx+1}/{len(image_data_list)} -> {target_path}")
                    # 以二进制写入模式保存文件
                    with open(target_path, 'wb') as f:
                        f.write(img_data)
                except Exception as save_e:
                    # 保存文件时出错
                    task_error_msg = f"错误: 保存图片 '{current_filename}' 到 '{target_path}' 时出错: {save_e}"
                    print(f"  [{api_type} Gen] 严重错误: {task_error_msg}")
                    traceback.print_exc()
                    all_samples_successful = False # 标记任务失败
                    break # 停止保存后续样本

        # --- 记录任务结果 ---
        if all_samples_successful:
            generated_count += 1
            log_msg = f"成功: {task['filename']} (生成 {len(image_data_list)}/{n_samples} 张并保存)"
            results_log.append(log_msg)
            print(f"  [{api_type} Gen] 任务成功: {log_msg}")
            # 将需要取消注释的原始 image 行添加到集合中
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
    # 按行处理原始 KAG 脚本
    for line in kag_script.splitlines():
        trimmed_line = line.strip() # 去除首尾空格，方便比较
        # 如果当前行是需要取消注释的行
        if trimmed_line in lines_to_uncomment:
            # 移除行首的分号和可能的前导空格
            uncommented_line = line.lstrip(';').lstrip()
            modified_script_lines.append(uncommented_line)
            print(f"  > 取消注释: {uncommented_line}")
            uncommented_count += 1
        else:
            # 否则，保留原始行
            modified_script_lines.append(line)

    # 将处理后的行重新组合成脚本字符串
    modified_script = "\n".join(modified_script_lines)
    print(f"[{api_type} Gen] KAG 脚本修改完成，共取消注释 {uncommented_count} 个图片标签。")

    # --- 返回最终结果 ---
    final_message = f"{api_type} 图片生成完成。成功任务: {generated_count}, 失败任务: {failed_count}."
    print(final_message)
    # 返回包含消息、详细日志和修改后脚本的字典
    return {
        "message": final_message,
        "details": results_log,
        "modified_script": modified_script
    }, None # 第二个元素是错误信息，这里为 None 表示函数本身执行成功
