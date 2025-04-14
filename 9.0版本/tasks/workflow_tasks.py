# tasks/workflow_tasks.py
import re
import os
import time
from pathlib import Path
import traceback
import json

# --- LLM 相关任务 ---

def task_llm_preprocess(api_helpers, prompt_templates, llm_config, novel_text):
    """(非流式) 后台任务：调用 LLM 进行格式化"""
    print("执行后台任务：步骤一 - 格式化文本 (非流式)...")
    proxy_config = {k: llm_config.get(k) for k in ["use_proxy", "proxy_address", "proxy_port"]}
    prompt = prompt_templates.PREPROCESSING_PROMPT_TEMPLATE.format(
        pre_instruction=llm_config.get('preInstruction',''), post_instruction=llm_config.get('postInstruction',''), text_chunk=novel_text
    )
    # 传递新增的采样参数
    return api_helpers.call_google_non_stream(
        api_key=llm_config.get('apiKey'), api_base_url=llm_config.get('apiEndpoint'), model_name=llm_config.get('modelName'),
        prompt=prompt, temperature=llm_config.get('temperature'), max_output_tokens=llm_config.get('maxOutputTokens'),
        top_p=llm_config.get('topP'), top_k=llm_config.get('topK'), # 传递 topP, topK
        prompt_type="Preprocessing", proxy_config=proxy_config
    )

def task_llm_enhance(api_helpers, prompt_templates, llm_config, formatted_text, profiles_dict):
    """(非流式) 后台任务：调用 LLM 添加提示词"""
    print("执行后台任务：步骤二 - 添加提示词 (非流式)...")
    if not profiles_dict or not isinstance(profiles_dict, dict): print("错误(task_llm_enhance): 传入的人物设定字典无效或为空。"); return None, "错误: 缺少有效的人物设定字典。"
    if not formatted_text: print("错误(task_llm_enhance): 传入的格式化文本为空。"); return None, "错误: 格式化文本不能为空。"
    print(f"  原始格式化文本 (前 500 字符): {formatted_text[:500]}"); print(f"  收到的人物设定字典: {profiles_dict}")

    # 1. 创建名称替换映射 和 用于 JSON 的有效 Profiles
    replacement_map = {}; effective_profiles_for_json = {}
    try:
        for key, data in profiles_dict.items():
            if isinstance(data, dict):
                display_name = data.get("display_name", key)
                if not display_name: print(f"警告(task_llm_enhance): 人物 Key '{key}' 缺少有效的 display_name，已跳过。"); continue
                replacement_name = data.get("replacement_name", "").strip(); effective_name = replacement_name or display_name
                if replacement_name and replacement_name != display_name: replacement_map[display_name] = replacement_name
                effective_profiles_for_json[effective_name] = {"positive": str(data.get("positive", "")), "negative": str(data.get("negative", ""))}
            else: print(f"警告(task_llm_enhance): 人物 Key '{key}' 的数据格式无效，已跳过。")
        print(f"  名称替换映射 (需要替换的): {replacement_map}"); print(f"  用于 JSON 的有效 Profiles: {effective_profiles_for_json}")
        if not effective_profiles_for_json: print("警告(task_llm_enhance): 未能从人物设定中构建有效的 Profiles 用于 JSON。")
    except Exception as e: print(f"错误(task_llm_enhance): 处理人物设定字典时出错: {e}"); traceback.print_exc(); return None, f"处理人物设定时出错: {e}"

    # 2. 在 formatted_text 中执行名称替换
    replaced_formatted_text = formatted_text
    try:
        if replacement_map:
            print("  开始在文本中执行名称替换...")
            for disp_name, repl_name in replacement_map.items():
                pattern = rf'\[{re.escape(disp_name)}\]'; replacement = f'[{repl_name}]'
                count_before = replaced_formatted_text.count(f'[{disp_name}]')
                replaced_formatted_text = re.sub(pattern, replacement, replaced_formatted_text)
                replaced_count = count_before - replaced_formatted_text.count(f'[{disp_name}]')
                print(f"    - 替换 '[{disp_name}]' 为 '[{repl_name}]'，共替换 {replaced_count} 次。")
            print("  文本中的名称替换完成。"); print(f"  替换后的文本 (前 500 字符): {replaced_formatted_text[:500]}")
        else: print("  无需执行名称替换。")
    except Exception as e: print(f"错误(task_llm_enhance): 在文本中替换名称时出错: {e}"); traceback.print_exc()

    # 3. 生成最终的 JSON 字符串
    try: final_profiles_json = json.dumps(effective_profiles_for_json, ensure_ascii=False, indent=2); print(f"  生成的最终 Profiles JSON: {final_profiles_json}")
    except Exception as e: print(f"错误(task_llm_enhance): 序列化有效 Profiles 为 JSON 时出错: {e}"); traceback.print_exc(); return None, f"生成 Profiles JSON 时出错: {e}"

    # 4. 构建 Prompt 并调用 LLM
    proxy_config = {k: llm_config.get(k) for k in ["use_proxy", "proxy_address", "proxy_port"]}
    try:
        prompt = prompt_templates.PROMPT_ENHANCEMENT_TEMPLATE.format(
            pre_instruction=llm_config.get('preInstruction',''), post_instruction=llm_config.get('postInstruction',''),
            character_profiles_json=final_profiles_json, formatted_text_chunk=replaced_formatted_text
        ); print("  Prompt 构建完成。")
    except Exception as e: print(f"错误(task_llm_enhance): 构建 Prompt 时出错: {e}"); traceback.print_exc(); return None, f"构建 Prompt 时出错: {e}"

    print("  调用 LLM API...")
    # 传递新增的采样参数
    result_text, error_message = api_helpers.call_google_non_stream(
        api_key=llm_config.get('apiKey'), api_base_url=llm_config.get('apiEndpoint'), model_name=llm_config.get('modelName'),
        prompt=prompt, temperature=llm_config.get('temperature'), max_output_tokens=llm_config.get('maxOutputTokens'),
        top_p=llm_config.get('topP'), top_k=llm_config.get('topK'), # 传递 topP, topK
        prompt_type="PromptEnhancement", proxy_config=proxy_config
    )
    if error_message: print(f"  LLM 调用失败: {error_message}"); return None, error_message
    elif result_text is None: print("  LLM 调用成功，但返回结果为空文本。"); return "", None
    else: print("  LLM 调用成功，收到结果。"); return result_text, None

