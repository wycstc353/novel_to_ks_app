# tasks/workflow_tasks.py
import re # 功能性备注: 导入正则表达式模块，用于文本处理
import logging # 功能性备注: 导入日志模块

# 功能性备注: 获取当前模块的 logger 实例
logger = logging.getLogger(__name__)

# --- LLM 相关任务 ---

# 功能性备注: 步骤一：格式化文本，调用 LLM API
def task_llm_preprocess(api_helpers, prompt_templates, global_config, text_data, provider="Google", stop_event=None): # 功能性备注: 添加 stop_event 参数
    """
    (非流式) 后台任务：调用 LLM 进行格式化。
    支持 Google 和 OpenAI。
    """
    logger.info(f"执行后台任务：步骤一 - 格式化文本 ({provider} 非流式)...") # 功能性备注
    task_id = f"步骤一 ({provider} 非流式)"

    # 功能性备注: 准备 Prompt (通用)
    prompt = prompt_templates.PREPROCESSING_PROMPT_TEMPLATE.format(
        pre_instruction=global_config.get('preInstruction',''),
        post_instruction=global_config.get('postInstruction',''),
        text_chunk=text_data
    )
    # 功能性备注: 获取全局代理配置和调试开关
    proxy_config = {k: global_config.get(k) for k in ["use_proxy", "proxy_address", "proxy_port"]}
    save_debug = global_config.get('saveDebugInputs', False) # 功能性备注

    # 逻辑备注: 在调用 API 前检查停止信号
    if stop_event and stop_event.is_set():
        logger.info(f"任务 {task_id} 在 API 调用前被停止。") # 功能性备注
        raise StopIteration("任务被用户停止") # 功能性备注: 抛出异常以通知包装器

    result_text, error_message = None, None # 功能性备注: 初始化结果变量

    # 逻辑备注: 根据提供商调用相应的 API 助手
    if provider == "Google":
        # 功能性备注: 获取 Google 特定配置
        google_config = api_helpers.app.get_google_specific_config()
        result_text, error_message = api_helpers.call_google_non_stream(
            api_key=google_config.get('apiKey'),
            api_base_url=google_config.get('apiEndpoint'),
            model_name=google_config.get('modelName'),
            prompt=prompt,
            temperature=global_config.get('temperature'), # 功能性备注: 使用全局参数
            max_output_tokens=global_config.get('maxOutputTokens'),
            top_p=global_config.get('topP'),
            top_k=global_config.get('topK'),
            prompt_type="Preprocessing",
            proxy_config=proxy_config,
            save_debug=save_debug # 功能性备注: 传递调试开关
        )
    elif provider == "OpenAI":
        # 功能性备注: 获取 OpenAI 特定配置
        openai_config = api_helpers.app.get_openai_specific_config()
        result_text, error_message = api_helpers.call_openai_non_stream(
            api_key=openai_config.get('apiKey'),
            api_base_url=openai_config.get('apiBaseUrl'),
            model_name=openai_config.get('modelName'),
            prompt=prompt,
            temperature=global_config.get('temperature'), # 功能性备注: 使用全局参数
            max_tokens=global_config.get('maxOutputTokens'), # 逻辑备注: 注意 OpenAI 参数名是 max_tokens
            custom_headers=openai_config.get('customHeaders'),
            proxy_config=proxy_config,
            save_debug=save_debug # 功能性备注: 传递调试开关
        )
    else:
        # 逻辑备注: 不支持的提供商
        error_message = f"错误 ({task_id}): 不支持的 LLM 提供商 '{provider}'"
        logger.error(f"不支持的 LLM 提供商 '{provider}' ({task_id})") # 逻辑备注

    # 逻辑备注: 在 API 调用后检查停止信号
    if stop_event and stop_event.is_set():
        logger.info(f"任务 {task_id} 在 API 调用后被停止，结果将被丢弃。") # 功能性备注
        raise StopIteration("任务被用户停止") # 功能性备注: 抛出异常以通知包装器

    # 功能性备注: 返回结果或错误信息
    return result_text, error_message

