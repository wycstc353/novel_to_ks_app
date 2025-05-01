# tasks/image_generation_tasks.py
import re # 功能性备注: 导入正则表达式模块，用于解析 KAG 脚本
import os # 功能性备注: 导入操作系统模块，用于路径操作和文件检查
import time # 功能性备注: 导入时间模块，用于生成时间戳和添加延时
import zipfile # 功能性备注: 导入 zipfile 模块，用于处理 NAI 返回的 Zip 文件
import io # 功能性备注: 导入 io 模块，用于内存中的字节流操作
import base64 # 功能性备注: 导入 base64 模块，用于图像数据的编码和解码
from pathlib import Path # 功能性备注: 导入 Path 对象，用于更方便地处理文件路径
import copy # 功能性备注: 导入 copy 模块，用于深拷贝工作流字典
import json # 功能性备注: 导入 json 模块，用于加载和保存 JSON 数据（例如 ComfyUI 工作流）
import uuid # 功能性备注: 导入 uuid 模块，用于生成 ComfyUI 的客户端 ID
import logging # 功能性备注: 导入日志模块
import random # 功能性备注: 导入 random 模块用于生成随机种子

# 功能性备注: 导入 ComfyUI API 助手中定义的上传函数
from api.comfyui_api_helper import upload_image_to_comfyui

# 功能性备注: 获取当前模块的 logger 实例
logger = logging.getLogger(__name__)

# --- 辅助函数 ---
def _find_node_id_by_title(workflow, title):
    """
    在工作流字典中根据节点标题查找节点 ID 和数据 (增强健壮性)。
    无论是否找到，都返回两个值 (node_id, node_data) 或 (None, None)。
    """
    # 逻辑备注: 检查输入标题和工作流数据的有效性
    if not title:
        return None, None
    if not workflow or not isinstance(workflow, dict):
        logger.warning(f"(_find_node_id_by_title): 工作流数据无效或为空 (类型: {type(workflow)})。") # 逻辑备注
        return None, None

    # 逻辑备注: 遍历工作流字典查找匹配的节点
    for node_id, node_data in workflow.items():
        # 逻辑备注: 增加更严格的检查，确保 node_data 和 _meta 结构符合预期
        if isinstance(node_data, dict) and \
           "_meta" in node_data and \
           isinstance(node_data.get("_meta"), dict) and \
           "title" in node_data["_meta"] and \
           node_data["_meta"].get("title") == title:
            # 功能性备注: 找到了匹配的节点
            return node_id, node_data # 返回 ID 和节点数据

    # 逻辑备注: 如果循环结束还没找到
    logger.warning(f"(_find_node_id_by_title): 未能在工作流中找到标题为 '{title}' 的节点。") # 逻辑备注
    return None, None # 确保在找不到时也返回两个 None

def _set_node_input(node_data, input_name, value):
    """安全地设置节点输入值"""
    # 逻辑备注: 检查节点数据和 inputs 键是否存在
    if isinstance(node_data, dict) and 'inputs' in node_data:
        # 逻辑备注: 如果输入值为 None，则尝试从节点输入中移除该键（使用 ComfyUI 默认值）
        if value is None:
             if input_name in node_data['inputs']:
                 logger.info(f"    - 输入值 '{input_name}' 为 None，将从节点输入中移除（使用默认）。") # 功能性备注
                 del node_data['inputs'][input_name]
             else:
                 logger.info(f"    - 输入值 '{input_name}' 为 None 且节点无此输入，跳过。") # 功能性备注
             return True
        else:
            # 逻辑备注: 设置或更新节点输入值
            node_data['inputs'][input_name] = value
            return True
    # 逻辑备注: 记录设置失败的警告
    logger.warning(f"    - 无法设置节点输入 '{input_name}'，节点数据无效或缺少 'inputs' 键。 Node Data: {str(node_data)[:100]}...") # 逻辑备注
    return False

