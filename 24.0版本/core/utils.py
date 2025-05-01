# core/utils.py
import re
import traceback
import logging # 导入日志模块

# 获取当前模块的 logger 实例
logger = logging.getLogger(__name__)

def replace_kag_placeholders(kag_script, prefix=""):
    """
    将 KAG 脚本中的 [INSERT_IMAGE_HERE:名字] 占位符替换为 注释掉的 [image storage="..."] 标签。
    """
    if not kag_script: return "", 0
    placeholder_regex = re.compile(r'\[INSERT_IMAGE_HERE:([^\]]+?)\]')
    character_image_counters = {} # 用于跟踪每个角色的图片序号
    replacements_made = 0 # 计数器

    def replace_match(match):
        nonlocal replacements_made
        character_name = match.group(1).strip()
        # 清理名称，用于文件名
        sanitized_name = re.sub(r'[\\/*?:"<>|\s\.]+', '_', character_name)
        if not sanitized_name:
            # 记录无效占位符的警告
            logger.warning(f"警告 (utils): 发现名称无效的占位符: {match.group(0)}")
            return match.group(0) # 返回原始占位符
        # 更新并获取序号
        character_image_counters[sanitized_name] = character_image_counters.get(sanitized_name, 0) + 1
        index = character_image_counters[sanitized_name]
        # 构建文件名和 KAG 标签
        filename = f"{prefix}{sanitized_name}_{index}.png"
        kag_tag = f';[image storage="{filename}" layer=0 page=fore visible=true]'
        replacements_made += 1
        # 记录替换信息
        logger.info(f"替换占位符 (utils): '{match.group(0)}' -> 注释的 KAG 标签 for '{filename}'")
        return kag_tag

    # 执行替换
    processed_script = placeholder_regex.sub(replace_match, kag_script)
    # 记录替换完成信息
    logger.info(f"图片占位符替换完成 (utils)，共替换 {replacements_made} 个。")
    return processed_script, replacements_made

