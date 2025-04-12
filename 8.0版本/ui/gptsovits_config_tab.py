# ui/gptsovits_config_tab.py
import customtkinter as ctk
from tkinter import StringVar, IntVar, DoubleVar, BooleanVar, messagebox, filedialog
import json
import os
import traceback

class GPTSoVITSConfigTab(ctk.CTkFrame):
    """GPT-SoVITS API 设置和人物语音映射的 UI 标签页"""
    def __init__(self, master, config_manager, app_instance):
        super().__init__(master, fg_color="transparent")
        self.config_manager = config_manager
        self.app = app_instance # 主应用实例
        # self.character_voice_map 用于存储当前编辑的人物语音映射
        self.character_voice_map = {}

        self.build_ui()
        self.load_initial_config()
        print("[GPTSoVITS Tab] UI 构建完成。")

    def build_ui(self):
        """构建 GPT-SoVITS 配置界面的 UI 元素"""
        # 配置主框架的网格布局
        self.grid_rowconfigure(3, weight=1) # 让映射列表区域可扩展
        self.grid_columnconfigure(1, weight=1) # 让右侧列可扩展

        # --- API 和路径设置 ---
        api_frame = ctk.CTkFrame(self, fg_color="transparent")
        api_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 5), sticky="ew")
        api_frame.grid_columnconfigure(1, weight=1)

        row_api = 0
        # API URL
        url_label = ctk.CTkLabel(api_frame, text="API 地址:")
        url_label.grid(row=row_api, column=0, padx=(0, 5), pady=5, sticky="w")
        self.api_url_var = StringVar()
        url_entry = ctk.CTkEntry(api_frame, textvariable=self.api_url_var, placeholder_text="例如: http://127.0.0.1:9880")
        url_entry.grid(row=row_api, column=1, padx=5, pady=5, sticky="ew")
        # --- 新增绑定 ---
        url_entry.bind("<FocusOut>", self.trigger_workflow_button_update) # 绑定失去焦点事件

        row_api += 1
        # 音频保存目录
        save_dir_label = ctk.CTkLabel(api_frame, text="音频保存目录:")
        save_dir_label.grid(row=row_api, column=0, padx=(0, 5), pady=5, sticky="w")
        self.save_dir_var = StringVar()
        dir_entry = ctk.CTkEntry(api_frame, textvariable=self.save_dir_var, placeholder_text="应用可访问的完整目录路径")
        dir_entry.grid(row=row_api, column=1, padx=5, pady=5, sticky="ew")
        # --- 新增绑定 ---
        dir_entry.bind("<FocusOut>", self.trigger_workflow_button_update) # 绑定失去焦点事件
        browse_button = ctk.CTkButton(api_frame, text="浏览...", width=60, command=self.browse_save_directory)
        browse_button.grid(row=row_api, column=2, padx=(5, 0), pady=5, sticky="w")

        row_api += 1
        # 音频文件前缀
        prefix_label = ctk.CTkLabel(api_frame, text="音频文件前缀:")
        prefix_label.grid(row=row_api, column=0, padx=(0, 5), pady=5, sticky="w")
        self.audio_prefix_var = StringVar(value="cv_") # 默认值
        prefix_entry = ctk.CTkEntry(api_frame, textvariable=self.audio_prefix_var, width=150)
        prefix_entry.grid(row=row_api, column=1, padx=5, pady=5, sticky="w")


        # --- 默认生成参数 ---
        param_frame = ctk.CTkFrame(self, fg_color="transparent")
        param_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=5, sticky="ew")
        # 配置参数框架内部列权重，使其均匀分布
        param_frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1, uniform="gptsv_params")

        col_param = 0
        # How to Cut
        cut_label = ctk.CTkLabel(param_frame, text="切分方式:")
        cut_label.grid(row=0, column=col_param, padx=5, pady=5, sticky="w")
        self.how_to_cut_var = StringVar(value="不切")
        cut_options = ["不切", "凑四句一切", "凑50字一切", "按英文句号.切", "按中文句号。切", "按标点符号切"]
        cut_combo = ctk.CTkComboBox(param_frame, values=cut_options, variable=self.how_to_cut_var, width=120)
        cut_combo.grid(row=1, column=col_param, padx=5, pady=5, sticky="ew")

        col_param += 1
        # Top K
        top_k_label = ctk.CTkLabel(param_frame, text="Top K:")
        top_k_label.grid(row=0, column=col_param, padx=5, pady=5, sticky="w")
        self.top_k_var = IntVar(value=5)
        top_k_entry = ctk.CTkEntry(param_frame, textvariable=self.top_k_var, width=60)
        top_k_entry.grid(row=1, column=col_param, padx=5, pady=5, sticky="ew")

        col_param += 1
        # Top P
        top_p_label = ctk.CTkLabel(param_frame, text="Top P:")
        top_p_label.grid(row=0, column=col_param, padx=5, pady=5, sticky="w")
        self.top_p_var = DoubleVar(value=1.0)
        top_p_entry = ctk.CTkEntry(param_frame, textvariable=self.top_p_var, width=60)
        top_p_entry.grid(row=1, column=col_param, padx=5, pady=5, sticky="ew")

        col_param += 1
        # Temperature
        temp_label = ctk.CTkLabel(param_frame, text="Temperature:")
        temp_label.grid(row=0, column=col_param, padx=5, pady=5, sticky="w")
        self.temperature_var = DoubleVar(value=1.0)
        temp_entry = ctk.CTkEntry(param_frame, textvariable=self.temperature_var, width=60)
        temp_entry.grid(row=1, column=col_param, padx=5, pady=5, sticky="ew")

        col_param += 1
        # Ref Free
        self.ref_free_var = BooleanVar(value=False)
        ref_free_check = ctk.CTkCheckBox(param_frame, text="无参考模式", variable=self.ref_free_var)
        ref_free_check.grid(row=1, column=col_param, padx=5, pady=5, sticky="w")

        # --- 人物语音映射管理 ---
        map_manage_frame = ctk.CTkFrame(self, fg_color="transparent")
        map_manage_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=(10, 0), sticky="ew")

        add_map_button = ctk.CTkButton(map_manage_frame, text="添加映射条目", command=self.add_new_voice_map_entry)
        add_map_button.pack(side="left", padx=5)
        # 可以加一个“从人物设定导入名称”的按钮简化操作
        import_names_button = ctk.CTkButton(map_manage_frame, text="从人物设定导入名称", command=self.import_names_from_profiles)
        import_names_button.pack(side="left", padx=5)


        # --- 人物语音映射列表 (使用可滚动 Frame) ---
        self.map_scrollable_frame = ctk.CTkScrollableFrame(self, label_text="人物语音映射 (KAG 脚本名称 -> 参考语音)")
        self.map_scrollable_frame.grid(row=3, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="nsew")
        self.map_scrollable_frame.grid_columnconfigure(1, weight=1) # 让参考音频路径输入框扩展

        # 初始渲染空列表
        self.render_voice_map_list()

    def browse_save_directory(self):
        """打开目录选择对话框，让用户选择音频保存目录"""
        directory = filedialog.askdirectory(title="选择 GPT-SoVITS 音频保存目录", parent=self)
        if directory:
            self.save_dir_var.set(directory)
            print(f"GPT-SoVITS 音频保存目录已设置为: {directory}")
            # --- 新增：选择目录后也触发更新 ---
            self.trigger_workflow_button_update()
        else:
            print("用户取消选择目录。")

    def browse_ref_wav(self, entry_var):
        """打开文件选择对话框，让用户选择参考音频文件"""
        filepath = filedialog.askopenfilename(
            title="选择参考音频文件 (.wav)",
            filetypes=[("WAV 文件", "*.wav"), ("所有文件", "*.*")],
            parent=self
        )
        if filepath:
            entry_var.set(filepath) # 更新对应的输入框变量
            print(f"选择了参考音频: {filepath}")
            # --- 新增：选择文件后也触发更新 ---
            # 注意：这里可能需要更精细的控制，因为修改单个映射条目不一定需要全局更新
            # 但为了简单起见，先触发全局更新
            self.trigger_workflow_button_update()
        else:
            print("用户取消选择参考音频。")

    def render_voice_map_list(self):
        """根据 self.character_voice_map 重新绘制映射列表 UI"""
        print("[GPTSoVITS Tab] 开始渲染人物语音映射列表...")
        # 清空当前列表
        for widget in self.map_scrollable_frame.winfo_children():
            widget.destroy()

        # 确保 self.character_voice_map 是字典
        if not isinstance(self.character_voice_map, dict):
            print("错误: self.character_voice_map 不是字典类型！已重置为空字典。")
            self.character_voice_map = {}

        # 获取并排序 KAG 脚本中的人物名称
        kag_names = sorted(self.character_voice_map.keys())
        print(f"[GPTSoVITS Tab] 准备渲染 {len(kag_names)} 个映射条目。")

        if not kag_names:
            no_map_label = ctk.CTkLabel(self.map_scrollable_frame, text="请点击“添加映射条目”或“从人物设定导入名称”", text_color="gray")
            no_map_label.grid(row=0, column=0, columnspan=5, padx=10, pady=20, sticky="n")
        else:
            current_row = 0
            # 添加表头
            header_kag_name = ctk.CTkLabel(self.map_scrollable_frame, text="KAG 脚本名称", font=ctk.CTkFont(weight="bold"))
            header_kag_name.grid(row=current_row, column=0, padx=5, pady=2, sticky="w")
            header_ref_wav = ctk.CTkLabel(self.map_scrollable_frame, text="参考音频路径 (服务器路径)", font=ctk.CTkFont(weight="bold"))
            header_ref_wav.grid(row=current_row, column=1, padx=5, pady=2, sticky="w")
            header_ref_text = ctk.CTkLabel(self.map_scrollable_frame, text="参考文本", font=ctk.CTkFont(weight="bold"))
            header_ref_text.grid(row=current_row, column=2, padx=5, pady=2, sticky="w")
            header_ref_lang = ctk.CTkLabel(self.map_scrollable_frame, text="参考语言", font=ctk.CTkFont(weight="bold"))
            header_ref_lang.grid(row=current_row, column=3, padx=5, pady=2, sticky="w")
            current_row += 1

            for kag_name in kag_names:
                voice_data = self.character_voice_map.get(kag_name, {})
                if not isinstance(voice_data, dict):
                    print(f"警告: 人物 '{kag_name}' 的语音映射数据不是字典，已跳过。")
                    continue

                # --- 定义回调 ---
                def create_remove_callback(name):
                    # 修改：删除后触发按钮更新
                    return lambda: (self.remove_voice_map_entry(name), self.trigger_workflow_button_update())
                def create_update_callback(name, field_key, entry_var):
                    # 修改：更新后触发按钮更新
                    return lambda event=None: (self.update_voice_map_field(name, field_key, entry_var.get()), self.trigger_workflow_button_update())
                def create_browse_callback(entry_var):
                    # 修改：浏览后触发按钮更新 (虽然 browse_ref_wav 内部已加，这里再加一层保险)
                    return lambda: (self.browse_ref_wav(entry_var), self.trigger_workflow_button_update())

                # --- 创建 UI 元素 ---
                # KAG 名称 (标签)
                name_label = ctk.CTkLabel(self.map_scrollable_frame, text=kag_name, anchor="w")
                name_label.grid(row=current_row, column=0, padx=5, pady=2, sticky="w")

                # 参考音频路径
                ref_wav_var = StringVar(value=voice_data.get("refer_wav_path", ""))
                ref_wav_entry = ctk.CTkEntry(self.map_scrollable_frame, textvariable=ref_wav_var, placeholder_text="服务器上的 .wav 文件路径")
                ref_wav_entry.grid(row=current_row, column=1, padx=5, pady=2, sticky="ew")
                ref_wav_entry.bind("<FocusOut>", create_update_callback(kag_name, "refer_wav_path", ref_wav_var))
                # 暂时移除浏览按钮，因为它选择的是本地路径，可能引起混淆
                # browse_ref_button = ctk.CTkButton(self.map_scrollable_frame, text="...", width=20, command=create_browse_callback(ref_wav_var))
                # browse_ref_button.grid(row=current_row, column=1, padx=(0, 5), pady=2, sticky="e")

                # 参考文本
                ref_text_var = StringVar(value=voice_data.get("prompt_text", ""))
                ref_text_entry = ctk.CTkEntry(self.map_scrollable_frame, textvariable=ref_text_var)
                ref_text_entry.grid(row=current_row, column=2, padx=5, pady=2, sticky="ew")
                ref_text_entry.bind("<FocusOut>", create_update_callback(kag_name, "prompt_text", ref_text_var))

                # 参考语言
                ref_lang_var = StringVar(value=voice_data.get("prompt_language", "zh"))
                lang_options = ["zh", "en", "ja"] # 可以扩展
                ref_lang_combo = ctk.CTkComboBox(self.map_scrollable_frame, values=lang_options, variable=ref_lang_var, width=60)
                ref_lang_combo.grid(row=current_row, column=3, padx=5, pady=2, sticky="w")
                # 修改：ComboBox 变化时触发按钮更新
                ref_lang_combo.configure(command=lambda choice, name=kag_name, key="prompt_language", var=ref_lang_var: (self.update_voice_map_field(name, key, var.get()), self.trigger_workflow_button_update()))


                # 删除按钮
                remove_btn = ctk.CTkButton(self.map_scrollable_frame, text="删除", width=60,
                                          fg_color="#DB3E3E", hover_color="#B82E2E",
                                          command=create_remove_callback(kag_name))
                remove_btn.grid(row=current_row, column=4, padx=(10, 5), pady=2, sticky="e")

                current_row += 1

        print("[GPTSoVITS Tab] 语音映射列表渲染完成。")


    def add_new_voice_map_entry(self):
        """添加一个新的空映射条目"""
        print("[GPTSoVITS Tab] 请求添加新映射条目...")
        dialog = ctk.CTkInputDialog(text="请输入 KAG 脚本中的人物名称:", title="添加语音映射")
        kag_name_raw = dialog.get_input()

        if kag_name_raw is not None:
            kag_name = kag_name_raw.strip()
            if not kag_name:
                messagebox.showerror("名称错误", "KAG 脚本人物名称不能为空！", parent=self)
                return
            if kag_name in self.character_voice_map:
                messagebox.showerror("名称冲突", f"人物名称 '{kag_name}' 的映射已存在！", parent=self)
                return

            self.character_voice_map[kag_name] = {
                "refer_wav_path": "",
                "prompt_text": "",
                "prompt_language": "zh"
            }
            print(f"[GPTSoVITS Tab] 新映射条目 '{kag_name}' 已添加到内存。")
            self.render_voice_map_list() # 重新渲染列表 (内部会触发按钮更新)
            self.after(100, self._scroll_to_bottom)
        else:
            print("[GPTSoVITS Tab] 用户取消添加映射条目。")

    def import_names_from_profiles(self):
        """从 ProfilesTab 获取人物名称，并添加到语音映射中（如果不存在）"""
        print("[GPTSoVITS Tab] 请求从人物设定导入名称...")
        try:
            if hasattr(self.app, 'profiles_tab') and self.app.profiles_tab.winfo_exists():
                # --- 修改：从 profiles_tab 获取 key (原始名称) ---
                profile_keys = self.app.profiles_tab.character_profiles.keys()
                added_count = 0
                skipped_count = 0
                if not profile_keys:
                    messagebox.showinfo("无人物设定", "人物设定标签页中当前没有人物名称可供导入。", parent=self)
                    return

                for key in profile_keys: # 遍历 key
                    # 检查 key 是否已在语音映射中
                    if key not in self.character_voice_map:
                        self.character_voice_map[key] = { # 使用 key 作为语音映射的 key
                            "refer_wav_path": "",
                            "prompt_text": "",
                            "prompt_language": "zh"
                        }
                        added_count += 1
                    else:
                        skipped_count += 1
                # --- 修改结束 ---

                if added_count > 0:
                    print(f"[GPTSoVITS Tab] 成功导入 {added_count} 个新名称，跳过 {skipped_count} 个已存在名称。")
                    self.render_voice_map_list() # 重新渲染列表 (内部会触发按钮更新)
                    self.after(100, self._scroll_to_bottom)
                    messagebox.showinfo("导入完成", f"已成功导入 {added_count} 个新的人物名称到语音映射。\n请为它们配置参考语音信息。", parent=self)
                else:
                    messagebox.showinfo("无需导入", "所有人物设定中的名称均已存在于语音映射中。", parent=self)

            else:
                messagebox.showerror("错误", "无法访问人物设定标签页。", parent=self)
        except Exception as e:
            print(f"错误：从人物设定导入名称时出错: {e}")
            traceback.print_exc()
            messagebox.showerror("导入错误", f"从人物设定导入名称时发生错误:\n{e}", parent=self)


    def remove_voice_map_entry(self, name_to_remove):
        """从内存和 UI 中移除指定的语音映射条目"""
        print(f"[GPTSoVITS Tab] 请求删除映射条目: '{name_to_remove}'")
        if name_to_remove in self.character_voice_map:
            if messagebox.askyesno("确认删除", f"确定要删除人物 '{name_to_remove}' 的语音映射吗？", parent=self):
                try:
                    del self.character_voice_map[name_to_remove]
                    print(f"[GPTSoVITS Tab] 映射条目 '{name_to_remove}' 已从内存删除。")
                    # 注意：render_voice_map_list 会在回调中被调用，这里不需要重复调用
                    # self.render_voice_map_list() # 重新渲染 (内部会触发按钮更新)
                except Exception as e:
                    print(f"错误：删除映射条目 '{name_to_remove}' 时出错: {e}")
                    traceback.print_exc()
                    messagebox.showerror("删除错误", f"删除映射条目时出错:\n{e}", parent=self)
                    self.render_voice_map_list() # 尝试刷新
        else:
            print(f"警告: 尝试删除不存在的映射条目 '{name_to_remove}'。")
            self.render_voice_map_list() # 刷新 UI

    def update_voice_map_field(self, name, field_key, value):
        """更新内存中指定映射条目的字段值"""
        print(f"[GPTSoVITS Tab] 更新映射字段: 人物='{name}', 字段='{field_key}', 新值='{str(value)[:50]}...'")
        if name in self.character_voice_map:
            if isinstance(self.character_voice_map[name], dict):
                self.character_voice_map[name][field_key] = value.strip() if isinstance(value, str) else value
                print(f"[GPTSoVITS Tab] 内存中 '{name}' 的 '{field_key}' 字段已更新。")
                # 注意：trigger_workflow_button_update 会在回调中被调用
            else:
                print(f"错误：人物 '{name}' 的映射数据不是字典！无法更新字段 '{field_key}'。")
        else:
            print(f"警告: 尝试更新不存在的映射条目 '{name}' 的字段 '{field_key}'。")

    def _scroll_to_bottom(self):
        """尝试将映射列表滚动到底部"""
        try:
            if hasattr(self.map_scrollable_frame, '_parent_canvas') and self.map_scrollable_frame._parent_canvas:
                self.map_scrollable_frame._parent_canvas.yview_moveto(1.0)
                print("[GPTSoVITS Tab] 已尝试滚动映射列表到底部。")
        except Exception as e:
            print(f"警告：滚动映射列表到底部时出错: {e}")

    def load_initial_config(self):
        """从配置文件加载初始 GPT-SoVITS 配置并更新 UI"""
        print("正在加载 GPT-SoVITS 配置到 UI...")
        config = self.config_manager.load_config("gptsovits")

        self.api_url_var.set(config.get("apiUrl", ""))
        self.save_dir_var.set(config.get("audioSaveDir", ""))
        self.audio_prefix_var.set(config.get("audioPrefix", "cv_"))

        self.how_to_cut_var.set(config.get("how_to_cut", "不切"))
        self.top_k_var.set(int(config.get("top_k", 5)))
        self.top_p_var.set(float(config.get("top_p", 1.0)))
        self.temperature_var.set(float(config.get("temperature", 1.0)))
        self.ref_free_var.set(bool(config.get("ref_free", False)))

        # 加载人物语音映射
        self.character_voice_map = config.get("character_voice_map", {})
        # 确保加载的是字典
        if not isinstance(self.character_voice_map, dict):
            print("警告：加载的 character_voice_map 不是字典，已重置为空。")
            self.character_voice_map = {}

        # 渲染映射列表 (内部会触发按钮更新)
        self.render_voice_map_list()
        print("GPT-SoVITS 配置加载完成。")

    def get_config_data(self):
        """从 UI 元素收集当前的 GPT-SoVITS 配置数据"""
        print("正在从 UI 收集 GPT-SoVITS 配置数据...")
        # --- 输入校验 ---
        try: top_k = int(self.top_k_var.get())
        except: top_k = 5; print("警告: 无效的 Top K 输入，使用默认值 5。"); self.top_k_var.set(top_k)

        try: top_p = float(self.top_p_var.get())
        except: top_p = 1.0; print("警告: 无效的 Top P 输入，使用默认值 1.0。"); self.top_p_var.set(top_p)

        try: temperature = float(self.temperature_var.get())
        except: temperature = 1.0; print("警告: 无效的 Temperature 输入，使用默认值 1.0。"); self.temperature_var.set(temperature)

        # --- 确保 character_voice_map 中的路径是字符串 ---
        # （虽然 UI 绑定的是 StringVar，理论上已经是字符串，但做个检查）
        final_voice_map = {}
        for name, data in self.character_voice_map.items():
            if isinstance(data, dict):
                final_voice_map[name] = {
                    "refer_wav_path": str(data.get("refer_wav_path", "")),
                    "prompt_text": str(data.get("prompt_text", "")),
                    "prompt_language": str(data.get("prompt_language", "zh"))
                }

        config_data = {
            "apiUrl": self.api_url_var.get().rstrip('/'),
            "audioSaveDir": self.save_dir_var.get(),
            "audioPrefix": self.audio_prefix_var.get(),
            "how_to_cut": self.how_to_cut_var.get(),
            "top_k": top_k,
            "top_p": top_p,
            "temperature": temperature,
            "ref_free": self.ref_free_var.get(),
            "character_voice_map": final_voice_map # 使用清理/校验后的映射
        }
        print("GPT-SoVITS 配置数据收集完成。")
        return config_data

    # --- 新增方法：触发 WorkflowTab 更新 ---
    def trigger_workflow_button_update(self, event=None):
        """通知 WorkflowTab 更新按钮状态"""
        try:
            # 确保主应用和 workflow_tab 实例存在且窗口有效
            if hasattr(self.app, 'workflow_tab') and self.app.workflow_tab and self.app.workflow_tab.winfo_exists():
                print(f"[{type(self).__name__}] 触发 WorkflowTab 按钮状态更新...")
                # 调用 WorkflowTab 的 update_button_states 方法
                self.app.workflow_tab.update_button_states()
            else:
                print(f"[{type(self).__name__}] 无法触发更新：WorkflowTab 不可用。")
        except Exception as e:
            print(f"错误: 在 trigger_workflow_button_update ({type(self).__name__}) 中发生异常: {e}")
            traceback.print_exc()