def task_llm_suggest_bgm(api_helpers, prompt_templates, llm_config, enhanced_text):
    """(非流式) 后台任务：调用 LLM 添加 BGM 建议注释"""
    print("执行后台任务：步骤三 (内部) - 添加 BGM 建议...")
    proxy_config = {k: llm_config.get(k) for k in ["use_proxy", "proxy_address", "proxy_port"]}
    prompt = prompt_templates.BGM_SUGGESTION_TEMPLATE.format(
        pre_instruction=llm_config.get('preInstruction',''), post_instruction=llm_config.get('postInstruction',''), enhanced_text_chunk=enhanced_text
    )
    # 传递新增的采样参数
    return api_helpers.call_google_non_stream(
        api_key=llm_config.get('apiKey'), api_base_url=llm_config.get('apiEndpoint'), model_name=llm_config.get('modelName'),
        prompt=prompt, temperature=llm_config.get('temperature'), max_output_tokens=llm_config.get('maxOutputTokens'),
        top_p=llm_config.get('topP'), top_k=llm_config.get('topK'), # 传递 topP, topK
        prompt_type="BGMSuggestion", proxy_config=proxy_config
    )

def task_llm_convert_to_kag(api_helpers, prompt_templates, llm_config, text_with_suggestions):
    """(非流式) 后台任务：调用 LLM 将文本转换为 KAG 脚本"""
    print("执行后台任务：步骤三 (内部) - 转换 KAG...")
    proxy_config = {k: llm_config.get(k) for k in ["use_proxy", "proxy_address", "proxy_port"]}
    prompt = prompt_templates.KAG_CONVERSION_PROMPT_TEMPLATE.format(
        pre_instruction=llm_config.get('preInstruction',''), post_instruction=llm_config.get('postInstruction',''), text_chunk_with_suggestions=text_with_suggestions
    )
    # --- 修改：不再硬编码低温度，使用 llm_config 中的值 ---
    # temperature=0.1, # **移除硬编码**
    script_body, error = api_helpers.call_google_non_stream(
        api_key=llm_config.get('apiKey'), api_base_url=llm_config.get('apiEndpoint'), model_name=llm_config.get('modelName'),
        prompt=prompt,
        temperature=llm_config.get('temperature'), # 使用配置中的温度
        max_output_tokens=llm_config.get('maxOutputTokens'),
        top_p=llm_config.get('topP'), top_k=llm_config.get('topK'), # 传递 topP, topK
        prompt_type="KAGConversion", proxy_config=proxy_config
    )
    # --- 修改结束 ---
    if error: return None, error
    else: footer = "\n\n@s ; Script End"; final_script = (script_body or "") + footer; return final_script, None