def post_process_kag_script(raw_kag_script):
    """
    对 LLM 生成的 KAG 脚本进行格式后处理。
    """
    if not raw_kag_script: return ""
    processed_script = raw_kag_script.strip()
    logger.info("开始 KAG 脚本后处理 (utils)...")

    try:
        # 1. 移除 Markdown 代码块包裹
        if processed_script.startswith("```") and processed_script.endswith("```"):
            processed_script = processed_script[3:-3].strip()
            processed_script = re.sub(r'^[a-zA-Z]*\n', '', processed_script, count=1)
            logger.info("  > 1. 移除了 Markdown 代码块包裹 (utils)。")
        elif processed_script.startswith("```"):
             processed_script = processed_script[3:].strip()
             processed_script = re.sub(r'^[a-zA-Z]*\n', '', processed_script, count=1)
             logger.info("  > 1. 移除了开头的 Markdown 代码块标记 (utils)。")
        else:
             logger.info("  > 1. 未发现 Markdown 代码块包裹 (utils)。")

        # 2. 处理心声：将 *{{内容}}*[p] 替换为 （内容）[p]
        processed_script = re.sub(r'\*\{\{(.*?)\}\}\*(\[p\])', r'（\1）\2', processed_script, flags=re.MULTILINE)
        logger.info("  > 2. 心声格式 (*{{...}}* -> （...）) 处理完成 (utils)。")

        # 3. 修正 @playse 注释行的 name 属性
        def fix_playse_name(match):
            name_tag_line = match.group(1)
            correct_name = match.group(2)
            playse_line = match.group(3)
            # 尝试修正或添加 name 属性
            corrected_playse = re.sub(r'(;\s*name=)("?)(.*?)("?)(\s*;|$)', rf'\1"{re.escape(correct_name)}"\5', playse_line)
            if corrected_playse == playse_line and '; name=' not in playse_line:
                 corrected_playse = playse_line.rstrip() + f' ; name="{correct_name}"'
            elif corrected_playse == playse_line:
                 # 记录无法自动修正的警告
                 logger.warning(f"警告 (utils): 未能自动修正 @playse 行的 name 属性: {playse_line}")
            return f"{name_tag_line}\n{corrected_playse}"
        processed_script = re.sub(r'^(\[name\](.*?)\[/name\])\n(;\s*@playse.*)', fix_playse_name, processed_script, flags=re.MULTILINE)
        logger.info("  > 3. @playse 注释行的 name 属性修正完成 (utils)。")

        # 4. 清理对话行，确保被「」包裹且移除错误前缀
        def clean_dialogue_line(match):
            name_tag_line = match.group(1)
            name_in_tag = match.group(2)
            playse_line = match.group(3)
            dialogue_content = match.group(4).strip()
            end_tag = match.group(5)
            # 移除可能错误添加的前缀（如名字、引号）
            cleaned_content = re.sub(rf'^(?:「?{re.escape(name_in_tag)}」?|{re.escape(name_in_tag)}「|{re.escape(name_in_tag)}[ 　:：]+)(.*)', r'\1', dialogue_content, flags=re.IGNORECASE | re.DOTALL).strip()
            cleaned_content = re.sub(r'^["“「]*(.*?)[”」"]?$', r'\1', cleaned_content).strip()
            # 防止内容被完全移除
            if cleaned_content == name_in_tag:
                cleaned_content = ""
            # 确保使用「」包裹并添加 [p]
            final_dialogue_line = f"「{cleaned_content}」{end_tag or '[p]'}"
            return f"{name_tag_line}\n{playse_line}\n{final_dialogue_line}"
        processed_script = re.sub(r'^(\[name\](.*?)\[/name\])\n(;\s*@playse.*?)\n(.*?)(?:(\[p\])|$)', clean_dialogue_line, processed_script, flags=re.MULTILINE)
        logger.info("  > 4. 对话行格式清理 (移除错误前缀, 确保「」和[p]) 完成 (utils)。")

        # 5. 修正被错误包裹在对话引号内的 @playse 注释
        error_pattern = re.compile(r'^「(.*?)?(;?\s*@playse\s+storage=.*?;?\s*name=.*?)(.*?)?」(\[p\])$', flags=re.MULTILINE)
        corrected_lines_list = []
        last_index = 0
        corrected_count_step5 = 0
        temp_script_for_finditer = processed_script
        for match in error_pattern.finditer(temp_script_for_finditer):
            corrected_lines_list.append(temp_script_for_finditer[last_index:match.start()])
            before_comment = (match.group(1) or "").strip()
            playse_comment = match.group(2).strip()
            after_comment = (match.group(3) or "").strip()
            p_tag = match.group(4)
            # 确保 playse 注释以分号开头
            if not playse_comment.startswith(';'): playse_comment = ';' + playse_comment
            # 组合对话文本
            dialogue_text = (before_comment + " " + after_comment).strip()
            dialogue_line = f"「{dialogue_text}」{p_tag}" if dialogue_text else f"「」{p_tag}"
            # 尝试修正 playse 注释中的 name
            prev_text = temp_script_for_finditer[:match.start()]
            name_match = re.search(r'\[name\](.*?)\[/name\]\s*$', prev_text, re.MULTILINE)
            correct_name = name_match.group(1) if name_match else "Unknown"
            playse_comment = re.sub(r'(;\s*name=)("?)(.*?)("?)(\s*;|$)', rf'\1"{re.escape(correct_name)}"\5', playse_comment)
            if '; name=' not in playse_comment:
                 playse_comment = playse_comment.rstrip() + f' ; name="{correct_name}"'
            # 添加修正后的行
            corrected_lines_list.append(playse_comment)
            corrected_lines_list.append(dialogue_line)
            corrected_count_step5 += 1
            last_index = match.end()
        corrected_lines_list.append(temp_script_for_finditer[last_index:])
        if corrected_count_step5 > 0:
            processed_script = "\n".join(corrected_lines_list)
            logger.info(f"  > 5. 修正了 {corrected_count_step5} 处被错误包裹的 @playse 注释 (utils)。")
        else:
            logger.info("  > 5. 未发现需要修正的错误包裹的 @playse 注释 (utils)。")

        # 6. 为 @playse 注释行的 storage 属性添加序号
        logger.info("  > 6. 开始为 @playse storage 添加序号 (utils)...")
        speaker_audio_counters = {} # 跟踪每个说话人的语音序号
        numbered_lines = []
        processed_lines = processed_script.splitlines()
        playse_pattern = re.compile(r'^(\s*;\s*@playse\s+storage="PLACEHOLDER_([^"]+?)\.wav")(.*?;?\s*name="(.*?)".*)$')
        numbered_count = 0
        for line in processed_lines:
            match = playse_pattern.match(line)
            if match:
                prefix = match.group(1)
                speaker_name_in_placeholder = match.group(2)
                suffix = match.group(3)
                speaker_name_in_name_attr = match.group(4)
                # 优先使用 name 属性中的名字
                speaker_name = speaker_name_in_name_attr if speaker_name_in_name_attr else speaker_name_in_placeholder
                if not speaker_name:
                    # 记录无法确定说话人的警告
                    logger.warning(f"警告 (utils): 无法确定 @playse 行的说话人，跳过编号: {line}")
                    numbered_lines.append(line)
                    continue
                # 清理说话人名称用于文件名
                sanitized_speaker_name = re.sub(r'[\\/*?:"<>|\s\.]+', '_', speaker_name)
                if not sanitized_speaker_name:
                     # 记录清理后名称无效的警告
                     logger.warning(f"警告 (utils): 清理后的说话人名称无效，跳过编号: {line}")
                     numbered_lines.append(line)
                     continue
                # 更新并获取序号
                speaker_audio_counters[sanitized_speaker_name] = speaker_audio_counters.get(sanitized_speaker_name, 0) + 1
                index = speaker_audio_counters[sanitized_speaker_name]
                # 构建新的 storage 部分和整行
                new_storage_part = f'; @playse storage="PLACEHOLDER_{sanitized_speaker_name}_{index}.wav"'
                new_line = new_storage_part + suffix
                numbered_lines.append(new_line)
                numbered_count += 1
            else:
                numbered_lines.append(line) # 非 @playse 行直接添加
        processed_script = "\n".join(numbered_lines)
        logger.info(f"  > 6. 为 {numbered_count} 个 @playse storage 添加序号完成 (utils)。")

        # 7. 清理多余的空行
        processed_script = re.sub(r'\n{3,}', '\n\n', processed_script).strip()
        logger.info("  > 7. 清理多余空行完成 (utils)。")

        logger.info("KAG 脚本后处理完成 (utils)。")
        return processed_script

    except Exception as e:
        # 记录后处理失败的错误
        logger.exception(f"错误：KAG 脚本后处理失败 (utils): {e}")
        return raw_kag_script # 返回原始脚本

