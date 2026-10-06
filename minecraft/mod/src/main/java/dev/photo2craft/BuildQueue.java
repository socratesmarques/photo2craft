package dev.photo2craft;

import net.minecraft.block.Block;
import net.minecraft.block.BlockState;
import net.minecraft.registry.Registries;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.network.ServerPlayerEntity;
import net.minecraft.server.world.ServerWorld;
import net.minecraft.state.property.Property;
import net.minecraft.text.Text;
import net.minecraft.util.BlockRotation;
import net.minecraft.util.Identifier;
import net.minecraft.util.math.BlockPos;
import java.util.*;

/** All methods are called on the server thread. A single global budget covers all jobs. */
public final class BuildQueue {
    private record Change(BlockPos pos, BlockState before, BlockState after) {}
    private record History(ServerWorld world, List<Change> changes) {}
    private static final class Job {
        final UUID owner;
        final ServerWorld world;
        final Structure structure;
        final BlockPos origin;
        final int turns;
        final List<Change> changes = new ArrayList<>();
        int cursor, applied, lastPercent=-1;
        boolean placing, undo;
        Job(UUID owner, ServerWorld world, Structure s, BlockPos origin, int turns) {
            this.owner=owner; this.world=world; structure=s; this.origin=origin; this.turns=turns;
        }
    }
    private final ModConfig config;
    private final Map<UUID,Job> jobs = new LinkedHashMap<>();
    private final LinkedHashMap<UUID,History> history = new LinkedHashMap<>();
    public BuildQueue(ModConfig config) { this.config=config; }
    public boolean busy(UUID id) { return jobs.containsKey(id); }
    public int size() { return jobs.size(); }
    public void submit(ServerPlayerEntity p, ServerWorld world, BlockPos origin, Structure s, int turns) {
        if (busy(p.getUuid()) || jobs.size()>=config.maxJobs) throw new IllegalArgumentException("Fila ocupada. Aguarde ou use /build cancel.");
        jobs.put(p.getUuid(),new Job(p.getUuid(),world,s,origin,turns));
        p.sendMessage(Text.literal("Validando área: "+s.name()+" ("+s.blocks().size()+" blocos)."),false);
    }
    public boolean cancel(UUID id) {
        Job j=jobs.remove(id);
        if (j==null) return false;
        remember(j);
        return true;
    }
    public void undo(ServerPlayerEntity p) {
        if (busy(p.getUuid()) || jobs.size()>=config.maxJobs) throw new IllegalArgumentException("Fila ocupada");
        History h=history.remove(p.getUuid());
        if(h==null) throw new IllegalArgumentException("Nenhuma construção para desfazer nesta sessão");
        Job j=new Job(p.getUuid(),h.world(),null,BlockPos.ORIGIN,0);
        j.undo=true; j.placing=true; j.changes.addAll(h.changes());
        Collections.reverse(j.changes);
        jobs.put(p.getUuid(),j);
    }
    public void tick(MinecraftServer server) {
        int budget=config.blocksPerTick;
        var iterator=jobs.values().iterator();
        while(iterator.hasNext() && budget>0) {
            Job j=iterator.next();
            ServerPlayerEntity p=server.getPlayerManager().getPlayer(j.owner);
            if(p==null || !p.hasPermissionLevel(2) || p.getServerWorld()!=j.world) {
                remember(j); iterator.remove(); continue;
            }
            try {
                while(budget>0) {
                    if(!j.placing) {
                        if(j.cursor==j.structure.blocks().size()) { j.cursor=0; j.placing=true; continue; }
                        var c=j.structure.blocks().get(j.cursor++);
                        int[] xyz=j.structure.rotate(c,j.turns);
                        BlockPos pos=j.origin.add(xyz[0],xyz[1],xyz[2]);
                        checkArea(j.world,p,pos);
                        BlockState before=j.world.getBlockState(pos);
                        if(j.world.getBlockEntity(pos)!=null) throw new IllegalArgumentException("Área contém um bloco com inventário ou dados: "+pos.toShortString());
                        if(!config.replaceExisting && !before.isAir() && !before.isReplaceable())
                            throw new IllegalArgumentException("Área ocupada em "+pos.toShortString()+". Escolha um espaço livre.");
                        j.changes.add(new Change(pos,before,resolve(c,j.turns)));
                    } else {
                        if(j.cursor==j.changes.size()) {
                            remember(j); iterator.remove();
                            p.sendMessage(Text.literal(j.undo?"Construção desfeita (alterações posteriores foram preservadas).":"Construção concluída. /build undo para desfazer."),false);
                            break;
                        }
                        Change change=j.changes.get(j.cursor);
                        checkArea(j.world,p,change.pos());
                        BlockState current=j.world.getBlockState(change.pos());
                        BlockState expected=j.undo?change.after():change.before();
                        BlockState target=j.undo?change.before():change.after();
                        if(!current.equals(expected)) {
                            if(!j.undo) throw new IllegalArgumentException("Área mudou durante a construção. Use /build undo antes de tentar novamente.");
                        } else if(!current.equals(target)) {
                            // Listener updates only: generated palette excludes physics/redstone blocks.
                            if(!j.world.setBlockState(change.pos(),target,Block.NOTIFY_LISTENERS))
                                throw new IllegalArgumentException("Não foi possível colocar bloco em "+change.pos().toShortString());
                        }
                        j.cursor++; j.applied=j.cursor;
                    }
                    budget--;
                    int total=j.placing?j.changes.size():j.structure.blocks().size();
                    int percent=(int)(100L*j.cursor/Math.max(1,total));
                    if(percent/10!=j.lastPercent/10 || j.lastPercent<0) {
                        p.sendMessage(Text.literal((!j.placing?"Validando... ":j.undo?"Desfazendo... ":"Construindo... ")+percent+"%"),true);
                        j.lastPercent=percent;
                    }
                }
            } catch(RuntimeException e) {
                remember(j); iterator.remove();
                p.sendMessage(Text.literal("Photo2Craft: "+e.getMessage()),false);
            }
        }
    }
    private void remember(Job j) {
        if(j.undo) {
            if(j.cursor<j.changes.size()) {
                var remaining=new ArrayList<>(j.changes.subList(j.cursor,j.changes.size()));
                Collections.reverse(remaining);
                history.put(j.owner,new History(j.world,List.copyOf(remaining)));
            }
            return;
        }
        if(j.applied>0) {
            history.remove(j.owner);
            history.put(j.owner,new History(j.world,List.copyOf(j.changes.subList(0,j.applied))));
            while(history.size()>8) history.remove(history.keySet().iterator().next());
        }
    }
    private static void checkArea(ServerWorld world,ServerPlayerEntity p,BlockPos pos) {
        if(world.isOutOfHeightLimit(pos) || !world.getWorldBorder().contains(pos)) throw new IllegalArgumentException("Fora dos limites do mundo");
        if(!world.isChunkLoaded(pos)) throw new IllegalArgumentException("Área não carregada. Aproxime-se ou reduza a construção.");
        if(!world.canPlayerModifyAt(p,pos)) throw new IllegalArgumentException("Sem permissão para alterar esta área");
    }
    private static BlockState resolve(Structure.Cell cell,int turns) {
        Identifier id=Identifier.tryParse(cell.block());
        if(id==null || !Registries.BLOCK.containsId(id)) throw new IllegalArgumentException("Bloco desconhecido");
        BlockState state=Registries.BLOCK.get(id).getDefaultState();
        for(var entry:cell.states().entrySet()) {
            Property<?> property=state.getBlock().getStateManager().getProperty(entry.getKey());
            if(property==null) throw new IllegalArgumentException("Estado desconhecido");
            state=apply(state,property,entry.getValue());
        }
        return state.rotate(switch(Math.floorMod(turns,4)) {
            case 1 -> BlockRotation.CLOCKWISE_90;
            case 2 -> BlockRotation.CLOCKWISE_180;
            case 3 -> BlockRotation.COUNTERCLOCKWISE_90;
            default -> BlockRotation.NONE;
        });
    }
    private static <T extends Comparable<T>> BlockState apply(BlockState state,Property<T> property,String value) {
        return state.with(property,property.parse(value).orElseThrow(()->new IllegalArgumentException("Valor de estado inválido")));
    }
}
