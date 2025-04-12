# tasks/workflow_tasks.py
"""
包含 WorkflowTab 后台任务的具体执行逻辑 (LLM 相关)。
图片生成任务已移至 image_generation_tasks.py。
"""
import re
import os
import time
from pathlib import Path
import traceback
import json # 需要 json 来序列化

# 注意：这个文件需要能够访问 api_helpers 和 utils
# 可以通过参数传递实例，或者直接导入（如果它们是无状态的）
# 当前选择：让调用者 (WorkflowTab) 传递 api_helpers 实例


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
    # 调用非流式 API 助手 (通过 facade)
    return api_helpers.call_google_non_stream(
        api_key=llm_config.get('apiKey'),
        api_base_url=llm_config.get('apiEndpoint'),
        model_name=llm_config.get('modelName'),
        prompt=prompt,
        temperature=llm_config.get('temperature'), # 格式化任务通常也需要较低温度
        max_output_tokens=llm_config.get('maxOutputTokens'),
        prompt_type="Preprocessing",
        proxy_config=proxy_config
    )

# --- 修改：task_llm_enhance ---
def task_llm_enhance(api_helpers, prompt_templates, llm_config, formatted_text, profiles_dict):
    """
    (非流式) 后台任务：调用 LLM 添加提示词。
    现在接收完整的 profiles_dict 并执行名称替换。

    Args:
        api_helpers: api_helpers 模块的实例。
        prompt_templates: PromptTemplates 类的实例。
        llm_config (dict): LLM 配置字典。
        formatted_text (str): 格式化后的文本 (步骤一结果)。
        profiles_dict (dict): 完整的人物设定字典 (从 ProfilesTab 获取，包含 display_name, replacement_name 等)。

    Returns:
        tuple: (result: str or None, error: str or None)
    """
    print("执行后台任务：步骤二 - 添加提示词 (非流式)...")
    # 检查人物设定字典是否有效
    if not profiles_dict or not isinstance(profiles_dict, dict):
        print("错误(task_llm_enhance): 传入的人物设定字典无效或为空。")
        return None, "错误: 缺少有效的人物设定字典。"
    if not formatted_text:
        print("错误(task_llm_enhance): 传入的格式化文本为空。")
        return None, "错误: 格式化文本不能为空。"

    print(f"  原始格式化文本 (前 500 字符): {formatted_text[:500]}")
    print(f"  收到的人物设定字典: {profiles_dict}")

    # --- 1. 创建名称替换映射 和 用于 JSON 的有效 Profiles ---
    replacement_map = {}
    effective_profiles_for_json = {} # 用于生成最终 JSON 的字典
    try:
        for key, data in profiles_dict.items():
            if isinstance(data, dict):
                # 优先使用 display_name 字段，如果不存在则使用字典的 key
                display_name = data.get("display_name", key)
                if not display_name: # 如果 display_name 也是空，则跳过
                    print(f"警告(task_llm_enhance): 人物 Key '{key}' 缺少有效的 display_name，已跳过。")
                    continue

                # 获取替换名称，去除首尾空格
                replacement_name = data.get("replacement_name", "").strip()
                # 确定有效名称：优先使用替换名称，否则使用显示名称
                effective_name = replacement_name or display_name

                # 添加到替换映射 (仅当替换名称非空且与显示名称不同时才需要替换)
                if replacement_name and replacement_name != display_name:
                    # 键是需要被查找和替换的显示名称，值是替换后的名称
                    replacement_map[display_name] = replacement_name

                # 构建用于 JSON 的字典，使用有效名称作为 Key
                # 确保 positive 和 negative 存在且为字符串
                effective_profiles_for_json[effective_name] = {
                    "positive": str(data.get("positive", "")),
                    "negative": str(data.get("negative", ""))
                }
            else:
                # 如果数据格式不正确，记录警告并跳过
                print(f"警告(task_llm_enhance): 人物 Key '{key}' 的数据格式无效，已跳过。")

        print(f"  名称替换映射 (需要替换的): {replacement_map}")
        print(f"  用于 JSON 的有效 Profiles: {effective_profiles_for_json}")

        # 检查是否有有效的 profiles 用于 JSON
        if not effective_profiles_for_json:
             print("警告(task_llm_enhance): 未能从人物设定中构建有效的 Profiles 用于 JSON。")
             # 即使没有 profiles，也尝试继续，LLM 可能仍能处理文本，但不会添加 NAI 标签
             # return None, "错误: 未能构建有效的 Profiles JSON。" # 或者选择报错退出

    except Exception as e:
        print(f"错误(task_llm_enhance): 处理人物设定字典时出错: {e}")
        traceback.print_exc()
        return None, f"处理人物设定时出错: {e}"

    # --- 2. 在 formatted_text 中执行名称替换 ---
    # 注意：这一步非常关键，确保 LLM 看到的文本中的 [名字] 与 JSON 中的 key 匹配
    replaced_formatted_text = formatted_text
    try:
        if replacement_map: # 仅当有需要替换的名称时执行
            print("  开始在文本中执行名称替换...")
            # 按照映射执行替换，注意 re.escape
            # 遍历 replacement_map 中的每一对 (显示名称 -> 替换名称)
            for disp_name, repl_name in replacement_map.items():
                # 构建正则表达式，匹配 `[显示名称]`
                # 使用 re.escape 确保名称中的特殊字符 (如 '.') 被正确处理
                pattern = rf'\[{re.escape(disp_name)}\]'
                # 构建替换字符串 `[替换名称]`
                replacement = f'[{repl_name}]'
                # 在文本中执行替换
                count_before = replaced_formatted_text.count(f'[{disp_name}]') # 统计替换前数量 (调试用)
                replaced_formatted_text = re.sub(pattern, replacement, replaced_formatted_text)
                count_after = replaced_formatted_text.count(f'[{disp_name}]') # 统计替换后数量 (应为 0)
                replaced_count = count_before - count_after
                print(f"    - 替换 '[{disp_name}]' 为 '[{repl_name}]'，共替换 {replaced_count} 次。")
            print("  文本中的名称替换完成。")
            print(f"  替换后的文本 (前 500 字符): {replaced_formatted_text[:500]}")
        else:
            print("  无需执行名称替换。")

    except Exception as e:
        print(f"错误(task_llm_enhance): 在文本中替换名称时出错: {e}")
        traceback.print_exc()
        # 即使替换失败，也尝试继续，但可能导致 NAI 标签生成失败
        # return None, f"替换文本中名称时出错: {e}" # 或者选择报错退出

    # --- 3. 生成最终的 JSON 字符串 ---
    try:
        # 使用 effective_profiles_for_json 生成 JSON
        # 如果 effective_profiles_for_json 为空，则生成 '{}'
        final_profiles_json = json.dumps(effective_profiles_for_json, ensure_ascii=False, indent=2)
        print(f"  生成的最终 Profiles JSON: {final_profiles_json}")
    except Exception as e:
        print(f"错误(task_llm_enhance): 序列化有效 Profiles 为 JSON 时出错: {e}")
        traceback.print_exc()
        return None, f"生成 Profiles JSON 时出错: {e}"


    # --- 4. 构建 Prompt 并调用 LLM ---
    # 提取代理配置
    proxy_config = {k: llm_config.get(k) for k in ["use_proxy", "proxy_address", "proxy_port"]}
    # 构建 Prompt (使用替换后的文本和有效的 JSON)
    try:
        prompt = prompt_templates.PROMPT_ENHANCEMENT_TEMPLATE.format(
            pre_instruction=llm_config.get('preInstruction',''),
            post_instruction=llm_config.get('postInstruction',''),
            character_profiles_json=final_profiles_json, # 使用生成的有效 JSON
            formatted_text_chunk=replaced_formatted_text # 使用名称替换后的文本
        )
        print("  Prompt 构建完成。")
        # print("--- Prompt Start ---") # 调试：打印完整 Prompt
        # print(prompt)
        # print("--- Prompt End ---")
    except Exception as e:
        print(f"错误(task_llm_enhance): 构建 Prompt 时出错: {e}")
        traceback.print_exc()
        return None, f"构建 Prompt 时出错: {e}"

    # 调用非流式 API 助手 (通过 facade)
    print("  调用 LLM API...")
    result_text, error_message = api_helpers.call_google_non_stream(
        api_key=llm_config.get('apiKey'),
        api_base_url=llm_config.get('apiEndpoint'),
        model_name=llm_config.get('modelName'),
        prompt=prompt,
        temperature=llm_config.get('temperature'), # 添加提示词可以保留一些温度
        max_output_tokens=llm_config.get('maxOutputTokens'),
        prompt_type="PromptEnhancement",
        proxy_config=proxy_config
    )

    if error_message:
        print(f"  LLM 调用失败: {error_message}")
        return None, error_message
    elif result_text is None:
        print("  LLM 调用成功，但返回结果为空文本。")
        return "", None # 返回空字符串表示成功但无内容
    else:
        print("  LLM 调用成功，收到结果。")
        # print(f"  LLM 结果 (前 500 字符): {result_text[:500]}") # 调试用
        return result_text, None
