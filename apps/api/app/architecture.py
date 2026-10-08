"""Architectural schema 2.0 and deterministic compiler; export stays Structure 1.0."""
from collections import deque
from math import sqrt, floor, ceil
from typing import Annotated, Literal
from pydantic import Field, model_validator
from .blueprint import Point, Part, _inside, _line
from .schemas import StrictModel, Size, Cell, Structure, PALETTE
from .scene_plan import Study, Assessment

Id = Annotated[str, Field(pattern=r'^[a-z][a-z0-9_]{0,47}$')]
Note = Annotated[str, Field(min_length=1, max_length=240)]


class ArchitecturalStudy(Study):
    architectural_style: Note
    apparent_floors: int = Field(ge=1, le=32, strict=True)
    preserve: list[Note] = Field(min_length=1, max_length=12)
    unknown: list[Note] = Field(max_length=8)
    # Perspective compatibility is assessed BEFORE using image-space scores.
    orthographic_comparable: bool


class Material(StrictModel):
    id: Id
    block: str = Field(max_length=80)
    states: dict[str, str] = Field(default_factory=dict, max_length=8)

    @model_validator(mode='after')
    def known(self):
        Cell(x=0, y=0, z=0, block=self.block, states=self.states)
        if self.block == 'minecraft:air':
            raise ValueError('Use operação cut para aberturas, não material air')
        return self


class Evidence(StrictModel):
    kind: Literal['visible', 'inferred', 'unknown']
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    references: list[Annotated[int, Field(ge=0, le=3, strict=True)]] = Field(max_length=4)
    note: Note

    @model_validator(mode='after')
    def consistent(self):
        if self.kind == 'visible' and not self.references:
            raise ValueError('Elemento visível precisa apontar a referência')
        if self.kind == 'unknown' and self.confidence > .5:
            raise ValueError('Elemento desconhecido não pode ter alta confiança')
        return self


class Element(StrictModel):
    id: Id
    kind: Literal['volume', 'foundation', 'wall', 'floor', 'roof', 'tower', 'column', 'arch',
                  'balcony', 'stairs', 'door', 'window', 'fence', 'detail']
    shape: Literal['box', 'ellipsoid', 'cylinder', 'pyramid', 'gable', 'line', 'stairs', 'arch']
    start: Point
    end: Point
    axis: Literal['x', 'y', 'z']
    hollow: bool
    thickness: int = Field(ge=1, le=4, strict=True)
    operation: Literal['add', 'cut', 'paint']
    material: Id | None
    # Explicit earlier elements whose occupied cells may be replaced.
    overlaps: list[Id] = Field(max_length=16)
    evidence: Evidence

    @model_validator(mode='after')
    def coherent(self):
        if self.shape != 'line' and any(a > b for a, b in zip(self.start.xyz(), self.end.xyz())):
            raise ValueError('Limites invertidos')
        if self.shape in {'gable', 'stairs', 'arch'} and self.axis == 'y':
            raise ValueError('Eixo deve ser x ou z para telhado, escada ou arco')
        if (self.operation == 'cut') != (self.material is None):
            raise ValueError('cut exige material=null; add/paint exigem material')
        if self.operation in {'cut', 'paint'} and not self.overlaps:
            raise ValueError('Abertura/pintura precisa indicar overlaps')
        if self.operation != 'add' and self.hollow:
            raise ValueError('cut/paint não aceita hollow')
        return self


class Relation(StrictModel):
    source: Id
    target: Id
    relation: Literal['above', 'left_of', 'in_front_of', 'touching']


