from __future__ import annotations

from pathlib import Path
from customer_project.remote_fs import RemotePath

from PySide6.QtCore import Signal, QObject
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QStackedWidget,
    QComboBox,
    QGroupBox,
    QListView,
    QScrollArea,
)

import ai
import qtawesome as qta
from builder.build_service import BuildService
from config.logging_setup import get_logger
from customer_project.project_manager import CustomerProjectManager
from executor.build_queue import BuildQueue
from review.review_service import ReviewService, ReviewDecision
from ui.review_panel import ReviewPanel
from ui.manual_panel import ManualPanel
from ui.queue_panel import QueuePanel
from ui.rule_panel import RulePanel


class TabLineEdit(QLineEdit):
    """QLineEdit 子类：拦截 Tab 键用于远程补全。

    Qt 的 Tab 焦点导航在 QApplication::notify() 层面就消费了事件，
    覆盖 event() 或 eventFilter 都无效。
    正确做法（Qt 官方文档）：覆盖 focusNextPrevChild() 返回 False，
    阻止 Qt 用 Tab 切焦点，然后 Tab 事件才能到达 keyPressEvent()。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tab_callback = None  # callback(text: str)

    def set_tab_callback(self, callback):
        """设置 Tab 回调：callback(text) 在按 Tab 时调用。"""
        self._tab_callback = callback

    def focusNextPrevChild(self, next_child: bool) -> bool:
        """阻止 Tab 键触发 Qt 焦点导航，让 Tab 事件传递到 keyPressEvent。"""
        return False

    def keyPressEvent(self, event):
        from PySide6.QtCore import Qt
        if event.key() == Qt.Key_Tab:
            text = self.text()
            if self._tab_callback and text:
                self._tab_callback(text)
            event.accept()
            return
        super().keyPressEvent(event)


class TerminalTextEdit(QTextEdit):
    """QTextEdit 子类：拦截 Tab 键用于远程补全。

    和 TabLineEdit 同理：focusNextPrevChild()→False 阻止焦点跳转，
    keyPressEvent() 拦截 Tab 触发补全回调。
    用户在 QTextEdit 里本地打字，字符不逐个发到 shell，
    所以 Tab 补全不能用 \\t 发到 shell（bash 不知道当前输入），
    而是用 exec_command 独立查询补全候选。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tab_callback = None  # callback()

    def set_tab_callback(self, callback):
        self._tab_callback = callback

    def focusNextPrevChild(self, next_child: bool) -> bool:
        return False

    def keyPressEvent(self, event):
        from PySide6.QtCore import Qt
        if event.key() == Qt.Key_Tab:
            if self._tab_callback:
                self._tab_callback()
            event.accept()
            return
        super().keyPressEvent(event)


class _LogEmitter(QObject):
    """线程安全的日志信号发射器。"""
    log_received = Signal(str)
    finished = Signal(str, int)  # status, exit_code
    completion_result = Signal(str)  # Tab 补全结果


