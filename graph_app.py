import sys
import random
import itertools
from PySide6.QtWidgets import (QApplication, QGraphicsView, QGraphicsScene, 
                             QGraphicsEllipseItem, QGraphicsLineItem, 
                             QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QTextEdit, QLabel, 
                             QGraphicsSimpleTextItem, QSpinBox)
from PySide6.QtCore import Qt, QLineF
from PySide6.QtGui import QPen, QBrush, QFont, QPainter

# ==========================================
# 1. 節點 (Node)
# ==========================================
class Node(QGraphicsEllipseItem):
    def __init__(self, x, y, node_id, log_callback, create_link_callback):
        super().__init__(-20, -20, 40, 40)
        self.setPos(x, y)
        self.node_id = node_id 
        self.log_callback = log_callback
        self.create_link_callback = create_link_callback
        
        self.setBrush(QBrush(Qt.GlobalColor.cyan))
        self.setPen(QPen(Qt.GlobalColor.black, 2))
        self.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        
        self.links = []       
        self.temp_line = None 
        self.is_dragging = False

        self.text_item = QGraphicsSimpleTextItem(str(self.node_id), self)
        font = QFont("Arial", 12, QFont.Weight.Bold)
        self.text_item.setFont(font)
        text_rect = self.text_item.boundingRect()
        self.text_item.setPos(-text_rect.width() / 2, -text_rect.height() / 2)

    def add_link(self, link):
        self.links.append(link)

    def remove_link(self, link):
        if link in self.links:
            self.links.remove(link)

    def itemChange(self, change, value):
        if change == QGraphicsEllipseItem.GraphicsItemChange.ItemPositionHasChanged:
            for link in self.links:
                link.update_position()
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.temp_line = QGraphicsLineItem(QLineF(self.scenePos(), event.scenePos()))
            pen = QPen(Qt.GlobalColor.gray, 2, Qt.PenStyle.DashLine)
            self.temp_line.setPen(pen)
            self.scene().addItem(self.temp_line)
            event.accept()
        elif event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.temp_line:
            self.temp_line.setLine(QLineF(self.scenePos(), event.scenePos()))
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.temp_line:
            self.scene().removeItem(self.temp_line)
            self.temp_line = None
            for item in self.scene().items(event.scenePos()):
                if isinstance(item, Node) and item != self:
                    self.create_link_callback(self, item)
                    break
            event.accept()
        else:
            super().mouseReleaseEvent(event)
            if event.button() == Qt.MouseButton.LeftButton and self.is_dragging:
                self.log_callback(f"📍 節點 {self.node_id} 移動到 ({int(self.pos().x())}, {int(self.pos().y())})")
                self.is_dragging = False

# ==========================================
# 2. 連線 (Link)
# ==========================================
class Link(QGraphicsLineItem):
    def __init__(self, source, target):
        super().__init__()
        self.source, self.target = source, target
        self.source.add_link(self)
        self.target.add_link(self)
        self.setPen(QPen(Qt.GlobalColor.red, 2))
        self.setFlag(QGraphicsLineItem.GraphicsItemFlag.ItemIsSelectable)
        self.setZValue(-1)
        self.update_position()

    def update_position(self):
        self.setLine(QLineF(self.source.pos(), self.target.pos()))