# 功能性备注: 步骤二：添加提示词，调用 LLM API
# 逻辑备注: *** 修改点：添加 prompt_style 参数 ***
def task_llm_enhance(api_helpers, prompt_templates, global_config, formatted_text, profiles_dict, profiles_json_for_prompt, provider="Google", prompt_style="sd_comfy", stop_event=None): # 功能性备注: 添加 stop_event 参数
    """
    (非流式) 后台任务：调用 LLM 添加提示词。
    支持 Google 和 OpenAI。
    根据 prompt_style 选择不同的模板 (NAI 或 SD/Comfy)。
    """
    # 逻辑备注: 根据 prompt_style 更新日志信息
    style_name = "NAI" if prompt_style == "nai" else "SD/Comfy"
    logger.info(f"执行后台任务：步骤二 - 添加 {style_name} 提示词 ({provider} 非流式)...") # 功能性备注
    task_id = f"步骤二-{style_name} ({provider} 非流式)"

    # 逻辑备注: 输入校验
    if not profiles_dict or not isinstance(profiles_dict, dict):
        logger.error("传入的人物设定字典无效或为空。") # 逻辑备注
        return None, "错误: 缺少有效的人物设定字典。"
    if not formatted_text:
        logger.error("传入的格式化文本为空。") # 逻辑备注
        return None, "错误: 格式化文本不能为空。"
    if not profiles_json_for_prompt:
        logger.error("传入的人物设定 JSON 为空。") # 逻辑备注
        return None, "错误: 缺少人物设定 JSON。"

    logger.debug(f"原始格式化文本 (前 500 字符): {formatted_text[:500]}") # 功能性备注 (调试)
    # 逻辑备注: 传入的 JSON 现在包含所有四个提示词字段
    logger.debug(f"用于 Prompt 的 JSON (包含所有提示词字段, 前 500 字符): {profiles_json_for_prompt[:500]}...") # 功能性备注 (调试)

    # 功能性备注: 1. 名称替换 (通用逻辑，保持不变)
    replacement_map = {}
    try:
        for key, data in profiles_dict.items():
            if isinstance(data, dict):
                display_name = data.get("display_name", key)
                if not display_name: continue
                replacement_name = data.get("replacement_name", "").strip()
                if replacement_name and replacement_name != display_name:
                    replacement_map[display_name] = replacement_name
        logger.debug(f"名称替换映射 (需要替换的): {replacement_map}") # 功能性备注 (调试)
    except Exception as e:
        logger.exception(f"处理人物设定字典时出错: {e}") # 逻辑备注
        return None, f"处理人物设定时出错: {e}"

    replaced_formatted_text = formatted_text
    try:
        if replacement_map:
            logger.info("开始在文本中执行名称替换...") # 功能性备注
            for disp_name, repl_name in replacement_map.items():
                pattern = rf'(\[{re.escape(disp_name)}\])'
                replaced_formatted_text = re.sub(pattern, f'[{repl_name}]', replaced_formatted_text)
                logger.debug(f"尝试替换 '[{disp_name}]' 为 '[{repl_name}]'。") # 功能性备注 (调试)
            logger.info("文本中的名称替换完成。") # 功能性备注
            logger.debug(f"替换后的文本 (前 500 字符): {replaced_formatted_text[:500]}") # 功能性备注 (调试)
        else:
            logger.info("无需执行名称替换。") # 功能性备注
    except Exception as e:
        logger.exception(f"在文本中替换名称时出错: {e}") # 逻辑备注
        # 逻辑备注: 替换出错不直接返回，继续尝试后续步骤

    # 功能性备注: 2. 构建 Prompt (根据 prompt_style 选择模板)
    try:
        # 逻辑备注: *** 修改点：根据 prompt_style 选择模板 ***
        if prompt_style == "nai":
            template = prompt_templates.NAI_PROMPT_ENHANCEMENT_TEMPLATE
            logger.info("使用 NAI 提示词增强模板。") # 功能性备注
        else: # 默认或 "sd_comfy"
            template = prompt_templates.SD_COMFY_PROMPT_ENHANCEMENT_TEMPLATE
            logger.info("使用 SD/Comfy 提示词增强模板。") # 功能性备注

        # 功能性备注: 使用选定的模板和替换后的文本构建最终的 Prompt
        prompt = template.format(
            pre_instruction=global_config.get('preInstruction',''),
            post_instruction=global_config.get('postInstruction',''),
            character_profiles_json=profiles_json_for_prompt, # 逻辑备注: 此 JSON 包含所有四个提示词字段
            formatted_text_chunk=replaced_formatted_text
        )
        logger.info("Prompt 构建完成。") # 功能性备注
    except Exception as e:
        logger.exception(f"构建 Prompt 时出错: {e}") # 逻辑备注
        return None, f"构建 Prompt 时出错: {e}"

    # 功能性备注: 3. 调用对应的 LLM API
    logger.info(f"调用 {provider} LLM API...") # 功能性备注
    proxy_config = {k: global_config.get(k) for k in ["use_proxy", "proxy_address", "proxy_port"]}
    save_debug = global_config.get('saveDebugInputs', False) # 功能性备注
    result_text, error_message = None, None

    # 逻辑备注: 在调用 API 前检查停止信号
    if stop_event and stop_event.is_set():
        logger.info(f"任务 {task_id} 在 API 调用前被停止。") # 功能性备注
        raise StopIteration("任务被用户停止") # 功能性备注: 抛出异常以通知包装器

    # 逻辑备注: 根据提供商调用相应的 API 助手
    if provider == "Google":
        google_config = api_helpers.app.get_google_specific_config()
        result_text, error_message = api_helpers.call_google_non_stream(
            api_key=google_config.get('apiKey'),
            api_base_url=google_config.get('apiEndpoint'),
            model_name=google_config.get('modelName'),
            prompt=prompt,
            temperature=global_config.get('temperature'),
            max_output_tokens=global_config.get('maxOutputTokens'),
            top_p=global_config.get('topP'),
            top_k=global_config.get('topK'),
            prompt_type=f"PromptEnhancement_{style_name}", # 功能性备注: 区分调试文件名
            proxy_config=proxy_config,
            save_debug=save_debug # 功能性备注
        )
    elif provider == "OpenAI":
        openai_config = api_helpers.app.get_openai_specific_config()
        result_text, error_message = api_helpers.call_openai_non_stream(
            api_key=openai_config.get('apiKey'),
            api_base_url=openai_config.get('apiBaseUrl'),
            model_name=openai_config.get('modelName'),
            prompt=prompt,
            temperature=global_config.get('temperature'),
            max_tokens=global_config.get('maxOutputTokens'),
            custom_headers=openai_config.get('customHeaders'),
            proxy_config=proxy_config,
            save_debug=save_debug # 功能性备注
        )
    else:
        error_message = f"错误 ({task_id}): 不支持的 LLM 提供商 '{provider}'"
        logger.error(f"不支持的 LLM 提供商 '{provider}' ({task_id})") # 逻辑备注

    # 逻辑备注: 在 API 调用后检查停止信号
    if stop_event and stop_event.is_set():
        logger.info(f"任务 {task_id} 在 API 调用后被停止，结果将被丢弃。") # 功能性备注
        raise StopIteration("任务被用户停止") # 功能性备注: 抛出异常以通知包装器

    # 功能性备注: 4. 处理结果
    if error_message:
        logger.error(f"LLM 调用失败: {error_message}") # 逻辑备注
        return None, error_message
    elif result_text is None:
        logger.warning("LLM 调用成功，但返回结果为空文本。") # 逻辑备注
        return "", None
    else:
        logger.info("LLM 调用成功，收到结果。") # 功能性备注
        return result_text, None

