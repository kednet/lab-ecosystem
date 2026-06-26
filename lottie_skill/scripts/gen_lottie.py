"""Create a new Lottie JSON animation from a Python spec (programmatic generation).

Usage example in your own script:
    from gen_lottie import LottieDoc, Rect, Ellipse, Path, Fill, Keyframe, hex_to_rgb01

    doc = LottieDoc(width=96, height=96, fps=30, duration_frames=30)
    doc.add_layer("heart", shapes=[
        Path(vertices=[(0,-16),(-26,-8),(-30,0),(0,30),(30,0),(26,-8)], closed=True),
        Fill(color=hex_to_rgb01("#800F2E")),
    ], position=(48,48), scale_keyframes=[
        Keyframe(t=0, value=85),
        Keyframe(t=15, value=110),
        Keyframe(t=30, value=85),
    ])
    doc.save("my_animation.json")
"""
import json
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Union


Number = Union[int, float]


def hex_to_rgb01(hex_str: str) -> List[float]:
    """Convert '#RRGGBB' to [r, g, b, 1.0] in 0-1 range."""
    h = hex_str.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return [r / 255, g / 255, b / 255, 1.0]


@dataclass
class Keyframe:
    """Generic keyframe for a single value (e.g. scale=85)."""
    t: int  # frame number
    value: Number
    # Easing: i/o control points. Defaults: smooth ease-in-out
    i_x: float = 0.4
    i_y: float = 1.0
    o_x: float = 0.6
    o_y: float = 0.0


@dataclass
class Vec2Keyframe:
    """Keyframe for 2D value (e.g. position=[x,y])."""
    t: int
    x: Number
    y: Number
    i_x: float = 0.4
    i_y: float = 1.0
    o_x: float = 0.6
    o_y: float = 0.0


@dataclass
class Vec3Keyframe:
    """Keyframe for 3D value (e.g. scale=[sx,sy,sz])."""
    t: int
    x: Number
    y: Number
    z: Number = 100
    i_x: float = 0.4
    i_y: float = 1.0
    o_x: float = 0.6
    o_y: float = 0.0


@dataclass
class Rect:
    """Rounded rectangle shape primitive."""
    width: Number
    height: Number
    corner_radius: Number = 0
    position: Tuple[Number, Number] = (0, 0)


@dataclass
class Ellipse:
    """Ellipse shape primitive. width/height = full diameter (not radius)."""
    width: Number
    height: Number
    position: Tuple[Number, Number] = (0, 0)


@dataclass
class Path:
    """Closed/open path shape primitive.
    vertices are anchor points, in_controls/out_controls are bezier control points.
    If in_controls/out_controls are empty, all points use [0,0] (straight lines, smooth poly).
    """
    vertices: List[Tuple[Number, Number]]
    closed: bool = True
    in_controls: Optional[List[Tuple[Number, Number]]] = None
    out_controls: Optional[List[Tuple[Number, Number]]] = None


@dataclass
class Fill:
    """Solid color fill."""
    color: List[float]  # [r, g, b, a] in 0-1
    opacity: Number = 100


@dataclass
class Layer:
    name: str
    shapes: List[Union[Rect, Ellipse, Path, Fill]] = field(default_factory=list)
    position: Tuple[Number, Number] = (0, 0)
    anchor: Tuple[Number, Number] = (0, 0)
    scale: Union[Number, Tuple[Number, Number]] = 100  # uniform or [sx, sy]
    opacity: Number = 100
    rotation: Number = 0
    scale_keyframes: Optional[List[Vec3Keyframe]] = None
    opacity_keyframes: Optional[List[Keyframe]] = None
    position_keyframes: Optional[List[Vec2Keyframe]] = None


