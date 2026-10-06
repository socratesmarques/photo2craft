from typing import Protocol
from PIL import Image
from .schemas import GenerateOptions, Structure, Size, Cell

class StructureGenerator(Protocol):
    def generate(self, build_id: str, options: GenerateOptions, images: list[Image.Image]) -> Structure: ...

class ProceduralGenerator:
    """Image inputs are preserved for future vision providers; this MVP uses explicit options."""
    def generate(self, build_id: str, options: GenerateOptions, images: list[Image.Image]) -> Structure:
        sizes = {"small": (11, 11, 13), "medium": (17, 16, 19), "large": (25, 24, 27)}
        w, h, d = sizes.get(options.size, (options.width, options.height, options.depth))
        palettes = {
            "minecraft": ("oak_planks", "cobblestone", "spruce_planks"),
            "medieval": ("stone_bricks", "cobblestone", "spruce_planks"),
            "modern": ("white_concrete", "polished_andesite", "gray_concrete"),
            "fantasy": ("mossy_stone_bricks", "stone_bricks", "purple_concrete"),
            "cyberpunk": ("black_concrete", "gray_concrete", "cyan_concrete"),
        }
        wall, floor, roof = palettes[options.style]
        # Explicit air gives consistent interiors and enables clearing when replacement is enabled.
        grid = {(x,y,z): "air" for y in range(h) for z in range(d) for x in range(w)}
        def box(x0, y0, z0, x1, y1, z1, material):
            for y in range(max(0,y0), min(h,y1+1)):
                for z in range(max(0,z0), min(d,z1+1)):
                    for x in range(max(0,x0), min(w,x1+1)):
                        grid[x,y,z] = material
        box(0,0,0,w-1,0,d-1,floor)
        kind = options.type if options.type not in ("automatic", "other") else "house"
        if kind == "monument":
            for y in range(1,min(h,min(w,d)//2+1)):
                inset=y-1
                box(inset,y,inset,w-1-inset,y,d-1-inset,wall)
            grid[w//2,min(h-1,min(w,d)//2),d//2]="sea_lantern"
        elif kind == "castle":
            wall_h=max(4,h//2)
            box(0,1,0,w-1,wall_h,0,wall); box(0,1,d-1,w-1,wall_h,d-1,wall)
            box(0,1,0,0,wall_h,d-1,wall); box(w-1,1,0,w-1,wall_h,d-1,wall)
            for x in range(0,w,2):
                grid[x,wall_h+1,0]=wall; grid[x,wall_h+1,d-1]=wall
            for z in range(0,d,2):
                grid[0,wall_h+1,z]=wall; grid[w-1,wall_h+1,z]=wall
            for tx,tz in [(0,0),(w-3,0),(0,d-3),(w-3,d-3)]:
                box(tx,1,tz,tx+2,h-2,tz+2,wall)
                box(tx+1,1,tz+1,tx+1,h-3,tz+1,"air")
                for dx,dz in [(0,0),(2,0),(0,2),(2,2)]:grid[tx+dx,h-1,tz+dz]=roof
            box(w//2-1,1,0,w//2+1,3,0,"air")
        else:
            is_flat=kind=="building" or options.style in ("modern","cyberpunk")
            roof_h=1 if is_flat else min(w//2,h//3)
            wall_h=h-roof_h-1
            for y in range(1,wall_h+1):
                for x in range(w):
                    for z in (0,d-1):
                        grid[x,y,z]="glass" if y%4 in (2,3) and x%4 in (1,2) else wall
                for z in range(d):
                    for x in (0,w-1):
                        grid[x,y,z]="glass" if y%4 in (2,3) and z%4 in (1,2) else wall
            if is_flat:
                box(0,h-1,0,w-1,h-1,d-1,roof)
            else:
                for level in range(roof_h):
                    inset=round(level*(w//2)/max(1,roof_h-1))
                    box(inset,wall_h+1+level,0,w-1-inset,wall_h+1+level,d-1,roof)
            box(w//2,1,0,w//2,2,0,"air")
            if options.interior=="simple":
                box(2,1,2,4,1,2,"oak_planks")
                grid[2,2,2]="sea_lantern"
                if kind=="building":
                    for y in range(4,wall_h,4):
                        box(1,y,1,w-2,y,d-2,floor)
                        # Open shaft reserves access for a future stair generator.
                        box(w-3,y,d-3,w-2,y,d-2,"air")
        cells=[Cell(x=x,y=y,z=z,block="minecraft:"+material) for (x,y,z),material in grid.items()]
        return Structure(id=build_id,name=options.name,description=options.description,
                         size=Size(width=w,height=h,depth=d),blocks=cells)
