import random
import itertools
import math
import time 
from PySide6.QtWidgets import (QApplication, QGraphicsView, QGraphicsScene, 
                             QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QTextEdit, QLabel, QSpinBox, QDoubleSpinBox,
                             QProgressBar, QFrame)
from PySide6.QtCore import Qt, QThread, Signal, QPoint
from PySide6.QtGui import QPen, QFont, QPainter

from graph_items import Node, Link

# ==========================================
# 背景執行緒：高效能優化版 (對稱性破缺 + 進度管理)
# ==========================================
class SearchWorker(QThread):
    progress_updated = Signal(int, str) 
    log_msg = Signal(str)               
    search_finished = Signal(object, int, int, float) 

    def __init__(self, k, edges_data, nodes, weights):
        super().__init__()
        self.k = k
        self.edges_data = edges_data
        self.nodes = nodes
        self.weights = weights
        self._is_running = True 

    def stop(self):
        self._is_running = False

    def is_connected(self, edges_subset):
        if not self.nodes: return True
        # 建立鄰接表
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

        if self.nodes:
            dfs(self.nodes[0].node_id)
        return len(visited) == len(self.nodes)

    def get_max_diameter(self, edges_subset):
        adj = {node.node_id: [] for node in self.nodes}
        for u, v, _ in edges_subset:
            adj[u.node_id].append(v.node_id)
            adj[v.node_id].append(u.node_id)

        max_diameter = 0
        for start_node in self.nodes:
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

    def format_time(self, seconds):
        if seconds < 60: return f"{int(seconds)}s"
        if seconds < 3600: return f"{int(seconds//60)}m {int(seconds%60)}s"
        return f"{int(seconds//3600)}h {int((seconds%3600)//60)}m"

    def run(self):
        E_count = len(self.edges_data)
        V_count = len(self.nodes)
        
        # 🌟 對稱性破缺：固定第一條邊在組 0，搜尋量直接變為 K^(E-1)
        reduced_total = self.k ** (E_count - 1)
        valid_solutions = []

        self.log_msg.emit(f"開始搜尋... (對稱性優化後需檢查 {reduced_total:,} 種可能)")
        
        start_time = time.time() 
        last_update_time = start_time
        count = 0

        # 固定首位為 0，只對剩餘 E-1 條邊進行 itertools 排列
        for rest in itertools.product(range(self.k), repeat=E_count-1):
            if not self._is_running:
                break

            count += 1
            assignment = (0,) + rest 

            # UI 更新與速率/ETA 計算
            if count % 5000 == 0:
                now = time.time()
                elapsed = now - start_time
                if now - last_update_time >= 0.2:
                    pct = int((count / reduced_total) * 100)
                    speed = count / elapsed if elapsed > 0 else 0
                    eta = (reduced_total - count) / speed if speed > 0 else 0
                    text = f"檢查中: {count:,}/{reduced_total:,} ({pct}%) | 速率: {int(speed):,} c/s | 剩餘: {self.format_time(eta)}"
                    self.progress_updated.emit(pct, text)
                    last_update_time = now

            # 門檻檢查：必須每組都有邊
            if len(set(assignment)) < self.k: continue

            # 連通性與指標計算
            is_valid = True
            diameters = []
            for g_remove in range(self.k):
                subset = [self.edges_data[i] for i, g in enumerate(assignment) if g != g_remove]
                if not self.is_connected(subset):
                    is_valid = False
                    break
                diameters.append(self.get_max_diameter(subset))
            
            if is_valid:
                # M1 數量平衡
                group_sizes = [assignment.count(i) for i in range(self.k)]
                m1 = sum((s - E_count/self.k)**2 for s in group_sizes)
                # M2 拓樸平衡
                m2 = 0
                for node in self.nodes:
                    node_counts = [0]*self.k
                    for i, (u, v, _) in enumerate(self.edges_data):
                        if u == node or v == node: node_counts[assignment[i]] += 1
                    avg_n = sum(node_counts)/self.k
                    m2 += sum((c - avg_n)**2 for c in node_counts)
                
                valid_solutions.append({
                    "assignment": assignment, "m1": m1, "m2": m2, "m3": max(diameters)
                })

        final_elapsed = time.time() - start_time
        self.progress_updated.emit(100, f"搜尋結束 | 總耗時: {self.format_time(final_elapsed)}")

        if not valid_solutions:
            self.search_finished.emit(None, 0, 0, final_elapsed)
            return

        # 打分數邏輯
        m1_v, m2_v, m3_v = [s["m1"] for s in valid_solutions], [s["m2"] for s in valid_solutions], [s["m3"] for s in valid_solutions]
        mi1, ma1 = min(m1_v), max(m1_v)
        mi2, ma2 = min(m2_v), max(m2_v)
        mi3, ma3 = min(m3_v), max(m3_v)
        
        def norm(v, mi, ma): return (v - mi) / (ma - mi) if ma != mi else 0.0
        W1, W2, W3 = self.weights
        best_sol, best_score = None, float('inf')

        for sol in valid_solutions:
            score = W1*norm(sol["m1"],mi1,ma1) + W2*norm(sol["m2"],mi2,ma2) + W3*norm(sol["m3"],mi3,ma3)
            sol["final_score"] = score
            if score < best_score:
                best_score = score
                best_sol = sol

        best_count = sum(1 for s in valid_solutions if abs(s["final_score"] - best_score) < 1e-9)
        self.search_finished.emit(best_sol, len(valid_solutions), best_count, final_elapsed)

