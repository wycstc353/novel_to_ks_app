# core/utils.py
import re
import traceback # 导入 traceback

def replace_kag_placeholders(kag_script, prefix=""):
    """
    将 KAG 脚本中的 [INSERT_IMAGE_HERE:名字] 占位符替换为 注释掉的 [image storage="..."] 标签。

    Args:
        kag_script (str): 包含占位符的 KAG 脚本字符串。
        prefix (str, optional): 添加到生成的文件名前的前缀。 Defaults to "".

    Returns:
        tuple: (processed_script: str, replacements_made: int)
               处理后的脚本字符串和替换的数量。
    """
    if not kag_script:
        # 如果输入脚本为空，直接返回空字符串和0
        return "", 0

    # 正则表达式用于匹配占位符 [INSERT_IMAGE_HERE:名字]
    placeholder_regex = re.compile(r'\[INSERT_IMAGE_HERE:([^\]]+?)\]')
    # 字典用于跟踪每个角色图片名称的计数器，以生成唯一的索引
    character_image_counters = {}
    # 记录替换发生的次数
    replacements_made = 0

    def replace_match(match):
        """内部函数，用于处理每个匹配到的占位符"""
        nonlocal replacements_made # 允许修改外部作用域的 replacements_made 变量
        character_name = match.group(1).strip() # 获取捕获组1（名字），并去除首尾空格

        # 清理名称，移除或替换可能导致文件名无效的字符
        # 将非法字符（\ / * ? : " < > |）、空格、点都替换为下划线
        sanitized_name = re.sub(r'[\\/*?:"<>|\s\.]+', '_', character_name)

        if not sanitized_name:
            # 如果清理后的名称为空（例如，原始名称只包含非法字符），则发出警告并跳过
            print(f"警告 (utils): 发现名称无效的占位符: {match.group(0)}")
            return match.group(0) # 返回原始占位符，不做替换

        # 计算该角色的图片序号（从1开始）
        # 如果角色名不在计数器中，get返回0，然后+1；否则返回当前计数值，然后+1
        character_image_counters[sanitized_name] = character_image_counters.get(sanitized_name, 0) + 1
        index = character_image_counters[sanitized_name]

        # 构建文件名，格式为 "前缀清理后的名字_序号.png"
        filename = f"{prefix}{sanitized_name}_{index}.png" # 强制使用 .png 后缀

        # 构建要替换成的 KAG 标签字符串
        # 生成一个注释掉的 KAG image 标签，并且后面没有 [p]
        # 注意：以分号 ';' 开头表示这是 KAG 脚本中的注释行
        kag_tag = f';[image storage="{filename}" layer=0 page=fore visible=true]'

        replacements_made += 1 # 增加替换计数
        print(f"替换占位符 (utils): '{match.group(0)}' -> 注释的 KAG 标签 for '{filename}'")
        return kag_tag # 返回生成的注释标签

    # 使用正则表达式的 sub 方法，将所有匹配到的占位符替换为 replace_match 函数的返回值
    processed_script = placeholder_regex.sub(replace_match, kag_script)

    print(f"图片占位符替换完成 (utils)，共替换 {replacements_made} 个。")
    # 返回处理后的脚本和替换总数
    return processed_script, replacements_made

