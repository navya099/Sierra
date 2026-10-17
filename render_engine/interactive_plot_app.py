# interactive_plot_app.py
import sys
import json
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QVBoxLayout, QWidget, QToolBar, QAction
from PyQt5.QtCore import Qt
import pyqtgraph as pg


class InteractivePlotWindow(pg.PlotWidget):
    def __init__(self, ground_profile, vip_points, output_path):
        super().__init__()
        self.setWindowTitle("종단선형 인터랙티브 플롯 편집기")
        self.resize(900, 600)

        self.ground_profile = ground_profile
        self.vip_points = vip_points
        self.output_path = Path(output_path)
        self.selected_index = None
        self.current_mode = "선택"

        self.ground_line = pg.PlotDataItem(pen=pg.mkPen('b', width=2))
        self.vip_line = pg.PlotDataItem(pen=pg.mkPen('r', width=2))
        self.scatter = pg.ScatterPlotItem(size=10, brush='r')

        self.addItem(self.ground_line)
        self.addItem(self.vip_line)
        self.addItem(self.scatter)

        self.scatter.sigClicked.connect(self.on_point_clicked)
        self.setLabel('bottom', 'STA')
        self.setLabel('left', 'EL')
        self.update_plot()

    def set_mode(self, mode):
        self.current_mode = mode
        if mode == "선택":
            self.setMouseEnabled(x=True, y=True)
        elif mode == "추가":
            self.setMouseEnabled(x=False, y=False)

    def save_to_json(self):
        """수정된 VIP 데이터를 JSON 파일로 저장하여 메인 프로그램에 전달"""
        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(self.vip_points, f)

    def on_point_clicked(self, scatter, points):
        if self.current_mode == "삭제":
            idx = points[0].index()
            if 0 <= idx < len(self.vip_points):
                self.vip_points.pop(idx)
                self.update_plot()
                self.save_to_json()

    def mousePressEvent(self, event):
        if self.current_mode == "추가" and event.button() == Qt.LeftButton:
            pos = self.plotItem.vb.mapSceneToView(event.pos())
            self.vip_points.append((pos.x(), pos.y()))
            self.vip_points.sort(key=lambda p: p[0])
            self.update_plot()
            self.save_to_json()
            event.accept()
            return

        if self.current_mode == "선택" and event.button() == Qt.LeftButton:
            pos = self.plotItem.vb.mapSceneToView(event.pos())
            for i, (sta, el) in enumerate(self.vip_points):
                if abs(sta - pos.x()) < (
                        self.plotItem.vb.viewRange()[0][1] - self.plotItem.vb.viewRange()[0][0]) * 0.02:
                    self.selected_index = i
                    self.setMouseEnabled(x=False, y=False)
                    event.accept()
                    return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.current_mode == "선택" and self.selected_index is not None and (event.buttons() & Qt.LeftButton):
            pos = self.plotItem.vb.mapSceneToView(event.pos())
            self.vip_points[self.selected_index] = (pos.x(), pos.y())
            self.update_plot()
            self.save_to_json()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.selected_index is not None:
            self.vip_points.sort(key=lambda p: p[0])
            self.selected_index = None
            self.setMouseEnabled(x=True, y=True)
            self.update_plot()
            self.save_to_json()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def update_plot(self):
        if self.ground_profile:
            gx = [sta for sta, _ in self.ground_profile]
            gy = [el for _, el in self.ground_profile]
            self.ground_line.setData(gx, gy)

        if self.vip_points:
            x = [sta for sta, _ in self.vip_points]
            y = [el for _, el in self.vip_points]
            self.vip_line.setData(x, y)
            self.scatter.setData(x, y)


def main():
    if len(sys.argv) < 3:
        return
    data_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])

    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    ground_profile = data.get("ground", [])
    vip_points = data.get("vips", [])

    app = QApplication(sys.argv)
    window = QWidget()
    window.setWindowTitle("종단선형 인터랙티브 플롯")
    window.resize(900, 600)

    layout = QVBoxLayout(window)
    toolbar = QToolBar()
    act_select = QAction("선택/이동", toolbar)
    act_add = QAction("추가", toolbar)
    act_delete = QAction("삭제", toolbar)

    toolbar.addAction(act_select)
    toolbar.addAction(act_add)
    toolbar.addAction(act_delete)
    layout.addWidget(toolbar)

    plot = InteractivePlotWindow(ground_profile, vip_points, output_file)
    layout.addWidget(plot)

    act_select.triggered.connect(lambda: plot.set_mode("선택"))
    act_add.triggered.connect(lambda: plot.set_mode("추가"))
    act_delete.triggered.connect(lambda: plot.set_mode("삭제"))

    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()