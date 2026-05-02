## 2024-05-02 - Desktop GUI (PySide6) Input Affordances
**Learning:** PySide6 QLineEdit default behavior does not map "Enter" to adjacent push buttons by default, limiting keyboard accessibility for search forms. Users often miss optional fields without explicit visual cues.
**Action:** When implementing QLineEdits near action buttons, always connect `returnPressed` for enter-to-submit behavior, and use `setPlaceholderText` for required format examples or to indicate optional fields without cluttering the label layout.
