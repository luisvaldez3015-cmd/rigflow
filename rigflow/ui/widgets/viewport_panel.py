from __future__ import annotations

import uuid
from rigflow.ui.qt import QtCore, QtWidgets, wrapInstance
from rigflow.ui import theme


class ViewportPanel(QtWidgets.QFrame):
    """Deferred Maya embedding with explicit cleanup and a safe headless state."""

    def __init__(self, title="Preview", controller=None, tint="source", parent=None):
        super().__init__(parent)
        self.controller = controller
        self.panel = None
        self._attempted = False
        self.isolate = ()
        self.setObjectName("sectionCard")
        self.setMinimumHeight(130)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        self.header = theme.label(title, heading=True)
        self.header.setStyleSheet("padding: 8px 12px; background: %s; border-top-left-radius: 6px; border-top-right-radius: 6px;" %
                                 ("#354553" if tint == "source" else "#424449"))
        layout.addWidget(self.header)
        self.host = QtWidgets.QWidget()
        token = uuid.uuid4().hex[:10]
        self.host.setObjectName("rigflowViewport_" + token)
        self.host_layout = QtWidgets.QVBoxLayout(self.host)
        # Maya parents native controls to a *Qt layout* found by object name
        # (cmds.setParent accepts QLayout names, not plain QWidget names).
        self.host_layout.setObjectName("rigflowViewportLayout_" + token)
        self.host_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.host, 1)
        self.placeholder = QtWidgets.QFrame()
        self.placeholder.setStyleSheet("QFrame { background: #282b2e; border: none; }")
        empty_layout = QtWidgets.QVBoxLayout(self.placeholder)
        empty_layout.setSpacing(4)
        empty_layout.addStretch()
        self.hint = theme.label("Viewport available inside Maya", muted=True)
        self.hint.setAlignment(QtCore.Qt.AlignCenter)
        empty_layout.addWidget(self.hint)
        empty_layout.addStretch()
        self.host_layout.addWidget(self.placeholder)
        self.setToolTip("Live Maya model panel, isolated to this character. Outside Maya a placeholder is shown.")

    def configure(self, nodes=(), title=None):
        nodes = tuple(n for n in nodes if n)
        if nodes != self.isolate:
            self.release()
            self.isolate = nodes
        if title:
            self.header.setText(title)
        if self.isVisible():
            self._embed()

    def showEvent(self, event):
        super().showEvent(event)
        QtCore.QTimer.singleShot(0, self._embed)

    def _embed(self):
        if self._attempted or self.controller is None or not self.isVisible():
            return
        self._attempted = True
        try:
            # Force Qt to allocate a native control before MQtUtil lookup.
            self.host.winId()
            panel = self.controller.create_viewport(self.host_layout.objectName(), isolate=self.isolate)
            if not panel:
                return
            self.panel = panel
            # Maya already inserted the pane layout into host_layout (setParent to a
            # Qt layout adds the native control there). Wrapping it is only needed to
            # keep a Python reference; failing to wrap must not destroy the viewport.
            self.placeholder.hide()
            self.embedded = self._wrap_container(panel)
            QtCore.QTimer.singleShot(0, lambda expected=panel: self._frame_content(expected))
        except Exception as exc:
            self.release()
            self._attempted = True
            if self.controller:
                self.controller.session.status("Viewport unavailable: {}".format(exc), "warning")

    def _wrap_container(self, panel):
        try:
            from maya import OpenMayaUI as omui
            try:
                from shiboken6 import isValid  # type: ignore
            except ImportError:
                from shiboken2 import isValid  # type: ignore
            container = getattr(self.controller, "viewport_container", lambda _p: None)(panel) or panel
            pointer = omui.MQtUtil.findLayout(container) or omui.MQtUtil.findControl(container)
            if not pointer:
                return None
            widget = wrapInstance(int(pointer), QtWidgets.QWidget)
            if not isValid(widget):
                return None
            if widget.parentWidget() is not self.host:
                self.host_layout.addWidget(widget)
            widget.show()
            return widget
        except Exception as exc:  # non-fatal: the panel is already parented by Maya
            if self.controller:
                self.controller.session.status("Viewport embedded (no Qt handle: {})".format(exc), "info")
            return None

    def release(self):
        if self.panel and self.controller:
            self.controller.delete_viewport(self.panel)
        self.panel = None
        self._attempted = False
        self.placeholder.show()

    def _frame_content(self, expected):
        if self.panel == expected and self.isVisible():
            self.controller.frame_viewport(expected, self.isolate)

    def closeEvent(self, event):
        self.release()
        super().closeEvent(event)