# ==========================================
# 3. 主視窗 (MainWindow)
# ==========================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python Graph Editor - 最佳平衡容錯分析")
        self.resize(1200, 750)
        
        self.nodes = [] 
        self.edges_data = [] 
        self.node_id_counter = 0

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- 頂部按鈕區 ---
        top_layout = QHBoxLayout()
        self.add_node_btn = QPushButton("新增節點 (+)")
        self.add_node_btn.setFixedHeight(40)
        self.add_node_btn.clicked.connect(self.add_new_node)
        top_layout.addWidget(self.add_node_btn)

        # 組數輸入框與暴力搜尋按鈕
        top_layout.addWidget(QLabel("  想要分幾組(K)："))
        self.k_input = QSpinBox()
        self.k_input.setRange(2, 5) 
        self.k_input.setValue(2)
        self.k_input.setFixedSize(60, 40)
        top_layout.addWidget(self.k_input)

        self.brute_force_btn = QPushButton("暴力搜尋並計算最佳平衡解")
        self.brute_force_btn.setFixedHeight(40)
        self.brute_force_btn.setStyleSheet("background-color: #ffd700; color: black; font-weight: bold;")
        self.brute_force_btn.clicked.connect(self.run_brute_force)
        top_layout.addWidget(self.brute_force_btn)

        top_layout.addStretch()
        main_layout.addLayout(top_layout)

        # --- 繪圖區 ---
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        main_layout.addWidget(self.view)

        # --- 底部資訊區 ---
        info_layout = QHBoxLayout()
        log_layout = QVBoxLayout()
        log_layout.addWidget(QLabel("📋 系統紀錄 (包含評估指標分數)"))
        self.output_log = QTextEdit()
        self.output_log.setReadOnly(True)
        log_layout.addWidget(self.output_log)
        info_layout.addLayout(log_layout, 2)

        matrix_layout = QVBoxLayout()
        matrix_layout.addWidget(QLabel("🔢 鄰接矩陣 (Adjacency Matrix)："))
        self.matrix_display = QTextEdit()
        self.matrix_display.setReadOnly(True)
        self.matrix_display.setFont(QFont("Courier New", 13, QFont.Weight.Bold))
        matrix_layout.addWidget(self.matrix_display)
        info_layout.addLayout(matrix_layout, 1)
        
        main_layout.addLayout(info_layout)
        self.update_matrix_view()

    def log_message(self, message):
        self.output_log.append(message)
        self.output_log.verticalScrollBar().setValue(self.output_log.verticalScrollBar().maximum())

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            for item in self.scene.selectedItems():
                if isinstance(item, Node): self.remove_node(item)
                elif isinstance(item, Link): self.remove_link(item)
            self.update_matrix_view()
        else:
            super().keyPressEvent(event)

    def add_new_node(self):
        node_id = self.node_id_counter
        self.node_id_counter += 1
        rx, ry = random.randint(100, 500), random.randint(100, 400)
        new_node = Node(rx, ry, node_id, self.log_message, self.create_new_link)
        self.scene.addItem(new_node)
        self.nodes.append(new_node)
        self.update_matrix_view()

    def create_new_link(self, node_a, node_b):
        for u, v, _ in self.edges_data:
            if (u == node_a and v == node_b) or (u == node_b and v == node_a): return
        link = Link(node_a, node_b)
        self.scene.addItem(link)
        self.edges_data.append((node_a, node_b, link))
        self.log_message(f"🔗 建立連線：{node_a.node_id} <-> {node_b.node_id}")
        self.update_matrix_view()

    def remove_node(self, node):
        links_to_remove = [edge for edge in self.edges_data if edge[0] == node or edge[1] == node]
        for edge in links_to_remove: self.remove_link(edge[2])
        self.scene.removeItem(node)
        if node in self.nodes: self.nodes.remove(node)
        self.log_message(f"❌ 刪除了節點 {node.node_id}")

    def remove_link(self, link):
        link.source.remove_link(link)
        link.target.remove_link(link)
        self.scene.removeItem(link)
        self.edges_data = [edge for edge in self.edges_data if edge[2] != link]

    def update_matrix_view(self):
        n = len(self.nodes)
        if n == 0:
            self.matrix_display.setText("等待新增節點...")
            return
        id_map = {node.node_id: i for i, node in enumerate(self.nodes)}
        matrix = [[0] * n for _ in range(n)]
        for node_a, node_b, _ in self.edges_data:
            if node_a.node_id in id_map and node_b.node_id in id_map:
                u, v = id_map[node_a.node_id], id_map[node_b.node_id]
                matrix[u][v] = matrix[v][u] = 1

        header = "    " + " ".join([f"{node.node_id:1}" for node in self.nodes])
        divider = "    " + "-" * (n * 2)
        rows = [f"{node.node_id:1} | " + " ".join(map(str, matrix[i])) for i, node in enumerate(self.nodes)]
        self.matrix_display.setText(header + "\n" + divider + "\n" + "\n".join(rows))

    # ==========================================
    # 🌟 網路拓樸分析核心演算法
    # ==========================================
    def is_connected(self, edges_subset):
        """DFS 檢查圖是否連通"""
        if not self.nodes: return True
        adj = {node.node_id: [] for node in self.nodes}
        for u, v, _ in edges_subset:
            adj[u.node_id].append(v.node_id)
            adj[v.node_id].append(u.node_id)

        visited = set()
        def dfs(node_id):
            visited.add(node_id)
            for neighbor in adj[node_id]:
                if neighbor not in visited:
                    dfs(neighbor)

        dfs(self.nodes[0].node_id)
        return len(visited) == len(self.nodes)

    def get_max_diameter(self, edges_subset):
        """使用 BFS 計算圖中所有最短路徑的最大值 (即圖直徑)"""
        if not self.nodes: return 0
        
        adj = {node.node_id: [] for node in self.nodes}
        for u, v, _ in edges_subset:
            adj[u.node_id].append(v.node_id)
            adj[v.node_id].append(u.node_id)

        max_diameter = 0
        
        for start_node in self.nodes:
            if start_node.node_id not in adj: 
                continue
            
            visited_dist = {start_node.node_id: 0}
            queue = [start_node.node_id]
            
            while queue:
                curr = queue.pop(0)
                curr_dist = visited_dist[curr]
                
                for neighbor in adj[curr]:
                    if neighbor not in visited_dist:
                        visited_dist[neighbor] = curr_dist + 1
                        queue.append(neighbor)
                        if visited_dist[neighbor] > max_diameter:
                            max_diameter = visited_dist[neighbor]
                            
        return max_diameter

    def run_brute_force(self):
        k = self.k_input.value()
        E = len(self.edges_data)
        
        if E == 0:
            self.log_message("⚠️ 沒有連線可以分組。")
            return

        total_combinations = k ** E
        self.log_message(f"⏳ 開始暴力搜尋... ({E} 條邊分成 {k} 組，共需檢查 {total_combinations} 種可能)")
        self.log_message("⚠️ 程式計算中，如果邊數超過 12 條會較花時間，請耐心等候...")
        QApplication.processEvents() 

        # 恢復全部紅線
        for _, _, link in self.edges_data:
            link.setPen(QPen(Qt.GlobalColor.red, 2))

        valid_solutions = []

        # itertools.product 產生所有的排列組合
        for assignment in itertools.product(range(k), repeat=E):
            if len(set(assignment)) != k: continue

            is_valid = True
            diameters_after_failure = []
            
            # 檢查如果刪除任意一組 (group_to_remove)，剩下的網路是否連通
            for group_to_remove in range(k):
                remaining_edges = [
                    self.edges_data[i] 
                    for i, assigned_group in enumerate(assignment) 
                    if assigned_group != group_to_remove
                ]
                
                if not self.is_connected(remaining_edges):
                    is_valid = False
                    break
                else:
                    # 如果連通，計算斷掉該組後的網路直徑
                    diam = self.get_max_diameter(remaining_edges)
                    diameters_after_failure.append(diam)
            
            if is_valid:
                # ----------------------------------------
                # 計算三大原始懲罰指標 (M1, M2, M3)
                # ----------------------------------------
                # M1: 數量變異數 (平衡各組邊數)
                group_sizes = [assignment.count(i) for i in range(k)]
                avg_size = E / k
                m1_score = sum((size - avg_size) ** 2 for size in group_sizes)
                
                # M2: 拓樸變異數 (平衡節點對外連線的分散度)
                m2_score = 0
                for node in self.nodes:
                    node_group_counts = [0] * k
                    for i, (u, v, _) in enumerate(self.edges_data):
                        if u == node or v == node:
                            node_group_counts[assignment[i]] += 1
                    avg_node_links = sum(node_group_counts) / k
                    m2_score += sum((c - avg_node_links) ** 2 for c in node_group_counts)
                
                # M3: 最壞效能情況 (斷掉任一組後產生的最大直徑)
                m3_score = max(diameters_after_failure) 
                
                valid_solutions.append({
                    "assignment": assignment,
                    "m1": m1_score,
                    "m2": m2_score,
                    "m3": m3_score
                })

        # ----------------------------------------
        # 進行分數標準化與加權決策
        # ----------------------------------------
        if valid_solutions:
            m1_vals = [sol["m1"] for sol in valid_solutions]
            m2_vals = [sol["m2"] for sol in valid_solutions]
            m3_vals = [sol["m3"] for sol in valid_solutions]
            
            def normalize(val, vals_list):
                min_v, max_v = min(vals_list), max(vals_list)
                if min_v == max_v: return 0.0 # 避免分母為0
                return (val - min_v) / (max_v - min_v)

            # 設定指標權重
            W1 = 0.3 # 數量平衡 (30%)
            W2 = 0.3 # 拓樸平衡 (30%)
            W3 = 0.4 # 最壞直徑最小化 (40%)

            best_solution = None
            best_final_score = float('inf')

            for sol in valid_solutions:
                n_m1 = normalize(sol["m1"], m1_vals)
                n_m2 = normalize(sol["m2"], m2_vals)
                n_m3 = normalize(sol["m3"], m3_vals)
                
                # 計算最終加權總分 (分數越低越好)
                final_score = (W1 * n_m1) + (W2 * n_m2) + (W3 * n_m3)
                
                if final_score < best_final_score:
                    best_final_score = final_score
                    best_solution = sol

            valid_count = len(valid_solutions)
            self.log_message(f"✅ 搜尋完成！共有 【{valid_count}】 種合法分法。")
            self.log_message(f"🏆 最佳平衡解 (評估總分: {best_final_score:.3f} | 最壞直徑: {best_solution['m3']})")
            
            # 使用顏色調色盤替最佳解上色
            color_palette = [Qt.GlobalColor.blue, Qt.GlobalColor.green, Qt.GlobalColor.magenta, 
                             Qt.GlobalColor.darkYellow, Qt.GlobalColor.cyan]
            
            for i, group_index in enumerate(best_solution["assignment"]):
                _, _, link_item = self.edges_data[i]
                color = color_palette[group_index % len(color_palette)]
                link_item.setPen(QPen(color, 3))
                
            self.log_message("🎨 畫面已為你顯示「最平衡」的容錯拓樸分法！")
        else:
            self.log_message(f"❌ 搜尋完成！檢查了 {total_combinations} 種可能，【0】種合法解。這張圖目前的結構無法達成條件。")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())