# --- 修改：KAG 脚本后处理函数 ---
def post_process_kag_script(raw_kag_script):
    """
    对 LLM 生成的 KAG 脚本进行格式后处理。
    1. 将 *{{心声}}*[p] 替换为 （心声）[p]
    2. 修正 @playse 注释行的 name 属性。
    3. 清理对话行，确保被「」包裹且移除错误前缀。
    4. 修正被错误包裹在对话引号内的 @playse 注释。
    5. 清理多余的空行。

    Args:
        raw_kag_script (str): LLM 生成的原始 KAG 脚本。

    Returns:
        str: 经过后处理的 KAG 脚本。
    """
    if not raw_kag_script:
        return ""

    processed_script = raw_kag_script
    print("开始 KAG 脚本后处理 (utils)...")

    try:
        # 1. 处理心声：将 *{{内容}}*[p] 替换为 （内容）[p]
        processed_script = re.sub(r'\*\{\{(.*?)\}\}\*(\[p\])', r'（\1）\2', processed_script, flags=re.MULTILINE)
        print("  > 1. 心声格式 (*{{...}}* -> （...）) 处理完成 (utils)。")

        # 2. 修正 @playse 注释行的 name 属性
        #    查找 [name]标签 和 紧随其后的 @playse 注释行
        def fix_playse_name(match):
            name_tag_line = match.group(1) # [name]名字[/name]
            correct_name = match.group(2) # 名字
            playse_line = match.group(3) # ; @playse ... name=...

            # 查找 name= 部分并替换其值
            # 使用 re.escape 确保名字中的特殊字符被正确处理
            corrected_playse = re.sub(r'(;\s*name=)(.*?)(?=\s*;|$)', rf'\1"{re.escape(correct_name)}"', playse_line)
            # 如果 name= 不存在或格式错误，可能替换失败，但至少尝试了
            if corrected_playse == playse_line: # 如果没有发生替换
                 # 尝试在末尾添加（如果完全没有 name=）
                 if '; name=' not in playse_line:
                      corrected_playse = playse_line.rstrip() + f' ; name="{correct_name}"'
                 else: # 如果有 name= 但格式不对导致上面没替换成功，打印警告
                      print(f"警告 (utils): 未能自动修正 @playse 行的 name 属性: {playse_line}")

            return f"{name_tag_line}\n{corrected_playse}" # 返回修正后的两行

        # 匹配 [name]...[/name] 后紧跟 @playse 注释行
        processed_script = re.sub(r'^(\[name\](.*?)\[/name\])\n(;\s*@playse.*)', fix_playse_name, processed_script, flags=re.MULTILINE)
        print("  > 2. @playse 注释行的 name 属性修正完成 (utils)。")


        # 3. 清理对话行，确保被「」包裹且移除错误前缀
        #    现在处理的是 [name]... \n ;@playse... \n 「对话」... 结构
        def clean_dialogue_line(match):
            name_tag_line = match.group(1) # [name]名字[/name]
            name_in_tag = match.group(2) # 名字
            playse_line = match.group(3) # ; @playse ...
            dialogue_content = match.group(4).strip() # 对话内容
            end_tag = match.group(5) # [p] 或行尾的 None

            # 积极清理对话内容开头的错误前缀（名字、引号等）
            # 移除行首的 "「名字」" 或 "名字「" 或 "名字 " 或 "名字　" 或 "名字:" 或 "名字：" 或仅 "名字"
            cleaned_content = re.sub(rf'^(?:「?{re.escape(name_in_tag)}」?|{re.escape(name_in_tag)}「|{re.escape(name_in_tag)}[ 　:：]+)(.*)', r'\1', dialogue_content, flags=re.IGNORECASE | re.DOTALL)
            # 再次去除可能的旧引号或名字本身（如果清理后剩下的是名字）
            cleaned_content = re.sub(r'^["“「]*(.*?)[”」"]?$', r'\1', cleaned_content.strip())
            if cleaned_content.strip() == name_in_tag: # 如果清理后只剩下名字，说明原对话为空
                cleaned_content = ""

            # 确保被「」包裹，并有 [p] 结尾
            final_dialogue_line = f"「{cleaned_content.strip()}」{end_tag or '[p]'}"

            return f"{name_tag_line}\n{playse_line}\n{final_dialogue_line}"

        # 匹配 [name]... \n ;@playse... \n 对话行...
        processed_script = re.sub(r'^(\[name\](.*?)\[/name\])\n(;\s*@playse.*?)\n(.*?)(?:(\[p\])|$)', clean_dialogue_line, processed_script, flags=re.MULTILINE)
        print("  > 3. 对话行格式清理 (移除错误前缀, 确保「」和[p]) 完成 (utils)。")


        # 4. 修正被错误包裹在对话引号内的 @playse 注释 (作为补充修正)
        error_pattern = re.compile(r'^「(.*?)?(;?\s*@playse\s+storage=.*?;?\s*name=.*?)(.*?)?」(\[p\])$', flags=re.MULTILINE)
        corrected_lines = []
        last_index = 0
        corrected_count = 0
        for match in error_pattern.finditer(processed_script):
            corrected_lines.append(processed_script[last_index:match.start()])
            before_comment = (match.group(1) or "").strip()
            playse_comment = match.group(2).strip()
            after_comment = (match.group(3) or "").strip()
            p_tag = match.group(4)

            if not playse_comment.startswith(';'):
                playse_comment = ';' + playse_comment

            dialogue_text = (before_comment + " " + after_comment).strip()
            dialogue_line = f"「{dialogue_text}」{p_tag}" if dialogue_text else f"「」{p_tag}"

            # 查找此错误模式前的 [name] 标签以获取正确的名字
            prev_text = processed_script[:match.start()]
            name_match = re.search(r'\[name\](.*?)\[/name\]\s*$', prev_text, re.MULTILINE)
            correct_name = name_match.group(1) if name_match else "Unknown" # 获取名字

            # 修正 playse 注释中的 name
            playse_comment = re.sub(r'(;\s*name=)(.*?)(?=\s*;|$)', rf'\1"{re.escape(correct_name)}"', playse_comment)
            if '; name=' not in playse_comment: # 如果完全没有 name=
                 playse_comment = playse_comment.rstrip() + f' ; name="{correct_name}"'


            corrected_lines.append(playse_comment) # 注释行
            corrected_lines.append(dialogue_line)  # 对话行
            corrected_count += 1
            last_index = match.end()

        corrected_lines.append(processed_script[last_index:])
        if corrected_count > 0:
            processed_script = "\n".join(corrected_lines)
            print(f"  > 4. 修正了 {corrected_count} 处被错误包裹的 @playse 注释 (utils)。")
        else:
            print("  > 4. 未发现需要修正的错误包裹的 @playse 注释 (utils)。")

        # 5. 清理多余的空行
        processed_script = re.sub(r'\n{3,}', '\n\n', processed_script).strip()
        print("  > 5. 清理多余空行完成 (utils)。")

        print("KAG 脚本后处理完成 (utils)。")
        return processed_script

    except Exception as e:
        print(f"错误：KAG 脚本后处理失败 (utils): {e}")
        traceback.print_exc()
        # 后处理失败时，返回原始脚本，避免丢失内容
        return raw_kag_script