# --- 修改结束 ---


# --- 新增：BGM 建议任务 ---
def task_llm_suggest_bgm(api_helpers, prompt_templates, llm_config, enhanced_text):
    """
    (非流式) 后台任务：调用 LLM 在增强文本中添加 BGM 建议注释。

    Args:
        api_helpers: api_helpers 模块的实例。
        prompt_templates: PromptTemplates 类的实例。
        llm_config (dict): LLM 配置字典。
        enhanced_text (str): 包含提示词标记的文本 (步骤二的输出)。

    Returns:
        tuple: (result: str or None, error: str or None)
               result 是带有 BGM 建议注释的文本。
    """
    print("执行后台任务：步骤三 (内部) - 添加 BGM 建议...")
    # 提取代理配置
    proxy_config = {k: llm_config.get(k) for k in ["use_proxy", "proxy_address", "proxy_port"]}
    # 构建 Prompt
    prompt = prompt_templates.BGM_SUGGESTION_TEMPLATE.format(
        pre_instruction=llm_config.get('preInstruction',''),
        post_instruction=llm_config.get('postInstruction',''),
        enhanced_text_chunk=enhanced_text # 使用增强文本作为输入
    )
    # 调用非流式 API 助手 (通过 facade)
    return api_helpers.call_google_non_stream(
        api_key=llm_config.get('apiKey'),
        api_base_url=llm_config.get('apiEndpoint'),
        model_name=llm_config.get('modelName'),
        prompt=prompt,
        temperature=llm_config.get('temperature'), # BGM 建议可以保留一些温度
        max_output_tokens=llm_config.get('maxOutputTokens'), # 输出应该和输入差不多长，但要留足余量
        prompt_type="BGMSuggestion",
        proxy_config=proxy_config
    )