# --- 新增：重新注释 KAG 标签的函数 ---
def recomment_kag_image_tags(script_content):
    """
    将 KAG 脚本中未注释的 [image storage="..."] 标签重新注释掉。
    """
    if not script_content:
        return "", 0
    # 匹配不以分号开头的 [image ...] 行
    pattern = re.compile(r'^(?!\s*;)(\s*\[image\s+storage=.*?\])', flags=re.MULTILINE)
    count = 0
    def add_comment(match):
        nonlocal count
        count += 1
        # 在匹配到的行前面加上分号和空格
        return f";{match.group(1)}"

    processed_script = pattern.sub(add_comment, script_content)
    logger.info(f"重新注释图片标签完成 (utils)，共处理 {count} 个。")
    return processed_script, count

def recomment_kag_audio_tags(script_content):
    """
    将 KAG 脚本中未注释的 @playse storage="..." ... name="..." 标签重新注释掉。
    """
    if not script_content:
        return "", 0
    # 匹配不以分号开头的 @playse 行
    pattern = re.compile(r'^(?!\s*;)(\s*@playse\s+storage=.*?name=.*?)$', flags=re.MULTILINE)
    count = 0
    def add_comment(match):
        nonlocal count
        count += 1
        # 在匹配到的行前面加上分号和空格
        return f";{match.group(1)}"

    processed_script = pattern.sub(add_comment, script_content)
    logger.info(f"重新注释语音标签完成 (utils)，共处理 {count} 个。")
    return processed_script, count