# utils.py
import re

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
            print(f"警告: 发现名称无效的占位符: {match.group(0)}")
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
        print(f"替换占位符: '{match.group(0)}' -> 注释的 KAG 标签 for '{filename}'")
        return kag_tag # 返回生成的注释标签

    # 使用正则表达式的 sub 方法，将所有匹配到的占位符替换为 replace_match 函数的返回值
    processed_script = placeholder_regex.sub(replace_match, kag_script)

    print(f"图片占位符已替换为注释掉的 image 标签，共替换 {replacements_made} 个。")
    # 返回处理后的脚本和替换总数
    return processed_script, replacements_made