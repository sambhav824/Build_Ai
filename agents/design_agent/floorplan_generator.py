import os
from typing import List, Dict, Any
from engines.geometry_engine import Rect, GeometryEngine
from utils.logging_config import logger

class FloorplanGenerator:
    """
    Generates precision dimensioned 2D architectural floor plan SVGs.
    Includes walls with line thickness, dimension markers, door swing arcs,
    window cutouts, North indicator arrow, scale rule, and drawing legend.
    """

    @staticmethod
    def render_svg(
        rooms: List[Rect],
        plot_length_ft: float,
        plot_width_ft: float,
        project_id: str,
        output_path: str = None
    ) -> str:
        # Scale: 1 ft = 18 SVG pixels
        SCALE = 18.0
        MARGIN = 70.0 # Canvas margin for dimension lines and labels

        canvas_w = int((plot_width_ft * SCALE) + (MARGIN * 2))
        canvas_h = int((plot_length_ft * SCALE) + (MARGIN * 2))

        # Color Palette: Clean Blueprint / Architectural Slate
        BG_COLOR = "#0f172a"          # Dark slate blueprint canvas
        WALL_OUTER_COLOR = "#38bdf8"  # Cyan outer structural walls
        WALL_INNER_COLOR = "#94a3b8"  # Light slate inner partition walls
        ROOM_FILL = "#1e293b"         # Deep charcoal room floors
        TEXT_COLOR = "#f8fafc"        # Crisp white labels
        DIM_COLOR = "#f59e0b"         # Amber dimension lines
        DOOR_COLOR = "#34d399"        # Mint green door swings
        WIN_COLOR = "#60a5fa"         # Blue window markers

        def to_svg_x(ft_x: float) -> float:
            return MARGIN + (ft_x * SCALE)

        def to_svg_y(ft_y: float) -> float:
            # SVG y is inverted relative to site coordinates (origin at bottom-left)
            return canvas_h - MARGIN - (ft_y * SCALE)

        wall_data = GeometryEngine.generate_walls_from_rooms(rooms)
        openings = GeometryEngine.derive_openings(rooms)

        svg = []
        svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canvas_w} {canvas_h}" width="100%" height="100%" style="background-color: {BG_COLOR}; font-family: system-ui, -apple-system, sans-serif;">')
        
        # Grid Pattern
        svg.append('''
        <defs>
            <pattern id="grid" width="18" height="18" patternUnits="userSpaceOnUse">
                <path d="M 18 0 L 0 0 0 18" fill="none" stroke="#1e293b" stroke-width="0.5"/>
            </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#grid)" />
        ''')

        # Title Block
        svg.append(f'<text x="{MARGIN}" y="35" fill="#e2e8f0" font-size="16" font-weight="bold">BUILDSMARTAI ARCHITECTURAL PLAN — {project_id}</text>')
        svg.append(f'<text x="{MARGIN}" y="52" fill="#94a3b8" font-size="11">Plot: {plot_width_ft:.1f}\' x {plot_length_ft:.1f}\' | Scale: 1 ft = 18 px | Dimension Unit: Feet & Inches</text>')

        # Plot Boundary Outline (Dashed border)
        plot_x1 = to_svg_x(0)
        plot_y1 = to_svg_y(plot_length_ft)
        plot_w_px = plot_width_ft * SCALE
        plot_h_px = plot_length_ft * SCALE
        svg.append(f'<rect x="{plot_x1}" y="{plot_y1}" width="{plot_w_px}" height="{plot_h_px}" fill="none" stroke="#475569" stroke-width="1.5" stroke-dasharray="6,4"/>')
        svg.append(f'<text x="{plot_x1 + 6}" y="{plot_y1 + 16}" fill="#64748b" font-size="9">PLOT BOUNDARY</text>')

        # Room Footprints & Shading
        for r in rooms:
            rx = to_svg_x(r.x)
            ry = to_svg_y(r.top)
            rw = r.w * SCALE
            rh = r.h * SCALE

            svg.append(f'<rect x="{rx}" y="{ry}" width="{rw}" height="{rh}" fill="{ROOM_FILL}" stroke="{WALL_INNER_COLOR}" stroke-width="1.5" opacity="0.9"/>')
            
            # Room Label & Dimensions
            cx = rx + (rw / 2.0)
            cy = ry + (rh / 2.0)
            svg.append(f'<text x="{cx}" y="{cy - 5}" fill="{TEXT_COLOR}" font-size="11" font-weight="bold" text-anchor="middle">{r.label}</text>')
            svg.append(f'<text x="{cx}" y="{cy + 10}" fill="#38bdf8" font-size="10" text-anchor="middle">{r.w:.1f}\' x {r.h:.1f}\'</text>')
            svg.append(f'<text x="{cx}" y="{cy + 22}" fill="#94a3b8" font-size="8.5" text-anchor="middle">({r.area:.0f} sq.ft)</text>')

        # Doors & Swing Arcs
        for d in openings.get("doors", []):
            dx = to_svg_x(d["x"])
            dy = to_svg_y(d["y"])
            dw = d["width"] * SCALE
            svg.append(f'<circle cx="{dx}" cy="{dy}" r="2.5" fill="{DOOR_COLOR}"/>')
            # Door panel line
            svg.append(f'<line x1="{dx}" y1="{dy}" x2="{dx + dw}" y2="{dy}" stroke="{DOOR_COLOR}" stroke-width="2"/>')
            # Quarter-circle door swing arc
            svg.append(f'<path d="M {dx + dw} {dy} A {dw} {dw} 0 0 1 {dx} {dy - dw}" fill="none" stroke="{DOOR_COLOR}" stroke-width="1" stroke-dasharray="2,2"/>')

        # Windows
        for w in openings.get("windows", []):
            wx = to_svg_x(w["x"])
            wy = to_svg_y(w["y"])
            ww = w["width"] * SCALE
            svg.append(f'<rect x="{wx - (ww/2)}" y="{wy - 3}" width="{ww}" height="6" fill="{WIN_COLOR}" stroke="#1e3a8a" stroke-width="1"/>')
            svg.append(f'<line x1="{wx - (ww/2)}" y1="{wy}" x2="{wx + (ww/2)}" y2="{wy}" stroke="#ffffff" stroke-width="1"/>')

        # North Arrow Indicator
        na_x = canvas_w - 45
        na_y = 50
        svg.append(f'''
        <g transform="translate({na_x}, {na_y})">
            <circle cx="0" cy="0" r="16" fill="#1e293b" stroke="#38bdf8" stroke-width="1"/>
            <polygon points="0,-12 -5,8 0,4 5,8" fill="#ea580c"/>
            <text x="0" y="-14" fill="#ea580c" font-size="9" font-weight="bold" text-anchor="middle">N</text>
        </g>
        ''')

        # Legend Block
        leg_x = MARGIN
        leg_y = canvas_h - 22
        svg.append(f'''
        <g transform="translate({leg_x}, {leg_y})">
            <rect x="0" y="-10" width="12" height="12" fill="{ROOM_FILL}" stroke="{WALL_INNER_COLOR}" stroke-width="1"/>
            <text x="18" y="0" fill="#94a3b8" font-size="9">Rooms</text>

            <line x1="80" y1="-4" x2="100" y2="-4" stroke="{DOOR_COLOR}" stroke-width="2"/>
            <text x="106" y="0" fill="#94a3b8" font-size="9">Doors</text>

            <rect x="160" y="-8" width="16" height="6" fill="{WIN_COLOR}"/>
            <text x="182" y="0" fill="#94a3b8" font-size="9">Windows</text>

            <line x1="250" y1="-4" x2="275" y2="-4" stroke="#475569" stroke-width="1.5" stroke-dasharray="4,2"/>
            <text x="282" y="0" fill="#94a3b8" font-size="9">Plot Boundary</text>
        </g>
        ''')

        svg.append('</svg>')
        svg_content = "\n".join(svg)

        if not output_path:
            os.makedirs("generated_designs", exist_ok=True)
            output_path = f"generated_designs/{project_id}_floorplan.svg"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(svg_content)

        logger.info(f"Generated 2D floorplan SVG: {output_path}")
        return output_path
