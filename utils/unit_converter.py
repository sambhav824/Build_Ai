from typing import Tuple

class UnitConverter:
    """
    Standard dimensional and area conversion utilities for construction engineering.
    """
    SQFT_TO_SQM = 0.092903
    SQM_TO_SQFT = 10.7639
    FT_TO_M = 0.3048
    M_TO_FT = 3.28084
    INCH_TO_MM = 25.4
    MM_TO_INCH = 0.0393701
    CFT_TO_CUM = 0.0283168
    CUM_TO_CFT = 35.3147

    @staticmethod
    def sqft_to_sqm(sqft: float) -> float:
        return round(sqft * UnitConverter.SQFT_TO_SQM, 2)

    @staticmethod
    def sqm_to_sqft(sqm: float) -> float:
        return round(sqm * UnitConverter.SQM_TO_SQFT, 2)

    @staticmethod
    def feet_to_meters(ft: float) -> float:
        return round(ft * UnitConverter.FT_TO_M, 2)

    @staticmethod
    def meters_to_feet(m: float) -> float:
        return round(m * UnitConverter.M_TO_FT, 2)

    @staticmethod
    def compute_plot_dimensions(area_sqft: float, length_ft: float = None, width_ft: float = None) -> Tuple[float, float, float]:
        """
        Derives or validates length, width, and area in sq ft.
        Assumes standard residential proportion 1:1.33 if only area is provided.
        """
        if length_ft and width_ft:
            calc_area = length_ft * width_ft
            return round(calc_area, 2), float(length_ft), float(width_ft)
        elif length_ft and area_sqft:
            width = area_sqft / length_ft
            return float(area_sqft), float(length_ft), round(width, 2)
        elif width_ft and area_sqft:
            length = area_sqft / width_ft
            return float(area_sqft), round(length, 2), float(width_ft)
        elif area_sqft:
            # Aspect ratio 1.33: length = sqrt(area * 1.33), width = area / length
            length = (area_sqft * 1.333) ** 0.5
            width = area_sqft / length
            return float(area_sqft), round(length, 2), round(width, 2)
        return 1200.0, 40.0, 30.0
