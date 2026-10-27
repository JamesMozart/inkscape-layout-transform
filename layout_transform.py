#!/usr/bin/env python3
import math

import numpy as np

import inkex
from inkex import Transform


class LayoutTransform(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--scale_x", type=float, default=1.0)
        pars.add_argument("--scale_y", type=float, default=1.0)
        pars.add_argument("--shear_x", type=float, default=0.0)
        pars.add_argument("--shear_y", type=float, default=0.0)
        pars.add_argument("--rotate_deg", type=float, default=0.0)
        pars.add_argument("--tension", type=float, default=0.0)

    def _translate_by(self, elem, delta_x, delta_y):
        if abs(delta_x) > 1e-9 or abs(delta_y) > 1e-9:
            elem.transform = (
                Transform(f"translate({delta_x}, {delta_y})") @ elem.transform
            )

    def _tension_weights(self, ox, oy):
        """Vectorized w = 1 + tension * (1 - r / r_max); r_max over the batch."""
        tension = self.options.tension
        if abs(tension) < 1e-9:
            return np.ones_like(ox)
        r = np.hypot(ox, oy)
        r_max = float(r.max()) if r.size else 0.0
        if r_max < 1e-9:
            return np.ones_like(ox)
        return 1.0 + tension * (1.0 - r / r_max)

    def effect(self):
        if not self.svg.selection:
            inkex.errormsg("Please select at least one object.")
            return

        bbox = self.svg.selection.bounding_box()
        if bbox is None:
            return
        center_x, center_y = bbox.center_x, bbox.center_y

        # --- collect elements + their bboxes exactly once ---
        elems = []
        centers = []
        for elem in self.svg.selection:
            eb = elem.bounding_box()
            if eb is None:
                continue
            elems.append(elem)
            centers.append((eb.center_x, eb.center_y))

        if not elems:
            return

        cx = np.array([c[0] for c in centers], dtype=float)
        cy = np.array([c[1] for c in centers], dtype=float)

        sx = self.options.shear_x
        sy = self.options.shear_y
        scale_x = self.options.scale_x
        scale_y = self.options.scale_y
        angle_rad = math.radians(self.options.rotate_deg)

        has_shear = abs(sx) > 1e-9 or abs(sy) > 1e-9
        has_scale = abs(scale_x - 1.0) > 1e-9 or abs(scale_y - 1.0) > 1e-9
        has_rotate = abs(angle_rad) > 1e-9

        if not (has_shear or has_scale or has_rotate):
            return

        # accumulated per-element translation
        total_dx = np.zeros_like(cx)
        total_dy = np.zeros_like(cy)

        # ---------- Stage 1: position-only shear ----------
        if has_shear:
            ox = cx - center_x
            oy = cy - center_y
            new_ox = ox + sx * oy
            new_oy = oy + sy * ox
            dx = new_ox - ox
            dy = new_oy - oy
            w = self._tension_weights(ox, oy)
            dx *= w
            dy *= w
            total_dx += dx
            total_dy += dy
            # layout has moved; reflect that for the next stage
            cx += dx
            cy += dy

        # ---------- Stage 2: scale spacing independently per axis ----------
        if has_scale:
            ox = cx - center_x
            oy = cy - center_y
            w = self._tension_weights(ox, oy)
            dx = ox * (scale_x - 1.0)
            dy = oy * (scale_y - 1.0)
            dx *= w
            dy *= w
            total_dx += dx
            total_dy += dy
            cx += dx
            cy += dy

        # ---------- Stage 3: position-only rotation ----------
        if has_rotate:
            ox = cx - center_x
            oy = cy - center_y
            w = self._tension_weights(ox, oy)
            cos_a = np.cos(w * angle_rad)
            sin_a = np.sin(w * angle_rad)
            new_ox = ox * cos_a - oy * sin_a
            new_oy = ox * sin_a + oy * cos_a
            dx = new_ox - ox
            dy = new_oy - oy
            total_dx += dx
            total_dy += dy

        # ---------- write back once per element ----------
        for elem, dx_i, dy_i in zip(elems, total_dx, total_dy):
            self._translate_by(elem, float(dx_i), float(dy_i))


if __name__ == "__main__":
    LayoutTransform().run()