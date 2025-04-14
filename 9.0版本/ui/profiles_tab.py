# ui/profiles_tab.py
import customtkinter as ctk
from tkinter import StringVar, messagebox, filedialog
import json
import os
import traceback

class ProfilesTab(ctk.CTkFrame):
    """人物设定管理的 UI 标签页"""
    def __init__(self, master, config_manager, app_instance):
        super().__init__(master, fg_color="transparent")
        self.config_manager = config_manager
        self.app = app_instance
        self.character_profiles = {}
        self.loaded_filepath = None

        # --- 修改：将 UI 构建分为固定部分和滚动部分 ---
        self.grid_rowconfigure(1, weight=1) # 让滚动区域行扩展
        self.grid_columnconfigure(0, weight=1) # 让列扩展

        # --- 固定部分：文件操作按钮区域 ---
        self.button_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.button_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.load_button = ctk.CTkButton(self.button_frame, text="加载设定文件 (.json)", command=self.load_profiles_from_file)
        self.load_button.pack(side="left", padx=5)
        self.save_button = ctk.CTkButton(self.button_frame, text="保存当前设定到文件", command=self.save_profiles_to_file, state="disabled")
        self.save_button.pack(side="left", padx=5)
        self.add_button = ctk.CTkButton(self.button_frame, text="添加人物", command=self.add_new_profile)
        self.add_button.pack(side="left", padx=5)
        self.file_status_label = ctk.CTkLabel(self.button_frame, text="尚未加载人物设定文件", text_color="gray", wraplength=300)
        self.file_status_label.pack(side="left", padx=10, fill="x", expand=True)

        # --- 滚动部分：人物列表区域 ---
        self.scrollable_frame = ctk.CTkScrollableFrame(self, label_text="人物列表")
        self.scrollable_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        # 配置滚动框架内部的列权重
        self.scrollable_frame.grid_columnconfigure(1, weight=1) # 替换名称列
        self.scrollable_frame.grid_columnconfigure(2, weight=1) # 正向提示列
        self.scrollable_frame.grid_columnconfigure(3, weight=1) # 负向提示列
        # --- 修改结束 ---

        print("[ProfilesTab] 人物设定标签页 UI 构建完成。")
        self.render_profiles_list()

    def render_profiles_list(self):
        """根据 self.character_profiles 的内容重新绘制人物列表 UI"""
        print("[ProfilesTab] 开始渲染人物列表...")
        for widget in self.scrollable_frame.winfo_children(): widget.destroy() # 清空滚动区域

        if not isinstance(self.character_profiles, dict):
             print("错误: self.character_profiles 不是字典类型！已重置为空字典。")
             self.character_profiles = {}
        names = sorted(self.character_profiles.keys())
        print(f"[ProfilesTab] 准备渲染 {len(names)} 个人物。")

        if not names:
            no_profiles_label = ctk.CTkLabel(self.scrollable_frame, text="请加载设定文件、从步骤一导入或点击“添加人物”按钮。", text_color="gray")
            no_profiles_label.grid(row=0, column=0, columnspan=5, padx=10, pady=20, sticky="n")
            self.save_button.configure(state="disabled") # 列表为空时禁用保存
            print("[ProfilesTab] 列表为空，显示提示信息，禁用保存按钮。")
        else:
            self.save_button.configure(state="normal") # 有内容时启用保存
            current_row = 0
            # 添加表头
            header_disp_name = ctk.CTkLabel(self.scrollable_frame, text="显示名称", font=ctk.CTkFont(weight="bold"))
            header_disp_name.grid(row=current_row, column=0, padx=5, pady=2, sticky="w")
            header_repl_name = ctk.CTkLabel(self.scrollable_frame, text="替换名称 (可选)", font=ctk.CTkFont(weight="bold"))
            header_repl_name.grid(row=current_row, column=1, padx=5, pady=2, sticky="w")
            header_pos = ctk.CTkLabel(self.scrollable_frame, text="正向提示词", font=ctk.CTkFont(weight="bold"))
            header_pos.grid(row=current_row, column=2, padx=5, pady=2, sticky="w")
            header_neg = ctk.CTkLabel(self.scrollable_frame, text="负向提示词", font=ctk.CTkFont(weight="bold"))
            header_neg.grid(row=current_row, column=3, padx=5, pady=2, sticky="w")
            current_row += 1

            # 遍历人物并创建 UI 元素
            for name_key in names:
                profile_data = self.character_profiles.get(name_key, {})
                if not isinstance(profile_data, dict): print(f"警告: 人物 '{name_key}' 的数据不是字典格式，已跳过渲染。"); continue

                entry_frame = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
                entry_frame.grid(row=current_row, column=0, columnspan=5, pady=(0, 8), sticky="ew")
                entry_frame.grid_columnconfigure(1, weight=1); entry_frame.grid_columnconfigure(2, weight=1); entry_frame.grid_columnconfigure(3, weight=1)

                # 定义回调函数
                def create_remove_callback(key): return lambda: self.remove_profile(key)
                def create_update_callback(key, field_type, entry_var): return lambda event=None: self.update_profile_field(key, field_type, entry_var.get())

                # 创建 UI 元素
                display_name = profile_data.get("display_name", name_key)
                name_label = ctk.CTkLabel(entry_frame, text=display_name, anchor="w", width=120)
                name_label.grid(row=0, column=0, padx=5, pady=2, sticky="w")
                repl_var = StringVar(value=profile_data.get("replacement_name", ""))
                repl_entry = ctk.CTkEntry(entry_frame, textvariable=repl_var, placeholder_text="为空则使用显示名称")
                repl_entry.grid(row=0, column=1, padx=5, pady=2, sticky="ew")
                repl_entry.bind("<FocusOut>", create_update_callback(name_key, "replacement_name", repl_var))
                pos_var = StringVar(value=profile_data.get("positive", ""))
                pos_entry = ctk.CTkEntry(entry_frame, textvariable=pos_var)
                pos_entry.grid(row=0, column=2, padx=5, pady=2, sticky="ew")
                pos_entry.bind("<FocusOut>", create_update_callback(name_key, "positive", pos_var))
                neg_var = StringVar(value=profile_data.get("negative", ""))
                neg_entry = ctk.CTkEntry(entry_frame, textvariable=neg_var)
                neg_entry.grid(row=0, column=3, padx=5, pady=2, sticky="ew")
                neg_entry.bind("<FocusOut>", create_update_callback(name_key, "negative", neg_var))
                remove_btn = ctk.CTkButton(entry_frame, text="删除", width=60, fg_color="#DB3E3E", hover_color="#B82E2E", command=create_remove_callback(name_key))
                remove_btn.grid(row=0, column=4, padx=(10, 0), pady=2, sticky="e")
                current_row += 1
        print("[ProfilesTab] 人物列表渲染完成。")

    def update_profile_field(self, name_key, field_type, value):
        """更新内存中指定人物的字段"""
        print(f"[ProfilesTab] 更新字段请求：Key='{name_key}', 字段='{field_type}', 新值='{value[:30]}...'")
        if name_key in self.character_profiles:
            if field_type in ["replacement_name", "positive", "negative"]:
                if isinstance(self.character_profiles[name_key], dict):
                    self.character_profiles[name_key][field_type] = value.strip()
                    print(f"[ProfilesTab] 内存中 '{name_key}' 的 '{field_type}' 字段已更新。")
                else: print(f"错误：人物 '{name_key}' 在内存中的设定数据不是字典格式！无法更新字段 '{field_type}'。")
            else: print(f"警告: 尝试更新未知的字段类型 '{field_type}' 对于人物 '{name_key}'")
        else: print(f"警告: 尝试更新不存在的人物 Key '{name_key}' 的字段 '{field_type}'。")

    def remove_profile(self, name_key_to_remove):
        """移除指定的人物设定"""
        print(f"[ProfilesTab] 请求删除人物 Key: '{name_key_to_remove}'")
        if name_key_to_remove in self.character_profiles:
            display_name = self.character_profiles[name_key_to_remove].get("display_name", name_key_to_remove)
            if messagebox.askyesno("确认删除", f"确定要删除人物 '{display_name}' (Key: {name_key_to_remove}) 吗？", parent=self):
                try:
                    del self.character_profiles[name_key_to_remove]
                    print(f"[ProfilesTab] 人物 Key '{name_key_to_remove}' 已从内存字典中删除。")
                    self.render_profiles_list() # 重新渲染 UI
                except Exception as e: print(f"错误：删除人物 Key '{name_key_to_remove}' 时发生意外错误: {e}"); traceback.print_exc(); messagebox.showerror("删除错误", f"删除人物时出错:\n{e}", parent=self); self.render_profiles_list()
        else: print(f"警告: 尝试删除不存在的人物 Key '{name_key_to_remove}'。"); self.render_profiles_list()

    def add_new_profile(self):
        """添加新的人物设定"""
        print("[ProfilesTab] 请求添加新人物...")
        dialog = ctk.CTkInputDialog(text="请输入新人物的名称 (这将是显示名称和内部 Key):", title="添加人物")
        new_name_raw = dialog.get_input()
        if new_name_raw is not None:
            new_name = new_name_raw.strip()
            print(f"[ProfilesTab] 用户输入名称: '{new_name}'")
            if not new_name: messagebox.showerror("名称错误", "人物名称不能为空！", parent=self); print("错误：用户尝试添加空名称。"); return
            if new_name in self.character_profiles: messagebox.showerror("名称冲突", f"人物名称 (Key) '{new_name}' 已经存在！", parent=self); print(f"错误：用户尝试添加已存在的 Key '{new_name}'。"); return
            # 添加到内存字典
            self.character_profiles[new_name] = {"display_name": new_name, "replacement_name": "", "positive": "", "negative": ""}
            print(f"[ProfilesTab] 新人物 '{new_name}' 已添加到内存字典。")
            self.render_profiles_list() # 重新渲染 UI
            self.after(100, self._scroll_to_bottom) # 尝试滚动到底部
        else: print("[ProfilesTab] 用户取消添加人物。")

    def _scroll_to_bottom(self):
        """尝试将列表滚动到底部"""
        try:
            if hasattr(self.scrollable_frame, '_parent_canvas') and self.scrollable_frame._parent_canvas:
                self.scrollable_frame._parent_canvas.yview_moveto(1.0)
                print("[ProfilesTab] 已尝试滚动到列表底部。")
        except Exception as e: print(f"警告：滚动到列表底部时出错: {e}")

    def load_profiles_from_file(self):
        """加载人物设定文件"""
        print("[ProfilesTab] 请求加载人物设定文件...")
        result = self.config_manager.load_character_profiles_from_file(parent_window=self)
        if result:
            profiles, filepath = result
            print(f"[ProfilesTab] 文件加载成功，路径: {filepath}")
            print(f"[ProfilesTab] 加载并可能迁移后的人物设定数据: {profiles}")
            self.character_profiles = profiles # 更新内存数据
            self.loaded_filepath = filepath
            self.render_profiles_list() # 更新 UI
            filename = os.path.basename(filepath)
            self.file_status_label.configure(text=f"当前设定: {filename}", text_color="green")
        else:
            print("[ProfilesTab] 文件加载失败或用户取消。")
            if self.loaded_filepath: filename = os.path.basename(self.loaded_filepath); self.file_status_label.configure(text=f"加载失败/取消 (仍使用: {filename})", text_color="orange")
            else: self.file_status_label.configure(text="加载失败或取消", text_color="orange")

    def save_profiles_to_file(self):
        """保存当前人物设定到文件"""
        print("[ProfilesTab] 请求保存人物设定文件...")
        if not self.character_profiles: messagebox.showwarning("无设定", "当前没有人物设定数据可以保存。", parent=self); print("[ProfilesTab] 保存取消：内存中没有人物设定。"); return
        invalid_keys = [key for key in self.character_profiles.keys() if not key or key.isspace()]
        if invalid_keys: messagebox.showerror("内部错误", f"发现无效的人物 Key：\n{', '.join(invalid_keys)}\n请修正后再保存。", parent=self); print(f"[ProfilesTab] 保存取消：发现无效 Key: {invalid_keys}"); self.render_profiles_list(); return
        print(f"[ProfilesTab] 准备将以下数据保存到文件:", json.dumps(self.character_profiles, indent=2, ensure_ascii=False))
        success = self.config_manager.save_character_profiles_to_file(profiles=self.character_profiles, parent_window=self)
        if success: print("[ProfilesTab] 文件保存成功。"); self.file_status_label.configure(text="当前设定已保存", text_color="green")
        else: print("[ProfilesTab] 文件保存失败或用户取消。"); self.file_status_label.configure(text="保存失败或取消", text_color="orange")

    def get_profiles_for_step2(self):
        """返回供步骤二使用的 profiles 字典和 JSON 字符串"""
        print("[ProfilesTab] 请求获取供步骤二使用的 Profiles 字典和 JSON...")
        current_profiles = self.character_profiles
        print("[ProfilesTab] 当前内存中的人物设定:", current_profiles)
        if not current_profiles: print("[ProfilesTab] 获取数据：人物设定为空。"); messagebox.showwarning("无设定", "当前没有人物设定数据。", parent=self); return None, None
        invalid_keys = [key for key in current_profiles.keys() if not key or key.isspace()]
        if invalid_keys: messagebox.showerror("名称错误", f"发现无效的人物 Key：\n{', '.join(invalid_keys)}\n请修正。", parent=self); print("[ProfilesTab] 获取数据失败：发现无效 Key。"); self.render_profiles_list(); return None, None
        effective_profiles_for_json = {}
        for key, data in current_profiles.items():
            if isinstance(data, dict):
                effective_name = data.get("replacement_name", "").strip() or data.get("display_name", key)
                effective_profiles_for_json[effective_name] = {"positive": data.get("positive", ""), "negative": data.get("negative", "")}
            else: print(f"警告：人物 Key '{key}' 的数据格式无效，已在生成 JSON 时跳过。")
        try:
            json_string = json.dumps(effective_profiles_for_json, ensure_ascii=False, indent=2)
            print("[ProfilesTab] 成功生成供步骤二使用的 JSON 字符串。")
            return current_profiles.copy(), json_string # 返回完整字典和 JSON 字符串
        except Exception as e: print(f"错误：将人物设定转换为 JSON 字符串时出错: {e}"); traceback.print_exc(); messagebox.showerror("内部错误", f"无法将人物设定转换为 JSON 格式:\n{e}", parent=self); return None, None