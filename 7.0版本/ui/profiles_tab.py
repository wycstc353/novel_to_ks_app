# ui/profiles_tab.py
import customtkinter as ctk
from tkinter import StringVar, messagebox, filedialog # 使用标准 tkinter 的 messagebox 和 filedialog
import json
import os # 需要 os 来获取文件名
import traceback # 用于打印详细错误

class ProfilesTab(ctk.CTkFrame):
    """人物设定管理的 UI 标签页"""
    def __init__(self, master, config_manager, app_instance):
        super().__init__(master, fg_color="transparent")
        self.config_manager = config_manager
        self.app = app_instance
        # self.character_profiles 用于存储当前编辑的人物设定
        # 这是内存中的权威数据源，所有操作都应先修改它，然后更新 UI
        self.character_profiles = {}
        self.loaded_filepath = None # 记录当前加载的文件路径，用于状态显示

        self.build_ui()
        print("[ProfilesTab] 人物设定标签页 UI 构建完成。")
        # 初始时不加载任何文件，等待用户操作
        self.render_profiles_list() # 初始渲染空列表

    def build_ui(self):
        """构建人物设定界面的 UI 元素"""
        # 配置主框架的网格布局
        self.grid_rowconfigure(1, weight=1) # 让列表区域 (第1行) 可扩展
        self.grid_columnconfigure(0, weight=1) # 让列 (第0列) 可扩展

        # --- 文件操作按钮区域 ---
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew") # 放置在第0行，水平填充

        # 加载按钮
        self.load_button = ctk.CTkButton(button_frame, text="加载设定文件 (.json)", command=self.load_profiles_from_file)
        self.load_button.pack(side="left", padx=5)

        # 保存按钮 (初始禁用，因为没有数据)
        self.save_button = ctk.CTkButton(button_frame, text="保存当前设定到文件", command=self.save_profiles_to_file, state="disabled")
        self.save_button.pack(side="left", padx=5)

        # 添加人物按钮
        self.add_button = ctk.CTkButton(button_frame, text="添加人物", command=self.add_new_profile)
        self.add_button.pack(side="left", padx=5)

        # 文件状态标签
        self.file_status_label = ctk.CTkLabel(button_frame, text="尚未加载人物设定文件", text_color="gray", wraplength=300) # wraplength 限制宽度自动换行
        self.file_status_label.pack(side="left", padx=10, fill="x", expand=True) # 填充剩余空间

        # --- 人物列表区域 (使用可滚动的 Frame) ---
        self.scrollable_frame = ctk.CTkScrollableFrame(self, label_text="人物列表")
        self.scrollable_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew") # 放置在第1行，填充所有方向
        # 配置滚动框架内部的列权重，让内容水平扩展
        self.scrollable_frame.grid_columnconfigure(0, weight=1)

    def render_profiles_list(self):
        """根据 self.character_profiles 的内容重新绘制人物列表 UI"""
        print("[ProfilesTab] 开始渲染人物列表...")
        # --- 清空当前列表 ---
        # 遍历滚动框架内的所有子控件并销毁它们
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        # --- 数据校验 ---
        # 确保 self.character_profiles 是一个字典
        if not isinstance(self.character_profiles, dict):
             print("错误: self.character_profiles 不是字典类型！已重置为空字典。")
             self.character_profiles = {} # 如果不是字典，重置为空，防止后续错误

        # --- 获取并排序人物名称 ---
        # 获取字典的所有键 (人物名称) 并排序，以便列表按名称显示
        names = sorted(self.character_profiles.keys())
        print(f"[ProfilesTab] 准备渲染 {len(names)} 个人物。")

        # --- 根据列表内容更新 UI ---
        if not names:
            # 如果列表为空，显示提示信息
            no_profiles_label = ctk.CTkLabel(self.scrollable_frame, text="请加载设定文件或点击“添加人物”按钮。", text_color="gray")
            no_profiles_label.grid(row=0, column=0, padx=10, pady=20, sticky="n") # 放置在顶部
            # 禁用保存按钮，因为没有内容可保存
            self.save_button.configure(state="disabled")
            print("[ProfilesTab] 列表为空，显示提示信息，禁用保存按钮。")
        else:
            # 如果列表有内容，启用保存按钮
            self.save_button.configure(state="normal")
            current_row = 0 # 用于 grid 布局的行计数器
            # 遍历排序后的人物名称
            for name in names:
                # 从内存字典中获取该人物的数据，使用 .get 提供默认空字典以防万一
                profile_data = self.character_profiles.get(name, {})

                # 再次校验获取到的数据是否为字典
                if not isinstance(profile_data, dict):
                     print(f"警告: 人物 '{name}' 的数据不是字典格式，已跳过渲染。数据: {profile_data}")
                     continue # 跳过这个无效的人物条目

                # --- 为每个人物创建一个独立的 Frame ---
                entry_frame = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
                entry_frame.grid(row=current_row, column=0, pady=(0, 8), sticky="ew") # 每行之间留点空隙
                # 配置 entry_frame 内部列权重，让提示词输入框可以扩展
                entry_frame.grid_columnconfigure(1, weight=1) # 正向提示框列
                entry_frame.grid_columnconfigure(2, weight=1) # 负向提示框列

                # --- 定义回调函数 (使用闭包捕获当前循环的 name) ---
                # 创建删除按钮的回调，捕获当前的 name
                def create_remove_callback(n):
                    return lambda: self.remove_profile(n)
                # 创建更新字段的回调，捕获当前 name、字段类型和对应的 StringVar
                def create_update_callback(n, field_type, entry_var):
                    # 当输入框失去焦点 (<FocusOut>) 时触发更新
                    return lambda event=None: self.update_profile_field(n, field_type, entry_var.get())

                # --- 创建 UI 元素 ---
                # 删除按钮
                remove_btn = ctk.CTkButton(entry_frame, text="删除", width=60,
                                          fg_color="#DB3E3E", hover_color="#B82E2E", # 红色系
                                          command=create_remove_callback(name)) # 绑定删除回调
                # 放置在最右侧，跨越两行 (名称行和提示词行)
                remove_btn.grid(row=0, column=3, rowspan=2, padx=(10, 0), pady=2, sticky="ns")

                # 名称标签和输入框
                name_label = ctk.CTkLabel(entry_frame, text="名称:", width=50, anchor="w")
                name_label.grid(row=0, column=0, padx=(0, 5), pady=2, sticky="w")
                name_var = StringVar(value=name) # 使用 StringVar 绑定输入框内容
                name_entry = ctk.CTkEntry(entry_frame, textvariable=name_var)
                name_entry.grid(row=0, column=1, columnspan=2, padx=5, pady=2, sticky="ew") # 跨越两列
                # 绑定失去焦点事件，用于处理名称更改
                # 使用 lambda 捕获当前的 name 值作为 old_name
                name_entry.bind("<FocusOut>", lambda event, current_name=name, var=name_var: self.handle_name_change(current_name, var.get()))

                # 正向提示标签和输入框
                pos_label = ctk.CTkLabel(entry_frame, text="正向:", width=50, anchor="w")
                pos_label.grid(row=1, column=0, padx=(0, 5), pady=2, sticky="w")
                pos_var = StringVar(value=profile_data.get("positive", "")) # 获取正向提示，默认为空
                pos_entry = ctk.CTkEntry(entry_frame, textvariable=pos_var)
                pos_entry.grid(row=1, column=1, padx=5, pady=2, sticky="ew")
                # 绑定失去焦点事件，更新内存中的 "positive" 字段
                pos_entry.bind("<FocusOut>", create_update_callback(name, "positive", pos_var))

                # 负向提示标签和输入框
                neg_label = ctk.CTkLabel(entry_frame, text="负向:", width=50, anchor="w")
                neg_label.grid(row=1, column=2, padx=(10, 5), pady=2, sticky="w") # 与正向提示之间留点空隙
                neg_var = StringVar(value=profile_data.get("negative", "")) # 获取负向提示，默认为空
                neg_entry = ctk.CTkEntry(entry_frame, textvariable=neg_var)
                neg_entry.grid(row=1, column=2, padx=5, pady=2, sticky="ew")
                # 绑定失去焦点事件，更新内存中的 "negative" 字段
                neg_entry.bind("<FocusOut>", create_update_callback(name, "negative", neg_var))

                current_row += 1 # 移动到下一行

        print("[ProfilesTab] 人物列表渲染完成。")

    def handle_name_change(self, old_name, new_name_raw):
        """处理人物名称更改事件 (在名称输入框失去焦点时触发)"""
        new_name = new_name_raw.strip() # 获取新名称并去除首尾空格
        print(f"[ProfilesTab] 处理名称更改请求：从 '{old_name}' 到 '{new_name}'")

        # --- 校验新名称 ---
        if not new_name:
            # 如果新名称为空，显示错误并强制重新渲染列表 (会恢复旧名称)
            messagebox.showerror("名称错误", f"人物名称不能为空！无法将 '{old_name}' 重命名为空。", parent=self)
            print(f"错误：尝试将 '{old_name}' 重命名为空名称。")
            self.render_profiles_list() # 重新渲染以恢复 UI
            return

        if new_name == old_name:
            # 如果名称未改变，无需任何操作
            print("[ProfilesTab] 名称未改变，无需操作。")
            return

        # 检查新名称是否已存在 (且不是旧名称自身)
        if new_name in self.character_profiles:
            messagebox.showerror("名称冲突", f"人物名称 '{new_name}' 已经存在！请使用其他名称。", parent=self)
            print(f"错误：尝试将 '{old_name}' 重命名为已存在的名称 '{new_name}'。")
            self.render_profiles_list() # 重新渲染以恢复 UI
            return

        # --- 更新内存中的字典 ---
        # 检查旧名称是否存在于字典中 (理论上应该存在)
        if old_name in self.character_profiles:
            print(f"[ProfilesTab] 正在更新内存字典：将键 '{old_name}' 替换为 '{new_name}'...")
            # 从字典中移除旧条目，并获取其对应的值 (profile_data)
            profile_data = self.character_profiles.pop(old_name)
            # 使用新名称作为键，将原来的值重新添加到字典中
            self.character_profiles[new_name] = profile_data
            print(f"[ProfilesTab] 内存字典更新完成。旧键 '{old_name}' 已移除，新键 '{new_name}' 已添加。")
            # **重要：修改了字典的键后，必须重新渲染整个列表**
            # 因为 UI 元素的绑定回调函数可能仍然持有旧的名称
            self.render_profiles_list()
        else:
            # 如果旧名称在字典中找不到，这是一个异常情况
            print(f"错误：尝试更改名称时，在内存字典中找不到旧名称 '{old_name}'！")
            # 可能发生了并发修改或其他逻辑错误，重新渲染以尝试同步状态
            self.render_profiles_list()

    def update_profile_field(self, name, field_type, value):
        """更新内存中指定人物的指定字段 (在提示词输入框失去焦点时触发)"""
        print(f"[ProfilesTab] 更新字段请求：人物='{name}', 字段='{field_type}', 新值='{value[:30]}...'") # 只打印部分值避免过长日志

        # --- 直接修改内存中的字典 ---
        # 检查人物名称是否存在于字典中
        if name in self.character_profiles:
            # 检查字段类型是否是预期的 "positive" 或 "negative"
            if field_type in ["positive", "negative"]:
                # 再次确保该人物对应的值确实是字典 (防御性编程)
                if isinstance(self.character_profiles[name], dict):
                    # 更新字典中对应字段的值 (去除首尾空格)
                    self.character_profiles[name][field_type] = value.strip()
                    print(f"[ProfilesTab] 内存中 '{name}' 的 '{field_type}' 字段已更新。")
                else:
                     # 如果值不是字典，记录错误
                     print(f"错误：人物 '{name}' 在内存中的设定数据不是字典格式！无法更新字段 '{field_type}'。")
            else:
                 # 如果字段类型未知，记录警告
                 print(f"警告: 尝试更新未知的字段类型 '{field_type}' 对于人物 '{name}'")
        else:
            # 如果人物名称在字典中找不到
            # 这可能在名称刚刚被修改后、UI尚未完全更新时短暂发生，通常可以忽略
            # 但如果持续出现，则表明状态同步可能存在问题
            print(f"警告: 尝试更新不存在或刚被重命名的人物 '{name}' 的字段 '{field_type}'。可能由于名称更改导致，通常可忽略。")
        # 注意：这里只更新内存数据，不重新渲染整个列表，因为只是字段值变化，
        # UI 上的输入框已经通过 StringVar 显示了新值。

    def remove_profile(self, name_to_remove):
        """从内存和 UI 中移除指定的人物设定"""
        print(f"[ProfilesTab] 请求删除人物: '{name_to_remove}'")
        # 检查人物是否存在于内存字典中
        if name_to_remove in self.character_profiles:
            # 弹出确认对话框
            if messagebox.askyesno("确认删除", f"确定要删除人物 '{name_to_remove}' 吗？\n此操作将立即从当前编辑的设定中移除，但不会影响已保存的文件。", parent=self):
                # --- 关键：直接从内存字典中删除 ---
                try:
                    del self.character_profiles[name_to_remove]
                    print(f"[ProfilesTab] 人物 '{name_to_remove}' 已从内存字典中删除。")
                    # --- 删除后必须重新渲染列表以更新 UI ---
                    self.render_profiles_list()
                except KeyError:
                    # 理论上不应该发生，因为前面检查过存在性
                    print(f"错误：尝试删除人物 '{name_to_remove}' 时发生 KeyError (可能并发问题?)")
                    self.render_profiles_list() # 尝试刷新 UI
                except Exception as e:
                    print(f"错误：删除人物 '{name_to_remove}' 时发生意外错误: {e}")
                    traceback.print_exc()
                    messagebox.showerror("删除错误", f"删除人物时出错:\n{e}", parent=self)
                    self.render_profiles_list() # 尝试刷新 UI
        else:
            # 如果尝试删除一个不存在的人物 (可能UI状态不同步)
            print(f"警告: 尝试删除不存在的人物 '{name_to_remove}'。")
            self.render_profiles_list() # 刷新 UI 以确保一致性

    def add_new_profile(self):
        """弹出对话框让用户输入新人物名称，并添加到内存和 UI"""
        print("[ProfilesTab] 请求添加新人物...")
        # 弹出输入对话框
        dialog = ctk.CTkInputDialog(text="请输入新人物的名称:", title="添加人物")
        new_name_raw = dialog.get_input() # 获取用户输入

        if new_name_raw is not None: # 检查用户是否点击了 "OK" (即使输入为空)
            new_name = new_name_raw.strip() # 去除首尾空格
            print(f"[ProfilesTab] 用户输入名称: '{new_name}'")

            # --- 校验名称 ---
            if not new_name:
                messagebox.showerror("名称错误", "人物名称不能为空！", parent=self)
                print("错误：用户尝试添加空名称。")
                return # 不进行添加

            if new_name in self.character_profiles:
                messagebox.showerror("名称冲突", f"人物名称 '{new_name}' 已经存在！", parent=self)
                print(f"错误：用户尝试添加已存在的名称 '{new_name}'。")
                return # 不进行添加

            # --- 关键：直接修改内存字典 ---
            # 添加新人物，初始提示词为空
            self.character_profiles[new_name] = {"positive": "", "negative": ""}
            print(f"[ProfilesTab] 新人物 '{new_name}' 已添加到内存字典。")

            # --- 添加后重新渲染列表以更新 UI ---
            self.render_profiles_list()

            # --- (可选) 尝试滚动到列表底部以显示新添加项 ---
            # 使用 after 延迟执行，确保 UI 更新完成
            self.after(100, self._scroll_to_bottom)

        else:
            # 用户点击了 "Cancel" 或关闭了对话框
            print("[ProfilesTab] 用户取消添加人物或输入为空。")

    def _scroll_to_bottom(self):
        """尝试将可滚动框架滚动到底部"""
        try:
            # CTkScrollableFrame 内部有一个 _parent_canvas
            if hasattr(self.scrollable_frame, '_parent_canvas') and self.scrollable_frame._parent_canvas:
                self.scrollable_frame._parent_canvas.yview_moveto(1.0) # 滚动到最底部
                print("[ProfilesTab] 已尝试滚动到列表底部。")
        except Exception as e:
            print(f"警告：滚动到列表底部时出错: {e}")


    def load_profiles_from_file(self):
        """加载人物设定文件，更新内存字典和 UI"""
        print("[ProfilesTab] 请求加载人物设定文件...")
        # 调用 config_manager 中的加载函数，它会处理文件对话框和 JSON 解析
        # 它需要父窗口 (self) 来显示可能的消息框
        result = self.config_manager.load_character_profiles_from_file(parent_window=self)

        if result:
            # 如果加载成功，result 是一个元组 (profiles_dict, filepath)
            profiles, filepath = result
            print(f"[ProfilesTab] 文件加载成功，路径: {filepath}")
            print(f"[ProfilesTab] 加载的人物设定数据: {profiles}") # 打印加载的数据

            # --- 关键：用加载的数据覆盖内存中的字典 ---
            self.character_profiles = profiles
            self.loaded_filepath = filepath # 记录文件路径

            # --- 用加载的数据重新渲染 UI 列表 ---
            self.render_profiles_list()

            # 更新文件状态标签
            filename = os.path.basename(filepath) # 只显示文件名
            self.file_status_label.configure(text=f"当前设定: {filename}", text_color="green")
            # 可以选择性地显示一个成功消息框
            # messagebox.showinfo("加载成功", f"已成功加载人物设定文件:\n{filepath}", parent=self)
        else:
            # 如果加载失败或用户取消
            print("[ProfilesTab] 文件加载失败或用户取消。")
            # 更新文件状态标签
            # 如果之前有加载文件，保持显示旧文件名，但颜色变灰？或者提示加载失败
            if self.loaded_filepath:
                 filename = os.path.basename(self.loaded_filepath)
                 self.file_status_label.configure(text=f"加载失败/取消 (仍使用: {filename})", text_color="orange")
            else:
                 self.file_status_label.configure(text="加载失败或取消", text_color="orange")


    def save_profiles_to_file(self):
        """将当前内存中的人物设定保存到用户指定的文件"""
        print("[ProfilesTab] 请求保存人物设定文件...")
        # --- 直接使用内存中的 self.character_profiles ---
        if not self.character_profiles:
            messagebox.showwarning("无设定", "当前没有人物设定数据可以保存。", parent=self)
            print("[ProfilesTab] 保存取消：内存中没有人物设定。")
            return

        # --- 在保存前最后一次检查名称是否有效 ---
        # 检查是否存在空名称或只包含空格的名称
        invalid_names = [name for name in self.character_profiles.keys() if not name or name.isspace()]
        if invalid_names:
             messagebox.showerror("名称错误", f"发现无效的人物名称（为空或只包含空格）：\n{', '.join(invalid_names)}\n\n请修正后再保存。", parent=self)
             print(f"[ProfilesTab] 保存取消：发现无效名称: {invalid_names}")
             # 可以考虑调用 render_profiles_list() 来刷新 UI，可能高亮显示问题条目 (如果实现了的话)
             self.render_profiles_list() # 刷新列表
             return

        print(f"[ProfilesTab] 准备将以下数据保存到文件:", json.dumps(self.character_profiles, indent=2, ensure_ascii=False)) # 打印待保存数据 (格式化)

        # 调用 config_manager 的保存函数，它会弹出文件对话框并处理写入
        # 传递内存中的设定数据和父窗口
        success = self.config_manager.save_character_profiles_to_file(
            profiles=self.character_profiles,
            parent_window=self
        )

        if success:
            # 如果保存成功
            print("[ProfilesTab] 文件保存成功。")
            # 更新文件状态标签 (可能需要获取保存的文件路径?)
            # config_manager.save_character_profiles_to_file 返回的只是 True/False
            # 如果需要更新状态标签为新文件名，需要修改保存函数返回路径
            # 暂时只提示已保存
            self.file_status_label.configure(text="当前设定已保存", text_color="green")
            # 可以选择性显示成功消息框
            # messagebox.showinfo("保存成功", "人物设定已成功保存。", parent=self)
        else:
            # 如果保存失败或用户取消
            print("[ProfilesTab] 文件保存失败或用户取消。")
            # 更新文件状态标签
            self.file_status_label.configure(text="保存失败或取消", text_color="orange")

    def get_profiles_json(self):
        """
        返回当前内存中人物设定的 JSON 字符串，供其他模块 (如 WorkflowTab) 使用。
        在生成前会进行有效性检查。
        """
        print("[ProfilesTab] 请求获取人物设定 JSON 字符串...")
        # --- 直接使用内存中的 self.character_profiles ---
        current_profiles = self.character_profiles
        print("[ProfilesTab] 当前内存中的人物设定:", current_profiles)

        # --- 检查字典是否为空 ---
        if not current_profiles:
             print("[ProfilesTab] 获取 JSON：人物设定为空。")
             messagebox.showwarning("无设定", "当前没有人物设定数据。\n请先加载或添加人物设定，然后才能在步骤二中使用。", parent=self) # 提示用户
             return None # 返回 None 表示没有有效数据

        # --- 检查是否有无效名称 ---
        invalid_names = [name for name in current_profiles.keys() if not name or name.isspace()]
        if invalid_names:
             messagebox.showerror("名称错误", f"执行操作前发现无效的人物名称（为空或只包含空格）：\n{', '.join(invalid_names)}\n\n请在“人物设定”标签页中修正后再继续。", parent=self)
             print("[ProfilesTab] 获取 JSON 失败：发现无效名称。")
             self.render_profiles_list() # 刷新列表以显示当前状态
             return None # 返回 None 表示数据无效

        # --- 尝试序列化为 JSON ---
        try:
            # ensure_ascii=False 保证中文等非 ASCII 字符正确显示
            # indent=2 添加缩进，方便调试时查看生成的 JSON
            json_string = json.dumps(current_profiles, ensure_ascii=False, indent=2)
            print("[ProfilesTab] 成功生成人物设定 JSON 字符串。")
            return json_string
        except Exception as e:
            # 捕获 JSON 序列化过程中可能出现的错误
            print(f"错误：将人物设定转换为 JSON 字符串时出错: {e}")
            traceback.print_exc()
            messagebox.showerror("内部错误", f"无法将人物设定转换为 JSON 格式:\n{e}", parent=self)
            return None # 返回 None 表示转换失败
