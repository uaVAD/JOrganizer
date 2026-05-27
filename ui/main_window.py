import logging
import re
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTreeWidget, QTreeWidgetItem, QTextEdit,
    QPushButton, QLabel, QFileDialog, QGroupBox,
    QLineEdit, QProgressBar, QMessageBox, QHeaderView,
    QTabWidget, QComboBox, QDialog, QApplication, QAbstractItemView,
    QScrollArea, QTreeWidgetItemIterator,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QObject, QEvent, QSize
from PyQt6.QtGui import QFont, QColor, QIcon

from config.settings import COLORS, DB_PATH, BASE_DIR
from core.controller import AppController
from database import Database
from core.translator import Translator

logger = logging.getLogger(__name__)


class OperationThread(QThread):
    progress = pyqtSignal(int, int)
    log = pyqtSignal(str)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, preview, operations_manager, force=False):
        super().__init__()
        self.preview = preview
        self.operations_manager = operations_manager
        self.force = force

    def run(self):
        try:
            results = self.operations_manager.execute(self.preview, self.force)
            self.finished.emit(results)
        except Exception as e:
            logger.error(f"Operation failed: {e}")
            self.error.emit(str(e))


class _StretchFilter(QObject):
    def __init__(self, dialog, header, stretch_cols, arrow=2):
        super().__init__(dialog)
        self._h = header
        self._cols = stretch_cols
        self._arrow = arrow
        self._h.setStretchLastSection(False)
        dialog.installEventFilter(self)
        QTimer.singleShot(0, self._restretch)

    def _restretch(self):
        avail = self._h.width() - self._h.sectionSize(self._arrow)
        total = sum(self._h.sectionSize(i) for i in self._cols)
        if total > 0:
            r = avail / total
            for i in self._cols:
                self._h.resizeSection(i, max(80, int(self._h.sectionSize(i) * r)))

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Resize:
            self._restretch()
        return super().eventFilter(obj, event)


