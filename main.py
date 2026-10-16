import sys
import pyqtgraph as pg
from PyQt5.QtWidgets import (
    QApplication, QVBoxLayout, QWidget, QTableWidget, QTableWidgetItem,
    QToolBar, QAction
)
from PyQt5.QtCore import Qt
from Sierra.engine.profile_engine import slope

vip_points = []  # [(sta, el), ...]

def load_ground_profile_from_txt(path):
    coords = []
    with open(path, 'r') as f:
        for line in f:
            x, y = map(float, line.strip().split())
            coords.append((x, y))
    return coords

def update_table(table):
    table.blockSignals(True)
    n = len(vip_points)
    table.setRowCount(n)
    table.setColumnCount(6)
    table.setHorizontalHeaderLabels(["구분", "STA", "EL", "진입구배", "진출구배", "구배변화량"])

    if n == 0:
        table.blockSignals(False)
        return

    for i, (sta, el) in enumerate(vip_points):
        # 구분 라벨 설정 (첫 점은 BP, 중간은 VIP, 마지막은 EP)
        if n == 1:
            label = "BP/EP"
        elif i == 0:
            label = "BP"
        elif i == n - 1:
            label = "EP"
        else:
            label = f"VIP{i}"

        table.setItem(i, 0, QTableWidgetItem(label))
        table.setItem(i, 1, QTableWidgetItem(f"{sta:.2f}"))
        table.setItem(i, 2, QTableWidgetItem(f"{el:.2f}"))

        slope_in = None
        slope_out = None

        try:
            # 진입구배 (이전 점과의 구배)
            if i > 0:
                prev_sta, prev_el = vip_points[i - 1]
                slope_in = slope((prev_sta, prev_el), (sta, el))
                table.setItem(i, 3, QTableWidgetItem(f"{slope_in:.2f}"))

            # 진출구배 (다음 점과의 구배)
            if i < n - 1:
                next_sta, next_el = vip_points[i + 1]
                slope_out = slope((sta, el), (next_sta, next_el))
                table.setItem(i, 4, QTableWidgetItem(f"{slope_out:.2f}"))

            # 구배변화량
            if slope_in is not None and slope_out is not None:
                slope_change = slope_out - slope_in
                table.setItem(i, 5, QTableWidgetItem(f"{slope_change:.2f}"))
        except Exception:
            pass

    table.blockSignals(False)

class InteractivePlot(pg.PlotWidget):
    def __init__(self, table, ground_profile):
        super().__init__()
        self.table = table
        self.ground_profile = ground_profile
        self.selected_index = None
        self.current_mode = "선택"
        # 기존 __init__ 메서드 내부에 아래 줄을 추가합니다.
        self.table.itemChanged.connect(self.on_table_item_changed)
        # 아이템 관리
        self.ground_line = pg.PlotDataItem(pen=pg.mkPen('b', width=0))
        self.vip_line = pg.PlotDataItem(pen=pg.mkPen('r', width=0))
        self.scatter = pg.ScatterPlotItem(size=10, brush='r', data=list(range(len(vip_points))))

        self.addItem(self.ground_line)
        self.addItem(self.vip_line)
        self.addItem(self.scatter)

        # ScatterPlotItem의 클릭 시그널 연결
        self.scatter.sigClicked.connect(self.on_point_clicked)

        self.setLabel('bottom', 'STA')
        self.setLabel('left', 'EL')

    def set_mode(self, mode):
        self.current_mode = mode
        # 뷰 패닝(드래그로 화면 이동) 모드와 충돌 방지
        if mode == "선택":
            self.setMouseEnabled(x=True, y=True)
        elif mode == "추가":
            self.setMouseEnabled(x=False, y=False)  # 추가 모드일 때는 화면 이동 잠금

    def on_point_clicked(self, scatter, points):
        if self.current_mode == "삭제":
            idx = points[0].index()
            if 0 <= idx < len(vip_points):
                vip_points.pop(idx)
                self.update_plot()

    def mousePressEvent(self, event):
        if self.current_mode == "추가" and event.button() == Qt.LeftButton:
            pos = self.plotItem.vb.mapSceneToView(event.pos())
            vip_points.append((pos.x(), pos.y()))
            self.update_plot()
            event.accept()
            return

        if self.current_mode == "선택" and event.button() == Qt.LeftButton:
            # 클릭한 위치 근처의 점 찾기
            pos = self.plotItem.vb.mapSceneToView(event.pos())
            for i, (sta, el) in enumerate(vip_points):
                # 허용 오차 내에 있는지 확인 (화면 픽셀 또는 좌표 기준)
                if abs(sta - pos.x()) < (self.plotItem.vb.viewRange()[0][1] - self.plotItem.vb.viewRange()[0][0]) * 0.02:
                    self.selected_index = i
                    self.setMouseEnabled(x=False, y=False) # 점을 움직일 때 화면 이동 방지
                    event.accept()
                    return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.current_mode == "선택" and self.selected_index is not None and (event.buttons() & Qt.LeftButton):
            pos = self.plotItem.vb.mapSceneToView(event.pos())
            vip_points[self.selected_index] = (pos.x(), pos.y())
            self.update_plot()
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.selected_index is not None:
            self.selected_index = None
            self.setMouseEnabled(x=True, y=True) # 마우스를 떼면 화면 이동 다시 허용
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def update_plot(self):
        # 지반선
        if self.ground_profile:
            gx = [sta for sta, _ in self.ground_profile]
            gy = [el for _, el in self.ground_profile]
            self.ground_line.setData(gx, gy)

        # VIP 점과 선
        if vip_points:
            x = [sta for sta, _ in vip_points]
            y = [el for _, el in vip_points]
            self.vip_line.setData(x, y)
            self.scatter.setData(x, y)

        update_table(self.table)

    def on_table_item_changed(self, item):
        # update_table 실행 중 발생하는 변경은 무시 (무한 루프 방지)
        if self.table.signalsBlocked():
            return

        row = item.row()
        col = item.column()

        # STA(컬럼 1) 또는 EL(컬럼 2)만 수정 허용
        if col not in (1, 2):
            return

        try:
            val = float(item.text())
        except ValueError:
            return  # 숫자가 아니면 무시

        if 0 <= row < len(vip_points):
            sta, el = vip_points[row]
            if col == 1:
                sta = val
            elif col == 2:
                el = val

            # 데이터 업데이트
            vip_points[row] = (sta, el)

            # STA 기준 오름차순 정렬 (선이 꼬이는 것 방지)
            vip_points.sort(key=lambda p: p[0])

            # 그래프 및 테이블 전체 갱신
            self.update_plot()
def main():
    app = QApplication(sys.argv)
    widget = QWidget()
    layout = QVBoxLayout(widget)

    table = QTableWidget()
    ground_profile = load_ground_profile_from_txt("C:/TEMP/elevation.txt")

    plot = InteractivePlot(table, ground_profile)

    # 툴바 생성
    toolbar = QToolBar()
    select_action = QAction("선택", toolbar)
    add_action = QAction("추가", toolbar)
    delete_action = QAction("삭제", toolbar)

    toolbar.addAction(select_action)
    toolbar.addAction(add_action)
    toolbar.addAction(delete_action)

    # 모드 전환 연결
    select_action.triggered.connect(lambda: plot.set_mode("선택"))
    add_action.triggered.connect(lambda: plot.set_mode("추가"))
    delete_action.triggered.connect(lambda: plot.set_mode("삭제"))

    layout.addWidget(toolbar)
    layout.addWidget(plot)
    layout.addWidget(table)

    plot.update_plot()

    widget.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
