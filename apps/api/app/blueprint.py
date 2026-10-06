"""A bounded geometry language: the model supplies data, never executable code."""
from math import ceil
from typing import Literal
from pydantic import Field, field_validator, model_validator
from .schemas import PALETTE, Cell, GenerateOptions, Size, StrictModel, Structure


class Point(StrictModel):
    x: int = Field(ge=0, le=127, strict=True)
    y: int = Field(ge=0, le=127, strict=True)
    z: int = Field(ge=0, le=127, strict=True)

    def xyz(self):
        return (self.x, self.y, self.z)


class Part(StrictModel):
    shape: Literal["box", "ellipsoid", "cylinder", "pyramid", "gable", "line"]
    start: Point
    end: Point
    block: str
    axis: Literal["x", "y", "z"]
    hollow: bool = Field(strict=True)
    thickness: int = Field(ge=1, le=4, strict=True)

    @field_validator("block")
    @classmethod
    def allowed_block(cls, value):
        if value not in PALETTE:
            raise ValueError("Bloco não permitido no plano")
        return value

    @model_validator(mode="after")
    def ordered_box(self):
        if self.shape != "line" and any(a > b for a, b in zip(self.start.xyz(), self.end.xyz())):
            raise ValueError("Caixa invertida no plano")
        if self.shape == "gable" and self.axis == "y":
            raise ValueError("A cumeeira deve estar em X ou Z")
        return self


class Blueprint(StrictModel):
    summary: str = Field(min_length=1, max_length=600)
    assumptions: list[str] = Field(max_length=6)
    size: Size
    parts: list[Part] = Field(min_length=1, max_length=64)

    @field_validator("assumptions")
    @classmethod
    def short_assumptions(cls, values):
        if any(len(v) > 300 for v in values):
            raise ValueError("Explicação longa demais")
        return values


def blueprint_schema():
    schema = Blueprint.model_json_schema()
    schema["$defs"]["Part"]["properties"]["block"]["enum"] = list(PALETTE)
    return schema


def target_size(options: GenerateOptions, max_dimension: int) -> tuple[int, int, int]:
    if options.size == "custom":
        size = (options.width, options.height, options.depth)
    else:
        edge = min({"small": 16, "medium": 32, "large": 48}[options.size], max_dimension)
        size = (edge, edge, edge)
    if max(size) > max_dimension:
        raise ValueError("As dimensões excedem o limite configurado")
    return size


def _inside(shape, p, lo, hi, axis):
    if any(a > b for a, b in zip(lo, hi)):
        return False
    center = [(a + b) / 2 for a, b in zip(lo, hi)]
    radius = [(b - a + 1) / 2 for a, b in zip(lo, hi)]
    q = [(p[i] - center[i]) / radius[i] for i in range(3)]
    if any(p[i] < lo[i] or p[i] > hi[i] for i in range(3)):
        return False
    if shape == "box":
        return True
    if shape == "ellipsoid":
        return sum(v * v for v in q) <= 1
    if shape == "cylinder":
        return sum(q[i] ** 2 for i in range(3) if i != axis) <= 1
    if shape == "pyramid":
        factor = 1 - (p[axis] - lo[axis]) / (hi[axis] - lo[axis] + 1)
        return all(abs(q[i]) <= factor for i in range(3) if i != axis)
    # A gable is a triangular prism, with ridge along X or Z and height along Y.
    cross = 2 if axis == 0 else 0
    return abs(q[cross]) + (p[1] - lo[1]) / (hi[1] - lo[1] + 1) <= 1


def _line(part: Part, size):
    start, end = part.start.xyz(), part.end.xyz()
    steps = max(abs(a - b) for a, b in zip(start, end))
    radius = (part.thickness - 1) / 2
    extra = ceil(radius)
    for step in range(steps + 1):
        center = [round(a + (b - a) * step / max(1, steps)) for a, b in zip(start, end)]
        for dx in range(-extra, extra + 1):
            for dy in range(-extra, extra + 1):
                for dz in range(-extra, extra + 1):
                    if dx * dx + dy * dy + dz * dz > radius * radius:
                        continue
                    p = (center[0] + dx, center[1] + dy, center[2] + dz)
                    if all(0 <= p[i] < size[i] for i in range(3)):
                        yield p, part.block


def compile_blueprint(plan: Blueprint, build_id: str, options: GenerateOptions,
                      max_blocks: int, requested_size: tuple[int, int, int]) -> Structure:
    size = (plan.size.width, plan.size.height, plan.size.depth)
    if any(size[i] > requested_size[i] for i in range(3)):
        raise ValueError("O plano excede o tamanho solicitado")
    work = 0
    for part in plan.parts:
        for p in (part.start.xyz(), part.end.xyz()):
            if any(p[i] >= size[i] for i in range(3)):
                raise ValueError("Forma fora dos limites do plano")
        lengths = [abs(a - b) + 1 for a, b in zip(part.start.xyz(), part.end.xyz())]
        work += max(lengths) * 125 if part.shape == "line" else lengths[0] * lengths[1] * lengths[2]
    if work > 6_000_000:
        raise ValueError("Plano geométrico complexo demais")

    grid: dict[tuple[int, int, int], str] = {}
    for part in plan.parts:
        if part.shape == "line":
            cells = _line(part, size)
        else:
            lo, hi = part.start.xyz(), part.end.xyz()
            axis = "xyz".index(part.axis)
            inner_lo = tuple(v + part.thickness for v in lo)
            inner_hi = tuple(v - part.thickness for v in hi)
            cells = (
                ((x, y, z), "minecraft:air" if part.hollow and
                 _inside(part.shape, (x, y, z), inner_lo, inner_hi, axis) else part.block)
                for y in range(lo[1], hi[1] + 1)
                for z in range(lo[2], hi[2] + 1)
                for x in range(lo[0], hi[0] + 1)
                if _inside(part.shape, (x, y, z), lo, hi, axis)
            )
        for position, block in cells:
            grid[position] = block
            if len(grid) > max_blocks:
                raise ValueError("Plano excede o limite de blocos, incluindo ar")
    if not grid or all(v == "minecraft:air" for v in grid.values()):
        raise ValueError("O plano não contém blocos sólidos")
    cells = [Cell(x=x, y=y, z=z, block=block) for (x, y, z), block in sorted(
        grid.items(), key=lambda entry: (entry[0][1], entry[0][2], entry[0][0]))]
    return Structure(id=build_id, name=options.name, description=options.description,
                     size=plan.size, blocks=cells)
