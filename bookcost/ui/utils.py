"""UI utility helpers and event filters."""

from PySide6.QtCore import QCoreApplication, QEvent, QObject
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QSpinBox


class NoWheelSpinBoxFilter(QObject):
    """Global event filter to disable mouse wheel scrolling on all QSpinBox,
    QDoubleSpinBox, and QComboBox (dropdown) widgets. Prevents accidental selection/value changes when scrolling forms."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel:
            is_combo_child = isinstance(obj.parent(), QComboBox) if obj.parent() else False
            if isinstance(obj, (QSpinBox, QDoubleSpinBox, QComboBox)) or is_combo_child:
                event.ignore()
                target_parent = obj.parent().parent() if is_combo_child else obj.parent()
                if target_parent:
                    QCoreApplication.sendEvent(target_parent, event)
                return True
        return super().eventFilter(obj, event)


def install_no_wheel_filter(app):
    """Installs the NoWheelSpinBoxFilter on the given QApplication instance."""
    if app is not None:
        filter_obj = NoWheelSpinBoxFilter(app)
        app.installEventFilter(filter_obj)
        return filter_obj
    return None
