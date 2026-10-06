"""Named components and transactional, bounded edits; voxel contract remains 1.0."""
from typing import Literal, Annotated
from pydantic import Field, model_validator
from .schemas import StrictModel, Size
from .blueprint import Part, Blueprint, compile_blueprint
from .detailed_generator import DetailPart, expand_parts
from .materials import match_material

class Camera(StrictModel):
    # Position orbiting the model: yaw 0 = front (-Z), +90 = right (+X).
    yaw: float = Field(ge=-180, le=180, allow_inf_nan=False)
    pitch: float = Field(ge=-10, le=80, allow_inf_nan=False)

class Study(StrictModel):
    subject: str = Field(min_length=1,max_length=160)
    proportions: Size
    silhouette: str = Field(min_length=1,max_length=500)
    landmarks: list[str] = Field(min_length=1,max_length=12)
    symmetry: Literal['none','x','z']
    material_notes: str = Field(max_length=500)
    assumptions: list[str] = Field(max_length=6)
    camera: Camera

    @model_validator(mode='after')
    def short_text(self):
        if any(len(x)>300 for x in self.landmarks+self.assumptions):
            raise ValueError('Nota longa demais')
        return self

class Component(DetailPart):
    id: str = Field(pattern=r'^[a-z][a-z0-9_]{0,47}$')
    color: list[Annotated[int, Field(strict=True,ge=0,le=255)]] = Field(min_length=3,max_length=3)
    material: Literal['paint','stone','wood','glass','metal','fabric','ceramic','light','foliage','air']
    role: Literal['wall','roof','window','detail']

    @model_validator(mode='after')
    def valid_color(self):
        if any(type(n) is not int or n<0 or n>255 for n in self.color):
            raise ValueError('RGB inválido')
        if (self.block=='minecraft:air') != (self.material=='air'):
            raise ValueError('Ar precisa de material air')
        return self

class ScenePlan(StrictModel):
    summary: str = Field(min_length=1,max_length=400)
    size: Size
    components: list[Component] = Field(min_length=1,max_length=96)

    @model_validator(mode='after')
    def unique_ids(self):
        if len({p.id for p in self.components})!=len(self.components):
            raise ValueError('IDs de componentes duplicados')
        return self

class Edit(StrictModel):
    target: str = Field(pattern=r'^[a-z][a-z0-9_]{0,47}$')
    action: Literal['replace','add','remove']
    component: Component | None

    @model_validator(mode='after')
    def coherent(self):
        if self.action=='remove':
            if self.component is not None: raise ValueError('Remoção não aceita componente')
        elif self.component is None or self.component.id!=self.target:
            raise ValueError('Componente precisa corresponder ao alvo')
        return self

class Corrections(StrictModel):
    corrections: list[Edit] = Field(max_length=12)
    # Uniform coordinates remain voxel units. Optional overall resize scales existing parts.
    size: Size | None

class Assessment(StrictModel):
    structure: float = Field(ge=0,le=100,allow_inf_nan=False)
    detail: float = Field(ge=0,le=100,allow_inf_nan=False)
    silhouette: float = Field(ge=0,le=100,allow_inf_nan=False)
    proportion: float = Field(ge=0,le=100,allow_inf_nan=False)
    color: float = Field(ge=0,le=100,allow_inf_nan=False)
    issues: list[str] = Field(max_length=12)

    @model_validator(mode='after')
    def short_issues(self):
        if any(len(s)>240 for s in self.issues): raise ValueError('Issue longa demais')
        return self

class Assembly(Blueprint):
    parts: list[Part] = Field(min_length=1,max_length=192)


def compile_scene(plan,study,build_id,options,max_blocks,bounds):
    parts=[]
    for component in plan.components:
        data=component.model_dump(exclude={'id','color','material','role'})
        if component.material!='air':
            data['block']=match_material(component.color,component.material,component.role,options.allow_transparent)
        if not options.preserve_symmetry or study.symmetry != component.mirror:
            data['mirror']='none'
        parts.append(DetailPart.model_validate(data))
    assembly=Assembly(summary=plan.summary,assumptions=study.assumptions,size=plan.size,parts=expand_parts(parts,plan.size))
    return compile_blueprint(assembly,build_id,options,max_blocks,bounds)


def apply_corrections(plan,changes):
    """Copy then validate. Failure cannot mutate the current best plan."""
    data=plan.model_dump()
    if changes.size:
        old=plan.size.model_dump(); new=changes.size.model_dump()
        for component in data['components']:
            for corner in ('start','end'):
                for axis,key in zip('xyz',('width','height','depth')):
                    component[corner][axis]=round(component[corner][axis]*(new[key]-1)/max(1,old[key]-1))
        data['size']=new
    components={c['id']:c for c in data['components']}
    seen=set()
    for edit in changes.corrections:
        if edit.target in seen: raise ValueError('Alvo repetido na correção')
        seen.add(edit.target)
        if edit.action=='add':
            if edit.target in components: raise ValueError('ID adicionado já existe')
        elif edit.target not in components: raise ValueError('Alvo não existe')
        if edit.action=='remove': del components[edit.target]
        else: components[edit.target]=edit.component.model_dump()
    data['components']=list(components.values())
    return ScenePlan.model_validate(data)