# --- 修改：KAG 转换任务 ---
def task_llm_convert_to_kag(api_helpers, prompt_templates, llm_config, text_with_suggestions):
    """
    (非流式) 后台任务：调用 LLM 将带有提示词和 BGM 建议的文本转换为 KAG 脚本。

    Args:
        api_helpers: api_helpers 模块的实例。
        prompt_templates: PromptTemplates 类的实例。
        llm_config (dict): LLM 配置字典。
        text_with_suggestions (str): 包含提示词标记和 BGM 建议注释的文本。

    Returns:
        tuple: (result: str or None, error: str or None)
               result 是生成的 KAG 脚本主体。
    """
    print("执行后台任务：步骤三 (内部) - 转换 KAG...")
    # 提取代理配置
    proxy_config = {k: llm_config.get(k) for k in ["use_proxy", "proxy_address", "proxy_port"]}
    # 构建 Prompt (使用修改后的 KAG 模板)
    prompt = prompt_templates.KAG_CONVERSION_PROMPT_TEMPLATE.format(
        pre_instruction=llm_config.get('preInstruction',''),
        post_instruction=llm_config.get('postInstruction',''),
        text_chunk_with_suggestions=text_with_suggestions # 输入是带有建议的文本
    )
    # 调用非流式 API 助手获取脚本主体 (通过 facade)
    # **修改：明确设置较低的 temperature**
    script_body, error = api_helpers.call_google_non_stream(
        api_key=llm_config.get('apiKey'),
        api_base_url=llm_config.get('apiEndpoint'),
        model_name=llm_config.get('modelName'),
        prompt=prompt,
        temperature=0.1, # **降低温度以提高格式准确性**
        max_output_tokens=llm_config.get('maxOutputTokens'), # KAG 脚本可能比原文本长
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

# --- 图片生成任务 (已移至 image_generation_tasks.py) ---
# (task_generate_images 函数已移除)