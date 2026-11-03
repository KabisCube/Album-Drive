import json

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QPlainTextEdit, QScrollArea, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from file_paths import filesystem_path
from library import scan_library
from metadata import FIELDS, read_documents, write_metadata
from settings_store import library_cache_path
from themes import ChunkyTabBar, ThemedButton


class MetadataJob(QThread):
    def __init__(self, operation, parent):
        super().__init__(parent)
        self.operation = operation
        self.result = None
        self.error = ''

    def run(self):
        try:
            self.result = self.operation(self.isInterruptionRequested)
        except Exception as error:
            self.error = str(error)


class TagValueDialog(QDialog):
    def __init__(self, key='', value=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Edit metadata tag' if key else 'Add metadata tag')
        self.resize(620, 440)
        self.original_key, self.original_value = key, value
        layout = QVBoxLayout(self)
        self.key = QLineEdit(key)
        self.key.setPlaceholderText('Native tag name, such as TXXX:Custom or a Vorbis field name')
        layout.addWidget(QLabel('Tag name'))
        layout.addWidget(self.key)
        layout.addWidget(QLabel('Value (JSON). Binary values use base64; ID3 frames include their fields.'))
        self.value = QPlainTextEdit()
        self.value.setPlainText(json.dumps(json.loads(value), ensure_ascii=False, indent=2) if value is not None else '""')
        self.value.document().setModified(False)
        layout.addWidget(self.value, 1)
        self.error = QLabel()
        self.error.setTextFormat(Qt.PlainText)
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        buttons = QHBoxLayout()
        cancel = ThemedButton('Cancel')
        cancel.setAutoDefault(False)
        cancel.clicked.connect(self.reject)
        save = ThemedButton('Use value')
        save.setDefault(True)
        save.setProperty('themeRole', 'highlight')
        save.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    def accept(self):
        if not self.key.text().strip():
            self.error.setText('Enter a tag name.')
            return
        try:
            json.loads(self.value.toPlainText())
        except ValueError as error:
            self.error.setText(str(error))
            return
        if self.original_value is None and self.original_key and self.key.text() == self.original_key and not self.value.document().isModified():
            self.reject()
            return
        super().accept()


class MetadataEditor(QDialog):
    saved = Signal(object)
    saving = Signal(object)
    saveFinished = Signal()

    def __init__(self, album, track=None, parent=None):
        super().__init__(parent)
        self.setObjectName('metadataEditor')
        self.setWindowTitle('Album metadata' if track is None else 'Track metadata')
        self.setWindowModality(Qt.WindowModal)
        self.resize(800, 720)
        self.album = album
        self.tracks = list(album.tracks) if track is None else [track]
        self.cache_path = library_cache_path(parent.settings) if parent is not None else None
        self.documents = []
        self.dirty_fields = set()
        self.native_changes = {}
        self.native_values = {}
        self.artwork = None
        self.job = None
        self.job_kind = ''
        self.pending_result = None
        self.loading_fields = False
        layout = QVBoxLayout(self)
        scope = QLabel(f'Editing all {len(self.tracks)} tracks in “{album.title}”' if track is None else f'Editing “{track.title}”')
        scope.setObjectName('settingsSection')
        scope.setTextFormat(Qt.PlainText)
        scope.setWordWrap(True)
        self.scope_label = scope
        layout.addWidget(scope)
        hint = QLabel('Only fields you change will be applied to every track.' if track is None else str(track.path))
        hint.setTextFormat(Qt.PlainText)
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.tabs = QTabWidget()
        self.tabs.setTabBar(ChunkyTabBar(self.tabs))
        layout.addWidget(self.tabs, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        page = QWidget()
        form = QFormLayout(page)
        form.setContentsMargins(18, 16, 18, 16)
        form.setSpacing(10)
        self.fields = {}
        for key, label, *_ in FIELDS:
            editor = QPlainTextEdit() if key in ('comment', 'lyrics') else QLineEdit()
            if isinstance(editor, QPlainTextEdit):
                editor.setFixedHeight(120 if key == 'lyrics' else 80)
            editor.setAccessibleName(label)
            editor.textChanged.connect(lambda *args, field=key: self.mark_field(field))
            self.fields[key] = editor
            form.addRow(label, editor)
        scroll.setWidget(page)
        self.tabs.addTab(scroll, 'Fields')
        artwork_page = QWidget()
        artwork_layout = QVBoxLayout(artwork_page)
        self.artwork_preview = QLabel('No embedded artwork')
        self.artwork_preview.setAlignment(Qt.AlignCenter)
        self.artwork_preview.setMinimumHeight(250)
        artwork_layout.addWidget(self.artwork_preview, 1)
        self.artwork_label = QLabel('Embedded artwork is stored in the audio files.')
        self.artwork_label.setWordWrap(True)
        artwork_layout.addWidget(self.artwork_label)
        artwork_actions = QHBoxLayout()
        replace = ThemedButton('Replace artwork')
        replace.clicked.connect(self.choose_artwork)
        remove = ThemedButton('Remove all artwork')
        remove.clicked.connect(self.remove_artwork)
        artwork_actions.addWidget(replace)
        artwork_actions.addWidget(remove)
        artwork_layout.addLayout(artwork_actions)
        self.tabs.addTab(artwork_page, 'Artwork')
        native_page = QWidget()
        native_layout = QVBoxLayout(native_page)
        native_hint = QLabel('All stored tags, including custom fields. Double-click a tag to edit its value. Edits apply to every selected track. Edited Fields take precedence over matching tags here.')
        native_hint.setWordWrap(True)
        native_layout.addWidget(native_hint)
        self.tags = QTableWidget(0, 2)
        self.tags.setHorizontalHeaderLabels(['Tag', 'Value'])
        self.tags.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tags.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tags.verticalHeader().hide()
        self.tags.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tags.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tags.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tags.cellDoubleClicked.connect(lambda row, column: self.edit_tag(row))
        native_layout.addWidget(self.tags, 1)
        native_actions = QHBoxLayout()
        add = ThemedButton('Add tag')
        add.clicked.connect(lambda: self.edit_tag())
        edit = ThemedButton('Edit tag')
        edit.clicked.connect(lambda: self.edit_tag(self.tags.currentRow()))
        remove_tag = ThemedButton('Remove tag')
        remove_tag.clicked.connect(self.remove_tag)
        for button in (add, edit, remove_tag):
            native_actions.addWidget(button)
        self.edit_buttons = (replace, remove, add, edit, remove_tag)
        native_layout.addLayout(native_actions)
        self.tabs.addTab(native_page, 'All tags')
        self.status = QLabel('Loading metadata…')
        self.status.setTextFormat(Qt.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.error_details = QPlainTextEdit()
        self.error_details.setReadOnly(True)
        self.error_details.setMaximumHeight(120)
        self.error_details.hide()
        layout.addWidget(self.error_details)
        self.write_hint = QLabel('Changes are written to the audio files only when you press Save.')
        self.write_hint.setWordWrap(True)
        layout.addWidget(self.write_hint)
        actions = QHBoxLayout()
        self.cancel_button = ThemedButton('Cancel')
        self.cancel_button.setAutoDefault(False)
        self.cancel_button.clicked.connect(self.reject)
        self.save_button = ThemedButton('Save')
        self.save_button.setDefault(True)
        self.save_button.setProperty('themeRole', 'highlight')
        self.save_button.clicked.connect(self.save)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.save_button)
        layout.addLayout(actions)
        self.tabs.setEnabled(False)
        self.save_button.setEnabled(False)
        self.start_job('load', lambda cancelled: read_documents(self.tracks, cancelled))

    def start_job(self, kind, operation):
        self.job_kind = kind
        self.job = MetadataJob(operation, self)
        self.job.finished.connect(self.job_finished)
        self.job.start()

    def mark_field(self, key):
        if not self.loading_fields:
            self.dirty_fields.add(key)
            self.update_save_state()

    def update_save_state(self):
        writable = bool(self.documents) and all(document.writable for document in self.documents)
        self.save_button.setEnabled(self.job is None and writable and bool(self.dirty_fields or self.native_changes or self.artwork is not None))

    def populate(self):
        self.loading_fields = True
        for key, editor in self.fields.items():
            values = {document.fields[key] for document in self.documents}
            value = next(iter(values)) if len(values) == 1 else ''
            editor.setPlaceholderText('Mixed values — unchanged' if len(values) > 1 else '')
            if isinstance(editor, QPlainTextEdit):
                editor.setPlainText(value)
            else:
                editor.setText(value)
        self.loading_fields = False
        keys = set().union(*(document.tags.keys() for document in self.documents))
        for key in keys:
            values = {document.tags.get(key) for document in self.documents}
            self.native_values[key] = next(iter(values)) if len(values) == 1 else None
        self.populate_tags()
        artwork = self.documents[0].artwork
        self.show_artwork(artwork)
        if any(document.artwork != artwork for document in self.documents):
            self.artwork_label.setText('Artwork differs between tracks. It will stay unchanged unless you replace or remove it.')
        reasons = {document.reason for document in self.documents if not document.writable}
        self.tabs.setEnabled(True)
        for editor in self.fields.values():
            editor.setReadOnly(bool(reasons))
        for button in self.edit_buttons:
            button.setEnabled(not reasons)
        if reasons:
            self.status.setText('\n'.join(sorted(reasons)))
        else:
            self.status.setText('Only edited values will be saved.')
        self.update_save_state()

    def populate_tags(self):
        values = dict(self.native_values)
        values.update(self.native_changes)
        keys = sorted(key for key, value in values.items() if key not in self.native_changes or value is not None)
        self.tags.setRowCount(len(keys))
        for row, key in enumerate(keys):
            value = values[key]
            summary = 'Mixed values — unchanged' if value is None else value[:180]
            if value is not None:
                decoded = json.loads(value)
                if isinstance(decoded, dict) and decoded.get('frame') == 'APIC':
                    summary = 'Embedded image — double-click to inspect all fields'
                elif isinstance(decoded, dict) and 'fields' in decoded:
                    summary = str(decoded['fields'].get('text', decoded))[:180]
            self.tags.setItem(row, 0, QTableWidgetItem(key))
            self.tags.setItem(row, 1, QTableWidgetItem(summary))

    def edit_tag(self, row=None):
        if row is not None and row < 0:
            return
        key = self.tags.item(row, 0).text() if row is not None else ''
        value = self.native_changes.get(key, self.native_values.get(key))
        dialog = TagValueDialog(key, value, self)
        if dialog.exec() == QDialog.Accepted:
            new_key = dialog.key.text().strip()
            if key and key != new_key:
                self.native_changes[key] = None
            self.native_changes[new_key] = json.dumps(json.loads(dialog.value.toPlainText()), ensure_ascii=False, sort_keys=True)
            self.populate_tags()
            self.update_save_state()

    def remove_tag(self):
        row = self.tags.currentRow()
        if row >= 0:
            self.native_changes[self.tags.item(row, 0).text()] = None
            self.populate_tags()
            self.update_save_state()

    def show_artwork(self, data):
        pixmap = QPixmap()
        if data and pixmap.loadFromData(data):
            self.artwork_preview.setPixmap(pixmap.scaled(360, 360, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.artwork_preview.setPixmap(QPixmap())
            self.artwork_preview.setText('No embedded artwork')

    def choose_artwork(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Choose cover image', '', 'Cover images (*.jpg *.jpeg *.png)')
        if path:
            try:
                data = filesystem_path(path).read_bytes()
            except OSError as error:
                self.status.setText(str(error))
                return
            self.artwork = path
            self.show_artwork(data)
            self.artwork_label.setText('This front cover will be embedded in every selected track.')
            self.update_save_state()

    def remove_artwork(self):
        self.artwork = ''
        self.show_artwork(b'')
        self.artwork_label.setText('All embedded artwork will be removed from the selected tracks.')
        self.update_save_state()

    def save(self):
        if not self.save_button.isEnabled():
            return
        fields = {key: editor.toPlainText() if isinstance(editor, QPlainTextEdit) else editor.text()
                  for key, editor in self.fields.items() if key in self.dirty_fields}
        native_changes, artwork = dict(self.native_changes), self.artwork
        self.tabs.setEnabled(False)
        self.save_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.status.setText(f'Saving metadata to {len(self.documents)} files…')
        self.error_details.clear()
        self.error_details.hide()
        self.saving.emit([document.path for document in self.documents])
        def operation(cancelled):
            saved, errors = write_metadata(self.documents, fields, native_changes, artwork)
            albums, documents = [], self.documents
            if saved:
                try:
                    albums, _ = scan_library(self.album.folder, cache_path=self.cache_path)
                except Exception as error:
                    errors.append(f'Metadata was saved, but the library could not refresh: {error}')
            if errors:
                try:
                    documents = read_documents(self.tracks)
                except Exception as error:
                    errors.append(str(error))
            return saved, errors, albums, documents
        self.start_job('save', operation)

    def job_finished(self):
        job, kind = self.job, self.job_kind
        self.job = None
        job.deleteLater()
        if self.pending_result is not None:
            result, self.pending_result = self.pending_result, None
            super().done(result)
            return
        self.cancel_button.setEnabled(True)
        if job.error:
            self.status.setText(job.error)
            self.tabs.setEnabled(bool(self.documents) and all(document.writable for document in self.documents))
            self.update_save_state()
            if kind == 'save':
                self.saveFinished.emit()
            return
        if kind == 'load':
            self.documents = job.result
            if self.documents:
                self.populate()
            else:
                self.status.setText('No editable tracks were found.')
        else:
            saved, errors, albums, documents = job.result
            if saved:
                self.saved.emit(albums)
            self.saveFinished.emit()
            if errors:
                self.documents = documents
                self.status.setText(f'Saved {len(saved)} of {len(self.tracks)} files.')
                self.error_details.setPlainText('\n'.join(errors))
                self.error_details.show()
                self.tabs.setEnabled(True)
                self.update_save_state()
            else:
                self.accept()

    def done(self, result):
        if self.job is not None and self.job.isRunning():
            if self.job_kind == 'load':
                self.pending_result = result
                self.job.requestInterruption()
            return
        super().done(result)
