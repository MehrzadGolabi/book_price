## 2024-05-02 - PyQt/PySide6 Table Performance
**Learning:** In PySide6 applications, populating a `QTableWidget` row-by-row using `.insertRow()` in a loop causes expensive O(N^2) layout recalculations and repaints. Similarly, appending single items to a `QComboBox` in a loop triggers redundant signal emissions and layout updates.
**Action:** Always temporarily disable UI updates using `.setUpdatesEnabled(False)` before bulk data insertion in tables, pre-allocate the required number of rows using `.setRowCount()`, and restore updates with `.setUpdatesEnabled(True)` afterward. Use `addItems(list)` instead of a loop for `QComboBox`.
## 2024-05-24 - N+1 Queries in UI Iterations
**Learning:** Extracting input values from UI components in a loop and querying the database sequentially leads to an N+1 query problem, causing application unresponsiveness on UI threads.
**Action:** Always collect values from UI iterators first, then execute a single batch query (using conditions like `OR` or `IN`) before mapping the results back to the interface.
