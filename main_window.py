import random
import itertools
from PySide6.QtWidgets import (QApplication, QGraphicsView, QGraphicsScene, 
                             QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QTextEdit, QLabel, QSpinBox, QDoubleSpinBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPen, QFont, QPainter

from graph_items import Node, Link

# ==========================================
# 主視窗 (MainWindow)
# ==========================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python Graph Editor - 最佳平衡容錯分析 (自訂權重版)")
        self.resize(1200, 750)
        
        self.nodes = [] 
        self.edges_data = [] 
        self.node_id_counter = 0

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- 頂部按鈕區 (第一排) ---
        top_layout = QHBoxLayout()
        self.add_node_btn = QPushButton("新增節點 (+)")
        self.add_node_btn.setFixedHeight(40)
        self.add_node_btn.clicked.connect(self.add_new_node)
        top_layout.addWidget(self.add_node_btn)

        top_layout.addWidget(QLabel("  想要分幾組(K)："))
        self.k_input = QSpinBox()
        self.k_input.setRange(2, 5) 
        self.k_input.setValue(2)
        self.k_input.setFixedSize(60, 40)
        top_layout.addWidget(self.k_input)

        self.brute_force_btn = QPushButton("搜尋")
        self.brute_force_btn.setFixedHeight(40)
        self.brute_force_btn.setStyleSheet("background-color: #ffd700; color: black; font-weight: bold;")
        self.brute_force_btn.clicked.connect(self.run_brute_force)
        top_layout.addWidget(self.brute_force_btn)

        top_layout.addStretch()
        main_layout.addLayout(top_layout)

        # --- 權重設定區 (第二排) ---
        weight_layout = QHBoxLayout()
        
        weight_layout.addWidget(QLabel("指標權重設定 ->"))
        
        weight_layout.addWidget(QLabel("  W1 數量平衡 (邊數):"))
        self.w1_input = QDoubleSpinBox()
        self.w1_input.setRange(0.0, 10.0) 
        self.w1_input.setSingleStep(0.1)
        self.w1_input.setValue(0.3)
        weight_layout.addWidget(self.w1_input)

        weight_layout.addWidget(QLabel("  W2 拓樸平衡 (分散度):"))
        self.w2_input = QDoubleSpinBox()
        self.w2_input.setRange(0.0, 10.0)
        self.w2_input.setSingleStep(0.1)
        self.w2_input.setValue(0.3)
        weight_layout.addWidget(self.w2_input)

        weight_layout.addWidget(QLabel("  W3 效能平衡 (最壞直徑):"))
        self.w3_input = QDoubleSpinBox()
        self.w3_input.setRange(0.0, 10.0)
        self.w3_input.setSingleStep(0.1)
        self.w3_input.setValue(0.4)
        weight_layout.addWidget(self.w3_input)
        
        weight_layout.addStretch()
        main_layout.addLayout(weight_layout)

        # --- 繪圖區 ---
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        main_layout.addWidget(self.view)

        # --- 底部資訊區 ---
        info_layout = QHBoxLayout()
        log_layout = QVBoxLayout()
        log_layout.addWidget(QLabel("系統紀錄 (包含評估指標分數)"))
        self.output_log = QTextEdit()
        self.output_log.setReadOnly(True)
        log_layout.addWidget(self.output_log)
        info_layout.addLayout(log_layout, 2)

        matrix_layout = QVBoxLayout()
        matrix_layout.addWidget(QLabel("鄰接矩陣 (Adjacency Matrix)："))
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
        self.log_message(f"建立連線：{node_a.node_id} <-> {node_b.node_id}")
        self.update_matrix_view()

    def remove_node(self, node):
        links_to_remove = [edge for edge in self.edges_data if edge[0] == node or edge[1] == node]
        for edge in links_to_remove: self.remove_link(edge[2])
        self.scene.removeItem(node)
        if node in self.nodes: self.nodes.remove(node)
        self.log_message(f"刪除了節點 {node.node_id}")

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

    def is_connected(self, edges_subset):
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
            self.log_message("[提示] 沒有連線可以分組。")
            return

        total_combinations = k ** E
        self.log_message(f"開始暴力搜尋... ({E} 條邊分成 {k} 組，共需檢查 {total_combinations} 種可能)")
        self.log_message("[提示] 程式計算中，如果邊數超過 12 條會較花時間，請耐心等候...")
        QApplication.processEvents() 

        for _, _, link in self.edges_data:
            link.setPen(QPen(Qt.GlobalColor.red, 2))

        valid_solutions = []

        for assignment in itertools.product(range(k), repeat=E):
            if len(set(assignment)) != k: continue

            is_valid = True
            diameters_after_failure = []
            
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
                    diam = self.get_max_diameter(remaining_edges)
                    diameters_after_failure.append(diam)
            
            if is_valid:
                group_sizes = [assignment.count(i) for i in range(k)]
                avg_size = E / k
                m1_score = sum((size - avg_size) ** 2 for size in group_sizes)
                
                m2_score = 0
                for node in self.nodes:
                    node_group_counts = [0] * k
                    for i, (u, v, _) in enumerate(self.edges_data):
                        if u == node or v == node:
                            node_group_counts[assignment[i]] += 1
                    avg_node_links = sum(node_group_counts) / k
                    m2_score += sum((c - avg_node_links) ** 2 for c in node_group_counts)
                
                m3_score = max(diameters_after_failure) 
                
                valid_solutions.append({
                    "assignment": assignment,
                    "m1": m1_score,
                    "m2": m2_score,
                    "m3": m3_score
                })

        if valid_solutions:
            m1_vals = [sol["m1"] for sol in valid_solutions]
            m2_vals = [sol["m2"] for sol in valid_solutions]
            m3_vals = [sol["m3"] for sol in valid_solutions]
            
            def normalize(val, vals_list):
                min_v, max_v = min(vals_list), max(vals_list)
                if min_v == max_v: return 0.0
                return (val - min_v) / (max_v - min_v)

            raw_w1 = self.w1_input.value()
            raw_w2 = self.w2_input.value()
            raw_w3 = self.w3_input.value()
            
            total_w = raw_w1 + raw_w2 + raw_w3
            if total_w == 0:
                W1, W2, W3 = 0.33, 0.33, 0.33
            else:
                W1 = raw_w1 / total_w
                W2 = raw_w2 / total_w
                W3 = raw_w3 / total_w

            best_solution = None
            best_final_score = float('inf')

            for sol in valid_solutions:
                n_m1 = normalize(sol["m1"], m1_vals)
                n_m2 = normalize(sol["m2"], m2_vals)
                n_m3 = normalize(sol["m3"], m3_vals)
                
                final_score = (W1 * n_m1) + (W2 * n_m2) + (W3 * n_m3)
                
                if final_score < best_final_score:
                    best_final_score = final_score
                    best_solution = sol

            valid_count = len(valid_solutions)
            self.log_message(f"搜尋完成！共有 【{valid_count}】 種合法分法。")
            self.log_message(f"最佳平衡解 (評估總分: {best_final_score:.3f} | 最壞直徑: {best_solution['m3']})")
            
            color_palette = [Qt.GlobalColor.blue, Qt.GlobalColor.green, Qt.GlobalColor.magenta, 
                             Qt.GlobalColor.darkYellow, Qt.GlobalColor.cyan]
            
            for i, group_index in enumerate(best_solution["assignment"]):
                _, _, link_item = self.edges_data[i]
                color = color_palette[group_index % len(color_palette)]
                link_item.setPen(QPen(color, 3))
                
            self.log_message(f"畫面已依照自訂權重 (W1={W1:.2f}, W2={W2:.2f}, W3={W3:.2f}) 顯示最佳分法！")
        else:
            
            self.log_message(f"搜尋完成！檢查了 {total_combinations} 種可能，【0】種合法解。這張圖目前的結構無法達成條件。")