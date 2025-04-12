# core/prompts.py
import re

class PromptTemplates:
    """存储用于 LLM 调用的 Prompt 模板"""

    # --- PREPROCESSING_PROMPT_TEMPLATE (无变化) ---
    PREPROCESSING_PROMPT_TEMPLATE = """
{pre_instruction}

**任务：精确格式化小说文本，添加说话人标记**

请仔细阅读【原始小说文本】。
你的核心任务是：**仅在**那些**直接包含角色说的话（通常由引号 `“...”` 或 `「...」` 包裹）的文本行**的【正上方】，添加说话人标记 `[名字]`。

**必须严格遵守以下规则：**

1.  **识别对话行：** 找到那些主要内容是角色说的话的行，这些行通常以引号 `“` 或 `「` 开始，并以引号 `”` 或 `」` 结束。
2.  **确定说话人：** 根据对话行的上下文（通常是对话行之前紧邻的句子或段落）判断是谁在说话。
3.  **精确定位标记：** 将 `[说话人名字]` 标记**只添加在**你识别出的**对话行**（即被引号包裹的那一行）的【紧邻的上一行】。
4.  **处理内心想法：** 如果原文中明确标识了内心想法（例如，使用特殊的括号或引导词），则用 `*{{...}}*` 包裹那部分内心想法文本。如果没有明确标识，则不添加此标记。
5.  **绝对禁止：**
    *   **禁止**在非对话行（如纯粹的动作描述、场景描述、旁白）上方添加 `[名字]` 标记。
    *   **禁止**将 `[名字]` 标记添加到包含动作描述和对话的混合段落的开头。标记必须紧邻纯对话行。
    *   禁止生成任何新的文本内容。
    *   禁止修改或删除原始文本的任何字符。
    *   禁止添加除 `[名字]` 和 `*{{...}}*` 之外的任何标记。
    *   禁止进行任何解释或评论。

**--- 原始小说文本 ---**
{text_chunk}
**--- 文本结束 ---**

{post_instruction}

请根据以上所有规则和指令，输出带有精确标记的格式化文本：
"""

    # --- PROMPT_ENHANCEMENT_TEMPLATE (无变化) ---
    PROMPT_ENHANCEMENT_TEMPLATE = """
{pre_instruction}
你是一个高级小说处理助手，擅长理解上下文并生成符合场景的 NAI (NovelAI) 或 Stable Diffusion 风格的图像生成提示词。
你的任务是：阅读【已格式化文本】，参考【人物基础设定】，并在特定人物的对话或重要动作【之前】，智能地生成并添加提示词标记。
输入包含两部分：
1.  【已格式化文本】：包含 `[名字]` 说话人标记和 `*{{...}}*` 心声标记的文本。这是主要的上下文来源。
2.  【人物基础设定】：一个 JSON 字符串，格式为 `{{"人物名字1": {{"positive": "基础正面提示词", "negative": "基础负面提示词"}}, "人物名字2": {{...}} }}`。这些是每个角色**固定不变**的提示词。
严格遵循以下规则进行处理：
1.  **分析上下文**: 当遇到说话人标记 `[名字]` 时，仔细阅读该标记**之后**的几行文本（对话、动作描述等），理解当前场景、人物的情绪、动作和环境。
2.  **查找基础设定**: 在【人物基础设定】中查找当前说话人 `[名字]` 对应的基础提示词（positive 和 negative）。
3.  **动态生成提示词**: 基于你对当前上下文的理解（步骤 1），以及人物的基础设定（步骤 2），为当前场景**动态生成**额外的、描述性的提示词。这些动态提示词应该反映：
    *   人物的**当前情绪**（例如：`smiling`, `angry`, `crying`, `blushing`）
    *   人物的**主要动作或姿态**（例如：`raising hand`, `pointing forward`, `sitting on chair`, `leaning on wall`）
    *   **关键的场景元素或光照**（例如：`classroom background`, `night`, `window light`, ` dimly lit`）
    *   **与其他角色的互动**（如果适用，例如：`looking at other`, `holding hands with ...`）
    *   **(可选) LoRA 注入**: 如果场景适合某个特定的 LoRA 风格或角色，可以在动态生成的正面提示词中包含 `<lora:lora文件名:权重>` 标记。
4.  **组合提示词**:
    *   将**基础正面提示词**和**动态生成的正面提示词**（包括可能的 LoRA 标记）组合起来，用逗号 `,` 分隔。
    *   将**基础负面提示词**和**动态生成的负面提示词**（如果需要生成额外的负面词，通常较少）组合起来，用逗号 `,` 分隔。
5.  **添加标记**: 在识别到的 `[名字]` 标记行的【正上方】，添加一个新的标记行，格式为：`[NAI:{{名字}}|{{组合后的正面提示词}}|{{组合后的负面提示词}}]`。
    *   确保使用**双花括号 `{{ }}`** 包裹占位符名称，以防止 Python 格式化错误。
    *   如果某个角色的基础设定为空，并且根据上下文也无法生成有意义的动态提示词，则**不要**为该角色添加 `[NAI:...]` 标记。
    *   如果只有正面或负面提示词（基础+动态），另一部分留空，但**必须保留分隔符 `|`**。例如 `[NAI:{{名字}}|{{正面提示}}|]` 或 `[NAI:{{名字}}||{{负面提示}}]`。
6.  **处理心声/旁白**: 不要为心声 `*{{...}}*` 或普通旁白添加 `[NAI:...]` 标记。
7.  **保留原文和原有标记**: 除了按规则添加包含【组合后提示词】的 `[NAI:...]` 标记外，必须【完整保留】输入文本中的所有其他内容和标记 (`[名字]`, `*{{...}}*`)。
8.  **输出格式**: 直接输出带有新增标记的文本。不要包含任何代码块标记或额外的解释。

现在，请根据以下【人物基础设定】和【已格式化文本】的上下文，智能地生成并添加提示词标记：

--- CHARACTER BASE PROFILES (JSON) ---
{character_profiles_json}
--- CHARACTER BASE PROFILES END ---

--- FORMATTED TEXT START ---
{formatted_text_chunk}
--- FORMATTED TEXT END ---

{post_instruction}

Enhanced Text Output with Generated Prompts:
"""

    # --- BGM_SUGGESTION_TEMPLATE (无变化) ---
    BGM_SUGGESTION_TEMPLATE = """
{pre_instruction}
你是一位专业的游戏/视觉小说音乐监督。你的任务是阅读【包含提示词标记的文本】，分析文本内容的情节转折、场景变化和情绪基调，并在你认为**适合插入或更换背景音乐 (BGM)** 的位置，添加 BGM 推荐注释。

**严格遵循以下规则：**

1.  **分析文本**: 仔细阅读整个文本块，理解故事发展、场景地点、人物情绪（可以通过对话、动作描述、旁白以及 `[NAI:...]` 标记中的提示词来判断）。
2.  **识别关键点**: 找到那些适合引入 BGM 或改变 BGM 的关键节点，例如：
    *   场景切换（如从教室到街道，从白天到夜晚）。
    *   重要情节转折。
    *   角色情绪发生显著变化（如从平静到紧张，从悲伤到喜悦）。
    *   回忆场景的开始或结束。
    *   高潮或紧张时刻的开始。
3.  **生成推荐注释**: 在你识别出的关键点的【正上方】，插入一行 KAG 风格的注释，格式如下：
    `; BGM Suggestion: [类型/情绪: <这里写推荐的音乐类型或情绪描述>] [推荐网站: 魔王魂/DOVA-SYNDROME/甘茶の音楽工房]`
    *   **类型/情绪描述**: 必须简洁明了，例如 `日常轻松`, `紧张悬疑`, `悲伤钢琴曲`, `激昂战斗`, `温馨回忆`, `神秘氛围`, `搞笑滑稽` 等。
    *   **推荐网站**: 固定推荐这几个知名的免费 BGM 网站，方便用户查找。
4.  **插入占位符**: 在推荐注释的【下一行】，插入一个注释掉的 KAG `bgm` 标签占位符：
    `;[bgm storage=""]`
5.  **插入频率**: 不要过于频繁地插入推荐。只在确实需要改变音乐氛围的关键点进行推荐。如果一个场景的氛围持续不变，则不需要重复推荐相同的类型。
6.  **保留原文**: **绝对禁止**修改或删除【包含提示词标记的文本】中的任何原始内容和标记 (`[名字]`, `*{{...}}*`, `[NAI:...]`)。你的任务只是在合适的位置**插入**上述两种注释行。
7.  **输出格式**: 直接输出修改后的文本（即插入了 BGM 推荐注释和占位符的原始文本）。不要添加任何额外的解释或代码块标记。

**输入文本 (包含提示词标记):**
--- ENHANCED FORMATTED TEXT CHUNK START ---
{enhanced_text_chunk}
--- ENHANCED FORMATTED TEXT CHUNK END ---

{post_instruction}

**输出带有 BGM 建议注释的文本:**
"""

    # --- 修改 KAG_CONVERSION_PROMPT_TEMPLATE (添加示例，再次加强 Rule 3) ---
    KAG_CONVERSION_PROMPT_TEMPLATE = """
{pre_instruction}
你是一个将【已格式化并包含提示词和 BGM 建议标记】的小说文本转换为 KiriKiri2 KAG (ks) 脚本格式的专家。
输入文本包含 `[名字]`、`*{{...}}*`、`[NAI:名字|正面|负面]` 标记，以及以 `;` 开头的 BGM 建议注释和 `bgm` 占位符注释。
**核心任务**：严格按照规则将输入文本转换为 KAG 脚本，**专注于文本转换和生成指定的注释与占位符**。

**【极其重要】输出规则：**

1.  **遇到 `[NAI:名字|正面|负面]` 标记时：**
    *   **必须** 将其转换为 **两行** 输出：
        *   **第一行 (提示词注释):** 必须是 `; NAI Prompt for {{名字}}: Positive=[{{正面}}] Negative=[{{负面}}]` (以分号开头，无 `[p]`)
        *   **第二行 (图片占位符):** 必须是 `[INSERT_IMAGE_HERE:{{名字}}]` (无分号，无 `[p]`)
    *   原始的 `[NAI:...]` 标记**本身不应出现在输出中**。

2.  **遇到 `[名字]` 标记时：**
    *   将其理解为下一行对话的说话人。
    *   **必须** 将其转换为 **一行** KAG 风格的说话人名称标签，格式为： `[name]名字[/name]` (无 `[p]`)
    *   原始的 `[名字]` 标记**本身不应出现在输出中**。

3.  **处理对话（以 `“...”` 或 `「...」` 开始和结束的行）：**
    *   **情况 A：如果【紧邻的上一行】是说话人标记 `[某名字]`** (该标记已被规则 2 处理并转换为 `[name]某名字[/name]`):
        *   **必须** 生成 **两行** 输出，严格按照以下格式，顺序不能错：
        *   **第一行 (语音占位符注释):** 必须是 `; @playse storage="PLACEHOLDER_某名字_序号.wav" buf=0 ; name="某名字"` (注意：行首必须是分号 `;`，行尾绝对不能有 `[p]`)
        *   **第二行 (对话内容):** 必须是 `「原始对话内容(去除原始引号/括号)」[p]` (注意：行首必须是 `「`，行尾必须是 `[p]`)
        *   **【重要示例】**
            *   **输入片段:**
                ```
                [远坂时臣]
                “你好，世界。”
                ```
            *   **对应输出 (必须严格如下):**
                ```
                [name]远坂时臣[/name]
                ; @playse storage="PLACEHOLDER_远坂时臣_序号.wav" buf=0 ; name="远坂时臣"
                「你好，世界。」[p]
                ```
        *   *LLM 注意：请确保严格生成这两行，不要合并或省略。PLACEHOLDER 中的“序号”部分由后续代码处理，你只需输出名字。第二行必须包含原始的对话文本，而不是说话人的名字！*
    *   **情况 B：如果【紧邻的上一行】不是说话人标记** (例如旁白后的对话):
        *   **只输出一行：** `「原始对话内容(去除原始引号/括号)」[p]`
        *   *这种情况下不生成语音占位符注释。*
    *   **【格式要求重申】**
        *   语音占位符注释行 (` ; @playse ...`) **必须** 独立成行，以分号开头，**无** `[p]` 结尾。
        *   对话行 (`「...」[p]`) **必须** 独立成行，以 `「` 开头，以 `」[p]` 结尾，中间**只包含**实际对话文本。
        *   **绝对禁止**将 `@playse` 注释放在 `「」` 内部。
        *   **绝对禁止**在对话 `「」` 内包含说话人名字。

4.  **处理心声 `*{{...}}*`：**
    *   **保留** `*{{` 和 `}}*` 标记。
    *   **输出：**
        `*{{内心独白内容}}*[p]`
    *   心声内容（包括标记）和 `[p]` 在同一行。（后续将由 Python 代码处理为 `（...）`）

5.  **处理旁白/叙述：**
    *   任何不符合上述规则、**非空**、且**不以分号 `;` 开头**的文本行（除了已被处理的 `[名字]` 和 `[NAI:...]` 标记），都视为旁白。
    *   **输出：**
        `旁白/叙述的原始文本内容[p]`
    *   旁白内容和 `[p]` 在同一行。

6.  **处理注释行 (以 `;` 开头):**
    *   如果一行文本以分号 `;` 开头（例如 BGM 建议注释、`bgm` 占位符注释、**NAI 提示词注释**、**以及我们新生成的语音占位符注释**），则**原样保留这一行**，并且**不在末尾添加 `[p]`**。

7.  **忽略空行**: 忽略输入文本中的所有空行。不要为空行生成任何输出。

8.  **禁止额外内容**:
    *   **绝对禁止** 在输出中生成任何 KAG 的 `[image]` 或 `@playse` 标签（除非是按规则生成的**注释掉的** `@playse` 语音占位符）。只允许生成 `[INSERT_IMAGE_HERE:...]` 图片占位符和对应的提示词注释，以及注释掉的 `@playse` 语音占位符。
    *   不要添加任何解释性文字或代码块标记 (```)。
    *   严格遵守上述 `[p]` 标签的使用规则，确保每个有效的文本输出行（对话、心声、旁白）都以 `[p]` 结尾，且注释行、图片占位符行、语音占位符注释行没有 `[p]`。

**输入文本 (包含提示词和 BGM 建议标记):**
--- TEXT CHUNK WITH PROMPTS AND BGM SUGGESTIONS START ---
{text_chunk_with_suggestions}
--- TEXT CHUNK WITH PROMPTS AND BGM SUGGESTIONS END ---

{post_instruction}

**输出 KAG 脚本 (包含图片占位符、BGM 注释、[name] 标签和注释掉的 @playse 语音占位符):**
"""