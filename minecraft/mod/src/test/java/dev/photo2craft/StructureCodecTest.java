package dev.photo2craft;

import com.google.gson.*;
import org.junit.jupiter.api.Test;
import java.nio.charset.StandardCharsets;
import static org.junit.jupiter.api.Assertions.*;

class StructureCodecTest {
    private String fixture() throws Exception {
        try(var in=getClass().getResourceAsStream("/test-house.json")) {
            return new String(in.readAllBytes(),StandardCharsets.UTF_8);
        }
    }
    @Test void acceptsBackendFixture() throws Exception {
        var s=new StructureCodec(new ModConfig()).parse(fixture());
        assertEquals("test-house",s.id()); assertEquals(1573,s.blocks().size());
    }
    @Test void rejectsUntrustedData() throws Exception {
        for(String mutation:new String[]{"block","bounds","fraction","duplicate","state","version"}) {
            var root=JsonParser.parseString(fixture()).getAsJsonObject();
            var blocks=root.getAsJsonArray("blocks"); var first=blocks.get(0).getAsJsonObject();
            switch(mutation) {
                case "block" -> first.addProperty("block","minecraft:command_block");
                case "bounds" -> first.addProperty("x",128);
                case "fraction" -> first.addProperty("x",0.5);
                case "duplicate" -> blocks.add(first.deepCopy());
                case "state" -> first.add("states",JsonParser.parseString("{\"axis\":\"bad\"}"));
                case "version" -> root.addProperty("formatVersion","2.0");
            }
            assertThrows(RuntimeException.class,()->new StructureCodec(new ModConfig()).parse(root.toString()),mutation);
        }
    }
    @Test void enforcesBudget() throws Exception {
        var config=new ModConfig();config.maxBlocks=10;
        String json=fixture();
        assertThrows(RuntimeException.class,()->new StructureCodec(config).parse(json));
    }
    @Test void acceptsNewConcreteColors() throws Exception {
        var root=JsonParser.parseString(fixture()).getAsJsonObject();
        var first=root.getAsJsonArray("blocks").get(0).getAsJsonObject();
        first.add("states",new JsonObject());
        for(String color:new String[]{"blue","red","yellow","orange","light_blue","green","brown","pink","lime","magenta","light_gray"}) {
            first.addProperty("block","minecraft:"+color+"_concrete");
            assertDoesNotThrow(()->new StructureCodec(new ModConfig()).parse(root.toString()));
        }
    }
    @Test void rotatesRectangularFootprint() throws Exception {
        var s=new StructureCodec(new ModConfig()).parse(fixture());
        var cell=new Structure.Cell(0,2,0,"minecraft:stone_bricks",java.util.Map.of());
        assertArrayEquals(new int[]{12,2,0},s.rotate(cell,1));
        assertArrayEquals(new int[]{10,2,12},s.rotate(cell,2));
        assertArrayEquals(new int[]{0,2,10},s.rotate(cell,3));
    }
    @Test void capsResponseWhileStreaming() {
        var body=new ApiClient.LimitedBody(4);
        var canceled=new java.util.concurrent.atomic.AtomicBoolean(false);
        body.onSubscribe(new java.util.concurrent.Flow.Subscription() {
            public void request(long n) {}
            public void cancel() { canceled.set(true); }
        });
        body.onNext(java.util.List.of(java.nio.ByteBuffer.wrap(new byte[5])));
        assertTrue(canceled.get());
        assertTrue(body.getBody().toCompletableFuture().isCompletedExceptionally());
    }
}
