import json
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .config import ROOT

PALETTE = json.loads((ROOT / "shared/block-palette.json").read_text())

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class Size(StrictModel):
    width: int = Field(ge=1, le=128, strict=True)
    height: int = Field(ge=1, le=128, strict=True)
    depth: int = Field(ge=1, le=128, strict=True)

class Cell(StrictModel):
    x: int = Field(ge=0, le=127, strict=True)
    y: int = Field(ge=0, le=127, strict=True)
    z: int = Field(ge=0, le=127, strict=True)
    block: str = Field(max_length=80)
    states: dict[str, str] = Field(default_factory=dict, max_length=8)

    @model_validator(mode="after")
    def validate_palette(self):
        if self.block not in PALETTE:
            raise ValueError("Bloco não permitido")
        for key, value in self.states.items():
            if key not in PALETTE[self.block] or value not in PALETTE[self.block][key]:
                raise ValueError(f"Estado inválido: {key}={value}")
        return self

class Structure(StrictModel):
    formatVersion: Literal["1.0"] = "1.0"
    minecraftVersion: Literal["1.21.1"] = "1.21.1"
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    author: str = Field(default="local", min_length=1, max_length=100)
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    thumbnail: str | None = Field(default=None, max_length=256, pattern=r"^/api/builds/[A-Za-z0-9_-]{1,64}/thumbnail$")
    orientation: Literal["north"] = "north"
    size: Size
    blocks: list[Cell] = Field(min_length=1, max_length=100000)

    @model_validator(mode="after")
    def validate_bounds(self):
        seen = set()
        for b in self.blocks:
            if b.x >= self.size.width or b.y >= self.size.height or b.z >= self.size.depth:
                raise ValueError("Bloco fora das dimensões declaradas")
            xyz = (b.x, b.y, b.z)
            if xyz in seen:
                raise ValueError("Coordenada duplicada")
            seen.add(xyz)
        return self

class GenerateOptions(StrictModel):
    name: str = Field(default="Minha construção", min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    mode: Literal["procedural", "ai"] = "procedural"
    quality: Literal["quick", "detailed"] = "quick"
    type: str = Field(default="automatic", min_length=1, max_length=120)
    fidelity: int = Field(default=80, ge=0, le=100, strict=True)
    size: Literal["small", "medium", "large", "custom"] = "small"
    style: Literal["minecraft", "medieval", "modern", "fantasy", "cyberpunk"] = "medieval"
    interior: Literal["none", "simple"] = "none"
    width: int = Field(default=11, ge=9, le=64, strict=True)
    height: int = Field(default=11, ge=9, le=64, strict=True)
    depth: int = Field(default=13, ge=9, le=64, strict=True)
