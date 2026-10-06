package dev.photo2craft;

import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.minecraft.server.command.ServerCommandSource;
import net.minecraft.text.Text;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import static net.minecraft.server.command.CommandManager.*;

public final class Photo2Craft implements ModInitializer {
    private ModConfig config;
    private StructureCodec codec;
    private ApiClient api;
    private BuildQueue queue;
    private final Map<UUID,CompletableFuture<Structure>> pending=new HashMap<>();
    @Override public void onInitialize() {
        ServerLifecycleEvents.SERVER_STARTED.register(server -> {
            config=ModConfig.load(); codec=new StructureCodec(config); api=new ApiClient(config,codec); queue=new BuildQueue(config);
        });
        ServerLifecycleEvents.SERVER_STOPPING.register(server -> {
            pending.values().forEach(f->f.cancel(true)); pending.clear();
            if(api!=null) api.close(); queue=null;
        });
        ServerTickEvents.END_SERVER_TICK.register(server->{if(queue!=null) queue.tick(server);});
        CommandRegistrationCallback.EVENT.register((dispatcher,access,environment)->dispatcher.register(
            literal("build").requires(s->s.hasPermissionLevel(2))
                .then(literal("test").executes(c->test(c.getSource())))
                .then(literal("import").then(argument("id",StringArgumentType.word())
                    .executes(c->load(c.getSource(),StringArgumentType.getString(c,"id"),0))
                    .then(argument("rotation",IntegerArgumentType.integer(0,270))
                        .executes(c->load(c.getSource(),StringArgumentType.getString(c,"id"),IntegerArgumentType.getInteger(c,"rotation"))))))
                .then(literal("cancel").executes(c->cancel(c.getSource())))
                .then(literal("undo").executes(c->undo(c.getSource())))
        ));
    }
    private int test(ServerCommandSource source) {
        try {
            var player=source.getPlayerOrThrow();
            if(pending.containsKey(player.getUuid()) || pending.size()+queue.size()>=config.maxJobs)
                throw new IllegalArgumentException("Fila ocupada ou importação em andamento");
            try(var stream=Objects.requireNonNull(getClass().getResourceAsStream("/test-house.json"))) {
                var structure=codec.parse(new String(stream.readAllBytes(),StandardCharsets.UTF_8));
                queue.submit(player,player.getServerWorld(),player.getBlockPos().add(3,0,3),structure,0);
            }
            return 1;
        } catch(Exception e) { return error(source,e); }
    }
    private int load(ServerCommandSource source,String id,int rotation) {
        try {
            if(rotation%90!=0) throw new IllegalArgumentException("Rotação deve ser 0, 90, 180 ou 270");
            var player=source.getPlayerOrThrow(); UUID uuid=player.getUuid();
            if(pending.containsKey(uuid)||queue.busy(uuid)||pending.size()+queue.size()>=config.maxJobs)
                throw new IllegalArgumentException("Fila ocupada. Aguarde ou use /build cancel.");
            var world=player.getServerWorld(); var origin=player.getBlockPos().add(3,0,3); var server=source.getServer();
            var future=api.fetch(id); pending.put(uuid,future);
            source.sendFeedback(()->Text.literal("Buscando construção "+id+"..."),false);
            future.whenComplete((structure,failure)->server.execute(()->{
                if(!pending.remove(uuid,future) || queue==null) return;
                var current=server.getPlayerManager().getPlayer(uuid);
                if(current==null || !current.hasPermissionLevel(2)) return;
                if(current.getServerWorld()!=world) { error(source,new IllegalArgumentException("Você mudou de dimensão. Importe novamente.")); return; }
                if(failure!=null) { error(source,new IllegalArgumentException("Falha ao importar: "+rootMessage(failure))); return; }
                try { queue.submit(current,world,origin,structure,rotation/90); }
                catch(RuntimeException e) { error(source,e); }
            }));
            return 1;
        } catch(Exception e) { return error(source,e); }
    }
    private int cancel(ServerCommandSource source) {
        try {
            UUID uuid=source.getPlayerOrThrow().getUuid();
            var future=pending.remove(uuid); if(future!=null) future.cancel(true);
            boolean canceled=queue.cancel(uuid);
            source.sendFeedback(()->Text.literal(future!=null||canceled?"Cancelado. Blocos já colocados podem ser removidos com /build undo.":"Nenhuma tarefa em andamento."),false);
            return 1;
        } catch(Exception e) { return error(source,e); }
    }
    private int undo(ServerCommandSource source) {
        try {
            var player=source.getPlayerOrThrow();
            if(pending.containsKey(player.getUuid()) || pending.size()+queue.size()>=config.maxJobs)
                throw new IllegalArgumentException("Fila ocupada ou importação em andamento");
            queue.undo(player); return 1;
        }
        catch(Exception e) { return error(source,e); }
    }
    private static int error(ServerCommandSource source,Exception e) { source.sendError(Text.literal("Photo2Craft: "+e.getMessage())); return 0; }
    private static String rootMessage(Throwable e) { while(e.getCause()!=null) e=e.getCause(); return e.getMessage()==null?e.getClass().getSimpleName():e.getMessage(); }
}
