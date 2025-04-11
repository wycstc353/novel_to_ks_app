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
    # 调用非流式 API 助手 (通过 facade)
    return api_helpers.call_google_non_stream(
        api_key=llm_config.get('apiKey'),
        api_base_url=llm_config.get('apiEndpoint'),
        model_name=llm_config.get('modelName'),
        prompt=prompt,
        temperature=llm_config.get('temperature'), # 添加提示词可以保留一些温度
        max_output_tokens=llm_config.get('maxOutputTokens'),
        prompt_type="PromptEnhancement",
        proxy_config=proxy_config
    )

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