class MainWindow(QMainWindow):
    # ---- 蓝灰毛玻璃主题配色 ----
    CLR_BG = "#e0e3ed"           # 主背景（蓝灰，肉眼可见）
    CLR_SIDEBAR = "#f5f6f9"      # 侧边栏（蓝灰白）
    CLR_CARD = "#ffffff"     # 卡片背景（半透明白）
    CLR_CARD_BORDER = "#e5e5e5"  # 卡片边框
    CLR_INPUT_BG = "#f8f8f8"     # 输入框背景
    CLR_INPUT_BORDER = "#dcdcdc"  # 输入框边框
    CLR_TEXT = "#1a1a1a"         # 主文字（深灰蓝）
    CLR_TEXT_DIM = "#888888"     # 次要文字
    CLR_ACCENT = "#333333"       # 主色调（柔和紫）
    CLR_ACCENT2 = "#555555"      # 辅助色（蓝）
    CLR_GREEN = "#34c759"        # 成功
    CLR_RED = "#ff3b30"          # 错误
    CLR_ORANGE = "#ff9500"       # 警告

    def __init__(
        self,
        project_manager: CustomerProjectManager,
        review_service: ReviewService,
        build_service: BuildService,
        build_queue: BuildQueue = None,
        ssh_client=None,
        base_path: str = "",
    ) -> None:
        super().__init__()
        self._project_manager = project_manager
        self._review_service = review_service
        self._build_service = build_service
        self._build_queue = build_queue or BuildQueue()
        if ssh_client:
            self._build_queue.set_ssh_client(ssh_client)
        self._logger = get_logger()
        self._current_analysis = None
        self._ssh_client = ssh_client
        self._base_path = base_path
        self._customer_dir_map: dict[str, str] = {}
        self._bg_path = ""  # 自定义背景图路径

        # 网盘上传服务
        from upload_service import UploadService
        self._upload_service = UploadService(ssh_client)
        self._wdav_user = ""
        self._wdav_pass = ""
        self._wdav_folder = ""
        self._load_webdav_settings()

        # 实时日志信号
        self._log_emitter = _LogEmitter(self)
        self._log_emitter.log_received.connect(self._on_build_log_append)
        self._log_emitter.finished.connect(self._on_build_finished)
        self._log_emitter.completion_result.connect(self._on_completion_result)

        # 持久化 shell 会话
        self._shell_channel = None
        self._shell_running = False
        if self._ssh_client:
            self._init_shell()

        self._review_service.set_callback(self._on_review_requested)

        self.setWindowTitle("")
        self.resize(1200, 800)
        # macOS: 全尺寸内容视图 + 隐藏标题（保留红黄绿按钮，类似 WorkBuddy）
        from PySide6.QtCore import Qt
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinMaxButtonsHint
            | Qt.WindowType.WindowCloseButtonHint
        )




        self.setStyleSheet(f"""
            QMainWindow {{ background: {self.CLR_BG}; background-image: url(static/bg_frosted.png); background-position: center; }}
            QWidget {{ color: {self.CLR_TEXT}; font-size: 12px; background: transparent; }}
            QLabel {{ color: {self.CLR_TEXT}; background: transparent; }}
            QGroupBox {{ color: {self.CLR_TEXT}; background: transparent; }}
            QGroupBox::title {{ color: {self.CLR_TEXT}; }}
            QTabWidget::pane {{ border: 1px solid #d5d8e0; background: {self.CLR_BG};
                                border-radius: 10px; }}
            QTabBar::tab {{ background: #eceef2; color: {self.CLR_TEXT_DIM};
                            border: 1px solid #d5d8e0; padding: 8px 16px;
                            border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 2px; }}
            QTabBar::tab:selected {{ background: #ffffff; color: {self.CLR_ACCENT};
                                     border-bottom-color: #ffffff; font-weight: bold; }}
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{ background: transparent; width: 6px; }}
            QScrollBar::handle:vertical {{ background: #dcdcdc; border-radius: 3px; min-height: 30px; }}
            QScrollBar::handle:vertical:hover {{ background: #1a1a1a; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QCheckBox {{ color: {self.CLR_TEXT}; spacing: 6px; background: transparent; }}
            QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px;
                                    border: 1.5px solid #dcdcdc; background: #ffffff; }}
            QCheckBox::indicator:checked {{ background: {self.CLR_ACCENT}; border-color: {self.CLR_ACCENT}; }}
            QSpinBox {{ background: #ffffff; color: {self.CLR_TEXT};
                        border: 1px solid #d5d8e0; border-radius: 6px; padding: 4px; }}
            QSpinBox:focus {{ border-color: {self.CLR_ACCENT}; }}
        """)

        central = QWidget(self)
        central.setStyleSheet(f"background: {self.CLR_BG};")

        self.setCentralWidget(central)
        # macOS: 标题栏透明 + 全尺寸内容
        from PySide6.QtCore import QTimer
        # macOS 标题栏透明在 showEvent 中处理
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ========== 左侧导航栏 ==========
        sidebar = QWidget()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet(f"background: {self.CLR_SIDEBAR};")
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(16, 28, 16, 24)
        sb_layout.setSpacing(6)


        # Logo / 标题 + 版本号（去掉齿轮图标）
        from config.version import __version__
        logo_text = QLabel("软件输出自动化")
        logo_text.setStyleSheet("font-size: 14px; color: #999999; background: transparent;")
        ver_lbl = QLabel(f"v{__version__}")
        ver_lbl.setStyleSheet("font-size: 11px; color: #bbbbbb; background: transparent;")
        logo_row = QHBoxLayout()
        logo_row.setSpacing(6)
        logo_row.addWidget(logo_text)
        logo_row.addWidget(ver_lbl)
        logo_row.addStretch()
        sb_layout.addLayout(logo_row)
        sb_layout.addSpacing(16)

        # 导航按钮
        self._nav_btns: list[QPushButton] = []
        nav_items = [
            ("  自动模式", 0),
            ("  手动模式", 1),
            ("  审核面板", 2),
            ("  执行结果", 3),
            ("  编译构建", 4),
            ("  编译队列", 5),
            ("  规则管理", 6),
            ("  网盘上传", 7),
        ]
        nav_icons = ["fa5s.robot", "fa5s.wrench", "fa5s.clipboard-check", "fa5s.chart-bar", "fa5s.hammer", "fa5s.list", "fa5s.cogs", "fa5s.cloud-upload-alt"]
        for (text, idx), icon_name in zip(nav_items, nav_icons):
            btn = QPushButton(text)
            btn.setIcon(qta.icon(icon_name, color="#888888"))
            btn.setCursor(self.cursor())
            btn.setStyleSheet(self._nav_btn_style(False))
            btn.clicked.connect(lambda checked, i=idx: self._switch_mode(i))
            sb_layout.addWidget(btn)
            self._nav_btns.append(btn)


        sb_layout.addStretch()

        # ========== 右侧主内容区 ==========
        content_widget = QWidget()
        content_widget.setStyleSheet(f"background: {self.CLR_BG};")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(24, 12, 24, 20)
        content_layout.setSpacing(8)

        # ---- 目录设置卡片（重置按钮内嵌在标题行）----
        self._dir_card = self._make_card("目录设置")
        dir_card = self._dir_card
        dir_layout = dir_card.layout()

        # 重置按钮（卡片标题右侧）
        reset_btn = QPushButton("  重置")
        reset_btn.setIcon(qta.icon("fa5s.undo", color="#888888"))
        reset_btn.setStyleSheet(
            f"QPushButton {{ background-color: transparent; color: {self.CLR_TEXT_DIM}; "
            f"border: 1px solid {self.CLR_CARD_BORDER}; border-radius: 8px; padding: 6px 12px; font-size: 11px; }}"
            f"QPushButton:hover {{ background-color: rgba(0,0,0,0.06); }}"
        )
        reset_btn.clicked.connect(self._reset_all)
        # 把重置按钮放到卡片标题旁边
        title_row = QHBoxLayout()
        title_row.addStretch()
        title_row.addWidget(reset_btn)
        dir_layout.insertLayout(0, title_row)

        # 第一行: 项目 | 板型 | 区域 | 客户
        row1 = QHBoxLayout()
        row1.setSpacing(12)
        for label_text, attr_name, signal_name in [
            ("项目", "_project_combo", "_on_project_changed"),
            ("板型", "_board_combo", "_on_board_changed"),
            ("区域", "_region_combo", "_on_region_changed"),
            ("客户", "_customer_combo", "_on_customer_changed"),
        ]:
            col = QVBoxLayout()
            col.setSpacing(4)
            lbl = QLabel(label_text)
            lbl.setStyleSheet(f"font-size: 11px; background: transparent; color: {self.CLR_TEXT_DIM};")
            col.addWidget(lbl)
            combo = QComboBox()
            combo.setMinimumWidth(120)
            combo.setStyleSheet(self._combo_style())
            self._fix_combo(combo)
            combo.currentTextChanged.connect(getattr(self, signal_name))
            col.addWidget(combo)
            setattr(self, attr_name, combo)
            row1.addLayout(col)
        dir_layout.addLayout(row1)

        # 第二行: 客户目录
        row2 = QHBoxLayout()
        row2.setSpacing(12)
        lbl5 = QLabel("客户目录")
        lbl5.setStyleSheet(f"font-size: 11px; background: transparent; color: {self.CLR_TEXT_DIM};")
        row2.addWidget(lbl5)
        self._dir_combo = QComboBox()
        self._dir_combo.setStyleSheet(self._combo_style())
        self._fix_combo(self._dir_combo)
        self._dir_combo.currentTextChanged.connect(self._on_dir_changed)
        row2.addWidget(self._dir_combo, 1)
        dir_layout.addLayout(row2)

        # 第三行: 目标目录 + 复制按钮
        row3 = QHBoxLayout()
        row3.setSpacing(12)
        lbl7 = QLabel("目标目录")
        lbl7.setStyleSheet(f"font-size: 11px; background: transparent; color: {self.CLR_TEXT_DIM};")
        row3.addWidget(lbl7)
        self._target_dir_input = QLineEdit()
        self._target_dir_input.setPlaceholderText("留空直接修改源目录，填写则复制后再修改")
        self._target_dir_input.setStyleSheet(self._input_style())
        self._target_dir_input.textChanged.connect(self._on_target_dir_changed)
        row3.addWidget(self._target_dir_input, 1)
        copy_btn = QPushButton("  复制客户目录名")
        copy_btn.setIcon(qta.icon("fa5s.copy", color="#888888"))
        copy_btn.setStyleSheet(self._small_btn_style())
        copy_btn.clicked.connect(self._copy_source_name)
        row3.addWidget(copy_btn)
        dir_layout.addLayout(row3)

        # 第四行: 搜索
        row4 = QHBoxLayout()
        row4.setSpacing(12)
        lbl8 = QLabel("  搜索")
        lbl8.setStyleSheet(f"font-size: 11px; background: transparent; color: {self.CLR_TEXT_DIM};")
        row4.addWidget(lbl8)
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("输入 zip 文件名或客户目录名关键词…")
        self._search_input.setStyleSheet(self._input_style())
        self._search_input.returnPressed.connect(self._on_search)
        row4.addWidget(self._search_input, 1)
        search_btn = QPushButton("查找")
        search_btn.setStyleSheet(self._accent_btn_style())
        search_btn.clicked.connect(self._on_search)
        row4.addWidget(search_btn)
        clear_btn = QPushButton("清除")
        clear_btn.setStyleSheet(self._small_btn_style())
        clear_btn.clicked.connect(self._on_search_clear)
        row4.addWidget(clear_btn)
        dir_layout.addLayout(row4)

        content_layout.addWidget(dir_card)

        # ---- 主内容区（堆叠页面）----
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background: transparent;")

        # 包装函数：给页面加滚动条
        def _scroll_wrap(widget: QWidget) -> QScrollArea:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
            scroll.setWidget(widget)
            return scroll

        # 页面0: 自动模式
        self._ai_page = self._build_ai_page()
        self._stack.addWidget(_scroll_wrap(self._ai_page))

        # 页面1: 手动模式（已有内部滚动）
        self._manual_page = ManualPanel()
        self._manual_page.execute_requested.connect(self._on_manual_execute)
        self._stack.addWidget(self._manual_page)

        # 页面2: 审核
        self._review_page = QWidget()
        self._stack.addWidget(_scroll_wrap(self._review_page))
        self._review_page_layout = QVBoxLayout(self._review_page)

        # 页面3: 结果
        self._result_page = self._build_result_page()
        self._stack.addWidget(_scroll_wrap(self._result_page))

        # 页面4: 编译构建（终端区不需要外层滚动）
        self._build_page = self._build_build_page()
        self._stack.addWidget(self._build_page)

        # 页面5: 编译队列（已有内部滚动）
        self._queue_page = QueuePanel(self._build_queue)
        self._queue_page.build_requested.connect(self._on_queue_build_requested)
        self._queue_page.build_all_requested.connect(self._on_build_all)
        self._stack.addWidget(self._queue_page)

        # 页面6: 规则管理（已有内部滚动）
        self._rule_page = RulePanel()
        self._stack.addWidget(self._rule_page)

        # 页面7: 网盘上传
        self._upload_page = self._build_upload_page()
        self._stack.addWidget(_scroll_wrap(self._upload_page))

        self._stack.setCurrentIndex(0)
        content_layout.addWidget(self._stack, 1)



        root.addWidget(sidebar)
        root.addWidget(content_widget, 1)

        # 设置默认导航高亮
        self._nav_btns[0].setStyleSheet(self._nav_btn_style(True))
        self._update_nav_icons(0)


        # 窗口拖拽支持
        self._drag_pos = None

        # 初始化目录
        self._refresh_projects()

    # ========== 样式工具 ==========

    def _nav_btn_style(self, active: bool) -> str:
        if active:
            return (
                f"QPushButton {{ background-color: #e8e8e8; color: {self.CLR_TEXT}; "
                f"border: none; border-radius: 10px; padding: 11px 16px; font-size: 13px; "
                f"text-align: left; font-weight: bold; }}"
                f"QPushButton:hover {{ background-color: #e0e0e0; }}"
                f"QPushButton:pressed {{ background-color: #d8d8d8; }}"
            )
        return (
            f"QPushButton {{ background-color: transparent; color: {self.CLR_TEXT_DIM}; "
            f"border: none; border-radius: 10px; padding: 11px 16px; font-size: 13px; text-align: left; }}"
            f"QPushButton:hover {{ background-color: #f0f0f0; color: {self.CLR_TEXT}; }}"
            f"QPushButton:pressed {{ background-color: #e0e0e0; }}"
        )

    def _update_nav_icons(self, active_idx: int):
        nav_icon_names = ["fa5s.robot", "fa5s.wrench", "fa5s.clipboard-check", "fa5s.chart-bar", "fa5s.hammer", "fa5s.list", "fa5s.cogs", "fa5s.cloud-upload-alt"]
        for i, btn in enumerate(self._nav_btns):
            color = "#1a1a1a" if i == active_idx else "#888888"
            btn.setIcon(qta.icon(nav_icon_names[i], color=color))

    @staticmethod
    def _fix_combo(combo: QComboBox):
        """强制 QComboBox 使用 Qt 渲染下拉列表（macOS 原生不支持样式表）。"""
        view = QListView()
        view.setStyleSheet(
            "QListView { background: #ffffff; border: 1px solid #e5e5e5; outline: none; }"
            "QListView::item { padding: 2px 8px; }"
            "QListView::item:hover { background: #f0f0f0; }"
            "QListView::item:selected { background: #e0e0e0; color: #1a1a1a; }"
        )
        view.setUniformItemSizes(True)
        combo.setView(view)
        combo.setMaxVisibleItems(15)

    def _combo_style(self) -> str:
        return (
            f"QComboBox {{ background-color: transparent; color: {self.CLR_TEXT}; "
            f"border: 1px solid #dcdcdc; border-radius: 6px; "
            f"padding: 6px 10px; font-size: 12px; }}"
            f"QComboBox:hover {{ background-color: #f0f0f0; border-color: #aaaaaa; }}"
            f"QComboBox:focus {{ border-color: #999999; background-color: #f5f5f5; }}"
            f"QComboBox::drop-down {{ border: none; width: 20px; }}"
        )

    def _input_style(self) -> str:
        return (
            f"QLineEdit {{ background-color: {"transparent"}; color: {self.CLR_TEXT}; "
            f"border: 1px solid {self.CLR_INPUT_BORDER}; border-radius: 6px; "
            f"padding: 6px 10px; font-size: 12px; }}"
            f"QLineEdit:focus {{ border-color: {self.CLR_ACCENT}; }}"
        )

    def _text_edit_style(self) -> str:
        return (
            f"QTextEdit {{ background-color: {"transparent"}; color: {self.CLR_TEXT}; "
            f"border: 1px solid {self.CLR_INPUT_BORDER}; border-radius: 8px; "
            f"padding: 8px; font-family: Menlo,Consolas,monospace; font-size: 12px; }}"
        )

    def _accent_btn_style(self) -> str:
        return (
            f"QPushButton {{ background-color: #e0e0e0; color: {self.CLR_TEXT}; "
            f"border: none; border-radius: 8px; padding: 8px 18px; font-size: 12px; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: #d5d5d5; }}"
            f"QPushButton:pressed {{ background-color: #cccccc; }}"
            f"QPushButton:disabled {{ background: #f0f0f0; color: #aaa; }}"
        )

    def _small_btn_style(self) -> str:
        return (
            f"QPushButton {{ background-color: transparent; color: {self.CLR_TEXT_DIM}; "
            f"border: 1px solid {self.CLR_INPUT_BORDER}; border-radius: 6px; "
            f"padding: 5px 12px; font-size: 11px; }}"
            f"QPushButton:hover {{ background-color: #f0f0f0; border-color: #d0d0d0; color: {self.CLR_TEXT}; }}"
            f"QPushButton:pressed {{ background-color: #e0e0e0; }}"
        )

        lbl = card.findChild(QLabel, "stat_value")
        if lbl:
            lbl.setText(value)

    def _make_card(self, title: str) -> QGroupBox:
        card = QGroupBox(title)
        card.setStyleSheet(
            f"QGroupBox {{ background-color: {self.CLR_CARD}; border: 1px solid {self.CLR_CARD_BORDER}; "
            f"border-radius: 12px; padding: 16px 12px 8px 12px; margin-top: 16px; font-size: 13px; "
            f"font-weight: bold; color: {self.CLR_TEXT}; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 16px; padding: 0 8px; }}"
        )
        layout = QVBoxLayout(card)
        layout.setSpacing(10)
        return card

    def _try_mac_style(self):
        """设置 macOS 无标题栏 + 全尺寸内容视图（类似 WorkBuddy）。"""
        import platform
        if platform.system() != "Darwin":
            return
        if getattr(self, '_mac_styled', False):
            return
        try:
            import ctypes, os

            lib_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                    "static", "libmac_titlebar.dylib")
            lib = ctypes.cdll.LoadLibrary(lib_path)

            # 获取 NSWindow 指针: winId() -> NSView -> .window -> NSWindow
            from ui.mac_blur import _msg
            ns_view = ctypes.c_void_p(int(self.winId()))
            ns_win = _msg(ns_view, "window")
            if not ns_win:
                return

            # fix_titlebar(ns_window_ptr) — 透明标题栏 + 全尺寸内容 + 隐藏标题
            lib.fix_titlebar.argtypes = [ctypes.c_void_p]
            lib.fix_titlebar(ns_win)

            self._mac_styled = True
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._logger.error("mac_style 失败: %s", e)

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, '_mac_styled', False):
            # 立即调用，不再延迟——fullSizeContentView 需尽早设置
            self._try_mac_style()

    # ========== 窗口拖拽 ==========
    def mousePressEvent(self, event):
        from PySide6.QtCore import Qt
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        from PySide6.QtCore import Qt
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    # ========== 级联目录 ==========


    def _refresh_projects(self) -> None:
        """第一级：加载项目列表。"""
        self._project_combo.blockSignals(True)
        self._project_combo.clear()

        if self._ssh_client:
            try:
                stdin, stdout, stderr = self._ssh_client.exec_command(
                    f'ls -d {self._base_path}/*/', timeout=10
                )
                projects = []
                for d in stdout.read().decode().strip().split('\n'):
                    d = d.strip().rstrip('/')
                    if d:
                        name = Path(d).name
                        if not name.startswith('.'):
                            projects.append(name)
                self._project_combo.addItems(sorted(projects))
            except Exception as e:
                self._logger.error("获取项目列表失败: %s", e)
        else:
            # 本地模式
            dirs = self._project_manager.list_customer_dirs()
            self._project_combo.addItems([d.name for d in dirs if not d.name.endswith("_AUTO")])

        self._project_combo.blockSignals(False)
        if self._project_combo.count() > 0:
            self._on_project_changed(self._project_combo.currentText())

    def _on_project_changed(self, project_name: str) -> None:
        """第二级：扫描板型目录。"""
        self._board_combo.blockSignals(True)
        self._board_combo.clear()
        self._region_combo.clear()
        self._dir_combo.clear()

        if not project_name:
            self._board_combo.blockSignals(False)
            return

        if self._ssh_client:
            cus_config_path = f"{self._base_path}/{project_name}/code/cultraview/cusConfig"
            try:
                stdin, stdout, stderr = self._ssh_client.exec_command(
                    f'ls -d {cus_config_path}/*/', timeout=10
                )
                boards = []
                for d in stdout.read().decode().strip().split('\n'):
                    d = d.strip().rstrip('/')
                    if d:
                        name = Path(d).name
                        if not name.startswith('.') and not name.endswith('.sh') and not name.endswith('.csv') and not name.endswith('.mk'):
                            boards.append(name)
                self._board_combo.addItems(sorted(boards))
            except Exception as e:
                self._logger.error("获取板型列表失败: %s", e)

        self._board_combo.blockSignals(False)
        if self._board_combo.count() > 0:
            self._on_board_changed(self._board_combo.currentText())

    def _on_board_changed(self, board_name: str) -> None:
        """第三级：扫描区域目录。"""
        self._region_combo.blockSignals(True)
        self._region_combo.clear()
        self._dir_combo.clear()

        if not board_name:
            self._region_combo.blockSignals(False)
            return

        project_name = self._project_combo.currentText()
        if self._ssh_client:
            board_path = f"{self._base_path}/{project_name}/code/cultraview/cusConfig/{board_name}"
            try:
                stdin, stdout, stderr = self._ssh_client.exec_command(
                    f'ls -d {board_path}/*/', timeout=10
                )
                regions = []
                for d in stdout.read().decode().strip().split('\n'):
                    d = d.strip().rstrip('/')
                    if d:
                        name = Path(d).name
                        if not name.startswith('.'):
                            regions.append(name)
                self._region_combo.addItems(sorted(regions))
            except Exception as e:
                self._logger.error("获取区域列表失败: %s", e)

        self._region_combo.blockSignals(False)
        if self._region_combo.count() > 0:
            self._on_region_changed(self._region_combo.currentText())

    def _on_region_changed(self, region_name: str) -> None:
        """第四级：加载客户（公司名）列表。"""
        self._customer_combo.blockSignals(True)
        self._customer_combo.clear()
        self._dir_combo.clear()
        self._customer_dir_map.clear()

        if not region_name:
            self._customer_combo.blockSignals(False)
            return

        project_name = self._project_combo.currentText()
        board_name = self._board_combo.currentText()

        if self._ssh_client:
            region_path = f"{self._base_path}/{project_name}/code/cultraview/cusConfig/{board_name}/{region_name}"
            try:
                stdin, stdout, stderr = self._ssh_client.exec_command(
                    f'ls -d {region_path}/*/', timeout=10
                )
                customers = []
                for d in stdout.read().decode().strip().split('\n'):
                    d = d.strip().rstrip('/')
                    if d:
                        name = Path(d).name
                        if not name.startswith('.'):
                            customers.append(name)
                self._customer_combo.addItems(sorted(customers))
            except Exception as e:
                self._logger.error("获取客户列表失败: %s", e)

        self._customer_combo.blockSignals(False)
        if self._customer_combo.count() > 0:
            self._on_customer_changed(self._customer_combo.currentText())

    def _on_customer_changed(self, customer_name: str) -> None:
        """第五级：扫描客户目录（包含 build_config.txt 的目录）。"""
        self._dir_combo.blockSignals(True)
        self._dir_combo.clear()
        self._customer_dir_map.clear()

        if not customer_name:
            self._dir_combo.blockSignals(False)
            return

        project_name = self._project_combo.currentText()
        board_name = self._board_combo.currentText()
        region_name = self._region_combo.currentText()

        if self._ssh_client:
            customer_path = f"{self._base_path}/{project_name}/code/cultraview/cusConfig/{board_name}/{region_name}/{customer_name}"
            try:
                stdin, stdout, stderr = self._ssh_client.exec_command(
                    f'find {customer_path} -name "build_config.txt" -not -path "*/out/*" 2>/dev/null',
                    timeout=15
                )
                dirs = []
                for line in stdout.read().decode().strip().split('\n'):
                    line = line.strip()
                    if line:
                        customer_dir = str(Path(line).parent)
                        name = Path(customer_dir).name
                        dirs.append((name, customer_dir))

                seen = set()
                unique_dirs = []
                for name, full_path in sorted(dirs):
                    if name not in seen:
                        seen.add(name)
                        unique_dirs.append((name, full_path))
                        self._customer_dir_map[name] = full_path

                self._dir_combo.addItems([name for name, _ in unique_dirs])
            except Exception as e:
                self._logger.error("扫描客户目录失败: %s", e)

        self._dir_combo.blockSignals(False)
        if self._dir_combo.count() > 0:
            self._on_dir_changed(self._dir_combo.currentText())

    # ========== 搜索 ==========

    def _on_search(self) -> None:
        """根据 zip 文件名或关键词搜索客户目录。"""
        keyword = self._search_input.text().strip()
        if not keyword:
            return

        project_name = self._project_combo.currentText()
        if not project_name or not self._ssh_client:
            self.log_edit.append("[搜索] 请先登录并选择项目")
            return

        # 从 zip 文件名提取客户目录名
        dir_name = self._extract_dir_from_zip(keyword)

        self.log_edit.append(f"[搜索] 关键词: {keyword}")
        if dir_name and dir_name != keyword:
            self.log_edit.append(f"[搜索] 提取的目录名: {dir_name}")

        # 在服务器上搜索
        search_keyword = dir_name if dir_name else keyword
        base_search = f"{self._base_path}/{project_name}/code/cultraview/cusConfig"

        try:
            stdin, stdout, stderr = self._ssh_client.exec_command(
                f'find {base_search} -name "build_config.txt" -not -path "*/out/*" 2>/dev/null '
                f'| xargs grep -l "" 2>/dev/null '
                f'| while read f; do dir=$(dirname "$f"); name=$(basename "$dir"); '
                f'if echo "$name" | grep -qi "{search_keyword}"; then echo "$dir"; fi; done',
                timeout=30
            )
            results = stdout.read().decode().strip().split('\n')
            results = [r.strip() for r in results if r.strip()]

            if not results:
                self.log_edit.append("[搜索] 未找到匹配的客户目录")
                return

            # 优先精确匹配（basename 完全等于搜索关键词）
            exact = [r for r in results if Path(r).name == search_keyword]
            if exact:
                chosen = exact[0]
                self.log_edit.append(f"[搜索] 精确匹配: {Path(chosen).name}")
            else:
                self.log_edit.append(f"[搜索] 找到 {len(results)} 个模糊匹配:")
                for r in results[:10]:
                    self.log_edit.append(f"  - {Path(r).name}")
                if len(results) > 10:
                    self.log_edit.append(f"  ... 共 {len(results)} 个")
                chosen = results[0]
                self.log_edit.append(f"[搜索] 自动选中第一个: {Path(chosen).name}")

            # 解析路径，同步更新级联下拉框
            # 路径格式: .../cusConfig/{board}/{region}/{customer}/{dir_name}
            chosen_name = Path(chosen).name
            self._customer_dir_map[chosen_name] = chosen
            parts = Path(chosen).parts
            try:
                cus_idx = parts.index("cusConfig")
                board_val = parts[cus_idx + 1]
                region_val = parts[cus_idx + 2]
                customer_val = parts[cus_idx + 3]
                # 依次设置上级下拉框（触发级联会清空下级，所以要从上往下）
                b_idx = self._board_combo.findText(board_val)
                if b_idx >= 0:
                    self._board_combo.setCurrentIndex(b_idx)
                r_idx = self._region_combo.findText(region_val)
                if r_idx >= 0:
                    self._region_combo.setCurrentIndex(r_idx)
                c_idx = self._customer_combo.findText(customer_val)
                if c_idx >= 0:
                    self._customer_combo.setCurrentIndex(c_idx)
            except (ValueError, IndexError):
                pass  # 路径格式不符，只更新目录下拉框
            # 最后设置目录
            d_idx = self._dir_combo.findText(chosen_name)
            if d_idx >= 0:
                self._dir_combo.setCurrentIndex(d_idx)
            else:
                self._dir_combo.addItem(chosen_name)
                self._dir_combo.setCurrentText(chosen_name)

        except Exception as e:
            self.log_edit.append(f"[搜索] 搜索失败: {e}")

    def _on_search_clear(self) -> None:
        """清除搜索框并重置搜索状态。"""
        self._search_input.clear()
        self.log_edit.append("[搜索] 已清除")

    def _extract_dir_from_zip(self, zip_name: str) -> str:
        """从 zip 文件名提取客户目录名（DIR_ORDER）。

        文件名格式: {board}{version}_{tvsystem}_{DIR_ORDER}{pwminfo}_MO{order}_{emmc}_{buildtime}.zip
        pwminfo = _NNNmA_NNNHW (背光信息)
        例如: CV560-C55_V1_pa_WOPAI_CV560_C55_woolpad_500mA_TWO_20260604_500mA_900HW_MO80000001_8G_20260604195851.zip
        DIR_ORDER = WOPAI_CV560_C55_woolpad_500mA_TWO_20260604
        """
        import re

        # 去掉 .zip 后缀
        name = zip_name.replace('.zip', '').replace('.ZIP', '')

        # 找到 _MO 的位置（订单号标记）
        mo_match = re.search(r'_MO\d+', name)
        if not mo_match:
            return name

        # 取 _MO 之前的部分，再用正则去掉末尾 pwminfo (_NNNmA_NNNHW)
        before_mo = name[:mo_match.start()]
        before_pwminfo = re.sub(r'_\d+mA_\d+[A-Z]+$', '', before_mo)

        # 从前面去掉 board、version、tvsystem
        parts = before_pwminfo.split('_')

        i = 0
        # 跳过 board（含连字符，如 CV560-C55）
        if i < len(parts) and '-' in parts[i]:
            i += 1
        # 跳过 version（如 V1, V2）
        if i < len(parts) and re.match(r'^V\d+$', parts[i]):
            i += 1
        # 跳过 tvsystem（如 pa, isdb）
        if i < len(parts) and len(parts[i]) <= 6 and parts[i].isalpha():
            i += 1

        remaining = parts[i:]
        return '_'.join(remaining) if remaining else name

    # ========== 通用 ==========

    def _on_dir_changed(self, text: str) -> None:
        if text:
            source = self._get_source_path()
            if hasattr(self, "_build_cmd_input"):
                self._build_cmd_input.setText(self._build_default_compile_command())
            # 异步加载远程配置值到手动面板（含 CountryList 过滤）
            if self._ssh_client:
                self._manual_page.load_values(self._ssh_client, str(source))

    def _refresh_country_list(self) -> None:
        """从远程 ctv_data.xml 读取 CountryList，过滤手动面板国家选项。"""
        if not self._ssh_client:
            return
        source = self._get_source_path()
        xml_rel = "overlay/cultraview/common/apps/CtvMiddleware/CultraviewTvService/res/raw/ctv_data.xml"
        try:
            import shlex
            cmd = f"cat {shlex.quote(str(source) + '/' + xml_rel)} 2>/dev/null"
            stdin, stdout, stderr = self._ssh_client.exec_command(cmd, timeout=10)
            content = stdout.read().decode("utf-8", errors="replace")
            if not content:
                return
            import re
            m = re.search(r'name="CountryList"\s+item="([^"]+)"', content)
            if m:
                codes = [c.strip() for c in m.group(1).split(",")]
                self._manual_page.filter_country_list(codes)
                self._logger.info("CountryList 已过滤: %d 个国家", len(codes))
        except Exception as e:
            self._logger.warning("读取 CountryList 失败: %s", e)

    def _on_target_dir_changed(self, _text: str) -> None:
        """目标目录输入框变化时，自动刷新编译命令。"""
        if hasattr(self, "_build_cmd_input"):
            self._build_cmd_input.setText(self._build_default_compile_command())

    def _get_source_path(self):
        name = self._dir_combo.currentText()
        if name in self._customer_dir_map:
            return RemotePath(self._ssh_client, self._customer_dir_map[name])
        if self._base_path:
            return RemotePath(self._ssh_client, f"{self._base_path}/{name}")
        return RemotePath(self._ssh_client, f"{self._project_manager.root}/{name}")

    def _get_target_path(self):
        source = self._get_source_path()
        target_text = self._target_dir_input.text().strip()
        if not target_text:
            return source
        if target_text.startswith("/"):
            return RemotePath(self._ssh_client, target_text)
        return source.parent / target_text

    def _copy_source_name(self) -> None:
        name = self._dir_combo.currentText()
        if name:
            self._target_dir_input.setText(name)

    @staticmethod
    def _collect_ensure_status(registry) -> list[str]:
        """收集 ensure 类规则的执行状态（如 ctv_data_ensure）。"""
        from rules.ctv_data_rule import CtvDataRule
        status = []
        for rule in registry.rules:
            if isinstance(rule, CtvDataRule) and hasattr(rule, "last_action") and rule.last_action:
                action = rule.last_action
                if action == "added":
                    status.append(f"  ✅ {rule.name}：已添加到 customized 区域（值={rule.value}）")
                elif action == "replaced":
                    status.append(f"  🔄 {rule.name}：值已更新为 {rule.value}")
                elif action == "skipped_exists":
                    status.append(f"  ⏭️  {rule.name}：已存在，跳过")
                elif action == "skipped_file_missing":
                    status.append(f"  ⚠️  {rule.name}：ctv_data.xml 文件不存在，跳过")
                elif action == "skipped_insert_failed":
                    status.append(f"  ❌ {rule.name}：插入失败")
        return status

    # ========== 模式切换 ==========

    def _switch_mode(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        # 规则管理和编译队列页面隐藏目录设置
        self._dir_card.setVisible(index not in (4, 5, 6, 7))
        for i, btn in enumerate(self._nav_btns):
            btn.setStyleSheet(self._nav_btn_style(i == index))
        self._update_nav_icons(index)

    def _reset_all(self) -> None:
        if hasattr(self, 'requirement_edit'):
            self.requirement_edit.clear()
        self._target_dir_input.clear()
        if hasattr(self, 'log_edit'):
            self.log_edit.clear()
        if hasattr(self._manual_page, '_preview_edit'):
            self._manual_page._preview_edit.clear()
        self._review_service._decision = None
        self._review_service._current_analysis = None
        self._current_analysis = None
        if hasattr(self, 'run_button'):
            self.run_button.setEnabled(True)
            self.run_button.setText("  自动分析并提交审核")
        self._switch_mode(0)
        self._logger.info("已重置所有状态")

    # ========== 自动模式页面 ==========

    def _build_ai_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # 需求输入卡片
        req_card = self._make_card("客户需求")
        req_layout = req_card.layout()

        req_header = QHBoxLayout()
        req_header.addStretch()
        import_btn = QPushButton("  导入文件")
        import_btn.setIcon(qta.icon("fa5s.folder-open", color="#888888"))
        import_btn.setStyleSheet(self._small_btn_style())
        import_btn.clicked.connect(self._import_requirement_file)
        req_header.addWidget(import_btn)
        clear_btn = QPushButton("🗑 清空")
        clear_btn.setStyleSheet(self._small_btn_style())
        clear_btn.clicked.connect(lambda: self.requirement_edit.clear())
        req_header.addWidget(clear_btn)
        req_layout.addLayout(req_header)

        self.requirement_edit = QTextEdit()
        self.requirement_edit.setPlaceholderText(
            "例如：修改电流为 550，打开杜比，关闭预装 ESharePlus"
        )
        self.requirement_edit.setStyleSheet(self._text_edit_style())
        self.requirement_edit.setMinimumHeight(120)
        req_layout.addWidget(self.requirement_edit)

        self.run_button = QPushButton("  自动分析并提交审核")
        self.run_button.setIcon(qta.icon("fa5s.rocket", color="#1a1a1a"))
        self.run_button.setStyleSheet(self._accent_btn_style())
        self.run_button.clicked.connect(self._on_analyze)
        req_layout.addWidget(self.run_button)

        layout.addWidget(req_card)

        # 日志卡片
        log_card = self._make_card("日志")
        log_layout = log_card.layout()
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setStyleSheet(self._text_edit_style())
        self.log_edit.setMaximumHeight(150)
        log_layout.addWidget(self.log_edit)
        layout.addWidget(log_card)

        return page

    # ========== 导入文件 ==========

    def _import_bg_image(self) -> None:
        """导入自定义背景图片。"""
        from PySide6.QtWidgets import QFileDialog
        from PySide6.QtGui import QPixmap, QPalette, QBrush
        from PySide6.QtCore import Qt
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择背景图片", str(Path.home() / "Desktop"),
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.webp);;所有文件 (*)"
        )
        if not file_path:
            return
        abs_path = str(Path(file_path).resolve())
        pixmap = QPixmap(abs_path)
        if pixmap.isNull():
            return
        pal = self.palette()
        pal.setBrush(QPalette.ColorRole.Window, QBrush(pixmap.scaled(
            self.size(), Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )))
        self.setPalette(pal)
        self._bg_path = abs_path
        if hasattr(self, 'log_edit'):
            self.log_edit.append(f"[背景] 已更换: {Path(file_path).name}")

    def _import_requirement_file(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        desktop = str(Path.home() / "Desktop")
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择需求文件", desktop,
            "所有支持的文件 (*.txt *.md *.log *.csv *.docx);;Word 文档 (*.docx);;文本文件 (*.txt *.md *.log *.csv);;所有文件 (*)"
        )
        if not file_path:
            return
        try:
            text = self._read_file_content(file_path)
            existing = self.requirement_edit.toPlainText().strip()
            if existing:
                self.requirement_edit.setPlainText(existing + "\n" + text)
            else:
                self.requirement_edit.setPlainText(text)
            self.log_edit.append(f"[导入] 已追加文件: {Path(file_path).name} ({len(text)} 字符)")
        except Exception as e:
            self.log_edit.append(f"[错误] 读取文件失败: {e}")

    def _read_file_content(self, file_path: str) -> str:
        path = Path(file_path)
        suffix = path.suffix.lower()
        if suffix == ".docx":
            import docx
            doc = docx.Document(file_path)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n".join(paragraphs)
        else:
            return path.read_text(encoding="utf-8")

    # ========== 结果页面 ==========

    def _build_result_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        result_card = self._make_card("执行结果")
        rc_layout = result_card.layout()

        self._result_title = QLabel()
        self._result_title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {self.CLR_TEXT};")
        rc_layout.addWidget(self._result_title)

        self._result_detail = QTextEdit()
        self._result_detail.setReadOnly(True)
        self._result_detail.setStyleSheet(self._text_edit_style())
        rc_layout.addWidget(self._result_detail, 1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._enqueue_btn = QPushButton("＋ 加入编译队列")
        self._enqueue_btn.setStyleSheet(
            f"QPushButton {{ background: {self.CLR_ACCENT}; color: white; border: none;"
            " border-radius: 6px; padding: 6px 18px; font-size: 13px; min-width: 80px; }"
            "QPushButton:hover { background: #3a8ee6; }"
        )
        self._enqueue_btn.clicked.connect(self._enqueue_current_result)
        self._enqueue_btn.setVisible(False)
        btn_layout.addWidget(self._enqueue_btn)
        back_btn = QPushButton("← 返回")
        back_btn.setStyleSheet(self._small_btn_style())
        back_btn.clicked.connect(lambda: self._switch_mode(0))
        btn_layout.addWidget(back_btn)
        rc_layout.addLayout(btn_layout)

        layout.addWidget(result_card)
        return page

    def _build_build_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        build_card = self._make_card("远程编译")
        build_layout = build_card.layout()

        # 状态标签
        self._build_status_label = QLabel("等待编译...")
        self._build_status_label.setStyleSheet("font-size: 14px; color: #666; padding: 10px;")
        build_layout.addWidget(self._build_status_label)

        cmd_row = QHBoxLayout()
        cmd_lbl = QLabel("编译命令:")
        cmd_lbl.setStyleSheet(f"font-size: 11px; background: transparent; color: {self.CLR_TEXT_DIM};")
        cmd_row.addWidget(cmd_lbl)
        self._build_cmd_input = QLineEdit()
        self._build_cmd_input.setPlaceholderText("留空则自动按当前目录生成：ctvbuild all -o <板型 区域 客户 订单>")
        self._build_cmd_input.setStyleSheet(self._input_style())
        cmd_row.addWidget(self._build_cmd_input, 1)
        build_layout.addLayout(cmd_row)

        build_btn_row = QHBoxLayout()
        build_btn_row.addStretch()
        self._build_btn = QPushButton("  开始编译")
        self._build_btn.setIcon(qta.icon("fa5s.hammer", color="#1a1a1a"))
        self._build_btn.setStyleSheet(self._accent_btn_style())
        self._build_btn.clicked.connect(self._on_start_build)
        build_btn_row.addWidget(self._build_btn)

        self._cancel_build_btn = QPushButton("  取消(Ctrl+C)")
        self._cancel_build_btn.setIcon(qta.icon("fa5s.stop-circle", color="#e17055"))
        self._cancel_build_btn.setStyleSheet(self._small_btn_style())
        self._cancel_build_btn.clicked.connect(self._on_cancel_build)
        build_btn_row.addWidget(self._cancel_build_btn)
        build_layout.addLayout(build_btn_row)

        self._build_log = TerminalTextEdit()
        self._build_log.setStyleSheet(self._text_edit_style())
        self._build_log.setMinimumHeight(220)
        self._build_log.installEventFilter(self)
        self._build_log.set_tab_callback(self._on_terminal_tab)
        from PySide6.QtCore import Qt as _Qt2; self._build_log.setFocusPolicy(_Qt2.StrongFocus)
        self._shell_input_pos = 0  # 记录用户可输入区域的起始位置
        build_layout.addWidget(self._build_log, 1)

        # 命令输入框
        input_row = QHBoxLayout()
        input_lbl = QLabel("命令输入:")
        input_lbl.setStyleSheet(f"font-size: 11px; background: transparent; color: {self.CLR_TEXT_DIM};")
        input_row.addWidget(input_lbl)
        self._build_input = TabLineEdit()
        self._build_input.setPlaceholderText("输入命令后按回车执行（有编译时发到 tmux，否则直接 SSH 执行）")
        self._build_input.setStyleSheet(self._input_style())
        self._build_input.returnPressed.connect(self._on_build_input_send)
        self._build_input.set_tab_callback(self._do_remote_completion)
        input_row.addWidget(self._build_input, 1)
        send_btn = QPushButton("发送")
        send_btn.setStyleSheet(self._small_btn_style())
        send_btn.clicked.connect(self._on_build_input_send)
        input_row.addWidget(send_btn)
        build_layout.addLayout(input_row)

        # 补全提示标签（独立 QLabel，不被终端渲染覆盖）
        self._completion_label = QLabel("")
        self._completion_label.setStyleSheet(f"font-size: 11px; background: transparent; color: {self.CLR_ACCENT2}; padding: 2px 8px;")
        build_layout.addWidget(self._completion_label)
        # 输入变化时清除补全提示
        self._build_input.textChanged.connect(lambda _: self._completion_label.setText(""))

        # tmux 快捷按钮
        tmux_row = QHBoxLayout()
        tmux_lbl = QLabel("tmux:")
        tmux_lbl.setStyleSheet(f"font-size: 11px; background: transparent; color: {self.CLR_TEXT_DIM};")
        tmux_row.addWidget(tmux_lbl)
        tmux_cmds = [
            ("查看会话", "tmux ls"),
            ("杀掉全部", "tmux kill-server"),
        ]
        for label, cmd in tmux_cmds:
            btn = QPushButton(label)
            btn.setStyleSheet(self._small_btn_style())
            btn.clicked.connect(lambda checked, c=cmd: self._exec_quick_cmd(c))
            tmux_row.addWidget(btn)
        tmux_row.addStretch()
        build_layout.addLayout(tmux_row)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        back_btn = QPushButton("← 返回执行结果")
        back_btn.setStyleSheet(self._small_btn_style())
        back_btn.clicked.connect(lambda: self._switch_mode(3))
        btn_row.addWidget(back_btn)
        build_layout.addLayout(btn_row)

        layout.addWidget(build_card, 1)
        return page

    def _build_upload_page(self) -> QWidget:
        """网盘上传页面。"""
        from PySide6.QtCore import Qt
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # 网盘设置卡片
        settings_card = self._make_card("网盘设置")
        sl = settings_card.layout()

        # 账号
        r1 = QHBoxLayout(); r1.setSpacing(10)
        r1.addWidget(QLabel("账号:"))
        self._wdav_user_input = QLineEdit()
        self._wdav_user_input.setStyleSheet(self._input_style())
        self._wdav_user_input.setPlaceholderText("网盘用户名")
        self._wdav_user_input.setText(self._wdav_user)
        r1.addWidget(self._wdav_user_input, 1)
        r1.addWidget(QLabel("密码:"))
        self._wdav_pass_input = QLineEdit()
        self._wdav_pass_input.setStyleSheet(self._input_style())
        self._wdav_pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._wdav_pass_input.setPlaceholderText("网盘密码")
        self._wdav_pass_input.setText(self._wdav_pass)
        r1.addWidget(self._wdav_pass_input, 1)
        sl.addLayout(r1)

        # 文件夹
        r2 = QHBoxLayout(); r2.setSpacing(10)
        r2.addWidget(QLabel("文件夹:"))
        self._wdav_folder_input = QLineEdit()
        self._wdav_folder_input.setStyleSheet(self._input_style())
        self._wdav_folder_input.setPlaceholderText("如 software/FAE")
        self._wdav_folder_input.setText(self._wdav_folder)
        r2.addWidget(self._wdav_folder_input, 1)
        save_btn = QPushButton("  保存设置")
        save_btn.setStyleSheet(self._small_btn_style())
        save_btn.clicked.connect(self._save_webdav_settings)
        r2.addWidget(save_btn)
        sl.addLayout(r2)
        layout.addWidget(settings_card)

        # 上传操作卡片
        upload_card = self._make_card("上传文件")
        ul = upload_card.layout()

        # zip 文件路径
        r3 = QHBoxLayout(); r3.setSpacing(10)
        r3.addWidget(QLabel("文件路径:"))
        self._upload_zip_input = QLineEdit()
        self._upload_zip_input.setStyleSheet(self._input_style())
        self._upload_zip_input.setPlaceholderText("远程服务器上的 zip 文件路径")
        r3.addWidget(self._upload_zip_input, 1)
        browse_btn = QPushButton("  浏览服务器")
        browse_btn.setIcon(qta.icon("fa5s.folder-open", color="#888"))
        browse_btn.setStyleSheet(self._small_btn_style())
        browse_btn.clicked.connect(self._on_browse_server)
        r3.addWidget(browse_btn)
        find_btn = QPushButton("  查找最新 zip")
        find_btn.setStyleSheet(self._small_btn_style())
        find_btn.clicked.connect(self._on_find_zip)
        r3.addWidget(find_btn)
        ul.addLayout(r3)

        # 上传按钮
        r4 = QHBoxLayout(); r4.setSpacing(10); r4.addStretch()
        self._upload_btn = QPushButton("  上传到网盘")
        self._upload_btn.setIcon(qta.icon("fa5s.cloud-upload-alt", color="#1a1a1a"))
        self._upload_btn.setStyleSheet(self._accent_btn_style())
        self._upload_btn.clicked.connect(self._on_upload)
        r4.addWidget(self._upload_btn)
        ul.addLayout(r4)

        # 上传结果（可复制）
        self._upload_result_widget = QWidget()
        self._upload_result_widget.setVisible(False)
        self._upload_result_widget.setStyleSheet(
            f"QWidget {{ background: #f0faf0; border: 1px solid #c0e0c0; border-radius: 8px; padding: 8px; }}")
        res_lay = QVBoxLayout(self._upload_result_widget)
        res_lay.setContentsMargins(12, 8, 12, 8)
        res_lay.setSpacing(6)

        self._upload_name_lbl = QLabel("")
        self._upload_name_lbl.setStyleSheet(f"font-size: 12px; color: {self.CLR_TEXT}; background: transparent;")
        res_lay.addWidget(self._upload_name_lbl)

        link_row = QHBoxLayout(); link_row.setSpacing(8)
        link_label = QLabel("软件路径:")
        link_label.setStyleSheet(f"font-size: 12px; color: {self.CLR_TEXT_DIM}; background: transparent;")
        link_row.addWidget(link_label)
        self._upload_link_lbl = QLabel("")
        self._upload_link_lbl.setStyleSheet(f"font-size: 12px; color: #4a90d9; background: transparent;")
        self._upload_link_lbl.setWordWrap(True)
        self._upload_link_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        link_row.addWidget(self._upload_link_lbl, 1)
        copy_link_btn = QPushButton("  复制软件路径")
        copy_link_btn.setIcon(qta.icon("fa5s.copy", color="#888"))
        copy_link_btn.setStyleSheet(self._small_btn_style())
        copy_link_btn.clicked.connect(self._on_copy_upload_link)
        link_row.addWidget(copy_link_btn)
        copy_all_btn = QPushButton("  复制全部")
        copy_all_btn.setIcon(qta.icon("fa5s.copy", color="#888"))
        copy_all_btn.setStyleSheet(self._small_btn_style())
        copy_all_btn.clicked.connect(self._on_copy_upload_all)
        link_row.addWidget(copy_all_btn)
        res_lay.addLayout(link_row)

        self._upload_status_lbl = QLabel("")
        self._upload_status_lbl.setStyleSheet(f"font-size: 11px; color: {self.CLR_TEXT_DIM}; background: transparent;")
        res_lay.addWidget(self._upload_status_lbl)

        ul.addWidget(self._upload_result_widget)

        # 错误提示
        self._upload_error_lbl = QLabel("")
        self._upload_error_lbl.setStyleSheet(f"font-size: 12px; color: {self.CLR_RED}; background: transparent; padding: 4px;")
        self._upload_error_lbl.setWordWrap(True)
        self._upload_error_lbl.setVisible(False)
        ul.addWidget(self._upload_error_lbl)

        layout.addWidget(upload_card)
        layout.addStretch()
        return page

    def _get_build_code_dir(self) -> str:
        target_path = str(self._get_target_path())
        marker = "/code/cultraview/cusConfig"
        if marker in target_path:
            return target_path.split(marker, 1)[0] + "/code"
        return target_path

    def _build_default_compile_command(self, target_path: str = "") -> str:
        code_dir = self._get_build_code_dir()
        if not target_path:
            target_path = str(self._get_target_path())
        marker = "/code/cultraview/cusConfig/"

        order_args = ""
        if marker in target_path:
            relative = target_path.split(marker, 1)[1]
            segments = [seg for seg in relative.split("/") if seg]
            if segments:
                order_args = " " + " ".join(segments)

        return f"cd {code_dir} && EXACT_MATCH=1 ctvbuild all -o{order_args}"

    # ── WebDAV 设置 ──

    def _load_webdav_settings(self):
        from PySide6.QtCore import QSettings
        s = QSettings("CtvAuto", "SoftwareOutput")
        self._wdav_user = s.value("wdav/user", "")
        self._wdav_folder = s.value("wdav/folder", "software/FAE")
        try:
            import keyring
            self._wdav_pass = keyring.get_password("CtvAuto-WebDAV", self._wdav_user) or ""
        except Exception:
            self._wdav_pass = ""

    def _save_webdav_settings(self):
        from PySide6.QtCore import QSettings
        user = self._wdav_user_input.text().strip()
        pwd = self._wdav_pass_input.text().strip()
        folder = self._wdav_folder_input.text().strip()
        s = QSettings("CtvAuto", "SoftwareOutput")
        s.setValue("wdav/user", user)
        s.setValue("wdav/folder", folder)
        try:
            import keyring
            if user and pwd:
                keyring.set_password("CtvAuto-WebDAV", user, pwd)
        except Exception:
            pass
        self._wdav_user = user
        self._wdav_pass = pwd
        self._wdav_folder = folder
        self._upload_error_lbl.setText("")
        self._upload_error_lbl.setVisible(False)
        self._upload_name_lbl.setText("✓ 网盘设置已保存")
        self._upload_link_lbl.setText("")
        self._upload_status_lbl.setText("")
        self._upload_result_widget.setVisible(True)

    def _on_find_zip(self):
        code_dir = self._get_build_code_dir()
        self._upload_error_lbl.setVisible(False)
        self._upload_status_lbl.setText("正在查找最新 zip 文件…")
        import threading
        def _find():
            try:
                path = self._upload_service.find_latest_zip(code_dir)
                self._log_emitter.completion_result.emit(f"__ZIP__{path}" if path else "__ZIP__NOT_FOUND")
            except Exception as e:
                self._log_emitter.completion_result.emit(f"__ZIP__ERROR:{e}")
        threading.Thread(target=_find, daemon=True).start()

    def _on_browse_server(self):
        """打开远程文件浏览器对话框。"""
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QPushButton, QHBoxLayout, QLabel, QScrollArea
        import shlex
        dlg = QDialog(self)
        dlg.setWindowTitle("浏览服务器文件")
        dlg.setMinimumSize(650, 500)
        dlg.setStyleSheet("QDialog { background: #ffffff; }")

        lay = QVBoxLayout(dlg)
        lay.setSpacing(8)

        # ── 项目快捷按钮 ──
        proj_label = QLabel("快速进入项目 out_emmc:")
        proj_label.setStyleSheet("font-size: 12px; color: #666; background: transparent;")
        lay.addWidget(proj_label)

        proj_scroll = QScrollArea()
        proj_scroll.setWidgetResizable(True)
        proj_scroll.setFixedHeight(44)
        proj_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        proj_btn_container = QWidget()
        proj_btn_layout = QHBoxLayout(proj_btn_container)
        proj_btn_layout.setContentsMargins(0, 0, 0, 0)
        proj_btn_layout.setSpacing(6)

        # 加载项目列表
        try:
            stdin, stdout, stderr = self._ssh_client.exec_command(
                f'ls -d {self._base_path}/*/', timeout=10)
            projects = []
            for d in stdout.read().decode().strip().split('\n'):
                d = d.strip().rstrip('/')
                if d:
                    name = Path(d).name
                    if not name.startswith('.'):
                        projects.append(name)
        except Exception:
            projects = []

        for proj in sorted(projects):
            btn = QPushButton(proj)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background: #f0f2f5; color: #333; border: 1px solid #ddd;"
                " border-radius: 6px; padding: 4px 10px; font-size: 11px; }"
                "QPushButton:hover { background: #e0e4ea; border-color: #bbb; }"
            )
            btn.clicked.connect(lambda _, p=proj: _load(f"{self._base_path}/{p}/code/out_emmc"))
            proj_btn_layout.addWidget(btn)
        proj_btn_layout.addStretch()
        proj_scroll.setWidget(proj_btn_container)
        lay.addWidget(proj_scroll)

        # 路径栏
        path_row = QHBoxLayout()
        self._browse_path = self._get_build_code_dir() + "/out_emmc"
        path_lbl = QLabel(self._browse_path)
        path_lbl.setStyleSheet("font-size: 12px; color: #666; padding: 4px;")
        path_lbl.setWordWrap(True)
        path_row.addWidget(path_lbl, 1)
        lay.addLayout(path_row)

        # 文件列表
        file_list = QListWidget()
        file_list.setStyleSheet(
            "QListWidget { border: 1px solid #e0e0e0; border-radius: 6px; }"
            "QListWidget::item { padding: 6px 10px; font-size: 12px; }"
            "QListWidget::item:hover { background: #f0f0f0; }"
            "QListWidget::item:selected { background: #e0e8f0; }"
        )
        lay.addWidget(file_list, 1)

        # 加载目录内容
        def _load(path: str):
            file_list.clear()
            path_lbl.setText(path)
            self._browse_path = path
            try:
                # 一条命令列出所有条目及类型（d=目录，-=文件）
                stdin, stdout, stderr = self._ssh_client.exec_command(
                    f'ls -1F --color=never {shlex.quote(path)} 2>/dev/null', timeout=10)
                entries = stdout.read().decode().strip().split('\n')
                # 加上级目录
                if path != "/":
                    item = QListWidgetItem("📁  ..")
                    item.setData(256, str(Path(path).parent))
                    item.setData(257, "dir")
                    file_list.addItem(item)
                dirs = []
                files = []
                for name in sorted(entries):
                    if not name or name.startswith('.'):
                        continue
                    # ls -F 会在目录后加 /，可执行文件加 *，链接加 @
                    if name.endswith('/'):
                        name = name[:-1]
                        dirs.append(name)
                    elif name.endswith('*') or name.endswith('@'):
                        name = name[:-1]
                        files.append(name)
                    else:
                        files.append(name)
                for name in dirs:
                    full = f"{path}/{name}" if path != "/" else f"/{name}"
                    item = QListWidgetItem(f"📁  {name}")
                    item.setData(256, full)
                    item.setData(257, "dir")
                    file_list.addItem(item)
                for name in files:
                    full = f"{path}/{name}" if path != "/" else f"/{name}"
                    item = QListWidgetItem(f"📄  {name}")
                    item.setData(256, full)
                    item.setData(257, "file")
                    file_list.addItem(item)
            except Exception as e:
                file_list.addItem(f"错误: {e}")

        import shlex
        _load(self._browse_path)

        # 双击进入目录
        def _on_dblclick(item):
            path = item.data(256)
            kind = item.data(257)
            if kind == "dir":
                _load(path)
            else:
                self._upload_zip_input.setText(path)
                dlg.accept()
        file_list.itemDoubleClicked.connect(_on_dblclick)

        # 底部按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        select_btn = QPushButton("  选择当前路径")
        select_btn.setStyleSheet(self._accent_btn_style())
        def _select():
            # 选中当前选中的文件，或当前目录
            current = file_list.currentItem()
            if current and current.data(257) == "file":
                self._upload_zip_input.setText(current.data(256))
                dlg.accept()
            elif current and current.data(257) == "dir":
                _load(current.data(256))
        select_btn.clicked.connect(_select)
        btn_row.addWidget(select_btn)
        cancel_btn = QPushButton("  取消")
        cancel_btn.setStyleSheet(self._small_btn_style())
        cancel_btn.clicked.connect(dlg.reject)
        btn_row.addWidget(cancel_btn)
        lay.addLayout(btn_row)

        dlg.exec()

    def _on_copy_upload_link(self):
        link = self._upload_link_lbl.text()
        if link:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(link)
            self._upload_status_lbl.setText("✓ 链接已复制到剪贴板")

    def _on_copy_upload_all(self):
        name = self._upload_name_lbl.text()
        link = self._upload_link_lbl.text()
        text = f"{name}\n{link}" if link else name
        if text:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(text)
            self._upload_status_lbl.setText("✓ 已复制到剪贴板")

    def _on_upload(self):
        user = self._wdav_user_input.text().strip()
        pwd = self._wdav_pass_input.text().strip()
        folder = self._wdav_folder_input.text().strip()
        zip_path = self._upload_zip_input.text().strip()
        if not user or not pwd:
            self._upload_error_lbl.setText("❌ 请先填写网盘账号和密码")
            self._upload_error_lbl.setVisible(True)
            return
        if not zip_path:
            self._upload_error_lbl.setText("❌ 请填写或查找 zip 文件路径")
            self._upload_error_lbl.setVisible(True)
            return
        self._upload_btn.setEnabled(False)
        self._upload_btn.setText("  上传中…")
        self._upload_error_lbl.setVisible(False)
        self._upload_name_lbl.setText("正在上传…")
        self._upload_link_lbl.setText("")
        self._upload_status_lbl.setText("")
        self._upload_result_widget.setVisible(True)
        import threading
        def _do():
            result = self._upload_service.upload_file(zip_path, folder, user, pwd)
            self._log_emitter.completion_result.emit(
                f"__UPLOAD__{'OK' if result.success else 'FAIL'}|{result.filename}|{result.link}|{result.size}|{result.error}")
        threading.Thread(target=_do, daemon=True).start()

    def eventFilter(self, obj, event):
        """拦截日志框的键盘事件，发送到 shell。"""
        from PySide6.QtCore import QEvent, Qt

        # ---- 日志框键盘事件 → 发到 shell ----
        if obj is self._build_log and event.type() == QEvent.KeyPress:
            # Tab 由 TerminalTextEdit.keyPressEvent 处理，这里不再拦截
            # Ctrl+C → 发送中断信号
            from PySide6.QtCore import Qt as _Qt
            if event.key() == _Qt.Key_C and event.modifiers() & _Qt.ControlModifier:
                if self._shell_channel and self._shell_running:
                    self._shell_channel.send("\x03")
                return True

            # 方向键 → 命令历史
            if event.key() == _Qt.Key_Up:
                if self._shell_channel and self._shell_running:
                    self._shell_channel.send("\x1b[A")
                return True
            if event.key() == _Qt.Key_Down:
                if self._shell_channel and self._shell_running:
                    self._shell_channel.send("\x1b[B")
                return True
            if event.key() == _Qt.Key_Right:
                if self._shell_channel and self._shell_running:
                    self._shell_channel.send("\x1b[C")
                return True
            if event.key() == _Qt.Key_Left:
                if self._shell_channel and self._shell_running:
                    self._shell_channel.send("\x1b[D")
                return True

            # Escape → 发送 ESC
            if event.key() == _Qt.Key_Escape:
                if self._shell_channel and self._shell_running:
                    self._shell_channel.send("\x1b")
                return True

            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if self._shell_channel and self._shell_running:
                    # 尝试提取用户输入的命令
                    doc = self._build_log.document()
                    text = doc.toPlainText()
                    last_line = text.split("\n")[-1] if "\n" in text else text
                    cmd = last_line.strip()
                    import re as _re
                    m = _re.match(r'^[^@]+@[^:]+:[^$#]*[$#]\s*(.*)', cmd)
                    if m and m.group(1).strip():
                        # 有明确命令，发送命令+回车
                        self._shell_channel.send(m.group(1).rstrip() + "\n")
                    else:
                        # 没有明确命令（如纯提示符行），发送纯回车
                        self._shell_channel.send("\n")
                return True
            # 阻止在历史区域编辑
            cursor = self._build_log.textCursor()
            if cursor.position() < self._shell_input_pos:
                if event.key() not in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right,
                                        Qt.Key_Home, Qt.Key_End, Qt.Key_PageUp, Qt.Key_PageDown):
                    # 移到末尾
                    cursor.movePosition(cursor.MoveOperation.End)
                    self._build_log.setTextCursor(cursor)
                    if event.key() in (Qt.Key_Backspace, Qt.Key_Delete):
                        return True
        return super().eventFilter(obj, event)

    def _init_shell(self) -> None:
        """初始化持久化 shell 会话。"""
        import threading
        try:
            transport = self._ssh_client.get_transport()
            if not transport:
                return
            ch = transport.open_session()
            self._term_cols = 200
            self._term_rows = 50
            ch.get_pty(term='xterm-256color', width=self._term_cols, height=self._term_rows)
            ch.invoke_shell()
            # cd 到工作目录
            work_dir = self._base_path or "/home/user"
            ch.send(f"cd {work_dir}\n")
            self._shell_channel = ch
            self._shell_running = True
            # pyte 终端模拟器
            import pyte
            import threading as _th
            self._term_lock = _th.Lock()
            self._term_screen = pyte.Screen(self._term_cols, self._term_rows)
            self._term_stream = pyte.Stream(self._term_screen)
            # 后台读取输出
            threading.Thread(target=self._shell_reader, daemon=True).start()
            self._logger.info("持久化 shell 会话已建立")
        except Exception as e:
            self._logger.error("初始化 shell 失败: %s", e)

    def _shell_reader(self) -> None:
        """后台线程持续读取 shell 输出，pyte 解析 + 防抖渲染。"""
        import time
        ch = self._shell_channel
        if not ch:
            return
        dirty = False
        last_time = 0.0
        while self._shell_running:
            try:
                if ch.recv_ready():
                    data = ch.recv(8192).decode("utf-8", errors="replace")
                    if data:
                        with self._term_lock:
                            self._term_stream.feed(data)
                        dirty = True
                        last_time = time.monotonic()
                elif dirty and (time.monotonic() - last_time) > 0.08:
                    self._log_emitter.log_received.emit("__TERM__")
                    dirty = False
                elif ch.exit_status_ready():
                    if dirty:
                        self._log_emitter.log_received.emit("__TERM__")
                    break
                else:
                    time.sleep(0.01)
            except Exception:
                break
        self._shell_running = False

    def _on_start_build(self) -> None:
        try:
            # 用实际目标路径生成编译命令，确保后缀正确
            target = str(self._get_target_path())
            cmd = self._build_default_compile_command(target_path=target)
            self._build_cmd_input.setText(cmd)

            self._build_log.clear()
            self._build_btn.setEnabled(False)
            self._cancel_build_btn.setEnabled(True)
            self._build_btn.setText("编译中…")
            self._last_build_pos = 0
            self._build_done = False

            # 设置信号驱动的实时日志回调
            self._build_service.set_callbacks(
                on_log=self._log_emitter.log_received.emit,
                on_finished=lambda status, code: self._log_emitter.finished.emit(status, code),
            )
            build_job = self._build_service.submit(str(self._get_target_path()), command=cmd)
            self._build_log.append(f"[编译] 任务已提交: {build_job.task_id}")

        except Exception as e:
            self._build_log.append(f"[错误] 启动编译失败: {e}")
            self._build_btn.setEnabled(True)
            self._cancel_build_btn.setEnabled(False)
            self._build_btn.setText("  开始编译")

    def _on_cancel_build(self) -> None:
        # 有编译任务 → 取消编译
        if self._build_service.current_handle() and self._build_service.current_handle().is_running():
            self._build_service.cancel()
            self._build_log.append("[编译] 已发送取消请求")
            
            # 更新 UI 状态
            self._build_done = True
            self._build_status_label.setText("已取消编译")
            self._build_status_label.setStyleSheet("font-size: 14px; color: #e17055; padding: 10px; font-weight: bold;")
            self._cancel_build_btn.setEnabled(False)
            
            # 更新队列状态（只更新当前编译的项）
            from executor.build_queue import QueueItemStatus
            if hasattr(self, '_current_build_queue_id') and self._current_build_queue_id:
                self._build_queue.update_status(self._current_build_queue_id, QueueItemStatus.CANCELLED)
                self._logger.info("队列状态已更新为取消: %s", self._current_build_queue_id)
                self._current_build_queue_id = None
        # 有 shell 会话 → 发送 Ctrl+C
        elif self._shell_channel and self._shell_running:
            self._shell_channel.send("\x03")
        else:
            self._build_log.append("[编译] 当前没有可取消的任务")

    def _exec_quick_cmd(self, cmd: str) -> None:
        """快捷按钮执行命令。"""
        if self._shell_channel and self._shell_running:
            self._shell_channel.send(cmd + "\n")
        else:
            self._build_log.append("[错误] shell 会话未建立")

    def _on_completion_result(self, result: str) -> None:
        """Tab 补全结果回调（主线程）。"""
        if result.startswith("__TAB__"):
            new_cmd = result[7:]
            cursor = self._build_log.textCursor()
            cursor.setPosition(self._shell_input_pos)
            cursor.movePosition(cursor.MoveOperation.EndOfLine, cursor.MoveMode.KeepAnchor)
            cursor.insertText(new_cmd)
            self._shell_input_pos = self._build_log.document().characterCount() - len(new_cmd)
            cursor.movePosition(cursor.MoveOperation.End)
            self._build_log.setTextCursor(cursor)
        elif result.startswith("__STATUS__"):
            self._completion_label.setText(result[10:])
        elif result.startswith("__ZIP__"):
            path = result[7:]
            if path == "NOT_FOUND":
                self._upload_error_lbl.setText("❌ 未找到 zip 文件")
                self._upload_error_lbl.setVisible(True)
                self._upload_result_widget.setVisible(False)
            elif path.startswith("ERROR:"):
                self._upload_error_lbl.setText(f"❌ 查找失败: {path[6:]}")
                self._upload_error_lbl.setVisible(True)
                self._upload_result_widget.setVisible(False)
            else:
                self._upload_zip_input.setText(path)
                self._upload_error_lbl.setVisible(False)
                self._upload_name_lbl.setText(f"✓ 找到: {path.rsplit('/', 1)[-1]}")
                self._upload_link_lbl.setText("")
                self._upload_status_lbl.setText("")
                self._upload_result_widget.setVisible(True)
        elif result.startswith("__UPLOAD__"):
            parts = result[10:].split("|", 4)
            ok, filename, link, size, error = (parts + [""] * 5)[:5]
            self._upload_btn.setEnabled(True)
            self._upload_btn.setText("  上传到网盘")
            if ok == "OK":
                self._upload_error_lbl.setVisible(False)
                self._upload_name_lbl.setText(f"软件名称: {filename}  ({size})")
                self._upload_link_lbl.setText(link if link else "（未生成链接）")
                self._upload_status_lbl.setText("")
                self._upload_result_widget.setVisible(True)
            else:
                self._upload_error_lbl.setText(f"❌ 上传失败: {error}")
                self._upload_error_lbl.setVisible(True)
                self._upload_result_widget.setVisible(False)

    def _on_terminal_tab(self) -> None:
        """终端区 Tab 补全（后台线程执行，避免阻塞 UI）。"""
        import shlex, os, re, threading

        if not (hasattr(self, '_ssh_client') and self._ssh_client):
            return

        # ---- 从 QTextEdit 提取当前命令 ----
        start_pos = self._shell_input_pos
        doc_text = self._build_log.document().toPlainText()
        lines = doc_text.split('\n')
        char_count = 0
        target_line = ""
        for line in lines:
            char_count += len(line) + 1
            if char_count > start_pos:
                target_line = line
                break

        m = re.match(r'^[^@]+@[^:]+:[^$#]*[$#]\s*(.*)', target_line.strip())
        cmd_text = m.group(1).rstrip() if m else target_line.strip()

        if not cmd_text:
            return

        parts = cmd_text.rstrip().split()
        last_word = parts[-1]
        prefix_words = parts[:-1]
        is_cd = prefix_words and prefix_words[0] == "cd"
        has_slash = "/" in last_word
        cwd = self._base_path or "/home/user"

        # ---- 后台执行 SSH 查询 ----
        def _do_complete():
            try:
                if is_cd:
                    ssh_cmd = f"cd {shlex.quote(cwd)} && compgen -d -- {shlex.quote(last_word)} 2>/dev/null | head -20" if not has_slash else                               f"compgen -d -- {shlex.quote(last_word)} 2>/dev/null | head -20"
                else:
                    if has_slash:
                        ssh_cmd = f"compgen -f -- {shlex.quote(last_word)} 2>/dev/null | head -20"
                    else:
                        ssh_cmd = (
                            f"cd {shlex.quote(cwd)} && "
                            f"(compgen -f -- {shlex.quote(last_word)} 2>/dev/null | head -10; "
                            f"compgen -ac -- {shlex.quote(last_word)} 2>/dev/null | head -10) | sort -u | head -20"
                        )

                _, stdout, _ = self._ssh_client.exec_command(ssh_cmd, timeout=5)
                candidates = [line.strip() for line in stdout.readlines() if line.strip()]

                if not candidates:
                    self._completion_label.setText(f"无匹配: {last_word}")
                    return

                if len(candidates) == 1:
                    completed = candidates[0]
                    if is_cd or has_slash:
                        check_path = completed if completed.startswith("/") else f"{cwd}/{completed}"
                        _, st_out, _ = self._ssh_client.exec_command(
                            f"test -d {shlex.quote(check_path)} && echo DIR || echo NOTDIR", timeout=3
                        )
                        kind = st_out.read().decode().strip()
                        if kind == "DIR" and not completed.endswith("/"):
                            completed += "/"
                    new_cmd = " ".join(prefix_words + [completed]) if prefix_words else completed
                    self._completion_label.setText(f"✓ {completed}")
                else:
                    common = os.path.commonprefix(candidates)
                    display = "  ".join(candidates[:8])
                    if len(candidates) > 8:
                        display += f"  ... 共{len(candidates)}个"
                    self._completion_label.setText(f"候选 ({len(candidates)}): {display}")
                    if common and common != last_word:
                        new_cmd = " ".join(prefix_words + [common]) if prefix_words else common
                    else:
                        return

                # 通过信号回主线程更新 QTextEdit
                self._log_emitter.log_received.emit(f"__TAB__{new_cmd}")

            except Exception as e:
                self._completion_label.setText(f"[错误] {e}")

        threading.Thread(target=_do_complete, daemon=True).start()

    def _do_remote_completion(self, text: str) -> None:
        """使用 SSH exec_command 查询补全候选，更新输入框（不影响持久化 shell 状态）。"""
        import shlex
        import os


        parts = text.rstrip().split()
        if not parts:
            return

        last_word = parts[-1]
        prefix_words = parts[:-1]
        is_cd = prefix_words and prefix_words[0] == "cd"
        has_slash = "/" in last_word

        # 使用 _base_path 作为 cwd（_get_shell_cwd 解析 pyte 不可靠）
        cwd = self._base_path or "/home/user"

        try:
            # 构建 SSH 补全命令
            if is_cd:
                # cd 命令 → 目录补全（compgen -d）
                if has_slash:
                    ssh_cmd = f"compgen -d -- {shlex.quote(last_word)} 2>/dev/null | head -20"
                else:
                    ssh_cmd = f"cd {shlex.quote(cwd)} && compgen -d -- {shlex.quote(last_word)} 2>/dev/null | head -20"
            else:
                # 其他命令 → 文件 + 命令混合补全
                if has_slash:
                    ssh_cmd = f"compgen -f -- {shlex.quote(last_word)} 2>/dev/null | head -20"
                else:
                    ssh_cmd = (
                        f"cd {shlex.quote(cwd)} && "
                        f"(compgen -f -- {shlex.quote(last_word)} 2>/dev/null | head -10; "
                        f"compgen -ac -- {shlex.quote(last_word)} 2>/dev/null | head -10) | sort -u | head -20"
                    )


            _, stdout, _ = self._ssh_client.exec_command(ssh_cmd, timeout=5)
            candidates = [line.strip() for line in stdout.readlines() if line.strip()]


            if not candidates:
                self._completion_label.setText(f"无匹配: {last_word}")
                return

            # 处理补全结果
            if len(candidates) == 1:
                completed = candidates[0]
                # cd 命令或路径 → 检查是否是目录，加 /
                if is_cd or has_slash:
                    check_path = completed if completed.startswith("/") else f"{cwd}/{completed}"
                    _, st_out, _ = self._ssh_client.exec_command(
                        f"test -d {shlex.quote(check_path)} && echo DIR || echo NOTDIR", timeout=3
                    )
                    kind = st_out.read().decode().strip()
                    if kind == "DIR" and not completed.endswith("/"):
                        completed += "/"

                new_text = " ".join(prefix_words + [completed]) if prefix_words else completed
                self._build_input.setText(new_text)
                self._completion_label.setText(f"✓ {completed}")

            elif len(candidates) > 1:
                common = os.path.commonprefix(candidates)
                # 显示候选列表
                display = "  ".join(candidates[:8])
                if len(candidates) > 8:
                    display += f"  ... 共{len(candidates)}个"
                self._completion_label.setText(f"候选 ({len(candidates)}): {display}")

                if common and common != last_word:
                    new_text = " ".join(prefix_words + [common]) if prefix_words else common
                    self._build_input.setText(new_text)
                else:
                    pass

        except Exception as e:
            self._completion_label.setText(f"[错误] {e}")

    def _on_build_input_send(self) -> None:
        cmd = self._build_input.text().strip()
        if not cmd:
            return
        self._build_input.clear()

        # 有运行中的编译 → 发到 tmux 会话（用 shlex.quote 防特殊字符逃逸）
        handle = self._build_service.current_handle()
        if handle and handle.is_running():
            import shlex
            session_name = f"ctvbuild-{handle.task_id}"
            try:
                self._ssh_client.exec_command(
                    f"tmux send-keys -t {session_name} -l {shlex.quote(cmd)}"
                )
                self._ssh_client.exec_command(
                    f"tmux send-keys -t {session_name} Enter"
                )
                self._build_log.append(f"[输入] >>> {cmd}")
            except Exception as e:
                self._build_log.append(f"[输入] 发送失败: {e}")
            return

        # 没有编译 → 通过持久化 shell 执行
        if self._shell_channel and self._shell_running:
            self._shell_channel.send(cmd + "\n")
        else:
            self._build_log.append("[错误] shell 会话未建立")

    def _on_build_log_append(self, text: str) -> None:
        """实时追加日志（由信号驱动，在主线程执行）。"""
        # Tab 补全结果
        if text.startswith("__TAB__"):
            new_cmd = text[7:]
            cursor = self._build_log.textCursor()
            cursor.setPosition(self._shell_input_pos)
            cursor.movePosition(cursor.MoveOperation.EndOfLine, cursor.MoveMode.KeepAnchor)
            cursor.insertText(new_cmd)
            self._shell_input_pos = self._build_log.document().characterCount() - len(new_cmd)
            cursor.movePosition(cursor.MoveOperation.End)
            self._build_log.setTextCursor(cursor)
            return

        # pyte 终端渲染
        if text == "__TERM__":
            try:
                import re as _re2
                with self._term_lock:
                    screen = self._term_screen
                    all_lines = list(screen.display)
                    cursor_y = screen.cursor.y
                    cursor_x = screen.cursor.x
                filtered = []
                for line in all_lines:
                    if _re2.match(r'^\[\d+\]\s+\d+:', line.strip()):
                        continue
                    filtered.append(line)
                while filtered and not filtered[-1].strip():
                    filtered.pop()
                display_text = "\n".join(filtered)
                if display_text:
                    self._build_log.setPlainText(display_text)
                cursor_row = cursor_y
                cursor_col = cursor_x
                doc = self._build_log.document()
                block = doc.findBlockByLineNumber(min(cursor_row, doc.blockCount() - 1))
                if block.isValid():
                    pos = block.position() + min(cursor_col, block.length() - 1)
                else:
                    pos = doc.characterCount() - 1
                cursor = self._build_log.textCursor()
                cursor.setPosition(max(0, pos))
                self._build_log.setTextCursor(cursor)
                self._shell_input_pos = cursor.position()
                sb = self._build_log.verticalScrollBar()
                sb.setValue(sb.maximum())
            except Exception as e:
                self._logger.error("终端渲染失败: %s", e)
            return

        # 编译日志直接追加
        if text:
            import re as _re
            clean = _re.sub(r'\x1b\[[0-9;]*m', '', text)
            clean = _re.sub(r'\x1b\[[\?0-9;]*[A-Za-z]', '', clean)
            clean = _re.sub(r'\x1b\[[0-9;]*[HJ]', '', clean)
            if not clean:
                return
            cursor = self._build_log.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self._build_log.setTextCursor(cursor)
            self._build_log.insertPlainText(clean)
            self._shell_input_pos = self._build_log.document().characterCount() - 1
            sb = self._build_log.verticalScrollBar()
            sb.setValue(sb.maximum())

        # 检查是否编译完成
        handle = self._build_service.current_handle()
        if handle and not handle.is_running():
            self._on_build_finished(handle.status, handle.exit_code or 0)

    def _on_build_finished(self, status: str, exit_code: int) -> None:
        """编译完成回调。"""
        if getattr(self, "_build_done", False):
            return
        self._build_done = True
        self._build_btn.setEnabled(True)
        self._cancel_build_btn.setEnabled(False)
        self._build_btn.setText("  开始编译")
        status_text = "编译成功" if status == "succeeded" else "编译失败"
        self._build_log.append(f"\n[编译] {status_text} (退出码: {exit_code})")
        
        # 更新队列状态
        from executor.build_queue import QueueItemStatus
        if hasattr(self, "_current_build_queue_id") and self._current_build_queue_id:
            queue_status = QueueItemStatus.SUCCEEDED if status == "succeeded" else QueueItemStatus.FAILED
            self._build_queue.update_status(self._current_build_queue_id, queue_status, exit_code=exit_code)
            self._logger.info("队列状态已更新: %s -> %s", self._current_build_queue_id, queue_status.value)
            self._current_build_queue_id = None

            # 自动连编：成功后取下一个 pending 继续，失败则停止
            if status == "succeeded" and getattr(self, "_auto_chain", False):
                pending = self._build_queue.get_pending()
                if pending:
                    nxt = pending[0]
                    self._build_log.append(f"[编译] 自动开始下一个: {nxt.customer_name}")
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(1200, lambda nid=nxt.id: self._start_queue_build(nid, auto_chain=True))
                else:
                    self._auto_chain = False
                    self._build_log.append("[编译] 队列全部编译完成 🎉")
                    from PySide6.QtWidgets import QMessageBox
                    self._styled_msg_box(
                        QMessageBox.Icon.Information, "全部完成",
                        "编译队列已全部编译完成。"
                    ).exec()
            elif status != "succeeded":
                self._auto_chain = False
                self._build_log.append("[编译] 编译失败，自动连编已停止")

    # ========== 自动分析流程 ==========

    def _on_analyze(self) -> None:
        requirement_text = self.requirement_edit.toPlainText().strip()
        if not requirement_text:
            self.log_edit.append("请先输入客户需求。")
            return

        self.log_edit.clear()
        self.log_edit.append("[自动] 正在分析需求…")
        self.run_button.setEnabled(False)
        self.run_button.setText("分析中…")

        try:
            # 从目录设置获取上下文信息
            # customer_dir 用完整路径（供 _check_country_in_list 读取 XML）
            _dir_name = self._dir_combo.currentText() if hasattr(self, "_dir_combo") else ""
            _dir_full = self._customer_dir_map.get(_dir_name, _dir_name)
            ctx = {
                "project": self._project_combo.currentText() if hasattr(self, "_project_combo") else "",
                "platform": self._board_combo.currentText() if hasattr(self, "_board_combo") else "",
                "region": self._region_combo.currentText() if hasattr(self, "_region_combo") else "",
                "customer": self._customer_combo.currentText() if hasattr(self, "_customer_combo") else "",
                "customer_dir": _dir_full,
                "target_dir": self._target_dir_input.text().strip() if hasattr(self, "_target_dir_input") else "",
                "base_path": self._base_path,
            }
            self._current_analysis = ai.analyze(requirement_text, **ctx)
            self.log_edit.append(f"[自动] 客户: {self._current_analysis.customer}")
            self.log_edit.append(f"[自动] 平台: {self._current_analysis.platform}")
            self.log_edit.append(f"[自动] 修改项: {len(self._current_analysis.modifications)} 条")
            self._logger.info("自动分析完成: %s", requirement_text[:80])
            self._review_service.request_review(self._current_analysis)
        except Exception as e:
            self.log_edit.append(f"[错误] 自动分析异常: {e}")
            self._logger.exception("自动分析异常")
            self.run_button.setEnabled(True)
            self.run_button.setText("  自动分析并提交审核")

    # ========== 审核 ==========

    def _on_review_requested(self, analysis: ai.AnalysisResult) -> None:
        self._clear_review_page()
        self._current_review_panel = ReviewPanel(analysis)
        self._current_review_panel.review_completed.connect(self._on_review_completed)
        self._review_page_layout.addWidget(self._current_review_panel)
        self._stack.setCurrentIndex(2)

    def _clear_review_page(self) -> None:
        while self._review_page_layout.count():
            item = self._review_page_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _on_review_completed(self, decision: ReviewDecision) -> None:
        self._review_service.submit_decision(decision)
        if not decision.approved:
            self.log_edit.append(f"[审核] ❌ 已拒绝: {decision.reason}")
            self._switch_mode(0)
            self.run_button.setEnabled(True)
            self.run_button.setText("  自动分析并提交审核")
            return
        self.log_edit.append("[审核] ✅ 已通过，开始执行…")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, self._execute_task)

    # ========== 手动模式执行 ==========

    def _on_manual_execute(self, modifications: list[dict]) -> None:
        """后台线程执行手动修改。"""
        self._logger.info("手动模式收到执行信号: %d 条修改", len(modifications))
        from PySide6.QtCore import QThread, Signal as QSignal

        class _Worker(QThread):
            finished = QSignal(dict)  # {html, changed_files, error}

            def __init__(self, parent_win, mods):
                super().__init__(parent_win)
                self._win = parent_win
                self._mods = mods

            def run(self):
                try:
                    result = self._win._do_manual_execute(self._mods)
                    self.finished.emit(result)
                except Exception as e:
                    self.finished.emit({"error": str(e)})

        self._manual_worker = _Worker(self, modifications)
        self._manual_worker.finished.connect(self._on_manual_finished)
        self._manual_worker.start()

    def _on_manual_finished(self, result: dict):
        """手动修改完成（主线程）。"""
        self._manual_page.hide_progress()
        error = result.get("error")
        if error:
            self._logger.error("手动模式执行失败: %s", error)
            self._result_title.setText("❌ 执行失败")
            self._result_detail.setPlainText(f"错误: {error}")
            self._stack.setCurrentIndex(3)
            return

        html = result.get("html", "")
        changed_files = result.get("changed_files", [])
        modifications = result.get("modifications", [])

        self._result_title.setText("手动修改结果")
        self._result_detail.setHtml(
            '<div style="font-family:Menlo,Consolas,monospace;font-size:12px;">' + html + '</div>')
        self._stack.setCurrentIndex(3)

        # 加入编译队列
        dir_combo = self._dir_combo if hasattr(self, "_dir_combo") else None
        customer_name = dir_combo.currentText() if dir_combo else "未知"
        self._last_result = {
            "project_path": str(self._get_target_path()),
            "modified_files": changed_files,
            "customer_name": customer_name,
            "analysis_summary": f"手动修改 {len(modifications)} 项",
        }
        if hasattr(self, "_enqueue_btn"):
            self._enqueue_btn.setVisible(True)
            self._enqueue_btn.setEnabled(True)
            self._enqueue_btn.setText("＋ 加入编译队列")

    def _do_manual_execute(self, modifications: list[dict]) -> dict:
        """实际执行逻辑（在后台线程中运行，返回结果 dict）。"""
        from rules.rule_matcher import build_rule_registry
        from patcher.rule_patcher import RulePatcher
        from executor.validators import validate_product_model

        source_path = self._get_source_path()
        target_path = self._get_target_path()

        if not source_path.exists():
            return {"html": '<div style="color:red;">❌ 源目录不存在</div>', "changed_files": [], "modifications": modifications}

        is_copy = source_path != target_path
        if is_copy:
            if target_path.exists():
                target_path.remote_rmtree()
            source_path.remote_copytree(target_path)

        warnings = []
        model_result = validate_product_model(target_path)
        if model_result.warnings:
            warnings.extend(model_result.warnings)

        # 快照
        CTV_DATA_PATH = "overlay/cultraview/common/apps/CtvMiddleware/CultraviewTvService/res/raw/ctv_data.xml"
        RULE_FILE_MAP = {
            "build_config": lambda m: m.get("file"),
            "preinstall": lambda m: "build_ctv_app.txt",
            "whitelist": lambda m: "etc/whiteList.conf",
            "prop": lambda m: m.get("file"),
            "ctv_data": lambda m: CTV_DATA_PATH,
            "country_list_first": lambda m: CTV_DATA_PATH,
            "language_first": lambda m: "configs/CtvLanguage.ini",
            "db_ini": lambda m: m.get("file"),
            "color_temp": lambda m: "configs/db.ini",
            "nla": lambda m: "configs/db.ini",
            "gain": lambda m: "configs/db.ini",
            "ctv_setting": lambda m: "configs/ctvsetting.xml",
        }
        file_snapshots: dict[str, str] = {}
        for mod in modifications:
            resolver = RULE_FILE_MAP.get(mod.get("type"))
            if resolver:
                f = resolver(mod)
                if f and f not in file_snapshots and (target_path / f).exists():
                    try:
                        file_snapshots[f] = (target_path / f).read_text(encoding="utf-8")
                    except UnicodeDecodeError:
                        file_snapshots[f] = (target_path / f).read_text(encoding="latin-1")

        registry = build_rule_registry(modifications)
        patcher = RulePatcher(registry, target_path)
        changed = patcher.apply_all()

        # diff
        file_diffs: dict[str, list[tuple[str, str]]] = {}
        for f_name, old_content in file_snapshots.items():
            f_path = target_path / f_name
            if f_path.exists():
                try:
                    new_content = f_path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    new_content = f_path.read_text(encoding="latin-1")
                if old_content != new_content:
                    file_diffs[f_name] = self._compute_line_diff(old_content, new_content)

        # 构建 HTML 结果
        html_parts: list[str] = []
        tag = "复制" if is_copy else "直接修改"
        html_parts.append(
            f'<div style="color:#999;font-size:11px;margin-bottom:4px;">'
            f'目标目录 <span style="color:#666;">{self._escape_html(str(target_path))}</span>'
            f' &nbsp;<span style="background:#eef;color:#666;padding:1px 6px;">{tag}</span></div>'
        )

        if warnings:
            html_parts.append(self._section_header("校验警告", "#fdecea", "#c0392b"))
            html_parts.append('<div style="padding:4px 12px;font-size:12px;">' +
                "".join(f'<div style="padding:1px 0;color:#c0392b;">· {self._escape_html(w)}</div>' for w in warnings) + '</div>')

        html_parts.append(self._section_header(f"修改概要 · {len(modifications)} 项", "#e8f0fe", "#1a56c4"))
        html_parts.append('<div style="padding:4px 12px;font-size:12px;">' +
            "".join(f'<div style="padding:1px 0;"><span style="color:#1a56c4;">{i}.</span> {self._escape_html(self._describe_mod(m))}</div>'
                    for i, m in enumerate(modifications, 1)) + '</div>')

        if changed:
            unique = sorted(set(str(f) for f in changed))
            html_parts.append(self._section_header(f"文件变更 · {len(unique)}", "#f0f0f0", "#666"))
            html_parts.append('<div style="padding:4px 12px;font-size:12px;">' +
                "".join(f'<div style="padding:1px 0;color:#555;">· {self._escape_html(Path(f).name)}</div>' for f in unique) + '</div>')

        if file_diffs:
            html_parts.append(self._section_header("修改详情", "#f3e8ff", "#6b21a8"))
            diff_html: list[str] = []
            for f_name, diffs in file_diffs.items():
                diff_html.append(f'<div style="margin-top:4px;font-weight:bold;color:#6b21a8;">{self._escape_html(Path(f_name).name)}</div>')
                for old_line, new_line in diffs:
                    if old_line and new_line:
                        diff_html.append(f'<div style="color:#999;">- {self._highlight_diff(old_line, new_line, True)}</div>')
                        diff_html.append(f'<div style="color:#1e7e34;">+ {self._highlight_diff(old_line, new_line, False)}</div>')
                    elif new_line:
                        diff_html.append(f'<div style="color:#1e7e34;font-weight:bold;">+ {self._escape_html(new_line)}</div>')
                    elif old_line:
                        diff_html.append(f'<div style="color:#999;text-decoration:line-through;">- {self._escape_html(old_line)}</div>')
            html_parts.append(f'<div style="padding:4px 12px;font-size:12px;">{"".join(diff_html)}</div>')

        changed_files = sorted(set(str(f) for f in changed)) if changed else []
        return {
            "html": "".join(html_parts),
            "changed_files": changed_files,
            "modifications": modifications,
        }

    # ========== 执行任务（自动模式）==========

    def _execute_task(self) -> None:
        try:
            from executor.validators import validate_product_model
            from rules.rule_matcher import build_rule_registry
            from patcher.rule_patcher import RulePatcher

            source_path = self._get_source_path()
            target_path = self._get_target_path()

            if not source_path.exists():
                raise FileNotFoundError(f"源目录不存在: {source_path}")

            is_copy = source_path != target_path
            if is_copy:
                if target_path.exists():
                    target_path.remote_rmtree()
                source_path.remote_copytree(target_path)

            warnings = []
            model_result = validate_product_model(target_path)
            if model_result.warnings:
                warnings.extend(model_result.warnings)

            # 收集快照
            file_snapshots: dict[str, str] = {}
            CTV_DATA_PATH = "overlay/cultraview/common/apps/CtvMiddleware/CultraviewTvService/res/raw/ctv_data.xml"
            RULE_FILE_MAP = {
                "build_config": lambda m: m.get("file"),
                "preinstall": lambda m: "build_ctv_app.txt",
                "whitelist": lambda m: "etc/whiteList.conf",
                "prop": lambda m: m.get("file"),
                "ctv_data": lambda m: CTV_DATA_PATH,
                "country_list_first": lambda m: CTV_DATA_PATH,
                "language_first": lambda m: "configs/CtvLanguage.ini",
                "db_ini": lambda m: m.get("file"),
                "color_temp": lambda m: "configs/db.ini",
                "nla": lambda m: "configs/db.ini",
                "gain": lambda m: "configs/db.ini",
                "sat_gain": lambda m: "configs/db.ini",
                "ctv_setting": lambda m: "configs/ctvsetting.xml",
            }
            for mod in self._current_analysis.modifications:
                resolver = RULE_FILE_MAP.get(mod.get("type"))
                if resolver:
                    f = resolver(mod)
                    if f and f not in file_snapshots and (target_path / f).exists():
                        file_snapshots[f] = (target_path / f).read_text(encoding="utf-8")

            req_text = self.requirement_edit.toPlainText() if hasattr(self, "requirement_edit") else ""
            registry = build_rule_registry(self._current_analysis.modifications, req_text)
            patcher = RulePatcher(registry, target_path)
            changed = patcher.apply_all()

            # 计算 diff
            file_diffs: dict[str, list[tuple[str, str]]] = {}
            for f_name, old_content in file_snapshots.items():
                f_path = target_path / f_name
                if f_path.exists():
                    new_content = f_path.read_text(encoding="utf-8")
                    if old_content != new_content:
                        diffs = self._compute_line_diff(old_content, new_content)
                        file_diffs[f_name] = diffs
                        self._logger.info("diff %s: %d 条变更", f_name, len(diffs))
                    else:
                        self._logger.info("diff %s: 内容未变化", f_name)
                else:
                    self._logger.info("diff %s: 文件不存在", f_name)

            # 显示结果（分区色块布局，突出重点）
            self._result_title.setText("自动分析执行结果")
            mods = self._current_analysis.modifications
            unique_files = sorted(set(str(f) for f in changed))
            confirmed_items: list[tuple[str, str, str]] = []
            for rule in registry.rules:
                for item in getattr(rule, "confirmed", []):
                    confirmed_items.append(item)
            ensure_status = self._collect_ensure_status(registry)

            html_parts: list[str] = []

            # 顶部目标目录（紧凑）
            tag = "复制" if is_copy else "直接修改"
            html_parts.append(
                f'<div style="color:#999;font-size:11px;margin-bottom:4px;">'
                f'目标目录 <span style="color:#666;">{self._escape_html(str(target_path))}</span>'
                f' &nbsp;<span style="background:#eef;color:#666;padding:1px 6px;">{tag}</span>'
                f"</div>"
            )

            # 校验警告（红色块，最醒目）
            if warnings:
                html_parts.append(self._section_header("校验警告", "#fdecea", "#c0392b"))
                witems = "".join(
                    f'<div style="padding:1px 0;color:#c0392b;">· {self._escape_html(w)}</div>'
                    for w in warnings
                )
                html_parts.append(f'<div style="padding:4px 12px;font-size:12px;">{witems}</div>')

            # 修改概要
            html_parts.append(self._section_header(f"修改概要 · {len(mods)} 项", "#e8f0fe", "#1a56c4"))
            mod_lines = "".join(
                f'<div style="padding:1px 0;"><span style="color:#1a56c4;">{i}.</span> '
                f"{self._escape_html(self._describe_mod(m))}</div>"
                for i, m in enumerate(mods, 1)
            )
            html_parts.append(f'<div style="padding:4px 12px;font-size:12px;">{mod_lines}</div>')

            # 确认项（绿色块，已是目标值）
            if confirmed_items:
                html_parts.append(self._section_header(
                    f"确认项 · 已是目标值 · {len(confirmed_items)}", "#e6f4ea", "#1e7e34"))
                ci = "".join(
                    f'<div style="padding:1px 0;">'
                    f'<span style="color:#1e7e34;font-weight:bold;">{self._escape_html(k)}</span>'
                    f' = <span style="color:#1e7e34;">{self._escape_html(v)}</span>'
                    f' <span style="color:#aaa;font-size:11px;">{self._escape_html(Path(f_name).name)}</span>'
                    f"</div>"
                    for f_name, k, v in confirmed_items
                )
                html_parts.append(f'<div style="padding:4px 12px;font-size:12px;">{ci}</div>')

            # 自动检查项
            if ensure_status:
                html_parts.append(self._section_header("自动检查项", "#fff8e1", "#b8860b"))
                es = "".join(f'<div style="padding:1px 0;">{self._escape_html(line)}</div>' for line in ensure_status)
                html_parts.append(f'<div style="padding:4px 12px;font-size:12px;">{es}</div>')

            # 文件变更
            if unique_files:
                html_parts.append(self._section_header(f"文件变更 · {len(unique_files)}", "#f0f0f0", "#666"))
                fl = "".join(f'<div style="padding:1px 0;color:#555;">· {self._escape_html(Path(f).name)}</div>' for f in unique_files)
                html_parts.append(f'<div style="padding:4px 12px;font-size:12px;">{fl}</div>')

            # 修改详情 diff（紫色块，重点）
            if file_diffs:
                html_parts.append(self._section_header("修改详情", "#f3e8ff", "#6b21a8"))
                diff_html: list[str] = []
                for f_name, diffs in file_diffs.items():
                    diff_html.append(
                        f'<div style="margin-top:4px;font-weight:bold;color:#6b21a8;">'
                        f'{self._escape_html(Path(f_name).name)}</div>'
                    )
                    for old_line, new_line in diffs:
                        if old_line and new_line:
                            diff_html.append(f'<div style="color:#999;">- {self._highlight_diff(old_line, new_line, is_old=True)}</div>')
                            diff_html.append(f'<div style="color:#1e7e34;">+ {self._highlight_diff(old_line, new_line, is_old=False)}</div>')
                        elif new_line:
                            diff_html.append(f'<div style="color:#1e7e34;font-weight:bold;">+ {self._escape_html(new_line)}</div>')
                        elif old_line:
                            diff_html.append(f'<div style="color:#999;text-decoration:line-through;">- {self._escape_html(old_line)}</div>')
                html_parts.append(f'<div style="padding:4px 12px;font-size:12px;">{"".join(diff_html)}</div>')

            html_content = "".join(html_parts)
            self._result_detail.setHtml(
                '<div style="font-family:Menlo,Consolas,monospace;font-size:12px;">'
                + html_content + "</div>"
            )

            self._logger.info("AI 执行完成: source=%s target=%s changed=%d", source_path, target_path, len(changed))
            self._stack.setCurrentIndex(3)
            self.run_button.setEnabled(True)
            self.run_button.setText("  自动分析并提交审核")

            # 保存本次执行结果，等用户确认后再加入编译队列
            self._last_result = {
                "project_path": str(self._get_target_path()),
                "modified_files": unique_files,
                "customer_name": (self._current_analysis.customer
                                  or self._current_analysis.target_customer_dir)
                                 if self._current_analysis else "未知",
                "analysis_summary": (self.requirement_edit.toPlainText()[:200]
                                     if hasattr(self, "requirement_edit") else ""),
            }
            if hasattr(self, "_enqueue_btn"):
                self._enqueue_btn.setVisible(True)
                self._enqueue_btn.setEnabled(True)
                self._enqueue_btn.setText("＋ 加入编译队列")

        except FileNotFoundError as e:
            self.log_edit.append(f"[错误] 目录不存在: {e}")
            self._switch_mode(0)
            self.run_button.setEnabled(True)
            self.run_button.setText("  自动分析并提交审核")
        except Exception as e:
            self.log_edit.append(f"[错误] {e}")
            self._logger.exception("执行任务异常")
            self._switch_mode(0)
            self.run_button.setEnabled(True)
            self.run_button.setText("  自动分析并提交审核")

    def _enqueue_current_result(self) -> None:
        """用户在结果页点击「加入编译队列」后执行。"""
        if not getattr(self, "_last_result", None):
            return
        try:
            r = self._last_result
            self._build_queue.add(
                customer_name=r["customer_name"],
                project_path=r["project_path"],
                modified_files=r["modified_files"],
                analysis_summary=r["analysis_summary"],
            )
            self.log_edit.append(f"[队列] 已加入编译队列: {r['customer_name']}")
            self._enqueue_btn.setEnabled(False)
            self._enqueue_btn.setText("✓ 已加入队列")
            from PySide6.QtWidgets import QMessageBox
            self._styled_msg_box(
                QMessageBox.Icon.Information, "已加入编译队列",
                f"客户 [{r['customer_name']}] 已加入编译队列。\n"
                f"请到「编译队列」页面点击「开始编译」。"
            ).exec()
            self._last_result = None
        except Exception as e:
            self.log_edit.append(f"[错误] 加入编译队列失败: {e}")
            self._logger.exception("加入编译队列失败")

    # ========== Diff 工具 ==========

    def _describe_mod(self, mod: dict) -> str:
        """把一条修改项翻译成人话。"""
        from ui.review_panel import ReviewPanel
        return ReviewPanel._describe_mod(ReviewPanel.__new__(ReviewPanel), mod)

    def _styled_msg_box(self, icon, title, text):
        """创建白底 QMessageBox，绕过 macOS 原生深色弹窗。"""
        from PySide6.QtWidgets import QMessageBox
        box = QMessageBox(self)
        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setText(text)
        box.setStyleSheet(
            "QMessageBox { background: #ffffff; }"
            "QMessageBox QLabel { color: #1a1a1a; background: transparent; font-size: 13px; }"
            "QMessageBox QPushButton { background: #e0e0e0; color: #1a1a1a; border: none; "
            "border-radius: 6px; padding: 6px 18px; font-size: 13px; min-width: 60px; }"
            "QMessageBox QPushButton:hover { background: #d5d5d5; }"
        )
        return box

    def _section_header(self, title: str, bg: str, color: str) -> str:
        """生成分区色块标题。"""
        return (f'<div style="background:{bg};color:{color};font-weight:bold;'
                f'padding:4px 10px;margin-top:8px;font-size:12px;">'
                f'{self._escape_html(title)}</div>')

    def _escape_html(self, text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _compute_line_diff(self, old_content: str, new_content: str) -> list[tuple[str, str]]:
        import difflib
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()
        diffs: list[tuple[str, str]] = []
        sm = difflib.SequenceMatcher(None, old_lines, new_lines)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "replace":
                for old_l, new_l in zip(old_lines[i1:i2], new_lines[j1:j2]):
                    diffs.append((old_l.strip(), new_l.strip()))
                if i2 - i1 > j2 - j1:
                    for old_l in old_lines[i1 + (j2 - j1):i2]:
                        diffs.append((old_l.strip(), ""))
                elif j2 - j1 > i2 - i1:
                    for new_l in new_lines[j1 + (i2 - i1):j2]:
                        diffs.append(("", new_l.strip()))
            elif tag == "insert":
                for new_l in new_lines[j1:j2]:
                    diffs.append(("", new_l.strip()))
            elif tag == "delete":
                for old_l in old_lines[i1:i2]:
                    diffs.append((old_l.strip(), ""))
        # 兜底：splitlines 后相同但字符串不同，说明只是换行符/末尾空白差异
        if not diffs and old_content != new_content:
            diffs.append(("（仅换行符/空白差异）", "（已规范化）"))
        return diffs

    def _highlight_diff(self, old_line: str, new_line: str, is_old: bool) -> str:
        import re
        import difflib

        def tokenize(line: str) -> list[str]:
            return re.split(r'([=,;\s]+)', line)

        old_tokens = tokenize(old_line)
        new_tokens = tokenize(new_line)

        sm = difflib.SequenceMatcher(None, old_tokens, new_tokens)
        parts = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                tokens = old_tokens[i1:i2] if is_old else new_tokens[j1:j2]
                parts.append(f'<span style="color:#888;">{self._escape_html("".join(tokens))}</span>')
            elif tag == "replace":
                tokens = old_tokens[i1:i2] if is_old else new_tokens[j1:j2]
                text = "".join(tokens)
                parts.append(f'<span style="color:red;font-weight:bold;">{self._escape_html(text)}</span>')
            elif tag == "insert" and not is_old:
                text = "".join(new_tokens[j1:j2])
                parts.append(f'<span style="color:green;font-weight:bold;">{self._escape_html(text)}</span>')
            elif tag == "delete" and is_old:
                text = "".join(old_tokens[i1:i2])
                parts.append(f'<span style="color:#888;text-decoration:line-through;">{self._escape_html(text)}</span>')

        return "".join(parts)

    def _on_queue_build_requested(self, queue_id: str) -> None:
        """卡片「开始编译」：单个编译，完成后停止。"""
        self._start_queue_build(queue_id, auto_chain=False)

    def _on_build_all(self) -> None:
        """「全部开始编译」：依次串行，成功后自动接下一个。"""
        pending = self._build_queue.get_pending()
        if not pending:
            return
        self._start_queue_build(pending[0].id, auto_chain=True)

    def _start_queue_build(self, queue_id: str, auto_chain: bool = False) -> None:
        try:
            self._auto_chain = auto_chain
            self._logger.info("=== _start_queue_build: %s (auto_chain=%s) ===", queue_id, auto_chain)
            item = self._build_queue.get_by_id(queue_id)
            if not item:
                self._logger.error("队列项不存在: %s", queue_id)
                return
            
            self._logger.info("从队列开始编译: %s", item.customer_name)
            
            # 检查同一项目（code 目录）是否已在编译
            # 提取项目名：/home/user/352_AN12_MP3/code/... -> 352_AN12_MP3
            def _extract_proj_name(path):
                parts = [p for p in path.replace('/', ' ').split() if p]
                if 'code' in parts:
                    idx = parts.index('code')
                    if idx > 0:
                        return parts[idx - 1]
                return ''
            
            cur_proj = _extract_proj_name(item.project_path)
            all_items = self._build_queue.get_all()
            for qi in all_items:
                if qi.id != queue_id and qi.status.value == "building":
                    qi_proj = _extract_proj_name(qi.project_path)
                    if cur_proj and qi_proj == cur_proj:
                        self._logger.warning("同一项目已在编译: %s", qi.customer_name)
                        from PySide6.QtWidgets import QMessageBox
                        self._styled_msg_box(
                            QMessageBox.Icon.Warning, "编译冲突",
                            f"项目 [{cur_proj}] 正在被 [{qi.customer_name}] 编译中，请等待完成后再试。"
                        ).exec()
                        return
            
            # 检查是否已有编译任务在运行
            handle = self._build_service.current_handle()
            if handle and handle.is_running():
                self._build_log.append("[编译] 已有编译任务在运行")
                return
            
            # 更新队列状态
            self._build_queue.update_status(queue_id, "building")
            self._logger.info("队列状态已更新")
            
            # 切换到编译页面
            self._switch_mode(4)
            self._build_status_label.setText(f"正在编译: {item.project_path}")
            self._build_log.clear()
            self._build_log.append(f"[编译] 客户: {item.customer_name}")
            self._build_log.append(f"[编译] 路径: {item.project_path}")
            self._cancel_build_btn.setEnabled(True)
            self._build_done = False
            self._current_build_queue_id = queue_id
            
            # 设置日志回调
            def on_log(text):
                self._log_emitter.log_received.emit(text)
            self._build_service.set_callbacks(
                on_log=on_log,
                on_finished=lambda status, code: self._log_emitter.finished.emit(status, code),
            )
            
            # 提交编译
            build_cmd = self._build_default_compile_command(target_path=item.project_path)
            # 同步编译命令输入框，让用户看到实际执行的命令
            if hasattr(self, "_build_cmd_input"):
                self._build_cmd_input.setText(build_cmd)
            self._logger.info("提交编译: %s", build_cmd)
            build_job = self._build_service.submit(item.project_path, command=build_cmd)
            self._build_queue.update_status(queue_id, "building", task_id=build_job.task_id)
            self._build_log.append(f"[编译] 任务ID: {build_job.task_id}")
            self._logger.info("编译已提交: %s", build_job.task_id)
        except Exception as e:
            self._logger.error("编译启动失败: %s", e, exc_info=True)
            self._build_log.append(f"[错误] {e}")

    def on_run(self) -> None:
        self._on_analyze()
