# core/utils.py
import re
import traceback

def replace_kag_placeholders(kag_script, prefix=""):
    """
    将 KAG 脚本中的 [INSERT_IMAGE_HERE:名字] 占位符替换为 注释掉的 [image storage="..."] 标签。
    """
    if not kag_script: return "", 0
    placeholder_regex = re.compile(r'\[INSERT_IMAGE_HERE:([^\]]+?)\]')
    character_image_counters = {}
    replacements_made = 0

    def replace_match(match):
        nonlocal replacements_made
        character_name = match.group(1).strip()
        sanitized_name = re.sub(r'[\\/*?:"<>|\s\.]+', '_', character_name)
        if not sanitized_name:
            print(f"警告 (utils): 发现名称无效的占位符: {match.group(0)}")
            return match.group(0)
        character_image_counters[sanitized_name] = character_image_counters.get(sanitized_name, 0) + 1
        index = character_image_counters[sanitized_name]
        filename = f"{prefix}{sanitized_name}_{index}.png"
        kag_tag = f';[image storage="{filename}" layer=0 page=fore visible=true]'
        replacements_made += 1
        print(f"替换占位符 (utils): '{match.group(0)}' -> 注释的 KAG 标签 for '{filename}'")
        return kag_tag

    processed_script = placeholder_regex.sub(replace_match, kag_script)
    print(f"图片占位符替换完成 (utils)，共替换 {replacements_made} 个。")
    return processed_script, replacements_made