class LottieDoc:
    """Builder for Lottie JSON v5.7+."""

    def __init__(self, width: int, height: int, fps: int = 30, duration_frames: int = 60, name: str = "animation"):
        self.width = width
        self.height = height
        self.fps = fps
        self.duration = duration_frames
        self.name = name
        self.layers: List[Layer] = []

    def add_layer(
        self,
        name: str,
        shapes: List[Union[Rect, Ellipse, Path, Fill]],
        position: Tuple[Number, Number] = (0, 0),
        scale: Union[Number, Tuple[Number, Number]] = 100,
        opacity: Number = 100,
        rotation: Number = 0,
        scale_keyframes: Optional[List[Vec3Keyframe]] = None,
        opacity_keyframes: Optional[List[Keyframe]] = None,
        position_keyframes: Optional[List[Vec2Keyframe]] = None,
    ) -> "LottieDoc":
        layer = Layer(
            name=name,
            shapes=shapes,
            position=position,
            scale=scale,
            opacity=opacity,
            rotation=rotation,
            scale_keyframes=scale_keyframes,
            opacity_keyframes=opacity_keyframes,
            position_keyframes=position_keyframes,
        )
        self.layers.append(layer)
        return self

    def to_dict(self) -> dict:
        layers_json = []
        # First layer in self.layers is drawn on TOP. Self.layers[0] should be the topmost visual layer.
        for i, layer in enumerate(self.layers):
            shapes_json = [self._shape_to_json(s) for s in layer.shapes]
            scale_value = (
                [layer.scale, layer.scale, 100]
                if isinstance(layer.scale, (int, float))
                else [layer.scale[0], layer.scale[1], 100]
            )

            scale_prop = (
                self._build_keyframes([Vec3Keyframe(t=kf.t, x=kf.x, y=kf.y, z=kf.z) for kf in layer.scale_keyframes])
                if layer.scale_keyframes
                else {"a": 0, "k": scale_value}
            )
            opacity_prop = (
                self._build_keyframes_simple([Keyframe(t=kf.t, value=kf.value) for kf in layer.opacity_keyframes])
                if layer.opacity_keyframes
                else {"a": 0, "k": layer.opacity}
            )
            pos_prop = (
                self._build_keyframes_pos(layer.position_keyframes)
                if layer.position_keyframes
                else {"a": 0, "k": [layer.position[0], layer.position[1], 0]}
            )

            layers_json.append({
                "ddd": 0,
                "ind": i + 1,
                "ty": 4,
                "nm": layer.name,
                "sr": 1,
                "ks": {
                    "o": opacity_prop,
                    "r": {"a": 0, "k": layer.rotation},
                    "p": pos_prop,
                    "a": {"a": 0, "k": [0, 0, 0]},
                    "s": scale_prop,
                },
                "ao": 0,
                "shapes": shapes_json,
                "ip": 0,
                "op": self.duration,
                "st": 0,
                "bm": 0,
            })

        return {
            "v": "5.7.6",
            "fr": self.fps,
            "ip": 0,
            "op": self.duration,
            "w": self.width,
            "h": self.height,
            "nm": self.name,
            "ddd": 0,
            "assets": [],
            "layers": layers_json,
            "markers": [],
        }

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @staticmethod
    def _shape_to_json(shape: Union[Rect, Ellipse, Path, Fill]) -> dict:
        if isinstance(shape, Rect):
            return {
                "ty": "rc",
                "p": {"a": 0, "k": list(shape.position)},
                "s": {"a": 0, "k": [shape.width, shape.height]},
                "r": {"a": 0, "k": shape.corner_radius},
            }
        if isinstance(shape, Ellipse):
            return {
                "ty": "el",
                "p": {"a": 0, "k": list(shape.position)},
                "s": {"a": 0, "k": [shape.width, shape.height]},
            }
        if isinstance(shape, Path):
            n = len(shape.vertices)
            if shape.in_controls is None:
                in_ctrls = [[0, 0] for _ in range(n)]
            else:
                in_ctrls = [list(c) for c in shape.in_controls]
            if shape.out_controls is None:
                out_ctrls = [[0, 0] for _ in range(n)]
            else:
                out_ctrls = [list(c) for c in shape.out_controls]
            return {
                "ty": "sh",
                "ks": {
                    "a": 0,
                    "k": {
                        "i": in_ctrls,
                        "o": out_ctrls,
                        "v": [list(v) for v in shape.vertices],
                        "c": shape.closed,
                    },
                },
            }
        if isinstance(shape, Fill):
            return {
                "ty": "fl",
                "c": {"a": 0, "k": shape.color},
                "o": {"a": 0, "k": shape.opacity},
            }
        raise TypeError(f"Unknown shape type: {type(shape)}")

    @staticmethod
    def _build_keyframes(kfs: List[Vec3Keyframe]) -> dict:
        out_kfs = []
        for i, kf in enumerate(kfs):
            is_last = i == len(kfs) - 1
            kf_dict = {"t": kf.t, "s": [kf.x, kf.y, kf.z]}
            if not is_last:
                kf_dict["i"] = {"x": [kf.i_x, kf.i_x, kf.i_x], "y": [kf.i_y, kf.i_y, kf.i_y]}
                kf_dict["o"] = {"x": [kf.o_x, kf.o_x, kf.o_x], "y": [kf.o_y, kf.o_y, kf.o_y]}
            out_kfs.append(kf_dict)
        return {"a": 1, "k": out_kfs}

    @staticmethod
    def _build_keyframes_simple(kfs: List[Keyframe]) -> dict:
        out_kfs = []
        for i, kf in enumerate(kfs):
            is_last = i == len(kfs) - 1
            kf_dict = {"t": kf.t, "s": [kf.value]}
            if not is_last:
                kf_dict["i"] = {"x": [kf.i_x], "y": [kf.i_y]}
                kf_dict["o"] = {"x": [kf.o_x], "y": [kf.o_y]}
            out_kfs.append(kf_dict)
        return {"a": 1, "k": out_kfs}

    @staticmethod
    def _build_keyframes_pos(kfs: List[Vec2Keyframe]) -> dict:
        out_kfs = []
        for i, kf in enumerate(kfs):
            is_last = i == len(kfs) - 1
            kf_dict = {"t": kf.t, "s": [kf.x, kf.y, 0]}
            if not is_last:
                kf_dict["i"] = {"x": [kf.i_x, kf.i_x, kf.i_x], "y": [kf.i_y, kf.i_y, kf.i_y]}
                kf_dict["o"] = {"x": [kf.o_x, kf.o_x, kf.o_x], "y": [kf.o_y, kf.o_y, kf.o_y]}
            out_kfs.append(kf_dict)
        return {"a": 1, "k": out_kfs}
