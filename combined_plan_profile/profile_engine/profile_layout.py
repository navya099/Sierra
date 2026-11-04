"""준공 종단면도에서 추출한 상대 배치 기준. DXF 좌표 단위 기준.

도곽 원점과는 무관한 밴드 좌하단 기준의 로컬 좌표계.
추후 도곽 위치가 확정되면 origin_x, origin_y만 변경한다.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class ProfileLayout:
    origin_x: float = 0.0
    origin_y: float = 0.0
    label_column_width: float = 40.0
    profile_width: float = 700.0
    alignment_height: float = 20.0
    ground_height: float = 20.0
    design_height: float = 20.0
    fill_height: float = 15.0
    cut_height: float = 15.0
    distance_rule_offset: float = 20.0
    grade_rule_offset: float = 40.0
    data_text_height: float = 2.4
    label_text_height: float = 5.0

    @property
    def alignment_top(self): return self.alignment_height
    @property
    def ground_top(self): return self.alignment_top + self.ground_height
    @property
    def design_top(self): return self.ground_top + self.design_height
    @property
    def fill_top(self): return self.design_top + self.fill_height
    @property
    def band_top(self): return self.fill_top + self.cut_height
    @property
    def distance_rule_y(self): return self.origin_y + self.band_top + self.distance_rule_offset
    @property
    def grade_rule_y(self): return self.origin_y + self.band_top + self.grade_rule_offset
    @property
    def data_left_x(self): return self.origin_x + self.label_column_width
    @property
    def data_right_x(self): return self.data_left_x + self.profile_width

    def xy(self, local_x: float, local_y: float):
        return self.origin_x + local_x, self.origin_y + local_y

    def band_line_y(self, local_y: float):
        return self.origin_y + local_y

    def station_x(self, sta: float, start_sta: float, horizontal_scale: float = 1000.0):
        if horizontal_scale <= 0:
            raise ValueError("horizontal_scale must be positive")
        return self.data_left_x + (sta - start_sta) * 1000.0 / horizontal_scale

    def elevation_y(self, elevation: float, datum_el: float,
                    graph_datum_y: float, vertical_scale: float = 400.0):
        if vertical_scale <= 0:
            raise ValueError("vertical_scale must be positive")
        return self.origin_y + graph_datum_y + (elevation - datum_el) * 1000.0 / vertical_scale