# ==========================================
# 主視窗 (MainWindow)
# ==========================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python Graph Editor - 最佳平衡容錯分析 (高效優化版)")
        self.resize(1300, 800)
        self.nodes, self.edges_data, self.node_id_counter, self.worker = [], [], 0, None
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 控制列
        top_layout = QHBoxLayout()
        self.add_node_btn = self.create_btn(top_layout, "新增節點 (+)", self.add_new_node)
        self.arrange_btn = self.create_btn(top_layout, "自動排列", self.arrange_nodes_circle)
        top_layout.addWidget(QLabel(" 分組(K)"))
        self.k_input = QSpinBox()
        self.k_input.setRange(2, 5); self.k_input.setValue(2); self.k_input.setFixedSize(80, 40)
        self.k_input.valueChanged.connect(lambda: self.update_stats_view())
        top_layout.addWidget(self.k_input)
        self.search_btn = self.create_btn(top_layout, "開始搜尋", self.start_background_search, "#ffd700")
        self.stop_btn = self.create_btn(top_layout, "停止搜尋", self.stop_background_search, "#ff4c4c", text_color="white")
        top_layout.addStretch()
        main_layout.addLayout(top_layout)

        # 權重列
        weight_layout = QHBoxLayout()
        self.w1_i = self.create_weight(weight_layout, "W1 數量:", 0.3)
        self.w2_i = self.create_weight(weight_layout, "W2 拓樸:", 0.3)
        self.w3_i = self.create_weight(weight_layout, "W3 效能:", 0.4)
        weight_layout.addStretch()
        main_layout.addLayout(weight_layout)

        self.p_bar = QProgressBar()
        self.p_bar.setVisible(False); self.p_bar.setRange(0, 100); self.p_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.p_bar)

        self.scene = QGraphicsScene(); self.scene.setSceneRect(0, 0, 1000, 800)
        self.view = QGraphicsView(self.scene); self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        main_layout.addWidget(self.view, stretch=7)

        # 底部面板
        info_layout = QHBoxLayout()
        self.log_te = self.create_te(info_layout, "System Log", 4)
        self.matrix_te = self.create_te(info_layout, "Adjacency Matrix", 2, mono=True)
        
        stat_box = QVBoxLayout(); stat_box.addWidget(QLabel("即時統計資訊"))
        self.st_n = QLabel("節點數量: 0"); self.st_e = QLabel("連線數量: 0")
        self.st_t = QLabel("可能分法: 0"); self.st_v = QLabel("合法分法: 等待...")
        for l in [self.st_n, self.st_e, self.st_t, self.st_v]:
            l.setFont(QFont("Arial", 11)); stat_box.addWidget(l)
        self.st_v.setStyleSheet("color: blue; font-weight: bold;")
        stat_box.addStretch(); info_layout.addLayout(stat_box, 1)
        main_layout.addLayout(info_layout, stretch=3)

        self.update_matrix_view(); self.update_stats_view(); self.stop_btn.setEnabled(False)

    def create_btn(self, layout, txt, slot, bg=None, text_color="black"):
        b = QPushButton(txt); b.setFixedHeight(40); b.clicked.connect(slot)
        if bg: b.setStyleSheet(f"background-color: {bg}; color: {text_color}; font-weight: bold;")
        layout.addWidget(b); return b

    def create_weight(self, layout, txt, val):
        layout.addWidget(QLabel(txt))
        s = QDoubleSpinBox(); s.setRange(0, 10); s.setSingleStep(0.1); s.setValue(val)
        layout.addWidget(s); return s

    def create_te(self, layout, title, stretch, mono=False):
        v = QVBoxLayout(); v.addWidget(QLabel(title))
        t = QTextEdit(); t.setReadOnly(True); t.setMinimumHeight(180)
        if mono: t.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        v.addWidget(t); layout.addLayout(v, stretch); return t

    def log_message(self, msg):
        self.log_te.append(msg); self.log_te.verticalScrollBar().setValue(self.log_te.verticalScrollBar().maximum())

    def add_new_node(self):
        self.node_id_counter += 1
        pos = self.view.mapToScene(self.view.viewport().rect().center())
        n = Node(pos.x(), pos.y(), self.node_id_counter - 1, self.log_message, self.create_new_link)
        self.scene.addItem(n); self.nodes.append(n)
        self.update_matrix_view(); self.update_stats_view()

    def create_new_link(self, na, nb):
        if any((u==na and v==nb) or (u==nb and v==na) for u,v,_ in self.edges_data): return
        l = Link(na, nb); self.scene.addItem(l); self.edges_data.append((na, nb, l))
        self.update_matrix_view(); self.update_stats_view()

    def remove_node(self, node):
        for e in [e for e in self.edges_data if e[0]==node or e[1]==node]: self.remove_link(e[2])
        self.scene.removeItem(node); self.nodes.remove(node)
        self.update_matrix_view(); self.update_stats_view()

    def remove_link(self, link):
        link.source.remove_link(link); link.target.remove_link(link)
        self.scene.removeItem(link); self.edges_data = [e for e in self.edges_data if e[2]!=link]
        self.update_matrix_view(); self.update_stats_view()

    def arrange_nodes_circle(self):
        if not self.nodes: return
        c = self.view.mapToScene(self.view.viewport().rect().center())
        r = max(150, len(self.nodes) * 20)
        for i, n in enumerate(self.nodes):
            a = 2 * math.pi * i / len(self.nodes)
            n.setPos(c.x() + r * math.cos(a), c.y() + r * math.sin(a))

    def update_matrix_view(self):
        n = len(self.nodes)
        if n == 0:
            self.matrix_te.setText("等待節點...")
            return
        id_m = {nd.node_id: i for i, nd in enumerate(self.nodes)}
        mt = [[0]*n for _ in range(n)]
        for u, v, _ in self.edges_data:
            if u.node_id in id_m and v.node_id in id_m:
                mt[id_m[u.node_id]][id_m[v.node_id]] = mt[id_m[v.node_id]][id_m[u.node_id]] = 1
        txt = "    " + " ".join([str(nd.node_id) for nd in self.nodes]) + "\n    " + "-"*(n*2) + "\n"
        for i, row in enumerate(mt): txt += f"{self.nodes[i].node_id} | " + " ".join(map(str, row)) + "\n"
        self.matrix_te.setText(txt)

    def update_stats_view(self):
        e, k = len(self.edges_data), self.k_input.value()
        self.st_n.setText(f"節點數量: {len(self.nodes)}")
        self.st_e.setText(f"連線數量: {e}")
        self.st_t.setText(f"可能分法: {k**e if e > 0 else 0:,}")
        self.st_v.setText("合法分法: 等待..."); self.st_v.setStyleSheet("color: blue; font-weight: bold;")

    def start_background_search(self):
        if not self.edges_data: return
        for _, _, l in self.edges_data: l.setPen(QPen(Qt.GlobalColor.red, 2))
        self.set_ui_enabled(False); self.p_bar.setVisible(True); self.p_bar.setValue(0)
        w_raw = (self.w1_i.value(), self.w2_i.value(), self.w3_i.value())
        total_w = sum(w_raw)
        weights = (0.33, 0.33, 0.33) if total_w == 0 else [w/total_w for w in w_raw]
        self.worker = SearchWorker(self.k_input.value(), self.edges_data, self.nodes, weights)
        self.worker.progress_updated.connect(lambda p, t: (self.p_bar.setValue(p), self.p_bar.setFormat(t)))
        self.worker.log_msg.connect(self.log_message)
        self.worker.search_finished.connect(self.on_search_finished); self.worker.start()

    def stop_background_search(self):
        if self.worker: self.worker.stop(); self.stop_btn.setEnabled(False)

    def set_ui_enabled(self, e):
        for w in [self.add_node_btn, self.arrange_btn, self.search_btn, self.k_input, self.w1_i, self.w2_i, self.w3_i, self.view]:
            w.setEnabled(e)
        self.stop_btn.setEnabled(not e)

    def on_search_finished(self, best, valid, b_count, elapsed):
        self.p_bar.setVisible(False); self.set_ui_enabled(True)
        self.st_v.setText(f"合法分法: {valid:,}"); self.st_v.setStyleSheet(f"color: {'green' if valid > 0 else 'red'}; font-weight: bold;")
        self.log_message(f"--- 搜尋結束 (耗時 {elapsed:.2f}s) ---")
        if valid > 0 and best:
            self.log_message(f"[結果] 發現 {valid:,} 合法解 | 同分最佳解 {b_count:,} 種")
            palette = [Qt.GlobalColor.blue, Qt.GlobalColor.green, Qt.GlobalColor.magenta, Qt.GlobalColor.darkYellow, Qt.GlobalColor.cyan]
            for i, group in enumerate(best["assignment"]): self.edges_data[i][2].setPen(QPen(palette[group % len(palette)], 3))