# --- 修改：KAG 脚本后处理函数 (增加语音占位符序号生成步骤) ---
def post_process_kag_script(raw_kag_script):
    """
    对 LLM 生成的 KAG 脚本进行格式后处理。
    1. 将 *{{心声}}*[p] 替换为 （心声）[p]
    2. 修正 @playse 注释行的 name 属性。
    3. 清理对话行，确保被「」包裹且移除错误前缀。
    4. 修正被错误包裹在对话引号内的 @playse 注释。
    5. 为 @playse 注释行的 storage 属性添加序号。
    6. 清理多余的空行。
    """
    if not raw_kag_script: return ""
    processed_script = raw_kag_script
    print("开始 KAG 脚本后处理 (utils)...")

    try:
        # 1. 处理心声：将 *{{内容}}*[p] 替换为 （内容）[p]
        processed_script = re.sub(r'\*\{\{(.*?)\}\}\*(\[p\])', r'（\1）\2', processed_script, flags=re.MULTILINE)
        print("  > 1. 心声格式 (*{{...}}* -> （...）) 处理完成 (utils)。")

        # 2. 修正 @playse 注释行的 name 属性
        def fix_playse_name(match):
            name_tag_line = match.group(1)
            correct_name = match.group(2)
            playse_line = match.group(3)
            corrected_playse = re.sub(r'(;\s*name=)(.*?)(?=\s*;|$)', rf'\1"{re.escape(correct_name)}"', playse_line)
            if corrected_playse == playse_line:
                 if '; name=' not in playse_line: corrected_playse = playse_line.rstrip() + f' ; name="{correct_name}"'
                 else: print(f"警告 (utils): 未能自动修正 @playse 行的 name 属性: {playse_line}")
            return f"{name_tag_line}\n{corrected_playse}"
        processed_script = re.sub(r'^(\[name\](.*?)\[/name\])\n(;\s*@playse.*)', fix_playse_name, processed_script, flags=re.MULTILINE)
        print("  > 2. @playse 注释行的 name 属性修正完成 (utils)。")

        # 3. 清理对话行，确保被「」包裹且移除错误前缀
        def clean_dialogue_line(match):
            name_tag_line = match.group(1)
            name_in_tag = match.group(2)
            playse_line = match.group(3)
            dialogue_content = match.group(4).strip()
            end_tag = match.group(5)
            cleaned_content = re.sub(rf'^(?:「?{re.escape(name_in_tag)}」?|{re.escape(name_in_tag)}「|{re.escape(name_in_tag)}[ 　:：]+)(.*)', r'\1', dialogue_content, flags=re.IGNORECASE | re.DOTALL)
            cleaned_content = re.sub(r'^["“「]*(.*?)[”」"]?$', r'\1', cleaned_content.strip())
            if cleaned_content.strip() == name_in_tag: cleaned_content = ""
            final_dialogue_line = f"「{cleaned_content.strip()}」{end_tag or '[p]'}"
            return f"{name_tag_line}\n{playse_line}\n{final_dialogue_line}"
        processed_script = re.sub(r'^(\[name\](.*?)\[/name\])\n(;\s*@playse.*?)\n(.*?)(?:(\[p\])|$)', clean_dialogue_line, processed_script, flags=re.MULTILINE)
        print("  > 3. 对话行格式清理 (移除错误前缀, 确保「」和[p]) 完成 (utils)。")

        # 4. 修正被错误包裹在对话引号内的 @playse 注释 (作为补充修正)
        error_pattern = re.compile(r'^「(.*?)?(;?\s*@playse\s+storage=.*?;?\s*name=.*?)(.*?)?」(\[p\])$', flags=re.MULTILINE)
        corrected_lines_list = [] # 使用列表存储处理后的行
        last_index = 0
        corrected_count_step4 = 0
        for match in error_pattern.finditer(processed_script):
            corrected_lines_list.append(processed_script[last_index:match.start()])
            before_comment = (match.group(1) or "").strip()
            playse_comment = match.group(2).strip()
            after_comment = (match.group(3) or "").strip()
            p_tag = match.group(4)
            if not playse_comment.startswith(';'): playse_comment = ';' + playse_comment
            dialogue_text = (before_comment + " " + after_comment).strip()
            dialogue_line = f"「{dialogue_text}」{p_tag}" if dialogue_text else f"「」{p_tag}"
            prev_text = processed_script[:match.start()]
            name_match = re.search(r'\[name\](.*?)\[/name\]\s*$', prev_text, re.MULTILINE)
            correct_name = name_match.group(1) if name_match else "Unknown"
            playse_comment = re.sub(r'(;\s*name=)(.*?)(?=\s*;|$)', rf'\1"{re.escape(correct_name)}"', playse_comment)
            if '; name=' not in playse_comment: playse_comment = playse_comment.rstrip() + f' ; name="{correct_name}"'
            corrected_lines_list.append(playse_comment)
            corrected_lines_list.append(dialogue_line)
            corrected_count_step4 += 1
            last_index = match.end()
        corrected_lines_list.append(processed_script[last_index:])
        if corrected_count_step4 > 0:
            processed_script = "\n".join(corrected_lines_list) # 从列表重新构建脚本
            print(f"  > 4. 修正了 {corrected_count_step4} 处被错误包裹的 @playse 注释 (utils)。")
        else:
            print("  > 4. 未发现需要修正的错误包裹的 @playse 注释 (utils)。")

        # --- 新增步骤 5: 为 @playse 注释行的 storage 属性添加序号 ---
        print("  > 5. 开始为 @playse storage 添加序号 (utils)...")
        speaker_audio_counters = {} # 初始化序号计数器
        numbered_lines = []         # 存储添加序号后的行
        processed_lines = processed_script.splitlines() # 按行分割脚本
        playse_pattern = re.compile(r'^(\s*;\s*@playse\s+storage="PLACEHOLDER_(.*?)\.wav")(.*?;?\s*name="(.*?)".*)$') # 匹配不带序号的占位符行
        numbered_count = 0
        for line in processed_lines:
            match = playse_pattern.match(line)
            if match:
                # 提取信息
                prefix = match.group(1) # ; @playse storage="PLACEHOLDER_名字
                speaker_name_in_placeholder = match.group(2) # 名字 (从 storage)
                suffix = match.group(3) # " buf=0 ; name="名字"...
                speaker_name_in_name_attr = match.group(4) # 名字 (从 name 属性)

                # 优先使用 name 属性中的名字来计数和生成文件名
                speaker_name = speaker_name_in_name_attr if speaker_name_in_name_attr else speaker_name_in_placeholder
                if not speaker_name: # 如果两个都为空，跳过
                    print(f"警告 (utils): 无法确定 @playse 行的说话人，跳过编号: {line}")
                    numbered_lines.append(line)
                    continue

                # 生成序号
                speaker_audio_counters[speaker_name] = speaker_audio_counters.get(speaker_name, 0) + 1
                index = speaker_audio_counters[speaker_name]

                # 构建新的带序号的 storage 属性部分
                new_storage_part = f'; @playse storage="PLACEHOLDER_{speaker_name}_{index}.wav"'
                # 组合成新的行
                new_line = new_storage_part + suffix
                numbered_lines.append(new_line)
                numbered_count += 1
                # print(f"    编号: {line} -> {new_line}") # 调试日志
            else:
                # 如果行不匹配，直接添加到结果列表
                numbered_lines.append(line)

        processed_script = "\n".join(numbered_lines) # 从列表重新构建脚本
        print(f"  > 5. 为 {numbered_count} 个 @playse storage 添加序号完成 (utils)。")
        # --- 序号添加步骤结束 ---

        # 6. 清理多余的空行 (原步骤 5)
        processed_script = re.sub(r'\n{3,}', '\n\n', processed_script).strip()
        print("  > 6. 清理多余空行完成 (utils)。")

        print("KAG 脚本后处理完成 (utils)。")
        return processed_script

    except Exception as e:
        print(f"错误：KAG 脚本后处理失败 (utils): {e}")
        traceback.print_exc()
        return raw_kag_script # 后处理失败时返回原始脚本