# --- 主任务函数 ---
def task_generate_images(api_helpers, api_type, shared_config, specific_config, kag_script, generation_options, use_img2img_toggle, character_profiles, stop_event=None): # 功能性备注: 添加 stop_event 参数
    """
    后台任务：解析 KAG 脚本中的任务，调用所选 API 生成图片（支持文生图/图生图/内绘/LoRA），
    并在成功后取消对应 image 标签的注释。
    如果目标文件已存在，则在文件名后附加时间戳。
    """
    # --- 获取调试开关 ---
    save_debug = False
    # 逻辑备注: 根据 API 类型确定使用哪个配置中的调试开关
    if api_type == "NAI":
        save_debug = specific_config.get('saveNaiDebugInputs', False)
    elif api_type in ["SD WebUI", "ComfyUI"]:
        save_debug = shared_config.get('saveImageDebugInputs', False)
    logger.info(f"执行图片生成后台任务 ({api_type})... Options: {generation_options}, Img2Img Toggle: {use_img2img_toggle}, Save Debug: {save_debug}") # 功能性备注

    # 功能性备注: 获取生成范围和指定文件名
    scope = generation_options.get('scope', 'all') # 逻辑修改: 默认值改为 'all' 或根据 UI 默认值调整
    specific_files_str = generation_options.get('specific_files', '')
    n_samples = max(1, generation_options.get('n_samples', 1)) # 功能性备注: 获取生成数量，至少为 1

    target_files = set()
    # 逻辑备注: 如果是指定范围，解析文件名列表
    if scope == 'specific':
        target_files = set(f.strip() for f in specific_files_str.split(',') if f.strip())
        if not target_files:
            # 逻辑备注: 如果范围是 'specific' 但未指定文件名，则返回错误
            logger.error("选择了“指定”范围但未提供有效的文件名。") # 逻辑备注
            return {"message": "错误：选择了“指定”范围但未提供有效的文件名。", "details": [], "modified_script": kag_script}, None

    # --- 解析 KAG 脚本中的图片生成任务 (逻辑修改: 识别注释和非注释标签) ---
    # 逻辑修改: 正则表达式现在捕获可选的分号，并记录是否被注释
    pattern = re.compile(
        r"^\s*(;\s*(?:(NAI)|(IMG))\s+Prompt for\s*(.*?):\s*Positive=\[(.*?)\](?:\s*Negative=\[(.*?)\])?)\s*$\n" # NAI 或 IMG 行
        r"(?:\s*(;\s*SD Prompt for\s*.*?:?\s*Positive=\[.*?\](?:\s*Negative=\[.*?\])?)\s*$\n)?" # 可选的旧 SD 行
        r"\s*((;?)(\[image\s+storage=\"(.*?)\".*?\]))", # Image 行 (带可选分号)
        re.MULTILINE | re.IGNORECASE
    )
    all_tasks = []
    logger.info(f"[{api_type} Gen] 开始解析 KAG 脚本寻找任务 (包括已生成和未生成的)...") # 功能性备注
    for match in pattern.finditer(kag_script):
        # 功能性备注: 从匹配组中提取信息
        prompt_comment_line = match.group(1).strip() if match.group(1) else ""
        is_nai_prompt = match.group(2) == "NAI"
        is_img_prompt = match.group(3) == "IMG"
        name = match.group(4).strip() if match.group(4) else "Unknown"
        positive_from_line = match.group(5).strip() if match.group(5) else ""
        negative_from_line = match.group(6).strip() if match.group(6) is not None else ""
        full_image_line = match.group(8).strip() if match.group(8) else "" # 完整的 image 行 (带或不带分号)
        is_commented = match.group(9) == ";" # 检查是否有分号
        image_tag_content = match.group(10).strip() if match.group(10) else "" # 不含分号的 image 标签内容
        filename = match.group(11).strip() if match.group(11) else ""

        # 逻辑备注: 根据找到的注释行类型，分配提取到的提示词
        nai_positive = ""; nai_negative = ""; sd_positive = ""; sd_negative = ""
        if is_nai_prompt:
            nai_positive = positive_from_line
            nai_negative = negative_from_line
        elif is_img_prompt:
            sd_positive = positive_from_line # 将 IMG 行的提示词赋给 SD/Comfy 使用
            sd_negative = negative_from_line
        else:
            # 逻辑备注: 如果匹配成功但无法确定类型（理论上不应发生），记录警告
            logger.warning(f"解析任务时无法确定提示词类型 (NAI/IMG)。Name='{name}', File='{filename}'")
            continue # 跳过此任务

        # 逻辑备注: 根据 API 类型选择最终使用的提示词
        positive_prompt = ""; negative_prompt = ""
        if api_type == "NAI":
            positive_prompt = nai_positive
            negative_prompt = nai_negative
        elif api_type in ["SD WebUI", "ComfyUI"]:
            positive_prompt = sd_positive
            negative_prompt = sd_negative
        else: # 逻辑备注: 未知 API 类型，默认使用 SD/Comfy 提示词
            positive_prompt = sd_positive
            negative_prompt = sd_negative
            logger.warning(f"未知的 API 类型 '{api_type}'，将使用 SD/Comfy (IMG) 提示词。") # 逻辑备注

        # 逻辑备注: 确保提取到必要信息
        if (nai_positive or sd_positive) and filename: # 逻辑修改: 检查 nai_positive 或 sd_positive 是否有内容
            task_data = {
                "name": name,
                "positive": positive_prompt, # 功能性备注: 使用根据 API 类型选择的提示词
                "negative": negative_prompt, # 功能性备注: 使用根据 API 类型选择的提示词
                "filename": filename,
                "prompt_comment_line": prompt_comment_line, # 功能性备注: 保留原始 NAI 或 IMG 注释行
                "full_image_line": full_image_line, # 功能性备注: 完整的 image 行 (带或不带分号)
                "image_tag_content": image_tag_content, # 功能性备注: 不含分号的 image 标签内容
                "is_commented": is_commented # 功能性备注: 记录原始注释状态
            }
            all_tasks.append(task_data)
        else:
             # 逻辑备注: 打印警告，跳过无效或格式不匹配的任务
             logger.warning(f"({api_type}): 跳过无效或格式不匹配的任务。文件名: '{filename}', 完整图片行: '{full_image_line[:50]}...'") # 逻辑备注
    logger.info(f"[{api_type} Gen] 解析完成，共找到 {len(all_tasks)} 个潜在任务。") # 功能性备注

    # --- 筛选需要执行的任务 (逻辑修改: 根据新的 scope) ---
    tasks_to_run = []
    if scope == 'all':
        tasks_to_run = all_tasks
    elif scope == 'uncommented': # 新增：未生成 (即被注释的)
        tasks_to_run = [t for t in all_tasks if t['is_commented']]
    elif scope == 'commented': # 新增：已生成 (即未被注释的)
        tasks_to_run = [t for t in all_tasks if not t['is_commented']]
    elif scope == 'specific':
        tasks_to_run = [t for t in all_tasks if t['filename'] in target_files]
        missing_files = target_files - {t['filename'] for t in tasks_to_run}
        if missing_files:
            logger.warning(f"({api_type}): 指定的文件在 KAG 脚本中未找到对应任务: {', '.join(missing_files)}") # 逻辑备注
        if not tasks_to_run:
            # 逻辑备注: 如果指定了文件名但一个都没找到，返回错误信息
            logger.error(f"未在脚本中找到指定的有效任务文件: {specific_files_str}") # 逻辑备注
            return {"message": f"未在脚本中找到指定的有效任务文件: {specific_files_str}", "details": [], "modified_script": kag_script}, None
    # 逻辑备注: 如果最终没有任务需要执行 (无论是 'all' 还是 'specific' 筛选后)
    if not tasks_to_run:
        logger.info(f"根据范围 '{scope}' 未找到需要执行的有效图片生成任务。") # 功能性备注
        return {"message": f"根据范围 '{scope}' 未找到需要执行的有效图片生成任务。", "details": [], "modified_script": kag_script}, None
    logger.info(f"[{api_type} Gen] 根据范围 '{scope}' 筛选后，准备执行 {len(tasks_to_run)} 个任务。") # 功能性备注

    # --- 准备 API 配置和保存路径 (保持不变) ---
    base_save_path = None; api_key = None; api_url = None; nai_proxy_config = None; workflow_file_path = None; base_workflow = None
    # 功能性备注: 获取共享配置中的保存目录
    save_dir = shared_config.get("imageSaveDir")
    if not save_dir:
        # 逻辑备注: 缺少保存目录配置，返回错误
        err_msg = "错误：共享图片配置中未指定图片保存目录。"
        logger.error(err_msg) # 逻辑备注
        return None, err_msg
    base_save_path = Path(save_dir)
    try:
        # 功能性备注: 创建目录并测试写入权限
        base_save_path.mkdir(parents=True, exist_ok=True)
        test_file = base_save_path / f".write_test_{os.getpid()}"
        test_file.touch()
        test_file.unlink()
        logger.info(f"[{api_type} Gen] 图片将保存到: {base_save_path.resolve()}") # 功能性备注
    except Exception as e:
        # 逻辑备注: 目录处理失败，返回错误
        err_msg = f"错误：图片保存目录 '{save_dir}' 处理失败: {e}"
        logger.exception(err_msg) # 逻辑备注
        return None, err_msg

    # 功能性备注: 根据 API 类型加载特定配置
    if api_type == "NAI":
        api_key = specific_config.get('naiApiKey')
        nai_proxy_config = {k: specific_config.get(k) for k in ["nai_use_proxy", "nai_proxy_address", "nai_proxy_port"]}
        if not api_key: logger.error("NAI API Key 未配置。"); return None, "错误：NAI API Key 未配置。" # 逻辑备注
    elif api_type == "SD WebUI":
        api_url = specific_config.get('sdWebUiUrl')
        if not api_url: logger.error("SD WebUI URL 未配置。"); return None, "错误：SD WebUI URL 未配置。" # 逻辑备注
    elif api_type == "ComfyUI":
        api_url = specific_config.get('comfyapiUrl')
        workflow_file_path = specific_config.get('comfyWorkflowFile')
        if not api_url: logger.error("ComfyUI URL 未配置。"); return None, "错误：ComfyUI URL 未配置。" # 逻辑备注
        if not workflow_file_path or not Path(workflow_file_path).is_file():
            # 逻辑备注: Comfy 工作流文件无效或不存在，返回错误
            err_msg = f"错误：ComfyUI 工作流文件路径无效或文件不存在: '{workflow_file_path}'"
            logger.error(err_msg) # 逻辑备注
            return None, err_msg
        try:
            # 功能性备注: 加载基础工作流 JSON 文件
            with open(workflow_file_path, 'r', encoding='utf-8') as f:
                base_workflow = json.load(f)
            logger.info(f"[{api_type} Gen] 成功加载基础工作流: {workflow_file_path}") # 功能性备注
        except Exception as e:
            # 逻辑备注: 加载或解析工作流失败，返回错误
            err_msg = f"错误：加载或解析 ComfyUI 工作流文件失败: {e}"
            logger.exception(err_msg) # 逻辑备注
            return None, err_msg
    else:
        # 逻辑备注: 未知的 API 类型，返回错误
        err_msg = f"错误：未知的 API 类型 '{api_type}'"
        logger.error(err_msg) # 逻辑备注
        return None, err_msg

    # --- 循环执行任务 ---
    generated_count = 0; failed_count = 0; results_log = []; lines_to_uncomment = set()

    for i, task in enumerate(tasks_to_run):
        # 逻辑备注: 在处理每个任务前检查停止信号
        if stop_event and stop_event.is_set():
            logger.info(f"任务在处理 '{task['filename']}' 之前被停止。") # 功能性备注
            task_error_msg = "任务被用户停止"
            break # 功能性备注: 跳出循环

        logger.info(f"\n--- [{api_type} Gen] {i+1}/{len(tasks_to_run)}: 处理任务 '{task['filename']}' (原始状态: {'已注释' if task['is_commented'] else '未注释'}, 请求生成 {n_samples} 张) ---") # 功能性备注
        filename_base, file_ext = os.path.splitext(task['filename']); file_ext = file_ext if file_ext else ".png"
        all_samples_successful = True; task_error_msg = None; image_data_list = []
        is_img2img_mode_active = False # 功能性备注: 标记当前任务是否执行图生图
        init_image_path = None
        init_image_b64 = None
        mask_path = None
        mask_b64 = None
        task_loras = [] # 功能性备注: 存储当前任务应用的 LoRA

        # 功能性备注: 获取当前任务对应的人物设定数据
        profile_data = character_profiles.get(task['name'])
        if isinstance(profile_data, dict):
            task_loras = profile_data.get("loras", []) # 获取 LoRA 列表
            if not isinstance(task_loras, list): task_loras = [] # 确保是列表
        else:
            profile_data = {} # 如果找不到人物，则为空字典

        # 功能性备注: 检查图生图/内绘条件
        if use_img2img_toggle: # 检查全局开关是否打开
            init_image_path = profile_data.get("image_path", "").strip()
            if init_image_path and os.path.exists(init_image_path):
                is_img2img_mode_active = True # 只有开关打开且路径有效才激活
                logger.info(f"  - 图生图模式已激活，使用参考图: {init_image_path}") # 功能性备注
                # 功能性备注: 读取并编码参考图 (Base64) - 仅 NAI 和 SD 需要在此步骤处理
                if api_type in ["NAI", "SD WebUI"]:
                    try:
                        with open(init_image_path, "rb") as img_file:
                            init_image_b64 = base64.b64encode(img_file.read()).decode('utf-8')
                        logger.info(f"  - 参考图已读取并编码为 Base64。") # 功能性备注
                    except Exception as img_read_e:
                        task_error_msg = f"错误：读取或编码参考图像 '{init_image_path}' 失败: {img_read_e}"
                        logger.exception(f"  - {task_error_msg}"); is_img2img_mode_active = False; init_image_b64 = None # 逻辑备注
                # 功能性备注: 检查并读取蒙版图 (可选) - 仅在参考图成功加载后进行
                if is_img2img_mode_active:
                    mask_path = profile_data.get("mask_path", "").strip()
                    if mask_path and os.path.exists(mask_path):
                        logger.info(f"  - 检测到蒙版图像: {mask_path}") # 功能性备注
                        # 功能性备注: NAI 和 SD 需要 Base64 编码
                        if api_type in ["NAI", "SD WebUI"]:
                            try:
                                 with open(mask_path, "rb") as mask_file:
                                     mask_b64 = base64.b64encode(mask_file.read()).decode('utf-8')
                                 logger.info(f"  - 蒙版图像已读取并编码为 Base64。将执行内/外绘模式。") # 功能性备注
                            except Exception as mask_read_e:
                                 logger.warning(f"  - 读取或编码蒙版图像失败: {mask_read_e}，将执行标准图生图。") # 逻辑备注
                                 mask_b64 = None
                        # 逻辑备注: 如果蒙版路径无效
                        elif mask_path:
                             logger.warning(f"  - 配置了蒙版路径但文件无效: '{mask_path}'，将执行标准图生图。") # 逻辑备注
                        else:
                             logger.info("  - 未配置蒙版图像，将执行标准图生图。") # 功能性备注
            # 逻辑备注: 处理参考图路径无效或未配置的情况
            elif init_image_path:
                 logger.warning(f"  - 图生图开关已启用，但人物 '{task['name']}' 的参考图路径无效或不存在，执行文生图。") # 逻辑备注
            else:
                 logger.info(f"  - 图生图开关已启用，但人物 '{task['name']}' 未配置参考图，执行文生图。") # 功能性备注
        else:
            logger.info("  - 图生图开关未启用，执行文生图。") # 功能性备注

        # --- *** 逻辑修改：确定当前任务使用的种子值 *** ---
        current_task_seed = -1 # 默认值
        if api_type == "NAI":
            if specific_config.get('naiRandomSeed', False):
                current_task_seed = random.randint(1, 2**31 - 1)
                logger.info(f"  - NAI 任务 '{task['filename']}' 使用客户端生成的随机种子: {current_task_seed}") # 功能性备注
            else:
                current_task_seed = specific_config.get('naiSeed', -1)
                logger.info(f"  - NAI 任务 '{task['filename']}' 使用配置种子: {current_task_seed}") # 功能性备注
        elif api_type in ["SD WebUI", "ComfyUI"]:
            if shared_config.get('sharedRandomSeed', False):
                current_task_seed = random.randint(1, 2**31 - 1)
                logger.info(f"  - {api_type} 任务 '{task['filename']}' 使用客户端生成的随机种子: {current_task_seed}") # 功能性备注
            else:
                current_task_seed = shared_config.get('seed', -1)
                logger.info(f"  - {api_type} 任务 '{task['filename']}' 使用配置种子: {current_task_seed}") # 功能性备注
        # --- *** 种子确定结束 *** ---

        # --- 调用 API (根据 api_type 和 is_img2img_mode_active) ---
        # 逻辑备注: 在调用具体 API 前再次检查停止信号
        if stop_event and stop_event.is_set():
            logger.info(f"任务在调用 API for '{task['filename']}' 之前被停止。") # 功能性备注
            task_error_msg = "任务被用户停止"
            break # 功能性备注: 跳出循环

        if api_type == "NAI":
            # 逻辑备注: NAI 不支持 LoRA 注入
            if task_loras: logger.warning("NAI API 不支持通过此方式注入 LoRA，将忽略人物设定的 LoRA 配置。") # 逻辑备注
            # 功能性备注: 构建 NAI 请求体
            payload = {
                "action": "generate", # 默认为 generate，如果内绘则改为 inpaint
                "input": task['positive'],
                "model": specific_config.get('naiModel'),
                "parameters": {
                    "width": shared_config.get('width'),
                    "height": shared_config.get('height'),
                    "scale": specific_config.get('naiScale'),
                    "sampler": specific_config.get('naiSampler'),
                    "steps": specific_config.get('naiSteps'),
                    "seed": current_task_seed, # 逻辑修改: 使用当前任务的种子
                    "n_samples": n_samples,
                    "ucPreset": specific_config.get('naiUcPreset'),
                    "qualityToggle": specific_config.get('naiQualityToggle'),
                    "sm": specific_config.get("naiSmea", False),
                    "sm_dyn": specific_config.get("naiSmeaDyn", False),
                    "dynamic_thresholding": specific_config.get("naiDynamicThresholding", False),
                    "uncond_scale": specific_config.get("naiUncondScale", 1.0),
                    "negative_prompt": task['negative']
                }
            }
            # 功能性备注: 处理图生图/内绘参数
            if is_img2img_mode_active and init_image_b64:
                payload["parameters"]["image"] = init_image_b64
                payload["parameters"]["strength"] = specific_config.get("naiReferenceStrength", 0.6)
                payload["parameters"]["noise"] = 1.0 - specific_config.get("naiReferenceInfoExtracted", 0.7)
                payload["parameters"]["add_original_image"] = specific_config.get("naiAddOriginalImage", True)
                if mask_b64:
                    payload["parameters"]["mask"] = mask_b64
                    payload["action"] = "inpaint" # 切换 action
                    logger.info("  - NAI 内绘模式参数已添加。") # 功能性备注
                else:
                    logger.info("  - NAI 图生图模式参数已添加。") # 功能性备注
            else:
                logger.info("  - NAI 文生图模式。") # 功能性备注

            # 功能性备注: 调用 NAI API 助手函数
            zip_data, task_error_msg = api_helpers.call_novelai_image_api(api_key, payload, proxy_config=nai_proxy_config, save_debug=save_debug)
            time.sleep(1) # 调用后等待

            # 逻辑备注: 在 API 调用后检查停止信号
            if stop_event and stop_event.is_set():
                logger.info(f"任务在 NAI API 调用后被停止，结果将被丢弃。") # 功能性备注
                task_error_msg = "任务被用户停止"
                break # 功能性备注: 跳出循环

            # 功能性备注: 处理返回的 Zip 数据
            if zip_data and not task_error_msg:
                try:
                    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
                        extracted_count = 0
                        for img_info in zf.infolist():
                            # 逻辑备注: 确保只提取 PNG 文件且不超过请求数量
                            if not img_info.is_dir() and img_info.filename.lower().endswith('.png') and extracted_count < n_samples:
                                image_data_list.append(zf.read(img_info.filename)); extracted_count += 1
                        # 逻辑备注: 检查返回数量是否符合预期
                        if len(image_data_list) != n_samples:
                            logger.warning(f"NAI 返回 PNG 图片数量 ({len(image_data_list)}) 与请求数量 ({n_samples}) 不符!") # 逻辑备注
                        if not image_data_list:
                            task_error_msg = "错误: 未能从 NAI Zip 文件中提取到 PNG 图片。"
                            logger.error(task_error_msg) # 逻辑备注
                except Exception as zip_e:
                    task_error_msg = f"错误: 解压 NAI Zip 文件失败: {zip_e}"
                    logger.exception(task_error_msg) # 逻辑备注
            elif not task_error_msg:
                task_error_msg = "错误: NAI API 调用成功但未返回数据。"
                logger.error(task_error_msg) # 逻辑备注

        elif api_type == "SD WebUI":
            # 功能性备注: 组合最终的提示词 (包括 LoRA 和全局附加提示)
            final_positive = task['positive']; add_pos = shared_config.get('additionalPositivePrompt', ''); final_negative = task['negative']; add_neg = shared_config.get('additionalNegativePrompt', '')
            if add_pos: final_positive += f", {add_pos}"
            if add_neg: final_negative = f"{final_negative}, {add_neg}" if final_negative else add_neg
            # 功能性备注: 添加 LoRA 到正向提示词
            lora_strings = []
            if task_loras:
                for lora in task_loras:
                    lora_name = lora.get("name")
                    model_weight = lora.get("model_weight", 1.0)
                    if lora_name:
                        lora_strings.append(f"<lora:{lora_name}:{model_weight}>")
                if lora_strings:
                    final_positive += " " + " ".join(lora_strings) # 用空格分隔 LoRA 标记
                    logger.info(f"  - 已将 {len(lora_strings)} 个 LoRA 添加到 SD WebUI 正向提示词。") # 功能性备注

            # 功能性备注: 构建 SD WebUI 请求体
            payload = {
                "prompt": final_positive.strip(', '),
                "negative_prompt": final_negative.strip(', '),
                "sampler_name": shared_config.get('sampler'),
                "steps": shared_config.get('steps'),
                "cfg_scale": shared_config.get('cfgScale'),
                "width": shared_config.get('width'),
                "height": shared_config.get('height'),
                "seed": current_task_seed, # 逻辑修改: 使用当前任务的种子
                "restore_faces": shared_config.get('restoreFaces'),
                "tiling": shared_config.get('tiling'),
                "n_iter": 1, # 迭代次数固定为 1
                "batch_size": n_samples, # 批处理大小等于请求的样本数
            }

            # 功能性备注: 确定 API 端点后缀和添加特定参数
            endpoint_suffix = "/sdapi/v1/txt2img" # 默认为文生图
            if is_img2img_mode_active and init_image_b64:
                # 逻辑备注: 如果是图生图模式
                payload["init_images"] = [init_image_b64]
                payload["denoising_strength"] = shared_config.get('denoisingStrength', 0.7)
                payload["resize_mode"] = specific_config.get('sdResizeMode', 1)
                endpoint_suffix = "/sdapi/v1/img2img" # 切换到图生图端点
                if mask_b64:
                    # 逻辑备注: 如果有蒙版，添加内绘参数
                    payload["mask"] = mask_b64
                    payload["mask_blur"] = shared_config.get('maskBlur', 4)
                    payload["inpainting_fill"] = specific_config.get('sdInpaintingFill', 1)
                    payload["inpainting_mask_invert"] = specific_config.get('sdMaskMode', 0)
                    payload["inpaint_full_res"] = specific_config.get('sdInpaintArea', 1) == 0
                    logger.info("  - SD WebUI 内绘模式参数已添加。") # 功能性备注
                else:
                    logger.info("  - SD WebUI 图生图模式参数已添加。") # 功能性备注
            else:
                # 逻辑备注: 如果是文生图模式
                logger.info("  - SD WebUI 文生图模式。") # 功能性备注
                # 功能性备注: 添加高清修复参数 (仅文生图时有效)
                if specific_config.get("sdEnableHR", False):
                    payload["enable_hr"] = True
                    payload["hr_scale"] = specific_config.get("sdHRScale", 2.0)
                    payload["hr_upscaler"] = specific_config.get("sdHRUpscaler", "Latent")
                    payload["hr_second_pass_steps"] = specific_config.get("sdHRSteps", 0)
                    payload["denoising_strength"] = shared_config.get('denoisingStrength', 0.7) # Hires fix 也需要 denoise
                    logger.info("  - SD WebUI 高清修复参数已添加。") # 功能性备注

            # 功能性备注: 添加覆盖设置 (模型, VAE, CLIP Skip)
            override_settings = {}
            if override_model := specific_config.get("sdOverrideModel"): override_settings["sd_model_checkpoint"] = override_model
            if override_vae := specific_config.get("sdOverrideVAE"): override_settings["sd_vae"] = override_vae
            override_settings["CLIP_stop_at_last_layers"] = shared_config.get("clipSkip", 1)
            if override_settings:
                payload["override_settings"] = override_settings
                logger.info(f"  - SD WebUI 覆盖设置已添加: {list(override_settings.keys())}") # 功能性备注

            # 功能性备注: 构建基础 API URL
            base_api_url = api_url.rstrip('/')
            logger.info(f"  - SD WebUI API Endpoint Suffix: {endpoint_suffix}") # 功能性备注

            # 功能性备注: 调用 SD WebUI API 助手函数
            base64_image_list, task_error_msg = api_helpers.call_sd_webui_api(base_api_url, endpoint_suffix, payload, save_debug=save_debug)
            time.sleep(0.2) # 调用后等待

            # 逻辑备注: 在 API 调用后检查停止信号
            if stop_event and stop_event.is_set():
                logger.info(f"任务在 SD WebUI API 调用后被停止，结果将被丢弃。") # 功能性备注
                task_error_msg = "任务被用户停止"
                break # 功能性备注: 跳出循环

            # 功能性备注: 处理返回的 Base64 图像列表
            if base64_image_list and not task_error_msg:
                # 逻辑备注: 检查返回数量是否符合预期
                if len(base64_image_list) != n_samples:
                    logger.warning(f"SD API 返回图片数量 ({len(base64_image_list)}) 与请求数量 ({n_samples}) 不符!") # 逻辑备注
                # 功能性备注: 解码 Base64 数据
                for idx, b64_img in enumerate(base64_image_list):
                    if idx >= n_samples: break # 最多只处理请求的数量
                    try:
                        # 逻辑备注: 处理可能的 data:image/... 前缀
                        b64_data = b64_img.split(',', 1)[-1] if isinstance(b64_img, str) and ',' in b64_img else b64_img
                        image_data_list.append(base64.b64decode(b64_data))
                    except Exception as dec_e:
                        # 逻辑备注: 解码失败错误
                        task_error_msg = f"错误: Base64 解码失败 (图片 {idx+1}): {dec_e}"; image_data_list = [];
                        logger.exception(task_error_msg) # 逻辑备注
                        break
            elif not task_error_msg:
                # 逻辑备注: API 调用成功但未返回数据错误
                task_error_msg = "错误: SD API 调用成功但未返回任何图片数据。"
                logger.error(task_error_msg) # 逻辑备注

        elif api_type == "ComfyUI":
            # 逻辑备注: 检查基础工作流是否已加载
            if not base_workflow: task_error_msg = "错误: 基础 ComfyUI 工作流未加载。"; logger.error(task_error_msg); break # 逻辑备注
            # 功能性备注: 深拷贝基础工作流，避免修改原始字典
            workflow_to_run = copy.deepcopy(base_workflow)
            modification_log = [] # 功能性备注: 记录工作流修改操作
            client_id = str(uuid.uuid4()) # 功能性备注: 为本次调用生成唯一的客户端 ID

            # 功能性备注: 获取节点标题配置
            pos_title = specific_config.get("comfyPositiveNodeTitle")
            neg_title = specific_config.get("comfyNegativeNodeTitle")
            sampler_title = specific_config.get("comfySamplerNodeTitle")
            latent_title = specific_config.get("comfyLatentImageNodeTitle")
            save_title = specific_config.get("comfyOutputNodeTitle")
            ckpt_title = specific_config.get("comfyCheckpointNodeTitle")
            vae_title = specific_config.get("comfyVAENodeTitle")
            clip_enc_title = specific_config.get("comfyClipTextEncodeNodeTitle")
            lora_loader_title = specific_config.get("comfyLoraLoaderNodeTitle") # 获取 LoRA 加载节点标题
            load_image_title = specific_config.get("comfyLoadImageNodeTitle") # 用于图生图
            # --- 新增开始 ---
            load_mask_title = specific_config.get("comfyLoadMaskNodeTitle") # 获取加载蒙版节点标题
            # --- 新增结束 ---
            face_detailer_title = specific_config.get("comfyFaceDetailerNodeTitle") # 可选
            tiling_sampler_title = specific_config.get("comfyTilingSamplerNodeTitle") # 可选

            # 功能性备注: 组合最终的提示词
            final_positive = task['positive']; add_pos = shared_config.get('additionalPositivePrompt', ''); final_negative = task['negative']; add_neg = shared_config.get('additionalNegativePrompt', '')
            if add_pos: final_positive += f", {add_pos}"
            if add_neg: final_negative = f"{final_negative}, {add_neg}" if final_negative else add_neg

            logger.info("  - 开始修改 ComfyUI 工作流节点...") # 功能性备注
            node_modified = False # 标记是否有节点被修改
            server_filename = None # 用于存储上传后的参考图文件名
            server_mask_filename = None # 用于存储上传后的蒙版文件名

            # --- 上传图片逻辑 (如果需要) ---
            if is_img2img_mode_active:
                logger.info("  - [ComfyUI Img2Img] 检测到图生图模式，尝试上传文件...") # 功能性备注
                if init_image_path:
                    # 功能性备注: 上传参考图
                    uploaded_name, upload_error = upload_image_to_comfyui(api_url, init_image_path, save_debug=save_debug)
                    if upload_error:
                        # 逻辑备注: 上传失败则记录错误并退回文生图
                        task_error_msg = f"参考图上传失败: {upload_error}"
                        modification_log.append(f"错误: {task_error_msg}")
                        logger.error(f"  - {task_error_msg}，图生图无法进行。") # 逻辑备注
                        is_img2img_mode_active = False # 退回文生图
                        modification_log.append("警告: 因参考图上传失败，已切换回文生图模式。")
                    else:
                        # 功能性备注: 上传成功则记录服务器文件名
                        server_filename = uploaded_name
                        modification_log.append(f"参考图上传成功: 服务器文件名 '{server_filename}'")
                else:
                    # 逻辑备注: 未提供有效本地路径
                    modification_log.append("警告: 图生图模式已启用，但未提供有效的本地参考图路径。")
                    logger.warning("图生图模式已启用，但未提供有效的本地参考图路径。") # 逻辑备注
                    is_img2img_mode_active = False # 退回文生图

                # 功能性备注: 如果参考图上传成功，且有蒙版路径，则上传蒙版
                if is_img2img_mode_active and mask_path:
                    uploaded_mask_name, upload_mask_error = upload_image_to_comfyui(api_url, mask_path, save_debug=save_debug)
                    if upload_mask_error:
                        # 逻辑备注: 蒙版上传失败则记录警告，但不中断图生图
                        mask_error_msg = f"蒙版图上传失败: {upload_mask_error}"
                        modification_log.append(f"警告: {mask_error_msg}，将执行标准图生图（如果可能）。")
                        logger.warning(f"  - {mask_error_msg}") # 逻辑备注
                    else:
                        # 功能性备注: 蒙版上传成功则记录服务器文件名
                        server_mask_filename = uploaded_mask_name
                        modification_log.append(f"蒙版图上传成功: 服务器文件名 '{server_mask_filename}'")

            # --- 修改工作流节点 ---
            # 功能性备注: 1. Checkpoint 覆盖
            ckpt_override = specific_config.get("comfyCkptName")
            if ckpt_override:
                ckpt_id, ckpt_node = _find_node_id_by_title(workflow_to_run, ckpt_title)
                if ckpt_node and _set_node_input(ckpt_node, "ckpt_name", ckpt_override):
                    modification_log.append(f"覆盖 Checkpoint '{ckpt_title}' 为 '{ckpt_override}'"); node_modified = True
                else: modification_log.append(f"警告: 未找到 Checkpoint 节点 '{ckpt_title}' 或设置失败，无法应用覆盖。")
            # 功能性备注: 2. VAE 覆盖
            vae_override = specific_config.get("comfyVaeName")
            if vae_override:
                # 功能性备注: 尝试查找单独的 VAE 加载节点
                vae_id, vae_node = _find_node_id_by_title(workflow_to_run, vae_title)
                if vae_node and _set_node_input(vae_node, "vae_name", vae_override):
                    modification_log.append(f"覆盖 VAE '{vae_title}' 为 '{vae_override}'"); node_modified = True
                else: modification_log.append(f"警告: 未找到 VAE 加载节点 '{vae_title}' 或设置失败，无法应用 VAE 覆盖。")
            # 功能性备注: 3. 提示词节点
            pos_id, pos_node = _find_node_id_by_title(workflow_to_run, pos_title)
            if pos_node and _set_node_input(pos_node, "text", final_positive.strip(', ')): modification_log.append(f"设置正向提示 '{pos_title}'"); node_modified = True
            else: modification_log.append(f"警告: 未找到或无法设置正向提示节点 '{pos_title}'")
            neg_id, neg_node = _find_node_id_by_title(workflow_to_run, neg_title)
            if neg_node and _set_node_input(neg_node, "text", final_negative.strip(', ')): modification_log.append(f"设置负向提示 '{neg_title}'"); node_modified = True
            else: modification_log.append(f"警告: 未找到或无法设置负向提示节点 '{neg_title}'")
            # 功能性备注: 4. CLIP Skip (应用于指定的 CLIP 编码节点)
            clip_skip_val = shared_config.get("clipSkip", 1)
            clip_enc_id, clip_enc_node = _find_node_id_by_title(workflow_to_run, clip_enc_title) # 查找用于 ClipSkip 的节点
            if clip_enc_node:
                 comfy_clip_skip = -abs(clip_skip_val) # ComfyUI 用负数表示跳过层数
                 if _set_node_input(clip_enc_node, "stop_at_clip_layer", comfy_clip_skip):
                     modification_log.append(f"设置 CLIP Skip '{clip_enc_title}' 为 {comfy_clip_skip}"); node_modified = True
                 else: modification_log.append(f"警告: 无法设置 CLIP Skip 节点 '{clip_enc_title}' 的输入。")
            else: modification_log.append(f"警告: 未找到 CLIP 编码节点 '{clip_enc_title}'，无法设置 CLIP Skip。")
            # 功能性备注: 5. 采样器节点 (注入共享参数)
            sampler_id, sampler_node = _find_node_id_by_title(workflow_to_run, sampler_title)
            if sampler_node:
                if _set_node_input(sampler_node, "seed", current_task_seed): modification_log.append(f"设置采样器种子 '{sampler_title}' 为 {current_task_seed}"); node_modified = True # 逻辑修改: 使用当前任务种子
                if _set_node_input(sampler_node, "steps", shared_config.get('steps')): modification_log.append(f"设置采样器步数 '{sampler_title}'"); node_modified = True
                if _set_node_input(sampler_node, "cfg", shared_config.get('cfgScale')): modification_log.append(f"设置采样器 CFG '{sampler_title}'"); node_modified = True
                if _set_node_input(sampler_node, "sampler_name", shared_config.get('sampler')): modification_log.append(f"设置采样器名称 '{sampler_title}'"); node_modified = True
                if _set_node_input(sampler_node, "scheduler", shared_config.get('scheduler')): modification_log.append(f"设置采样器调度器 '{sampler_title}'"); node_modified = True
                # 功能性备注: Denoise: 图生图用配置值，文生图固定为 1.0
                current_denoise = shared_config.get('denoisingStrength', 0.7) if is_img2img_mode_active else 1.0
                if _set_node_input(sampler_node, "denoise", current_denoise): modification_log.append(f"设置采样器 Denoise '{sampler_title}' 为 {current_denoise}"); node_modified = True
            else: modification_log.append(f"警告: 未找到采样器节点 '{sampler_title}'")
            # 功能性备注: 6. 潜空间节点 (设置尺寸和批处理大小，仅文生图时)
            latent_id, latent_node = _find_node_id_by_title(workflow_to_run, latent_title)
            if latent_node:
                if not is_img2img_mode_active: # 仅在文生图时修改尺寸和批处理
                    if _set_node_input(latent_node, "width", shared_config.get('width')): modification_log.append(f"设置潜空间宽度 '{latent_title}'"); node_modified = True
                    if _set_node_input(latent_node, "height", shared_config.get('height')): modification_log.append(f"设置潜空间高度 '{latent_title}'"); node_modified = True
                    if _set_node_input(latent_node, "batch_size", n_samples): modification_log.append(f"设置潜空间批处理大小为 {n_samples}"); node_modified = True
                else:
                    # 逻辑备注: 图生图模式下潜空间尺寸由 VAEEncode 决定，不修改
                    modification_log.append(f"信息: 图生图模式，潜空间尺寸由工作流决定。")
            else: modification_log.append(f"警告: 未找到潜空间节点 '{latent_title}'")
            # 功能性备注: 7. LoRA 覆盖 (如果人物设定中有 LoRA)
            if task_loras:
                # 逻辑备注: 目前只处理第一个 LoRA
                first_lora = task_loras[0]
                lora_name_override = first_lora.get("name")
                lora_model_w = first_lora.get("model_weight", 1.0)
                lora_clip_w = first_lora.get("clip_weight", 1.0)
                if lora_name_override:
                    lora_loader_id, lora_loader_node = _find_node_id_by_title(workflow_to_run, lora_loader_title)
                    if lora_loader_node:
                        if _set_node_input(lora_loader_node, "lora_name", lora_name_override): modification_log.append(f"设置 LoRA 名称 '{lora_loader_title}' 为 '{lora_name_override}'"); node_modified = True
                        if _set_node_input(lora_loader_node, "strength_model", lora_model_w): modification_log.append(f"设置 LoRA 模型权重 '{lora_loader_title}' 为 {lora_model_w}"); node_modified = True
                        if _set_node_input(lora_loader_node, "strength_clip", lora_clip_w): modification_log.append(f"设置 LoRA CLIP 权重 '{lora_loader_title}' 为 {lora_clip_w}"); node_modified = True
                    else: modification_log.append(f"警告: 配置了 LoRA 但未找到 LoRA 加载节点 '{lora_loader_title}'")
                else: modification_log.append(f"警告: 第一个 LoRA 条目缺少名称。")
            # 功能性备注: 8. 图生图/内绘处理 (设置 LoadImage 节点和可能的 Mask 节点)
            if is_img2img_mode_active:
                logger.info("  - 应用 ComfyUI 图生图/内绘设置 (使用上传后的文件名)...") # 功能性备注
                load_image_id, load_image_node = _find_node_id_by_title(workflow_to_run, load_image_title)
                if load_image_node and server_filename: # 必须有 LoadImage 节点且参考图上传成功
                    if _set_node_input(load_image_node, "image", server_filename):
                        modification_log.append(f"设置加载图像 '{load_image_title}' 为服务器文件 '{server_filename}'")
                        node_modified = True
                    else:
                         modification_log.append(f"警告: 无法设置加载图像节点 '{load_image_title}' 的输入。")
                         task_error_msg = f"图生图失败：无法设置 LoadImage 节点 '{load_image_title}'"
                         logger.error(task_error_msg) # 逻辑备注
                    # 功能性备注: 处理蒙版 (如果蒙版上传成功)
                    if server_mask_filename:
                        # --- 修改开始 ---
                        # 逻辑备注: 从配置中获取加载蒙版节点的标题
                        load_mask_title = specific_config.get("comfyLoadMaskNodeTitle", "Load_Mask_Image") # 使用默认值以防万一
                        if not load_mask_title:
                            modification_log.append("警告: 未在配置中指定加载蒙版节点的标题，无法应用蒙版。")
                            logger.warning("未在配置中指定加载蒙版节点的标题，无法应用蒙版。")
                        else:
                            # 逻辑备注: 使用配置的标题查找节点
                            load_mask_id, load_mask_node = _find_node_id_by_title(workflow_to_run, load_mask_title)
                            if load_mask_node:
                                 if _set_node_input(load_mask_node, "image", server_mask_filename):
                                     modification_log.append(f"设置加载蒙版 '{load_mask_title}' 为服务器文件 '{server_mask_filename}'")
                                     node_modified = True
                                 else:
                                     modification_log.append(f"警告: 无法设置加载蒙版节点 '{load_mask_title}' 的输入。")
                            else:
                                 # 逻辑备注: 未找到配置的蒙版加载节点
                                 modification_log.append(f"警告: 提供了蒙版图像并上传成功，但未在工作流中找到标题为 '{load_mask_title}' 的加载蒙版节点。内绘可能无法按预期工作。")
                        # --- 修改结束 ---
                    elif mask_path and not server_mask_filename:
                         # 逻辑备注: 本地有蒙版但上传失败或未使用
                         modification_log.append(f"信息: 检测到本地蒙版路径，但未使用或上传失败，执行标准图生图。")
                elif not load_image_node:
                    # 逻辑备注: 未找到加载图像节点
                    modification_log.append(f"警告: 图生图模式失败，未找到加载图像节点 '{load_image_title}'。")
                    task_error_msg = f"图生图失败：未找到 LoadImage 节点 '{load_image_title}'"
                    logger.error(task_error_msg) # 逻辑备注
                elif not server_filename:
                     # 逻辑备注: 参考图未上传成功
                     modification_log.append(f"警告: 图生图模式失败，参考图未成功上传或未提供。")
                     logger.warning("图生图模式失败，参考图未成功上传或未提供。") # 逻辑备注
            # 功能性备注: 9. 保存节点前缀 (使用任务中的文件名基础部分)
            save_id, save_node = _find_node_id_by_title(workflow_to_run, save_title)
            if save_node and _set_node_input(save_node, "filename_prefix", filename_base): modification_log.append(f"设置保存节点前缀 '{save_title}'"); node_modified = True
            else: modification_log.append(f"警告: 未找到保存节点 '{save_title}'")
            # 功能性备注: 10. 可选节点处理 (面部修复/Tiling) - 仅打印信息，实际效果依赖工作流
            if shared_config.get('restoreFaces'):
                face_detailer_id, face_detailer_node = _find_node_id_by_title(workflow_to_run, face_detailer_title)
                if face_detailer_node: modification_log.append(f"信息: 面部修复已启用 (找到节点 '{face_detailer_title}', 实际效果依赖工作流)")
                else: modification_log.append(f"警告: 面部修复已启用，但未找到节点 '{face_detailer_title}'")
            if shared_config.get('tiling'):
                 tiling_id, tiling_node = _find_node_id_by_title(workflow_to_run, tiling_sampler_title)
                 if tiling_node: modification_log.append(f"信息: Tiling 已启用 (找到节点 '{tiling_sampler_title}', 实际效果依赖工作流)")
                 else: modification_log.append(f"警告: Tiling 已启用，但未找到节点 '{tiling_sampler_title}'")

            logger.info(f"  [ComfyUI Gen] 工作流修改日志:\n    - " + "\n    - ".join(modification_log)) # 功能性备注

            # 逻辑备注: 只有在没有预处理错误时才调用 API
            if not task_error_msg:
                # 功能性备注: 调用 ComfyUI API 助手函数
                downloaded_images_bytes, api_error = api_helpers.call_comfyui_api(
                    api_url, workflow_to_run, expected_output_node_title=save_title, client_id=client_id, save_debug=save_debug
                )
                time.sleep(0.5) # API 调用后等待

                # 逻辑备注: 在 API 调用后检查停止信号
                if stop_event and stop_event.is_set():
                    logger.info(f"任务在 ComfyUI API 调用后被停止，结果将被丢弃。") # 功能性备注
                    task_error_msg = "任务被用户停止"
                    break # 功能性备注: 跳出循环

                if downloaded_images_bytes and not api_error:
                    # 功能性备注: API 调用成功且返回了图片数据
                    image_data_list = downloaded_images_bytes
                    # 逻辑备注: 检查返回数量是否符合预期
                    if len(image_data_list) != n_samples:
                        logger.warning(f"ComfyUI 返回图片数量 ({len(image_data_list)}) 与预期 ({n_samples}) 不符!") # 逻辑备注
                elif not api_error:
                    # 逻辑备注: API 调用成功但未返回数据
                    task_error_msg = "错误: ComfyUI API 调用成功但未返回任何图片数据。"
                    logger.error(task_error_msg) # 逻辑备注
                else:
                    # 逻辑备注: API 调用失败
                    task_error_msg = api_error # 使用 API 返回的错误信息
                    logger.error(f"ComfyUI API 调用失败: {task_error_msg}") # 逻辑备注
            else:
                 # 逻辑备注: 预处理阶段（如上传、节点查找）出错，不调用 API
                 logger.error(f"  - ComfyUI 任务因预处理错误中止: {task_error_msg}") # 逻辑备注

        # --- 保存图片 (统一处理，增加时间戳逻辑) ---
        if task_error_msg:
            # 逻辑备注: 如果在 API 调用或数据处理中出错
            all_samples_successful = False
            logger.error(f"  [{api_type} Gen] API 调用或数据处理失败: {task_error_msg}") # 逻辑备注
        else:
            # 逻辑备注: 如果 API 调用成功且返回了图片数据列表
            for sample_idx, img_data in enumerate(image_data_list):
                # 逻辑备注: 在保存每个样本前检查停止信号
                if stop_event and stop_event.is_set():
                    logger.info(f"任务在保存图片 {sample_idx+1} 之前被停止。") # 功能性备注
                    task_error_msg = "任务被用户停止"
                    all_samples_successful = False # 标记为不完全成功
                    break # 功能性备注: 跳出保存循环

                # 功能性备注: 构造初始文件名 (多样本时添加序号)
                current_filename_base = f"{filename_base}_{sample_idx+1}" if n_samples > 1 else filename_base
                current_filename = f"{current_filename_base}{file_ext}"
                target_path = None # 初始化 target_path
                try:
                    # 功能性备注: 清理文件名中的非法字符，替换为下划线
                    safe_filename_base = re.sub(r'[\\/:"*?<>|]', '_', current_filename_base)
                    safe_filename = f"{safe_filename_base}{file_ext}"
                    initial_target_path = base_save_path.joinpath(safe_filename)

                    # 逻辑备注: 检查路径是否合法 (防止路径穿越)
                    if '..' in safe_filename or not initial_target_path.resolve().is_relative_to(base_save_path.resolve()):
                        raise ValueError("检测到无效的文件名或路径穿越尝试。")

                    # 逻辑备注: 检查并处理文件扩展名，强制使用常见图片格式
                    if initial_target_path.suffix.lower() not in ['.png', '.jpg', '.jpeg', '.webp']:
                        logger.warning(f"    - 文件扩展名 '{initial_target_path.suffix}' 非预期，将强制保存为 .png") # 逻辑备注
                        initial_target_path = initial_target_path.with_suffix('.png')
                        safe_filename_base = initial_target_path.stem # 更新基础名以匹配新扩展名
                        file_ext = '.png' # 更新扩展名

                    # --- 新增：检查文件是否存在并添加时间戳 ---
                    target_path = initial_target_path
                    while target_path.exists():
                        timestamp = time.strftime("%Y%m%d_%H%M%S")
                        new_filename = f"{safe_filename_base}_{timestamp}{file_ext}"
                        target_path = base_save_path.joinpath(new_filename)
                        logger.info(f"    - 文件 '{initial_target_path.name}' 已存在，尝试新文件名: {target_path.name}") # 功能性备注
                        time.sleep(0.01) # 短暂等待，避免潜在的极低概率时间戳冲突
                    # --- 检查结束 ---

                    # 功能性备注: 保存图片到最终确定的路径
                    logger.info(f"  [{api_type} Gen] 保存图片 {sample_idx+1}/{len(image_data_list)} -> {target_path}") # 功能性备注
                    with open(target_path, 'wb') as f:
                        f.write(img_data)
                except Exception as save_e:
                    # 逻辑备注: 保存文件时出错
                    save_target_display = str(target_path) if target_path else f"目录 {base_save_path}"
                    task_error_msg = f"错误: 保存图片 '{current_filename}' 到 '{save_target_display}' 时出错: {save_e}"
                    logger.exception(f"  [{api_type} Gen] 严重错误: {task_error_msg}"); all_samples_successful = False; break # 逻辑备注
            # 逻辑备注: 如果是因为停止信号跳出了保存循环
            if stop_event and stop_event.is_set():
                logger.info(f"图片保存循环因停止信号中断。") # 功能性备注
                task_error_msg = "任务被用户停止" # 确保错误信息被设置

        # --- 记录任务结果 ---
        if all_samples_successful and image_data_list: # 必须 API 成功且所有样本保存成功
            generated_count += 1
            log_msg = f"成功: {task['filename']} (生成 {len(image_data_list)}/{n_samples} 张并保存)"
            results_log.append(log_msg)
            logger.info(f"  [{api_type} Gen] 任务成功: {log_msg}") # 功能性备注
            # 逻辑修改: 只有当任务原本是被注释的时候，才记录下来以便取消注释
            if task['is_commented']:
                lines_to_uncomment.add(task['full_image_line']) # 使用带分号的完整行作为 key
        else:
            # 逻辑备注: 任务失败
            failed_count += 1
            log_msg = f"失败 ({api_type}): {task['filename']} - {task_error_msg or '未知错误'}"
            results_log.append(log_msg)
            logger.error(f"  [{api_type} Gen] 任务失败: {log_msg}") # 逻辑备注

        # 逻辑备注: 如果是因为停止信号导致任务失败或中断，则跳出主循环
        if task_error_msg == "任务被用户停止":
            break

    # --- 修改 KAG 脚本 (取消注释) ---
    logger.info(f"[{api_type} Gen] 准备修改 KAG 脚本，取消 {len(lines_to_uncomment)} 个成功任务的注释...") # 功能性备注
    modified_script_lines = []
    uncommented_count = 0
    for line in kag_script.splitlines():
        trimmed_line = line.strip()
        # 逻辑修改: 使用带分号的完整行来匹配需要取消注释的行
        if trimmed_line in lines_to_uncomment:
            # 逻辑备注: 如果当前行是记录的成功任务行，则取消注释
            uncommented_line = line.lstrip(';').lstrip()
            modified_script_lines.append(uncommented_line)
            logger.info(f"  > 取消注释: {uncommented_line}") # 功能性备注
            uncommented_count += 1
        else:
            # 逻辑备注: 否则保留原行
            modified_script_lines.append(line)
    modified_script = "\n".join(modified_script_lines)
    logger.info(f"[{api_type} Gen] KAG 脚本修改完成，共取消注释 {uncommented_count} 个图片标签。") # 功能性备注

    # --- 返回最终结果 ---
    final_message = f"{api_type} 图片生成完成。成功任务: {generated_count}, 失败任务: {failed_count}."
    if task_error_msg == "任务被用户停止": # 逻辑备注: 如果是用户停止，修改最终消息
        final_message = f"{api_type} 图片生成任务被用户停止。成功任务: {generated_count}, 中断/失败任务: {failed_count + (len(tasks_to_run) - generated_count - failed_count)}."
    logger.info(final_message) # 功能性备注
    # 功能性备注: 返回包含消息、详细日志和修改后脚本的字典
    return {"message": final_message, "details": results_log, "modified_script": modified_script}, None