# 功能性备注: 步骤三（内部）：添加 BGM 建议，调用 LLM API
def task_llm_suggest_bgm(api_helpers, prompt_templates, llm_config_for_step3, enhanced_text, provider="Google", stop_event=None): # 功能性备注: 添加 stop_event 参数
    """
    (非流式) 后台任务：调用 LLM 添加 BGM 建议注释。
    支持 Google 和 OpenAI。
    llm_config_for_step3 包含了可能被覆盖的温度。
    """
    logger.info(f"执行后台任务：步骤三 (内部) - 添加 BGM 建议 ({provider} 非流式)...") # 功能性备注
    task_id = f"步骤三-BGM ({provider} 非流式)"

    # 功能性备注: 使用传入的 llm_config_for_step3 获取指令和参数
    prompt = prompt_templates.BGM_SUGGESTION_TEMPLATE.format(
        pre_instruction=llm_config_for_step3.get('preInstruction',''),
        post_instruction=llm_config_for_step3.get('postInstruction',''),
        enhanced_text_chunk=enhanced_text
    )
    proxy_config = {k: llm_config_for_step3.get(k) for k in ["use_proxy", "proxy_address", "proxy_port"]}
    save_debug = llm_config_for_step3.get('saveDebugInputs', False) # 功能性备注
    result_text, error_message = None, None # 功能性备注: 初始化结果变量

    # 逻辑备注: 在调用 API 前检查停止信号
    if stop_event and stop_event.is_set():
        logger.info(f"任务 {task_id} 在 API 调用前被停止。") # 功能性备注
        raise StopIteration("任务被用户停止") # 功能性备注: 抛出异常以通知包装器

    # 逻辑备注: 根据提供商调用相应的 API 助手
    if provider == "Google":
        google_config = api_helpers.app.get_google_specific_config()
        result_text, error_message = api_helpers.call_google_non_stream(
            api_key=google_config.get('apiKey'),
            api_base_url=google_config.get('apiEndpoint'),
            model_name=google_config.get('modelName'),
            prompt=prompt,
            temperature=llm_config_for_step3.get('temperature'), # 功能性备注: 使用可能被覆盖的温度
            max_output_tokens=llm_config_for_step3.get('maxOutputTokens'),
            top_p=llm_config_for_step3.get('topP'),
            top_k=llm_config_for_step3.get('topK'),
            prompt_type="BGMSuggestion",
            proxy_config=proxy_config,
            save_debug=save_debug # 功能性备注
        )
    elif provider == "OpenAI":
        openai_config = api_helpers.app.get_openai_specific_config()
        result_text, error_message = api_helpers.call_openai_non_stream(
            api_key=openai_config.get('apiKey'),
            api_base_url=openai_config.get('apiBaseUrl'),
            model_name=openai_config.get('modelName'),
            prompt=prompt,
            temperature=llm_config_for_step3.get('temperature'), # 功能性备注: 使用可能被覆盖的温度
            max_tokens=llm_config_for_step3.get('maxOutputTokens'),
            custom_headers=openai_config.get('customHeaders'),
            proxy_config=proxy_config,
            save_debug=save_debug # 功能性备注
        )
    else:
        error_message = f"错误 ({task_id}): 不支持的 LLM 提供商 '{provider}'"
        logger.error(f"不支持的 LLM 提供商 '{provider}' ({task_id})") # 逻辑备注

    # 逻辑备注: 在 API 调用后检查停止信号
    if stop_event and stop_event.is_set():
        logger.info(f"任务 {task_id} 在 API 调用后被停止，结果将被丢弃。") # 功能性备注
        raise StopIteration("任务被用户停止") # 功能性备注: 抛出异常以通知包装器

    # 功能性备注: 返回结果或错误信息
    return result_text, error_message

