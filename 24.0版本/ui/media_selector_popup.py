# ui/media_selector_popup.py
import customtkinter as ctk
import logging
from PIL import Image, ImageTk # 功能性备注: 导入 Pillow 库用于图像处理
import os # 功能性备注: 导入 os 用于路径操作
import re # 功能性备注: 导入 re 用于文本处理

# 功能性备注: 获取当前模块的 logger 实例
logger = logging.getLogger(__name__)

# 功能性备注: 缩略图默认尺寸
THUMBNAIL_SIZE = (128, 128)

class MediaSelectorPopup(ctk.CTkToplevel):
    """用于选择图片或语音任务的弹窗 (带详情预览和过滤)""" # 功能性备注: 更新类描述

    def __init__(self, parent, title, items, media_type, save_dir=None):
        """
        初始化弹窗。
        Args:
            parent: 父窗口 (通常是 WorkflowTab 实例)。
            title (str): 弹窗标题。
            items (list): 包含任务信息的字典列表，每个字典应包含 'id', 'name', 'status',
                          以及 'positive_prompt', 'negative_prompt', 'ref_image_path', 'mask_image_path' (图片类型可选),
                          或 'text' (语音类型可选)。
            media_type (str): 'image' 或 'audio'。
            save_dir (str, optional): 图片保存目录路径，用于查找已生成的图片。默认为 None。
        """
        super().__init__(parent)
        self.title(title)
        # 逻辑备注: 调整窗口大小以容纳左右面板
        self.geometry("950x650")
        self.attributes("-topmost", True)
        self.grab_set()
        self.parent = parent
        self.original_items = items # 功能性备注: 保存原始列表
        self.media_type = media_type
        self.save_dir = save_dir
        self.selected_ids = None
        self.checkbox_vars = {}
        self.current_detail_item_id = None
        self.current_detail_item_data = None # 功能性备注: 存储当前显示详情的完整数据

        # --- 功能性备注: 状态变量 ---
        self.filter_var = ctk.StringVar(value="all") # 功能性备注: 列表过滤状态变量
        # 功能性备注: 详情显示控制变量 (仅图片类型需要)
        self.show_prompts_var = ctk.BooleanVar(value=True)
        self.show_ref_image_var = ctk.BooleanVar(value=True)
        self.show_mask_image_var = ctk.BooleanVar(value=True)
        self.show_gen_image_var = ctk.BooleanVar(value=True)

        # --- 布局调整: 主框架分为左右两列 ---
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1, minsize=300)
        self.grid_columnconfigure(1, weight=2)

        # --- 顶部说明和图例 (跨两列) ---
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        top_frame.grid_columnconfigure(1, weight=1)
        legend_label_title = ctk.CTkLabel(top_frame, text="颜色说明:", font=ctk.CTkFont(weight="bold"))
        legend_label_title.grid(row=0, column=0, sticky="w", padx=(0, 5))
        legend_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        legend_frame.grid(row=0, column=1, sticky="ew")
        green_label = ctk.CTkLabel(legend_frame, text="绿色: 可生成", text_color="green"); green_label.pack(side="left", padx=5)
        yellow_label = ctk.CTkLabel(legend_frame, text="黄色: 已生成", text_color="orange"); yellow_label.pack(side="left", padx=5)
        red_label = ctk.CTkLabel(legend_frame, text="红色: 无法生成(缺配置)", text_color="red"); red_label.pack(side="left", padx=5)

        # --- 左侧: 任务列表区域 (包含过滤选项) ---
        left_pane = ctk.CTkFrame(self, fg_color="transparent")
        left_pane.grid(row=1, column=0, padx=(10, 5), pady=5, sticky="nsew")
        left_pane.grid_rowconfigure(1, weight=1) # 让滚动列表行扩展
        left_pane.grid_columnconfigure(0, weight=1)

        # 功能性备注: 添加列表过滤选项框架
        filter_frame = ctk.CTkFrame(left_pane)
        filter_frame.grid(row=0, column=0, padx=0, pady=(0, 5), sticky="ew")
        filter_label = ctk.CTkLabel(filter_frame, text="显示:")
        filter_label.pack(side="left", padx=(5, 5))
        # 功能性备注: 创建过滤单选按钮
        ctk.CTkRadioButton(filter_frame, text="全部", variable=self.filter_var, value="all", command=self._render_items).pack(side="left", padx=3)
        ctk.CTkRadioButton(filter_frame, text="未生成", variable=self.filter_var, value="ready", command=self._render_items).pack(side="left", padx=3)
        ctk.CTkRadioButton(filter_frame, text="已生成", variable=self.filter_var, value="generated", command=self._render_items).pack(side="left", padx=3)
        ctk.CTkRadioButton(filter_frame, text="错误", variable=self.filter_var, value="error", command=self._render_items).pack(side="left", padx=3)

        # 功能性备注: 任务列表滚动区域
        self.scrollable_frame = ctk.CTkScrollableFrame(left_pane, label_text=f"选择要生成的 {media_type} 任务")
        self.scrollable_frame.grid(row=1, column=0, sticky="nsew")
        self.scrollable_frame.grid_columnconfigure(0, weight=1)

        # --- 右侧: 详情显示区域 ---
        self.detail_pane = ctk.CTkFrame(self)
        self.detail_pane.grid(row=1, column=1, padx=(5, 10), pady=5, sticky="nsew")
        self.detail_pane.grid_columnconfigure(0, weight=1)
        # 功能性备注: 根据 media_type 构建不同的详情布局
        self._build_detail_pane()

        # --- 底部按钮区域 (跨两列) ---
        bottom_frame = ctk.CTkFrame(self)
        bottom_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        bottom_frame.grid_columnconfigure(0, weight=1)
        button_inner_frame = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        button_inner_frame.grid(row=0, column=1, sticky="e")
        ctk.CTkButton(button_inner_frame, text="全选", command=self._select_all).pack(side="left", padx=5)
        ctk.CTkButton(button_inner_frame, text="取消全选", command=self._deselect_all).pack(side="left", padx=5)
        ctk.CTkButton(button_inner_frame, text="确认选择", command=self._confirm_selection).pack(side="left", padx=5)
        ctk.CTkButton(button_inner_frame, text="取消", command=self._cancel).pack(side="left", padx=5)

        # --- 初始渲染列表和清空详情 ---
        self._render_items()
        self._clear_details_pane()

    def _build_detail_pane(self):
        """根据 media_type 构建右侧详情面板的 UI"""
        # 功能性备注: 清空现有详情控件 (如果重建)
        for widget in self.detail_pane.winfo_children():
            widget.destroy()

        if self.media_type == 'image':
            # --- 图片类型详情布局 ---
            # 功能性备注: 添加详情显示控制复选框
            detail_control_frame = ctk.CTkFrame(self.detail_pane, fg_color="transparent")
            detail_control_frame.grid(row=0, column=0, padx=10, pady=(5, 5), sticky="ew")
            ctk.CTkLabel(detail_control_frame, text="显示详情:").pack(side="left", padx=(0, 5))
            ctk.CTkCheckBox(detail_control_frame, text="提示词", variable=self.show_prompts_var, command=self._refresh_details_visibility).pack(side="left", padx=3)
            ctk.CTkCheckBox(detail_control_frame, text="参考图", variable=self.show_ref_image_var, command=self._refresh_details_visibility).pack(side="left", padx=3)
            ctk.CTkCheckBox(detail_control_frame, text="蒙版图", variable=self.show_mask_image_var, command=self._refresh_details_visibility).pack(side="left", padx=3)
            ctk.CTkCheckBox(detail_control_frame, text="生成图", variable=self.show_gen_image_var, command=self._refresh_details_visibility).pack(side="left", padx=3)

            # 功能性备注: 配置剩余行权重
            self.detail_pane.grid_rowconfigure(2, weight=1) # 正向提示
            self.detail_pane.grid_rowconfigure(4, weight=1) # 负向提示
            self.detail_pane.grid_rowconfigure(6, weight=2) # 图片区域

            # 正向提示词
            self.pos_prompt_label = ctk.CTkLabel(self.detail_pane, text="正面提示词:", anchor="w")
            self.pos_prompt_label.grid(row=1, column=0, padx=10, pady=(5, 2), sticky="w")
            self.pos_prompt_textbox = ctk.CTkTextbox(self.detail_pane, wrap="word", height=80, state="disabled")
            self.pos_prompt_textbox.grid(row=2, column=0, padx=10, pady=(0, 5), sticky="nsew")

            # 负向提示词
            self.neg_prompt_label = ctk.CTkLabel(self.detail_pane, text="负面提示词:", anchor="w")
            self.neg_prompt_label.grid(row=3, column=0, padx=10, pady=(5, 2), sticky="w")
            self.neg_prompt_textbox = ctk.CTkTextbox(self.detail_pane, wrap="word", height=80, state="disabled")
            self.neg_prompt_textbox.grid(row=4, column=0, padx=10, pady=(0, 10), sticky="nsew")

            # 图片显示区域框架
            self.image_display_frame = ctk.CTkFrame(self.detail_pane, fg_color="transparent")
            self.image_display_frame.grid(row=5, column=0, rowspan=2, padx=10, pady=5, sticky="nsew")
            self.image_display_frame.grid_columnconfigure((0, 1, 2), weight=1)
            self.image_display_frame.grid_rowconfigure(1, weight=1)

            # 参考图
            self.ref_img_label_title = ctk.CTkLabel(self.image_display_frame, text="参考图像:")
            self.ref_img_label_title.grid(row=0, column=0, pady=(5, 2))
            self.ref_image_label = ctk.CTkLabel(self.image_display_frame, text="无", width=THUMBNAIL_SIZE[0], height=THUMBNAIL_SIZE[1])
            self.ref_image_label.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")

            # 蒙版图
            self.mask_img_label_title = ctk.CTkLabel(self.image_display_frame, text="蒙版图像:")
            self.mask_img_label_title.grid(row=0, column=1, pady=(5, 2))
            self.mask_image_label = ctk.CTkLabel(self.image_display_frame, text="无", width=THUMBNAIL_SIZE[0], height=THUMBNAIL_SIZE[1])
            self.mask_image_label.grid(row=1, column=1, padx=5, pady=5, sticky="nsew")

            # 已生成图
            self.gen_img_label_title = ctk.CTkLabel(self.image_display_frame, text="已生成图像:")
            self.gen_img_label_title.grid(row=0, column=2, pady=(5, 2))
            self.generated_image_label = ctk.CTkLabel(self.image_display_frame, text="未选择", width=THUMBNAIL_SIZE[0], height=THUMBNAIL_SIZE[1])
            self.generated_image_label.grid(row=1, column=2, padx=5, pady=5, sticky="nsew")

        elif self.media_type == 'audio':
            # --- 语音类型详情布局 ---
            self.detail_pane.grid_rowconfigure(1, weight=1) # 让文本框扩展

            audio_text_label = ctk.CTkLabel(self.detail_pane, text="对应文本:", anchor="w")
            audio_text_label.grid(row=0, column=0, padx=10, pady=(10, 2), sticky="w")
            self.audio_text_display = ctk.CTkTextbox(self.detail_pane, wrap="word", state="disabled")
            self.audio_text_display.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")

    def _render_items(self):
        """在滚动框架内渲染任务列表项 (根据过滤条件)"""
        # 功能性备注: 清空旧内容
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.checkbox_vars.clear()

        # 功能性备注: 定义颜色映射
        color_map = {"ready": "green", "generated": "orange", "error": "red"}
        default_color = "gray"

        # 功能性备注: 根据过滤条件筛选列表
        current_filter = self.filter_var.get()
        filtered_items = []
        if current_filter == "all":
            filtered_items = self.original_items
        else:
            filtered_items = [item for item in self.original_items if item.get("status") == current_filter]

        # 功能性备注: 遍历筛选后的任务项并创建 UI 元素
        for idx, item in enumerate(filtered_items):
            item_id = item.get("id", f"未知ID_{idx}")
            item_name = item.get("name", "未知名称")
            item_status = item.get("status", "error")
            text_color = color_map.get(item_status, default_color)

            # 功能性备注: 创建 Checkbox，并绑定命令以更新详情面板
            var = ctk.BooleanVar()
            checkbox = ctk.CTkCheckBox(
                self.scrollable_frame,
                text=f"{item_name} - {item_id}",
                variable=var,
                text_color=text_color,
                # 逻辑备注: 当 Checkbox 状态改变时，调用 _on_item_selected
                command=lambda checked=var, item_data=item: self._on_item_selected(checked.get(), item_data)
            )
            checkbox.grid(row=idx, column=0, padx=5, pady=2, sticky="w")
            self.checkbox_vars[item_id] = var

    def _on_item_selected(self, is_checked, item_data):
        """当列表中的项目被选中或取消选中时调用"""
        # 逻辑备注: 只要点击就更新详情
        item_id = item_data.get("id")
        if item_id:
            self.current_detail_item_data = item_data # 功能性备注: 存储当前选中项的数据
            self._update_details_pane() # 功能性备注: 调用无参数的更新函数
        else:
            self._clear_details_pane()

    def _refresh_details_visibility(self):
        """根据详情控制复选框的状态刷新详情面板"""
        # 功能性备注: 当详情可见性复选框被点击时调用
        if self.current_detail_item_data:
            self._update_details_pane() # 功能性备注: 使用存储的数据重新更新详情

    def _clear_details_pane(self):
        """清空右侧详情面板的内容"""
        self.current_detail_item_id = None
        self.current_detail_item_data = None # 功能性备注: 清空存储的数据

        if self.media_type == 'image':
            # 清空文本框
            if hasattr(self, 'pos_prompt_textbox'):
                self.pos_prompt_textbox.configure(state="normal"); self.pos_prompt_textbox.delete("1.0", "end"); self.pos_prompt_textbox.configure(state="disabled")
            if hasattr(self, 'neg_prompt_textbox'):
                self.neg_prompt_textbox.configure(state="normal"); self.neg_prompt_textbox.delete("1.0", "end"); self.neg_prompt_textbox.configure(state="disabled")
            # 重置图片标签
            if hasattr(self, 'ref_image_label'): self.ref_image_label.configure(image=None, text="无")
            if hasattr(self, 'mask_image_label'): self.mask_image_label.configure(image=None, text="无")
            if hasattr(self, 'generated_image_label'): self.generated_image_label.configure(image=None, text="未选择")
            # 功能性备注: 根据复选框状态隐藏/显示标签和框架
            self._apply_detail_visibility()
        elif self.media_type == 'audio':
            if hasattr(self, 'audio_text_display'):
                self.audio_text_display.configure(state="normal"); self.audio_text_display.delete("1.0", "end"); self.audio_text_display.configure(state="disabled")

    def _apply_detail_visibility(self):
        """根据详情控制复选框状态显示/隐藏图片详情控件"""
        # 功能性备注: 仅在图片模式下执行
        if self.media_type != 'image': return

        # 功能性备注: 控制提示词区域的可见性
        show_prompts = self.show_prompts_var.get()
        for widget in [getattr(self, 'pos_prompt_label', None), getattr(self, 'pos_prompt_textbox', None),
                       getattr(self, 'neg_prompt_label', None), getattr(self, 'neg_prompt_textbox', None)]:
            if widget and widget.winfo_exists():
                if show_prompts: widget.grid()
                else: widget.grid_remove()

        # 功能性备注: 控制图片区域的可见性
        show_ref = self.show_ref_image_var.get()
        show_mask = self.show_mask_image_var.get()
        show_gen = self.show_gen_image_var.get()

        # 功能性备注: 控制图片显示框架的可见性
        img_frame = getattr(self, 'image_display_frame', None)
        if img_frame and img_frame.winfo_exists():
            if show_ref or show_mask or show_gen: img_frame.grid()
            else: img_frame.grid_remove()

        # 功能性备注: 控制单个图片标签及其标题的可见性
        for widget_pair in [(getattr(self, 'ref_img_label_title', None), getattr(self, 'ref_image_label', None)),
                            (getattr(self, 'mask_img_label_title', None), getattr(self, 'mask_image_label', None)),
                            (getattr(self, 'gen_img_label_title', None), getattr(self, 'generated_image_label', None))]:
            title_widget, img_widget = widget_pair
            should_show = False
            if title_widget == getattr(self, 'ref_img_label_title', None): should_show = show_ref
            elif title_widget == getattr(self, 'mask_img_label_title', None): should_show = show_mask
            elif title_widget == getattr(self, 'gen_img_label_title', None): should_show = show_gen

            if title_widget and title_widget.winfo_exists():
                if should_show: title_widget.grid()
                else: title_widget.grid_remove()
            if img_widget and img_widget.winfo_exists():
                if should_show: img_widget.grid()
                else: img_widget.grid_remove()

    def _update_details_pane(self):
        """根据 self.current_detail_item_data 更新右侧详情面板"""
        # 功能性备注: 使用存储的数据更新详情
        item_data = self.current_detail_item_data
        if not item_data:
            self._clear_details_pane()
            return

        item_id = item_data.get("id")
        if not item_id: return # ID 无效则不更新

        # 功能性备注: 更新当前 ID 跟踪
        self.current_detail_item_id = item_id
        logger.info(f"更新详情面板，显示任务: {item_id}")

        if self.media_type == 'image':
            # --- 更新图片详情 ---
            # 功能性备注: 应用可见性设置
            self._apply_detail_visibility()

            # 1. 更新提示词 (如果需要显示)
            if self.show_prompts_var.get():
                pos_prompt = item_data.get("positive_prompt", "无")
                neg_prompt = item_data.get("negative_prompt", "无")
                if hasattr(self, 'pos_prompt_textbox'):
                    self.pos_prompt_textbox.configure(state="normal"); self.pos_prompt_textbox.delete("1.0", "end"); self.pos_prompt_textbox.insert("1.0", pos_prompt); self.pos_prompt_textbox.configure(state="disabled")
                if hasattr(self, 'neg_prompt_textbox'):
                    self.neg_prompt_textbox.configure(state="normal"); self.neg_prompt_textbox.delete("1.0", "end"); self.neg_prompt_textbox.insert("1.0", neg_prompt); self.neg_prompt_textbox.configure(state="disabled")

            # 2. 更新参考图像 (如果需要显示)
            if self.show_ref_image_var.get() and hasattr(self, 'ref_image_label'):
                ref_path = item_data.get("ref_image_path")
                self._update_image_label(self.ref_image_label, ref_path, "无参考图")

            # 3. 更新蒙版图像 (如果需要显示)
            if self.show_mask_image_var.get() and hasattr(self, 'mask_image_label'):
                mask_path = item_data.get("mask_image_path")
                self._update_image_label(self.mask_image_label, mask_path, "无蒙版图")

            # 4. 更新已生成图像 (如果需要显示)
            if self.show_gen_image_var.get() and hasattr(self, 'generated_image_label'):
                generated_image_path = None
                if self.save_dir and item_id:
                    potential_path = os.path.join(self.save_dir, item_id)
                    if os.path.exists(potential_path):
                        generated_image_path = potential_path
                    else:
                        base_name, ext = os.path.splitext(item_id)
                        base_name_no_num = re.sub(r'_\d+$', '', base_name)
                        potential_base_path = os.path.join(self.save_dir, f"{base_name_no_num}{ext}")
                        if os.path.exists(potential_base_path):
                            generated_image_path = potential_base_path
                        else:
                            potential_num1_path = os.path.join(self.save_dir, f"{base_name_no_num}_1{ext}")
                            if os.path.exists(potential_num1_path):
                                generated_image_path = potential_num1_path
                self._update_image_label(self.generated_image_label, generated_image_path, "未生成")

        elif self.media_type == 'audio':
            # --- 更新语音详情 ---
            audio_text = item_data.get("text", "无对应文本") # 功能性备注: 获取传入的文本
            if hasattr(self, 'audio_text_display'):
                self.audio_text_display.configure(state="normal"); self.audio_text_display.delete("1.0", "end"); self.audio_text_display.insert("1.0", audio_text); self.audio_text_display.configure(state="disabled")

    def _update_image_label(self, label_widget, image_path, placeholder_text):
        """辅助函数：加载图片、创建缩略图并更新 CTkLabel"""
        # 功能性备注: 封装图片加载和标签更新逻辑
        thumbnail_image = None
        display_text = placeholder_text
        if image_path and os.path.exists(image_path):
            try:
                img = Image.open(image_path)
                img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
                if img.mode not in ['RGB', 'RGBA']: img = img.convert('RGBA')
                thumbnail_image = ctk.CTkImage(light_image=img, dark_image=img, size=(img.width, img.height))
                display_text = ""
            except Exception as e:
                logger.error(f"加载或创建缩略图失败: {image_path}, 错误: {e}")
                display_text = "加载失败"
                thumbnail_image = None
        # 功能性备注: 更新标签
        if label_widget and label_widget.winfo_exists(): # 逻辑备注: 增加控件存在性检查
            label_widget.configure(image=thumbnail_image, text=display_text)

    # --- 底部按钮回调 (保持不变) ---
    def _select_all(self):
        """选中所有当前可见的 Checkbox"""
        # 功能性备注: 实现全选功能 (只选当前过滤出的)
        current_filter = self.filter_var.get()
        for item_id, var in self.checkbox_vars.items():
            # 逻辑备注: 需要找到 item_id 对应的原始数据来判断 status
            original_item = next((item for item in self.original_items if item.get("id") == item_id), None)
            if original_item:
                item_status = original_item.get("status")
                if current_filter == "all" or item_status == current_filter:
                    var.set(True)
        # 逻辑备注: 全选后，默认显示最后一个项目的详情
        filtered_items = [item for item in self.original_items if current_filter == "all" or item.get("status") == current_filter]
        if filtered_items:
            last_item_data = filtered_items[-1]
            self.current_detail_item_data = last_item_data
            self._update_details_pane()

    def _deselect_all(self):
        """取消选中所有 Checkbox"""
        # 功能性备注: 实现取消全选功能
        for var in self.checkbox_vars.values():
            var.set(False)
        # 逻辑备注: 取消全选后，清空详情面板
        self._clear_details_pane()

    def _confirm_selection(self):
        """确认选择，收集选中的 ID 并关闭窗口"""
        # 功能性备注: 处理确认按钮点击事件
        self.selected_ids = [item_id for item_id, var in self.checkbox_vars.items() if var.get()]
        logger.info(f"弹窗选择已确认，选中 {len(self.selected_ids)} 项。")
        self.destroy()

    def _cancel(self):
        """取消选择并关闭窗口"""
        # 功能性备注: 处理取消按钮点击事件
        self.selected_ids = None
        logger.info("弹窗选择已取消。")
        self.destroy()

    def show(self):
        """显示弹窗并等待用户操作，返回选中的 ID 列表或 None"""
        # 功能性备注: 显示窗口并阻塞父窗口
        self.wait_window()
        return self.selected_ids