class ArchitecturalPlan(StrictModel):
    schema_version: Literal['2.0'] = '2.0'
    coordinate_system: Literal['x-east_y-up_z-south_blocks'] = 'x-east_y-up_z-south_blocks'
    orientation: Literal['north'] = 'north'
    structure_type: Note
    summary: Note
    size: Size
    palette: list[Material] = Field(min_length=1, max_length=24)
    elements: list[Element] = Field(min_length=1, max_length=96)
    relations: list[Relation] = Field(max_length=48)

    @model_validator(mode='after')
    def geometry(self):
        materials = {m.id for m in self.palette}
        if len(materials) != len(self.palette):
            raise ValueError('Material duplicado')
        seen = set()
        dims = (self.size.width, self.size.height, self.size.depth)
        for e in self.elements:
            if e.id in seen or e.id in e.overlaps:
                raise ValueError('ID duplicado ou autorreferência')
            if not set(e.overlaps) <= seen:
                raise ValueError(f'{e.id}: overlaps deve apontar elementos anteriores')
            if e.material is not None and e.material not in materials:
                raise ValueError(f'{e.id}: material inexistente')
            if any(p[i] >= dims[i] for p in (e.start.xyz(), e.end.xyz()) for i in range(3)):
                raise ValueError(f'{e.id}: coordenada fora das dimensões')
            seen.add(e.id)
        parts = {e.id: e for e in self.elements}
        for r in self.relations:
            if r.source not in seen or r.target not in seen or r.source == r.target:
                raise ValueError('Relação com alvo inválido')
            a, b = parts[r.source], parts[r.target]
            lo_a = tuple(min(x,y) for x,y in zip(a.start.xyz(),a.end.xyz()))
            hi_a = tuple(max(x,y) for x,y in zip(a.start.xyz(),a.end.xyz()))
            lo_b = tuple(min(x,y) for x,y in zip(b.start.xyz(),b.end.xyz()))
            hi_b = tuple(max(x,y) for x,y in zip(b.start.xyz(),b.end.xyz()))
            valid = {'above': lo_a[1] > hi_b[1], 'left_of': hi_a[0] < lo_b[0],
                     'in_front_of': hi_a[2] < lo_b[2],
                     'touching': all(max(lo_a[i],lo_b[i]) <= min(hi_a[i],hi_b[i])+1 for i in range(3))}[r.relation]
            if not valid:
                raise ValueError(f'Relação {r.relation} inconsistente: {r.source}/{r.target}')
        return self


class ArchitecturalAssessment(Assessment):
    comparable: bool
    perspective_note: Note


class ArchitecturalEdit(StrictModel):
    target: Id
    action: Literal['replace', 'add', 'remove']
    element: Element | None


class ArchitecturalCorrections(StrictModel):
    corrections: list[ArchitecturalEdit] = Field(max_length=6)


def apply_edits(plan, changes):
    data = plan.model_dump()
    elements = {e['id']: e for e in data['elements']}
    seen = set()
    for edit in changes.corrections:
        if edit.target in seen:
            raise ValueError('Alvo repetido')
        seen.add(edit.target)
        if edit.action == 'add':
            if edit.target in elements:
                raise ValueError('Alvo já existe')
        elif edit.target not in elements:
            raise ValueError('Alvo não existe')
        if edit.action == 'remove':
            if edit.element is not None:
                raise ValueError('Remoção exige element=null')
            del elements[edit.target]
        else:
            if edit.element is None or edit.element.id != edit.target:
                raise ValueError('Elemento não corresponde ao alvo')
            elements[edit.target] = edit.element.model_dump()
    data['elements'] = list(elements.values())
    return ArchitecturalPlan.model_validate(data)


def architecture_schema(model=ArchitecturalPlan):
    schema = model.model_json_schema()
    if 'Material' in schema.get('$defs', {}):
        schema['$defs']['Material']['properties']['block']['enum'] = [b for b in PALETTE if b != 'minecraft:air']
    return schema


def element_cells(e, size):
    lo, hi = e.start.xyz(), e.end.xyz()
    axis = 'xyz'.index(e.axis)
    if e.shape == 'line':
        part = Part(shape='line', start=e.start, end=e.end, block='minecraft:stone', axis=e.axis,
                    hollow=False, thickness=e.thickness)
        yield from ((p, False) for p, _ in _line(part, size))
        return
    inner_lo = tuple(v+e.thickness for v in lo)
    inner_hi = tuple(v-e.thickness for v in hi)
    for y in range(lo[1], hi[1]+1):
        for z in range(lo[2], hi[2]+1):
            for x in range(lo[0], hi[0]+1):
                p = (x,y,z)
                if e.shape == 'stairs':
                    # Ascends toward +axis, solid stepped volume, independent of partial block states.
                    height = 1 + (p[axis]-lo[axis])*(hi[1]-lo[1]+1)//(hi[axis]-lo[axis]+1)
                    inside = y-lo[1] < height
                elif e.shape == 'arch':
                    # Semicircular crown with grounded jambs. Inner/outer ellipses
                    # share a spring line; rounding leaves face-connected voxel steps.
                    cross = 2 if axis == 0 else 0
                    half = (hi[cross]-lo[cross]+1)/2
                    offset = abs(p[cross]-(lo[cross]+hi[cross])/2)
                    spring = lo[1]+(hi[1]-lo[1])//2
                    rise = hi[1]-spring
                    outer = spring+rise*sqrt(max(0,1-(offset/half)**2))
                    inner_half = max(.1,half-e.thickness)
                    inner = spring+max(0,rise-e.thickness)*sqrt(max(0,1-(offset/inner_half)**2))
                    inside = y <= ceil(outer) and (offset>=inner_half or y>=floor(inner))
                else:
                    inside = _inside(e.shape, p, lo, hi, axis)
                if inside:
                    hollow = e.hollow and e.shape not in {'stairs','arch'} and _inside(e.shape, p, inner_lo, inner_hi, axis)
                    yield p, hollow