# 功能性备注: 步骤三（内部）：转换 KAG 脚本，调用 LLM API
def task_llm_convert_to_kag(api_helpers, prompt_templates, llm_config_for_step3, text_with_suggestions, provider="Google", use_stream=True, result_queue=None, task_id="步骤三-KAG", update_target_widget=None, status_label_widget=None, stop_event=None): # 功能性备注: 添加 stop_event 参数
    """
    后台任务：调用 LLM 将文本转换为 KAG 脚本。
    支持 Google 和 OpenAI，支持流式和非流式。
    llm_config_for_step3 包含了可能被覆盖的温度。
    """
    logger.info(f"执行后台任务：步骤三 (内部) - 转换 KAG ({provider}{' 流式' if use_stream else ' 非流式'})...") # 功能性备注

    # 功能性备注: 构建 KAG 转换 Prompt
    prompt = prompt_templates.KAG_CONVERSION_PROMPT_TEMPLATE.format(
        pre_instruction=llm_config_for_step3.get('preInstruction',''),
        post_instruction=llm_config_for_step3.get('postInstruction',''),
        text_chunk_with_suggestions=text_with_suggestions
    )
    proxy_config = {k: llm_config_for_step3.get(k) for k in ["use_proxy", "proxy_address", "proxy_port"]}
    save_debug = llm_config_for_step3.get('saveDebugInputs', False) # 功能性备注

    if use_stream:
        # --- 流式处理 ---
        logger.info(f"[{task_id}] 执行流式 KAG 转换...") # 功能性备注
        stream_func = None
        stream_args = ()

        # 逻辑备注: 根据提供商选择流式函数和参数
        if provider == "Google":
            google_config = api_helpers.app.get_google_specific_config()
            stream_func = api_helpers.stream_google_response
            stream_args = (
                google_config.get('apiKey'), google_config.get('apiEndpoint'), google_config.get('modelName'),
                prompt, llm_config_for_step3.get('temperature'), llm_config_for_step3.get('maxOutputTokens'),
                llm_config_for_step3.get('topP'), llm_config_for_step3.get('topK'), "KAGConversion", proxy_config,
                save_debug # 功能性备注
            )
        elif provider == "OpenAI":
            openai_config = api_helpers.app.get_openai_specific_config()
            stream_func = api_helpers.stream_openai_response
            stream_args = (
                openai_config.get('apiKey'), openai_config.get('apiBaseUrl'), openai_config.get('modelName'),
                prompt, llm_config_for_step3.get('temperature'), llm_config_for_step3.get('maxOutputTokens'),
                openai_config.get('customHeaders'), proxy_config,
                save_debug # 功能性备注
            )
        else:
            # 逻辑备注: 不支持的提供商，发送错误到队列
            error_msg = f"不支持的提供商 {provider}"
            logger.error(f"{error_msg} ({task_id})") # 逻辑备注
            if result_queue: result_queue.put((task_id, "error", "stream_error", error_msg, update_target_widget, status_label_widget))
            return None, f"错误 ({task_id}): {error_msg}" # 逻辑备注: 非流式也返回错误

        if stream_func and result_queue:
            stream_finished_normally = False # 逻辑备注: 标记流是否正常结束
            try:
                # 功能性备注: 迭代处理流式 API 返回的结果
                # 逻辑备注: 流式函数的内部实现需要处理 stop_event，这里假设它会处理
                # 逻辑备注: _thread_wrapper 中也会在每次 yield 后检查 stop_event
                for status, data in stream_func(*stream_args):
                    # 逻辑备注: 在处理每个块之前检查停止信号 (由 _thread_wrapper 处理)
                    # if stop_event and stop_event.is_set(): raise StopIteration("任务在流式处理中被用户停止")
                    if status == "chunk": # 功能性备注: 收到数据块
                        result_queue.put((task_id, "success", "stream_chunk", data, update_target_widget, status_label_widget))
                    elif status == "error": # 功能性备注: 发生错误
                        result_queue.put((task_id, "error", "stream_error", data, update_target_widget, status_label_widget))
                        return None, data # 逻辑备注: 出错则返回错误
                    elif status == "warning": # 功能性备注: 收到警告
                        result_queue.put((task_id, "warning", "stream_warning", data, update_target_widget, status_label_widget))
                    elif status == "done": # 功能性备注: 流式结束信号
                        result_queue.put((task_id, "success", "stream_done", data, update_target_widget, status_label_widget))
                        stream_finished_normally = True # 逻辑备注: 标记正常结束
                        return None, None # 功能性备注: 流式处理完成，结果通过队列传递
                    else: # 功能性备注: 未知状态
                        result_queue.put((task_id, "warning", "stream_warning", f"未知状态: {status}", update_target_widget, status_label_widget))
                # 逻辑备注: 检查是否因非 'done' 信号退出循环
                if not stream_finished_normally:
                    logger.warning(f"KAG 流结束但无 'done' 信号。 ({task_id})") # 逻辑备注
                    # 逻辑备注: 即使没有 done 信号，也发送一个完成信号，确保后续流程触发
                    result_queue.put((task_id, "success", "stream_done", f"{task_id}: 处理完成", update_target_widget, status_label_widget))
            except StopIteration: # 功能性备注: 捕获由 _thread_wrapper 抛出的停止异常
                logger.info(f"任务 {task_id} (流式) 被停止。") # 功能性备注
                raise # 功能性备注: 重新抛出，让 _thread_wrapper 处理队列消息
            except Exception as stream_e:
                 # 逻辑备注: 捕获处理流时的异常
                 logger.exception(f"处理流时发生异常: {stream_e} ({task_id})") # 逻辑备注
                 result_queue.put((task_id, "error", "stream_error", f"流处理异常: {stream_e}", update_target_widget, status_label_widget))
                 return None, f"流处理异常: {stream_e}"
            return None, None # 功能性备注: 流式处理完成或被停止，结果通过队列传递
        else:
             # 逻辑备注: 流式处理失败：找不到 API 函数或结果队列
             error_msg = "流式处理失败：找不到 API 函数或结果队列。"
             logger.error(f"{error_msg} ({task_id})") # 逻辑备注
             if result_queue: result_queue.put((task_id, "error", "stream_error", error_msg, update_target_widget, status_label_widget))
             return None, error_msg

    else:
        # --- 非流式处理 ---
        logger.info(f"[{task_id}] 执行非流式 KAG 转换...") # 功能性备注
        script_body, error = None, None

        # 逻辑备注: 在调用 API 前检查停止信号
        if stop_event and stop_event.is_set():
            logger.info(f"任务 {task_id} 在 API 调用前被停止。") # 功能性备注
            raise StopIteration("任务被用户停止") # 功能性备注: 抛出异常以通知包装器

        # 逻辑备注: 根据提供商调用相应的 API 助手
        if provider == "Google":
            google_config = api_helpers.app.get_google_specific_config()
            script_body, error = api_helpers.call_google_non_stream(
                api_key=google_config.get('apiKey'), api_base_url=google_config.get('apiEndpoint'), model_name=google_config.get('modelName'),
                prompt=prompt, temperature=llm_config_for_step3.get('temperature'), max_output_tokens=llm_config_for_step3.get('maxOutputTokens'),
                top_p=llm_config_for_step3.get('topP'), top_k=llm_config_for_step3.get('topK'),
                prompt_type="KAGConversion", proxy_config=proxy_config,
                save_debug=save_debug # 功能性备注
            )
        elif provider == "OpenAI":
            openai_config = api_helpers.app.get_openai_specific_config()
            script_body, error = api_helpers.call_openai_non_stream(
                api_key=openai_config.get('apiKey'), api_base_url=openai_config.get('apiBaseUrl'), model_name=openai_config.get('modelName'),
                prompt=prompt, temperature=llm_config_for_step3.get('temperature'), max_tokens=llm_config_for_step3.get('maxOutputTokens'),
                custom_headers=openai_config.get('customHeaders'), proxy_config=proxy_config,
                save_debug=save_debug # 功能性备注
            )
        else:
            # 逻辑备注: 不支持的提供商
            error_msg = f"不支持的 LLM 提供商 '{provider}'"
            logger.error(f"{error_msg} ({task_id})") # 逻辑备注
            error = f"错误 ({task_id}): {error_msg}"

        # 逻辑备注: 在 API 调用后检查停止信号
        if stop_event and stop_event.is_set():
            logger.info(f"任务 {task_id} 在 API 调用后被停止，结果将被丢弃。") # 功能性备注
            raise StopIteration("任务被用户停止") # 功能性备注: 抛出异常以通知包装器

        # 功能性备注: 处理非流式结果
        if error:
            logger.error(f"非流式 KAG 转换失败: {error}") # 逻辑备注
            return None, error # 功能性备注: 返回错误
        else:
            logger.info(f"非流式 KAG 转换成功。") # 功能性备注
            # 功能性备注: 添加 KAG 脚本结尾
            footer = "\n\n@s ; Script End"
            final_script = (script_body or "") + footer
            return final_script, None # 功能性备注: 返回最终脚本和 None (表示无错误)