class MainWindow(QMainWindow):
    TYPE_COLORS = {
        'movie': '#10B981',
        'tv': '#7C3AED',
        'anime': '#F59E0B',
        'cartoon': '#EC4899',
        'unknown': '#6B7280',
    }

    CATEGORY_KEYS = ['anime', 'cartoon', 'movie', 'tv']
    CATEGORY_LABELS = ['Anime', 'Cartoons', 'Movies', 'TV Shows']

    TYPE_OPTIONS = ['movie', 'tv', 'anime', 'cartoon']

    def __init__(self):
        super().__init__()
        self.setMinimumSize(1200, 800)
        self._db = Database(DB_PATH)
        self._init_user_languages()
        self.tr = Translator(
            Path(__file__).parent.parent / 'languages',
            BASE_DIR / 'languages'
        )
        self.ctrl = AppController(self._db)
        self.selected_files = []
        self.dry_run_preview = []
        self.operation_thread = None
        self._tree_data = None
        self._type_overrides: dict[str, str] = {}
        self._category_dest = {k: '' for k in self.CATEGORY_KEYS}
        self._init_ui()
        icon_path = Path(__file__).parent.parent / 'assets' / 'JO.ico'
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self._load_settings()
        self._apply_translations()
        self._apply_stylesheet()
        self._auto_save_timer = QTimer(self)
        self._auto_save_timer.timeout.connect(self._save_settings)
        self._auto_save_timer.start(30000)

    def _init_user_languages(self):
        user_lang_dir = BASE_DIR / 'languages'
        if not user_lang_dir.exists():
            user_lang_dir.mkdir(parents=True)
            builtin_dir = Path(__file__).parent.parent / 'languages'
            if builtin_dir.exists():
                for f in builtin_dir.glob('*.json'):
                    import shutil
                    shutil.copy2(str(f), str(user_lang_dir / f.name))
                self._log(f'Default languages copied to {user_lang_dir}')

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 2)
        main_layout.setSpacing(2)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._create_left_panel(splitter)
        self._create_center_panel(splitter)
        main_layout.addWidget(splitter)
        self._create_bottom_panel(main_layout)
        splitter.setSizes([400, 800])

    def _create_left_panel(self, splitter):
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(5, 5, 5, 5)
        self.tabs = QTabWidget()
        self._add_source_tab(self.tabs)
        self._add_settings_tab(self.tabs)
        self._add_lang_tab(self.tabs)
        self.tabs.setCurrentIndex(0)
        left_layout.addWidget(self.tabs)
        self._log_group = QGroupBox('Logs')
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont('Consolas', 9))
        log_layout.addWidget(self.log_text)
        self._clear_log_btn = QPushButton('Clear Logs')
        self._clear_log_btn.clicked.connect(self.log_text.clear)
        log_layout.addWidget(self._clear_log_btn)
        self._log_group.setLayout(log_layout)
        left_layout.addWidget(self._log_group)
        splitter.addWidget(left_widget)

    def _add_settings_tab(self, tabs):
        outer = QWidget()
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(4, 2, 4, 4)
        self._categories_group = QGroupBox('Categories')
        settings_layout = QVBoxLayout(self._categories_group)
        settings_layout.setContentsMargins(8, 4, 8, 8)
        settings_layout.setSpacing(12)
        self._dest_inputs = {}
        self._dest_browse_btns = {}
        for key, label in zip(self.CATEGORY_KEYS, self.CATEGORY_LABELS):
            input_widget = QLineEdit()
            input_widget.setPlaceholderText(f'Select {label} folder...')
            input_widget.setReadOnly(True)
            self._dest_inputs[key] = input_widget
            browse_btn = QPushButton(f'{label} Folder...')
            browse_btn.clicked.connect(lambda checked, k=key: self._browse_category(k))
            browse_btn.setFixedHeight(32)
            self._dest_browse_btns[key] = browse_btn
            group_widget = QWidget()
            group_layout = QVBoxLayout(group_widget)
            group_layout.setContentsMargins(0, 0, 0, 0)
            group_layout.setSpacing(4)
            group_layout.addWidget(input_widget)
            group_layout.addWidget(browse_btn)
            settings_layout.addWidget(group_widget)
        settings_layout.addStretch()
        outer_layout.addWidget(self._categories_group)

        # watch_group = QGroupBox('Watch Folder')
        # watch_layout = QVBoxLayout(watch_group)
        # watch_layout.setContentsMargins(8, 4, 8, 8)
        # watch_layout.setSpacing(8)
        # self.watch_input = QLineEdit()
        # self.watch_input.setPlaceholderText('Select folder to watch...')
        # self.watch_input.setReadOnly(True)
        # watch_layout.addWidget(self.watch_input)
        # watch_browse_row = QHBoxLayout()
        # browse_watch_btn = QPushButton('Browse Watch Folder...')
        # browse_watch_btn.clicked.connect(self._browse_watch_folder)
        # browse_watch_btn.setFixedHeight(32)
        # watch_browse_row.addWidget(browse_watch_btn)
        # watch_layout.addLayout(watch_browse_row)
        # watch_status_row = QHBoxLayout()
        # self.watch_status_label = QLabel('Stopped')
        # self.watch_status_label.setStyleSheet(f'color: {COLORS["warning"]};')
        # watch_status_row.addWidget(self.watch_status_label)
        # watch_status_row.addStretch()
        # self.start_watch_btn = QPushButton('Start Watch')
        # self.start_watch_btn.clicked.connect(self._start_auto_watch)
        # self.start_watch_btn.setFixedHeight(32)
        # watch_status_row.addWidget(self.start_watch_btn)
        # self.stop_watch_btn = QPushButton('Stop Watch')
        # self.stop_watch_btn.clicked.connect(self._stop_auto_watch)
        # self.stop_watch_btn.setFixedHeight(32)
        # self.stop_watch_btn.setEnabled(False)
        # watch_status_row.addWidget(self.stop_watch_btn)
        # watch_layout.addLayout(watch_status_row)
        # outer_layout.addWidget(watch_group)

        tabs.addTab(outer, 'Destination Folders')

    def _add_source_tab(self, tabs):
        t = self.tr.tr
        project_dir = Path(__file__).parent.parent
        outer = QWidget()
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(4, 2, 4, 4)
        self._source_group = QGroupBox('Source')
        source_layout = QVBoxLayout(self._source_group)
        source_layout.setContentsMargins(8, 4, 8, 8)
        source_layout.setSpacing(8)
        browse_row = QHBoxLayout()
        browse_row.setContentsMargins(0, 0, 0, 0)
        browse_row.setSpacing(3)
        self.source_input = QLineEdit()
        self.source_input.setPlaceholderText('Click Browse to select folder...')
        self.source_input.setReadOnly(True)
        self.source_input.setFixedHeight(32)
        browse_row.addWidget(self.source_input, 1)
        self._source_browse_btn = QPushButton('Browse')
        self._source_browse_btn.clicked.connect(self._browse_source)
        self._source_browse_btn.setFixedHeight(32)
        self._source_browse_btn.setToolTip(t('hint.browse'))
        browse_row.addWidget(self._source_browse_btn)
        source_layout.addLayout(browse_row)
        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(6)
        self.scan_btn = QPushButton('Analyze Folder')
        self.scan_btn.clicked.connect(self._scan_source)
        self.scan_btn.setFixedHeight(36)
        self.scan_btn.setToolTip(t('hint.analyze'))
        action_row.addWidget(self.scan_btn, 1)
        self.refresh_scan_btn = QPushButton()
        self.refresh_scan_btn.setIcon(QIcon(str(project_dir / 'assets' / 'refresh.svg')))
        self.refresh_scan_btn.clicked.connect(self._refresh_scan)
        self.refresh_scan_btn.setEnabled(False)
        self.refresh_scan_btn.setFixedSize(36, 36)
        self.refresh_scan_btn.setToolTip(t('hint.refresh'))
        action_row.addWidget(self.refresh_scan_btn)
        source_layout.addLayout(action_row)
        source_layout.addStretch()
        outer_layout.addWidget(self._source_group)
        tabs.addTab(outer, 'Scan')

    def _add_lang_tab(self, tabs):
        t = self.tr.tr
        outer = QWidget()
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(4, 2, 4, 4)
        self._settings_group = QGroupBox(t('ui.tab_settings'))
        tab_layout = QVBoxLayout(self._settings_group)
        tab_layout.setContentsMargins(8, 4, 8, 8)
        tab_layout.setSpacing(8)
        lang_label = QLabel(t('ui.language'))
        tab_layout.addWidget(lang_label)
        self._lang_combo = QComboBox()
        self._lang_combo.setFixedHeight(32)
        for code, name in self.tr.available_languages():
            self._lang_combo.addItem(f'{name} ({code})', code)
        idx = self._lang_combo.findData(self.tr.current_lang)
        if idx >= 0:
            self._lang_combo.setCurrentIndex(idx)
        self._lang_combo.currentIndexChanged.connect(self._on_language_changed)
        self._lang_combo.setToolTip(t('hint.lang'))
        tab_layout.addWidget(self._lang_combo)
        api_label = QLabel(t('ui.api_keys'))
        tab_layout.addWidget(api_label)
        self._tmdb_key_input = QLineEdit()
        self._tmdb_key_input.setPlaceholderText(t('ui.tmdb_placeholder'))
        self._tmdb_key_input.setToolTip(t('hint.tmdb_key'))
        tab_layout.addWidget(self._tmdb_key_input)
        self._apply_save_btn = QPushButton(t('ui.apply_save'))
        self._apply_save_btn.clicked.connect(self._validate_tmdb_key)
        self._apply_save_btn.setFixedHeight(32)
        self._apply_save_btn.setToolTip(t('hint.apply_save'))
        tab_layout.addWidget(self._apply_save_btn)
        self._tmdb_status_label = QLabel()
        tab_layout.addWidget(self._tmdb_status_label)
        tab_layout.addStretch()
        outer_layout.addWidget(self._settings_group)
        tabs.addTab(outer, 'Settings')

    def _validate_tmdb_key(self):
        t = self.tr.tr
        key = self._tmdb_key_input.text().strip()
        if not key:
            self._tmdb_status_label.setText(t('ui.key_empty'))
            self._tmdb_status_label.setStyleSheet(f'color: {COLORS["warning"]};')
            return
        import requests as req
        try:
            resp = req.get(f'https://api.themoviedb.org/3/configuration?api_key={key}', timeout=10)
            if resp.status_code == 200:
                import config.settings as csettings
                csettings.TMDB_API_KEY = key
                self.ctrl.detector.api_detector.tmdb_key = key
                self._tmdb_status_label.setText(t('ui.key_valid'))
                self._tmdb_status_label.setStyleSheet(f'color: {COLORS["success"]};')
                self._save_settings()
                self._log('TMDB API key validated and saved')
            else:
                self._tmdb_status_label.setText(t('ui.key_invalid'))
                self._tmdb_status_label.setStyleSheet(f'color: {COLORS["error"]};')
        except Exception as e:
            self._tmdb_status_label.setText(t('ui.key_failed').format(str(e)))
            self._tmdb_status_label.setStyleSheet(f'color: {COLORS["error"]};')

    def _on_language_changed(self, index):
        code = self._lang_combo.itemData(index)
        if code and code != self.tr.current_lang:
            self.tr.set_language(code)
            self._apply_translations()
            self._save_settings()
            self._log(f'Language changed to: {code}')

    def _apply_translations(self):
        t = self.tr.tr
        from config.settings import VERSION
        self.setWindowTitle(f"JOrganizer {VERSION}")
        self.tabs.setTabText(0, t('ui.tab_scan'))
        self.tabs.setTabText(1, t('ui.tab_dest_folders'))
        self.tabs.setTabText(2, t('ui.tab_settings'))
        self._source_group.setTitle(t('ui.source'))
        self._categories_group.setTitle(t('ui.categories'))
        self._log_group.setTitle(t('ui.logs'))
        self._source_browse_btn.setText(t('ui.browse'))
        self._clear_log_btn.setText(t('ui.clear_logs'))
        self.scan_btn.setText(t('ui.analyze_folder'))
        self._settings_group.setTitle(t('ui.tab_settings'))
        self.preview_btn.setText(t('ui.preview_changes'))
        self.execute_btn.setText(t('ui.rename_move'))
        self.undo_btn.setText(t('ui.undo_last'))
        for key, label in zip(self.CATEGORY_KEYS, self.CATEGORY_LABELS):
            folder_key = f'ui.folder_{key}'
            self._dest_browse_btns[key].setText(f'{t(folder_key)}...')
            self._dest_inputs[key].setPlaceholderText(t('ui.dest_placeholder').format(label))
        self.source_input.setPlaceholderText(t('ui.source_placeholder'))
        self.file_tree.headerItem().setText(0, t('ui.tree_name'))
        self.file_tree.headerItem().setText(1, t('ui.tree_type'))
        self._tmdb_key_input.setPlaceholderText(t('ui.tmdb_placeholder'))
        self._apply_save_btn.setText(t('ui.apply_save'))
        self._source_browse_btn.setToolTip(t('hint.browse'))
        self.scan_btn.setToolTip(t('hint.analyze'))
        self.refresh_scan_btn.setToolTip(t('hint.refresh'))
        self._lang_combo.setToolTip(t('hint.lang'))
        self._apply_save_btn.setToolTip(t('hint.apply_save'))
        self._tmdb_key_input.setToolTip(t('hint.tmdb_key'))
        self.preview_btn.setToolTip(t('hint.preview'))
        self.execute_btn.setToolTip(t('hint.execute'))
        self.undo_btn.setToolTip(t('hint.undo'))
        for key, label in zip(self.CATEGORY_KEYS, self.CATEGORY_LABELS):
            self._dest_browse_btns[key].setToolTip(t('hint.browse_dest').format(label))

    def _create_center_panel(self, splitter):
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(5, 5, 5, 5)
        header = QHBoxLayout()
        self.folder_count_label = QLabel('Folders: 0')
        header.addWidget(self.folder_count_label)
        self.file_count_label = QLabel('Files: 0')
        self.file_count_label.setStyleSheet(f'color: {COLORS["warning"]};')
        header.addWidget(self.file_count_label)
        header.addStretch()
        center_layout.addLayout(header)
        self.file_tree = QTreeWidget()
        self.file_tree.setColumnCount(2)
        self.file_tree.setHeaderLabels(['Name', 'Type'])
        self.file_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.file_tree.setAlternatingRowColors(True)
        self.file_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.file_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.file_tree.itemSelectionChanged.connect(self._on_tree_selection)
        center_layout.addWidget(self.file_tree)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        center_layout.addWidget(self.progress_bar)
        action_layout = QHBoxLayout()
        project_dir = Path(__file__).parent.parent
        icon_preview = QIcon(str(project_dir / 'assets' / 'preview.svg'))
        icon_rename = QIcon(str(project_dir / 'assets' / 'rename.svg'))
        icon_undo = QIcon(str(project_dir / 'assets' / 'undo.svg'))

        self.preview_btn = QPushButton(icon_preview, 'Preview Changes')
        self.preview_btn.clicked.connect(self._start_preview)
        self.preview_btn.setFixedHeight(32)
        action_layout.addWidget(self.preview_btn)
        self.execute_btn = QPushButton(icon_rename, 'Rename && Move')
        self.execute_btn.clicked.connect(self._start_execution)
        self.execute_btn.setEnabled(False)
        self.execute_btn.setFixedHeight(32)
        action_layout.addWidget(self.execute_btn)
        self.undo_btn = QPushButton(icon_undo, 'Undo Last')
        self.undo_btn.clicked.connect(self._undo_last)
        self.undo_btn.setEnabled(False)
        self.undo_btn.setFixedHeight(32)
        action_layout.addWidget(self.undo_btn)
        center_layout.addLayout(action_layout)
        splitter.addWidget(center_widget)



    def _create_bottom_panel(self, main_layout):
        status_bar = QWidget()
        status_bar.setObjectName('statusBar')
        status_bar.setFixedHeight(32)
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(10, 2, 10, 2)
        status_layout.setSpacing(10)
        self.status_label = QLabel('Ready')
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        self.memory_label = QLabel('Memory: 0 MB')
        self.memory_label.setStyleSheet(f'color: {COLORS["warning"]};')
        status_layout.addWidget(self.memory_label)
        main_layout.addWidget(status_bar)

    def _apply_stylesheet(self):
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {COLORS['background']};
            }}
            QGroupBox {{
                color: #E5E7EB;
                border: 1px solid #374151;
                border-radius: 4px;
                margin-top: 8px;
                padding: 2px 4px 2px 4px;
                padding-top: 14px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #9CA3AF;
            }}
            QPushButton {{
                background-color: {COLORS['accent']};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: #6D28D9;
            }}
            QPushButton:disabled {{
                background-color: #4B5563;
            }}
            QLineEdit {{
                background-color: {COLORS['panel']};
                color: #E5E7EB;
                border: 1px solid #374151;
                border-radius: 3px;
                padding: 5px;
            }}
            QTextEdit {{
                background-color: {COLORS['panel']};
                color: #E5E7EB;
                border: 1px solid #374151;
                border-radius: 3px;
            }}
            QTreeWidget {{
                background-color: {COLORS['panel']};
                color: #E5E7EB;
                border: 1px solid #374151;
                alternate-background-color: #1E293B;
            }}
            QHeaderView::section {{
                background-color: {COLORS['panel']};
                color: #9CA3AF;
                padding: 5px;
                border: 1px solid #374151;
            }}
            QTabWidget::pane {{
                background-color: {COLORS['background']};
                border: 1px solid #374151;
                border-radius: 5px;
            }}
            QTabBar::tab {{
                background-color: {COLORS['panel']};
                color: #9CA3AF;
                padding: 8px 16px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
            }}
            QTabBar::tab:selected {{
                background-color: {COLORS['accent']};
                color: white;
            }}
            QProgressBar {{
                border: 1px solid #374151;
                border-radius: 5px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {COLORS['accent']};
                border-radius: 4px;
            }}
            #statusBar {{
                background-color: #0F172A;
                border-top: 1px solid #1F2937;
            }}
        """)

    def _log(self, message):
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.append(f'[{timestamp}] {message}')

    def _browse_category(self, category_key: str):
        label = self.CATEGORY_LABELS[self.CATEGORY_KEYS.index(category_key)]
        folder = QFileDialog.getExistingDirectory(self, f'{self.tr.tr("ui.dlg_select_source")} - {label}')
        if folder:
            self._dest_inputs[category_key].setText(folder)
            self._category_dest[category_key] = folder
            self._update_organizer()
            self._log(f'{label} set to: {folder}')

    def _update_organizer(self):
        dirs = {}
        for key in self.CATEGORY_KEYS:
            path_str = self._dest_inputs[key].text()
            if path_str:
                dirs[key] = Path(path_str)
        self.ctrl.set_category_dirs(dirs)
        self._update_execute_button()

    def _browse_watch_folder(self):
        folder = QFileDialog.getExistingDirectory(self, 'Select Watch Folder')
        if folder:
            self.watch_input.setText(folder)
            self._log(f'Watch folder set to: {folder}')

    def _browse_source(self):
        folder = QFileDialog.getExistingDirectory(self, self.tr.tr('ui.dlg_select_source'))
        if folder:
            self.source_input.setText(folder)
            self._log(f'Source set to: {folder}')

    def _scan_source(self):
        folder = self.source_input.text()
        if not folder:
            folder = QFileDialog.getExistingDirectory(self, 'Select Source Folder')
            if not folder:
                return
            self.source_input.setText(folder)
        t = self.tr.tr
        self._log(f'Analyzing: {folder}')
        self.status_label.setText(t('ui.status_analyzing'))
        self.progress_bar.setVisible(True)
        QApplication.processEvents()
        try:
            self._tree_data = self.ctrl.analyze_folder(Path(folder), self._on_scan_progress)
            self._populate_tree(self._tree_data)
            folder_count = len(self._tree_data.get('children', []))
            file_count = self._count_files()
            self.folder_count_label.setText(f'{t("ui.folders")}: {folder_count}')
            self.file_count_label.setText(f'{t("ui.files")}: {file_count}')
            self.refresh_scan_btn.setEnabled(True)
            self._log(f'Found {folder_count} media folders, {file_count} files')
        except Exception as e:
            self._log(f'Analysis failed: {e}')
            QMessageBox.critical(self, t('ui.dlg_error'), t('ui.msg_analysis_failed').format(str(e)))
        finally:
            self.progress_bar.setVisible(False)
            self.status_label.setText(t('ui.status_ready'))
        self._save_settings()

    def _on_scan_progress(self, percent, name):
        self.progress_bar.setValue(percent)
        self.status_label.setText(self.tr.tr('ui.status_analyzing_name').format(name))
        QApplication.processEvents()

    def _populate_tree(self, tree_data):
        self.file_tree.clear()
        root_path = tree_data['path']
        root_item = QTreeWidgetItem(self.file_tree)
        root_item.setText(0, str(root_path))
        root_item.setText(1, self.tr.tr('ui.tree_source'))
        root_item.setData(0, Qt.ItemDataRole.UserRole, str(root_path))
        root_item.setExpanded(True)
        font = root_item.font(0)
        font.setBold(True)
        root_item.setFont(0, font)

        for folder in tree_data.get('children', []):
            self._add_tree_node(root_item, folder)

    def _add_tree_node(self, parent, node):
        """Recursively build tree: category nodes (with children) or folder nodes (with files)."""
        mtype = node['media_type']
        display_name = node['name']
        folder_path = str(node['path'])

        item = QTreeWidgetItem(parent)
        item.setText(0, display_name)
        item.setData(0, Qt.ItemDataRole.UserRole, folder_path)
        item.setData(1, Qt.ItemDataRole.UserRole, 'folder')
        children = node.get('children')

        if children:
            item.setExpanded(True)
            type_label = mtype.upper() if mtype != 'unknown' else 'UNKNOWN [TMDB: N/A]'
            item.setText(1, type_label)
            color = self.TYPE_COLORS.get(mtype, '#6B7280')
            item.setForeground(1, QColor(color))
            for child in children:
                self._add_tree_node(item, child)
            return

        item.setExpanded(False)
        # Leaf folder node — add type dropdown
        combo = QComboBox()
        for t in self.TYPE_OPTIONS:
            combo.addItem(t.upper(), t)
        idx = combo.findData(mtype)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        item.setSizeHint(1, QSize(0, 28))
        self.file_tree.setItemWidget(item, 1, combo)
        combo.currentIndexChanged.connect(lambda i, p=folder_path, c=combo: self._on_folder_type_changed(p, c))
        color = self.TYPE_COLORS.get(mtype, '#6B7280')
        combo.setStyleSheet(f'QComboBox {{ color: {color}; background-color: transparent; border: none; font-weight: bold; }} QComboBox::drop-down {{ border: none; width: 16px; }} QComboBox QAbstractItemView {{ background-color: {COLORS["panel"]}; color: white; selection-background-color: {COLORS["accent"]}; }}')

        # Folder nodes with direct files
        font = item.font(0)
        font.setBold(True)
        item.setFont(0, font)

        for f in node.get('files', []):
            file_item = QTreeWidgetItem(item)
            file_item.setText(0, f['name'])
            file_item.setData(0, Qt.ItemDataRole.UserRole, str(f['path']))
            file_item.setData(1, Qt.ItemDataRole.UserRole, 'file')
            file_item.setData(2, Qt.ItemDataRole.UserRole, f.get('size', 0))

            if f.get('season') is not None and f.get('episode') is not None:
                file_item.setText(1, f"S{int(f['season']):02d}E{int(f['episode']):02d}")
            else:
                file_item.setText(1, mtype.upper())

            file_item.setForeground(1, QColor(self.TYPE_COLORS.get(mtype, '#6B7280')))

    def _refresh_scan(self):
        if not self._tree_data:
            return
        folder = self._tree_data['path']
        if not Path(folder).exists():
            QMessageBox.warning(self, self.tr.tr('ui.dlg_warning'), self.tr.tr('ui.msg_source_missing'))
            return
        self.source_input.setText(str(folder))
        self._scan_source()

    def _format_size(self, size_bytes):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f'{size_bytes:.1f} {unit}'
            size_bytes /= 1024.0
        return f'{size_bytes:.1f} PB'

    def _on_tree_selection(self):
        QTimer.singleShot(150, self._collect_selected_files)

    def _collect_selected_files(self):
        items = self.file_tree.selectedItems()
        paths = []
        total_bytes = 0
        for item in items:
            item_type = item.data(1, Qt.ItemDataRole.UserRole)
            path_str = item.data(0, Qt.ItemDataRole.UserRole)
            if not path_str:
                continue
            if item_type == 'file':
                paths.append(Path(path_str))
                total_bytes += item.data(2, Qt.ItemDataRole.UserRole) or 0
            elif item_type == 'folder':
                paths, total_bytes = self._collect_files_from_item(item, paths, total_bytes)

        self.selected_files = list(set(paths))
        self._update_execute_button()
        self.status_label.setText(self.tr.tr('ui.status_selected').format(len(self.selected_files)))
        self.memory_label.setText(f'{self.tr.tr("ui.memory")}: {self._format_size(total_bytes)}')

    def _update_execute_button(self):
        has_dest = any(p for p in self._category_dest.values())
        self.execute_btn.setEnabled(bool(self.selected_files and has_dest))

    def _collect_files_from_item(self, item, paths, total_bytes=0):
        for i in range(item.childCount()):
            child = item.child(i)
            child_type = child.data(1, Qt.ItemDataRole.UserRole)
            child_path = child.data(0, Qt.ItemDataRole.UserRole)
            if child_type == 'file' and child_path:
                paths.append(Path(child_path))
                total_bytes += child.data(2, Qt.ItemDataRole.UserRole) or 0
            else:
                paths, total_bytes = self._collect_files_from_item(child, paths, total_bytes)
        return paths, total_bytes

    def _on_folder_type_changed(self, folder_path: str, combo: QComboBox):
        """Handle manual type override from tree dropdown."""
        new_type = combo.currentData()
        if not new_type:
            return
        old_type = self._type_overrides.get(folder_path)
        if old_type == new_type:
            return
        self._type_overrides[folder_path] = new_type
        self._log(f'Type override: {Path(folder_path).name} -> {new_type}')

        # Update node in _tree_data
        self._update_node_type(folder_path, new_type)

        # Update combo text color
        new_color = self.TYPE_COLORS.get(new_type, '#6B7280')
        combo.setStyleSheet(f'QComboBox {{ color: {new_color}; background-color: transparent; border: none; font-weight: bold; }} QComboBox::drop-down {{ border: none; width: 16px; }} QComboBox QAbstractItemView {{ background-color: {COLORS["panel"]}; color: white; selection-background-color: {COLORS["accent"]}; }}')

        # Re-color child file items
        self._recolor_folder_files(folder_path, new_type)

    def _update_node_type(self, folder_path: str, new_type: str):
        """Recursively update media_type in _tree_data for the given folder path."""
        if not self._tree_data:
            return

        def walk(nodes):
            for node in nodes:
                if str(node['path']) == folder_path:
                    node['media_type'] = new_type
                    for f in node.get('files', []):
                        f['type'] = new_type
                    return True
                if walk(node.get('children', [])):
                    return True
            return False

        walk([self._tree_data])

    def _recolor_folder_files(self, folder_path: str, new_type: str):
        """Update the color of all file items under the given folder."""
        color = self.TYPE_COLORS.get(new_type, '#6B7280')
        for i in range(self.file_tree.topLevelItemCount()):
            root = self.file_tree.topLevelItem(i)
            self._recolor_item_recursive(root, folder_path, color, new_type)

    def _recolor_item_recursive(self, item, folder_path: str, color, new_type: str):
        if item.data(0, Qt.ItemDataRole.UserRole) == folder_path:
            for ci in range(item.childCount()):
                child = item.child(ci)
                if child.data(1, Qt.ItemDataRole.UserRole) == 'file':
                    child.setForeground(1, QColor(color))
                    child.setText(1, new_type.upper())
            return
        for ci in range(item.childCount()):
            self._recolor_item_recursive(item.child(ci), folder_path, color, new_type)

    SUBFOLDER_RX = re.compile(r'^(?:Season|Saison|Temporada|Volume|Vol)\s*\d{1,2}$|^Specials?$', re.IGNORECASE)

    def _get_type_for_folder(self, folder_path: str) -> str | None:
        """Get media_type for a folder path from _tree_data (respects overrides)."""
        path = Path(folder_path)
        if self.SUBFOLDER_RX.match(path.name):
            path = path.parent

        fp_str = str(path)
        override = self._type_overrides.get(fp_str)
        if override:
            return override
        root = self._tree_data
        if not root:
            return None

        def find(nodes):
            for n in nodes:
                np = n.get('path')
                if np and str(np) == fp_str:
                    mt = n.get('media_type')
                    if mt and mt != 'unknown':
                        return mt
                    return None
                kids = n.get('children')
                if kids:
                    result = find(kids)
                    if result:
                        return result
            return None

        return find([root])

    def _apply_type_overrides(self, preview: list[dict]) -> list[dict]:
        """Apply folder types from tree (auto + manual override) to preview results."""
        for item in preview:
            src = item.get('source', '')
            if not src:
                continue
            parent = str(Path(src).parent)
            new_type = self._get_type_for_folder(parent)
            if not new_type:
                continue
            det = item.get('detection')
            if not det:
                continue
            if det.get('type') == new_type:
                continue
            det['type'] = new_type
            item['type'] = new_type
            if self.ctrl.renamer and self.ctrl.organizer:
                new_name = self.ctrl.renamer.generate_new_filename(det, src)
                new_target = self.ctrl.organizer.get_target_path(det, new_name)
                item['dest'] = str(new_target)
                item['target'] = str(new_target)
        return preview

    def _start_preview(self):
        t = self.tr.tr
        if not self.selected_files:
            QMessageBox.warning(self, t('ui.dlg_warning'), t('ui.msg_select_files'))
            return
        if not self.ctrl.organizer:
            QMessageBox.warning(self, t('ui.dlg_warning'), t('ui.msg_set_dest'))
            return
        dest = next((Path(p) for p in self._category_dest.values() if p), Path())
        self.dry_run_preview = self.ctrl.preview(self.selected_files, dest)
        self._apply_type_overrides(self.dry_run_preview)
        self._log(f'Preview: {len(self.dry_run_preview)} actions previewed')
        self.execute_btn.setEnabled(True)
        self._show_preview_dialog()

    def _show_preview_dialog(self):
        t = self.tr.tr
        from PyQt6.QtCore import QSettings
        settings = QSettings('JOrganizer', 'JOrganizer')
        dialog = QDialog(self)
        dialog.setWindowTitle(t('ui.preview_changes'))
        dialog.setMinimumSize(900, 450)
        geo = settings.value('preview_geometry')
        if geo:
            dialog.restoreGeometry(geo)
        else:
            dialog.resize(1000, 500)
        layout = QVBoxLayout(dialog)

        table = QTreeWidget()
        table.setColumnCount(5)
        table.setHeaderLabels([t('ui.preview_source'), t('ui.preview_name'), '', t('ui.preview_dest'), t('ui.preview_rename')])
        table.setAlternatingRowColors(True)
        header = table.header()
        for i in (0, 1, 3, 4):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(2, 30)
        _StretchFilter(dialog, header, (0, 1, 3, 4))
        table.setRootIsDecorated(False)
        table.setSortingEnabled(True)

        for action in self.dry_run_preview:
            src_path = Path(action.get('source', ''))
            dst_path = Path(action.get('dest', ''))
            item = QTreeWidgetItem(table)
            item.setText(0, str(src_path.parent))
            item.setText(1, src_path.name)
            item.setText(2, '→')
            item.setText(3, str(dst_path.parent))
            item.setText(4, dst_path.name)
            item.setForeground(2, QColor(COLORS['success']))
            if not action.get('dest'):
                item.setForeground(0, QColor(COLORS['error']))
                item.setForeground(1, QColor(COLORS['error']))
                item.setText(2, '✗')
                item.setText(4, action.get('error', 'ERROR'))

        layout.addWidget(table)
        close_btn = QPushButton(t('ui.close'))
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)
        dialog.finished.connect(lambda: (
            settings.setValue('preview_geometry', dialog.saveGeometry()),
            settings.setValue('preview_col_widths', [header.sectionSize(i) for i in range(5)]),
        ))
        dialog.exec()

    def _show_unrecognized_dialog(self, unknown_items: list) -> list | None:
        t = self.tr.tr
        dialog = QDialog(self)
        dialog.setWindowTitle(t('ui.dlg_unrecognized'))
        dialog.setMinimumSize(650, 450)
        layout = QVBoxLayout(dialog)

        desc = QLabel(t('ui.unrecognized_desc'))
        desc.setStyleSheet('color: #F59E0B; font-weight: bold;')
        layout.addWidget(desc)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(8)

        rows = []
        for item in unknown_items:
            row = QWidget()
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(2)

            file_label = QLabel(f'❓ {item.get("name", "?")}')
            file_label.setStyleSheet('color: #E5E7EB;')
            row_layout.addWidget(file_label)

            type_label = QLabel(t('ui.detected_na'))
            type_label.setStyleSheet('color: #6B7280; font-size: 10px;')
            row_layout.addWidget(type_label)

            combo = QComboBox()
            combo.addItem(t('ui.skip_item'), 'skip')
            for key, label in zip(self.CATEGORY_KEYS, self.CATEGORY_LABELS):
                combo.addItem(label, key)
            row_layout.addWidget(combo)

            rows.append({'item': item, 'combo': combo, 'widget': row})
            scroll_layout.addWidget(row)

            if len(rows) < len(unknown_items):
                sep = QLabel('─' * 60)
                sep.setStyleSheet('color: #374151;')
                scroll_layout.addWidget(sep)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        btn_layout = QHBoxLayout()
        skip_all_btn = QPushButton(t('ui.skip_all'))
        apply_btn = QPushButton(t('ui.apply_selection'))
        apply_btn.setStyleSheet('background-color: #10B981;')
        cancel_btn = QPushButton(t('ui.cancel_process'))
        cancel_btn.setStyleSheet('background-color: #EF4444;')
        btn_layout.addWidget(skip_all_btn)
        btn_layout.addWidget(apply_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        result = []

        def do_skip_all():
            result.clear()
            dialog.accept()

        def do_apply():
            result.clear()
            for row in rows:
                chosen = row['combo'].currentData()
                if chosen != 'skip':
                    self._resolve_unknown_item(row['item'], chosen)
                    result.append(row['item'])
            dialog.accept()

        def do_cancel():
            result.clear()
            result.append(None)
            dialog.accept()

        skip_all_btn.clicked.connect(do_skip_all)
        apply_btn.clicked.connect(do_apply)
        cancel_btn.clicked.connect(do_cancel)

        dialog.exec()

        if not result:
            return []
        if result[0] is None:
            return None
        return result

    def _resolve_unknown_item(self, item: dict, category: str):
        src = Path(item['source'])
        fake_detection = {
            'type': category,
            'title': src.stem,
            'season': None,
            'episode': None,
            'year': None,
            'quality': None,
            'source': None,
            'confidence': 1.0,
            'level': 3,
            'method': 'user_override',
        }
        new_name = self.ctrl.renamer.generate_new_filename(fake_detection, str(src))
        target = self.ctrl.organizer.get_target_path(fake_detection, new_name)
        item['dest'] = str(target)
        item['type'] = category
        item['detection'] = fake_detection

    def _start_execution(self):
        t = self.tr.tr
        if not self.selected_files or not self.ctrl.organizer:
            QMessageBox.warning(self, t('ui.dlg_warning'), t('ui.msg_select_dest'))
            return
        dest = next((Path(p) for p in self._category_dest.values() if p), Path())
        self.dry_run_preview = self.ctrl.preview(self.selected_files, dest)
        self._apply_type_overrides(self.dry_run_preview)

        unknown = [item for item in self.dry_run_preview if item.get('type') == 'unknown' and item.get('dest')]
        if unknown:
            resolved = self._show_unrecognized_dialog(unknown)
            if resolved is None:
                self._log('Operation cancelled by user')
                return
            for resolved_item in resolved:
                idx = next(
                    (i for i, item in enumerate(self.dry_run_preview)
                     if item['source'] == resolved_item['source']),
                    None
                )
                if idx is not None:
                    self.dry_run_preview[idx] = resolved_item

        self.progress_bar.setVisible(True)
        self.status_label.setText(t('ui.status_executing'))
        self.execute_btn.setEnabled(False)
        self.preview_btn.setEnabled(False)
        self.operation_thread = OperationThread(self.dry_run_preview, self.ctrl.operations_manager)
        self.operation_thread.progress.connect(self._on_progress)
        self.operation_thread.log.connect(self._log)
        self.operation_thread.finished.connect(self._on_execution_finished)
        self.operation_thread.error.connect(self._on_execution_error)
        self.operation_thread.start()

    def _on_progress(self, current, total):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status_label.setText(self.tr.tr('ui.status_progress').format(current, total))

    def _on_execution_finished(self, results):
        self.progress_bar.setVisible(False)
        success_count = sum(1 for r in results if r.get('success'))
        fail_count = len(results) - success_count
        status = f'Execution: {success_count} moved'
        if fail_count:
            status += f', {fail_count} failed'
            for r in results:
                if not r.get('success'):
                    self._log(f"FAILED: {r.get('original', '?')} -> {r.get('error', 'unknown error')}")
        self.status_label.setText(status)
        self.execute_btn.setEnabled(True)
        self.preview_btn.setEnabled(True)
        self.undo_btn.setEnabled(success_count > 0)
        self._log(f'Execution complete: {success_count} succeeded, {fail_count} failed')
        self.dry_run_preview.clear()

    def _on_execution_error(self, error_msg):
        t = self.tr.tr
        self.progress_bar.setVisible(False)
        self.status_label.setText(t('ui.status_error'))
        self.execute_btn.setEnabled(True)
        self.preview_btn.setEnabled(True)
        QMessageBox.critical(self, t('ui.dlg_error'), t('ui.msg_execution_failed').format(error_msg))
        self._log(f'Error: {error_msg}')

    def _undo_last(self):
        t = self.tr.tr
        try:
            results = self.ctrl.undo_last()
            count = len([r for r in results if r.get('success')])
            self._log(f'Undo: {count} operation(s) reverted')
            self.status_label.setText(t('ui.status_undo').format(count))
        except Exception as e:
            QMessageBox.critical(self, t('ui.dlg_undo_error'), str(e))
            self._log(f'Undo failed: {e}')

    def _start_auto_watch(self):
        watch_folder = self.watch_input.text()
        if not watch_folder or not Path(watch_folder).exists():
            QMessageBox.warning(self, 'Warning', 'Select a valid watch folder first')
            return
        try:
            self.ctrl.start_watch(watch_folder, self._on_watched_file)
            self.watch_status_label.setText('Running')
            self.watch_status_label.setStyleSheet(f'color: {COLORS["success"]}')
            self.start_watch_btn.setEnabled(False)
            self.stop_watch_btn.setEnabled(True)
            self._log(f'Auto watch started for: {watch_folder}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to start watcher: {e}')

    def _stop_auto_watch(self):
        try:
            self.ctrl.stop_watch()
            self.watch_status_label.setText('Stopped')
            self.watch_status_label.setStyleSheet(f'color: {COLORS["warning"]}')
            self.start_watch_btn.setEnabled(True)
            self.stop_watch_btn.setEnabled(False)
            self._log('Auto watch stopped')
        except Exception as e:
            self._log(f'Error stopping watcher: {e}')

    def _on_watched_file(self, filepath: str):
        path = Path(filepath)
        self._log(f'New file detected: {path.name}')
        self.status_label.setText(f'Watch detected: {path.name}')

        info = self.ctrl.detect_file(str(path), quick=True)
        mtype = info.get('type', 'unknown')
        parent_folder = path.parent.name

        existing = None
        for i in range(self.file_tree.topLevelItem(0).childCount() if self.file_tree.topLevelItemCount() > 0 else 0):
            item = self.file_tree.topLevelItem(0).child(i)
            if item and item.text(0) == parent_folder:
                existing = item
                break

        if existing:
            file_item = QTreeWidgetItem(existing)
            file_item.setText(0, path.name)
            file_item.setData(0, Qt.ItemDataRole.UserRole, filepath)
            file_item.setData(1, Qt.ItemDataRole.UserRole, 'file')
            ep = ''
            if info.get('season') and info.get('episode'):
                ep = f"S{int(info['season']):02d}E{int(info['episode']):02d}"
            file_item.setText(1, ep or mtype.title())
            color = self.TYPE_COLORS.get(mtype, '#6B7280')
            file_item.setForeground(1, QColor(color))

        self.file_count_label.setText(f'Files: {self._count_files()}')

    def _count_files(self):
        count = 0
        if self._tree_data:
            for f in self._tree_data.get('children', []):
                count += self._count_node_files(f)
        return count

    def _count_node_files(self, node):
        if node.get('children'):
            return sum(self._count_node_files(c) for c in node['children'])
        return len(node.get('files', []))

    def _load_settings(self):
        src = self._db.get_setting('source_folder', '')
        geom = self._db.get_setting('window_geometry', '')
        lang = self._db.get_setting('language', '')
        tmdb = self._db.get_setting('tmdb_api_key', '')
        if src:
            self.source_input.setText(src)
        for key in self.CATEGORY_KEYS:
            val = self._db.get_setting(f'dest_{key}', '')
            self._dest_inputs[key].setText(val)
            self._category_dest[key] = val
        self._update_organizer()
        if lang and lang != self.tr.current_lang:
            self.tr.set_language(lang)
        if tmdb:
            self._tmdb_key_input.setText(tmdb)
            import config.settings as csettings
            csettings.TMDB_API_KEY = tmdb
            self.ctrl.detector.api_detector.tmdb_key = tmdb
        if geom:
            try:
                self.restoreGeometry(bytes.fromhex(geom))
            except Exception:
                pass

    def _save_settings(self):
        self._db.set_setting('source_folder', self.source_input.text())
        for key in self.CATEGORY_KEYS:
            self._db.set_setting(f'dest_{key}', self._dest_inputs[key].text())
        self._db.set_setting('language', self.tr.current_lang)
        self._db.set_setting('tmdb_api_key', self._tmdb_key_input.text().strip())
        try:
            geom = bytes(self.saveGeometry()).hex()
            self._db.set_setting('window_geometry', geom)
        except Exception:
            pass

    def closeEvent(self, event):
        self._save_settings()
        if self.ctrl.watcher_running:
            self._stop_auto_watch()
        if self.operation_thread and self.operation_thread.isRunning():
            self.operation_thread.quit()
            self.operation_thread.wait(5000)
        self._db.close()
        event.accept()