def compile_architecture(plan, build_id, options, max_blocks, bounds, reference_count=None):
    size = (plan.size.width, plan.size.height, plan.size.depth)
    if any(n > limit for n,limit in zip(size,bounds)):
        raise ValueError('Plano excede dimensões solicitadas')
    work = sum(max(abs(a-b)+1 for a,b in zip(e.start.xyz(),e.end.xyz()))*125 if e.shape=='line' else
               (e.end.x-e.start.x+1)*(e.end.y-e.start.y+1)*(e.end.z-e.start.z+1) for e in plan.elements)
    if work > 6_000_000:
        raise ValueError('Orçamento de operações geométricas excedido')
    from .materials import VISUALS
    for material in plan.palette:
        visual=VISUALS[material.block]
        if visual['gravity']:
            raise ValueError('Paleta arquitetônica não aceita blocos sujeitos à gravidade')
        if visual['transparent'] and not options.allow_transparent:
            raise ValueError('Vidro/transparência desativados nas opções')
    palette = {m.id: m for m in plan.palette}
    grid = {}; owners = {}; overwritten = 0
    for e in plan.elements:
        if reference_count is not None and any(i >= reference_count for i in e.evidence.references):
            raise ValueError(f'{e.id}: referência inexistente')
        material = palette.get(e.material)
        hits = 0
        for p, interior in element_cells(e,size):
            old = grid.get(p)
            air = e.operation == 'cut' or interior
            new = ('minecraft:air', ()) if air else (material.block, tuple(sorted(material.states.items())))
            if e.operation == 'paint' and (not old or old[0] == 'minecraft:air'):
                continue
            if old and old[0] != 'minecraft:air':
                hits += 1
                if old != new and owners[p] not in e.overlaps:
                    raise ValueError(f'Colisão não declarada: {e.id}/{owners[p]} em {p}')
                overwritten += old != new
            if e.operation in {'cut','paint'} and old and old[0] != 'minecraft:air' and owners[p] not in e.overlaps:
                raise ValueError(f'{e.id}: alvo de abertura/pintura não declarado')
            grid[p] = new
            if not old or old != new:
                owners[p] = e.id
            if len(grid) > max_blocks:
                raise ValueError('Limite de blocos incluindo ar excedido')
        if e.operation in {'cut','paint'} and not hits:
            raise ValueError(f'{e.id}: abertura/pintura não atingiu nenhum elemento')
    solid = {p for p,v in grid.items() if v[0] != 'minecraft:air'}
    if not solid:
        raise ValueError('Plano sem blocos sólidos')
    # Face-connected flood fill from ground, preserving supported cantilevers.
    reached = {p for p in solid if p[1] == 0}
    queue = deque(reached)
    while queue:
        x,y,z = queue.popleft()
        for p in ((x+1,y,z),(x-1,y,z),(x,y+1,z),(x,y-1,z),(x,y,z+1),(x,y,z-1)):
            if p in solid and p not in reached:
                reached.add(p); queue.append(p)
    if reached != solid:
        raise ValueError(f'{len(solid-reached)} blocos flutuantes sem conexão com a base')
    blocks = [Cell(x=x,y=y,z=z,block=value[0],states=dict(value[1])) for (x,y,z),value in sorted(grid.items(),key=lambda item:(item[0][1],item[0][2],item[0][0]))]
    return Structure(id=build_id,name=options.name,description=options.description,size=plan.size,blocks=blocks)


def migrate_scene(scene):
    """Explicit structural migration of stored/debug v1 ScenePlan; uncertainty is unknown.

    Geometry is validated separately; migration never fabricates visual evidence.
    """
    from .scene_plan import ScenePlan
    scene = ScenePlan.model_validate(scene)
    if any(c.mirror != 'none' for c in scene.components):
        raise ValueError('Expanda espelhamentos do ScenePlan antes de migrar')
    elements=[]; palette=[]
    for c in scene.components:
        mid='material_'+str(len(palette))
        if c.material != 'air':
            palette.append(dict(id=mid,block=c.block,states={}))
        elements.append(dict(id=c.id,kind=c.role if c.role in {'wall','roof','window','detail'} else 'volume',
                             **c.model_dump(include={'shape','start','end','axis','hollow','thickness'}),
                             operation='cut' if c.material=='air' else 'add',material=None if c.material=='air' else mid,
                             overlaps=[e['id'] for e in elements][-16:],
                             evidence=dict(kind='unknown',confidence=0,references=[],note='Migrado: evidência original não registrada.')))
    return ArchitecturalPlan(structure_type='Migrado',summary=scene.summary[:240],size=scene.size,palette=palette,elements=elements,relations=[])
