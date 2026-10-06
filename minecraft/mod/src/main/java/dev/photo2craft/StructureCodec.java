package dev.photo2craft;

import com.google.gson.*;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.*;

public final class StructureCodec {
    private final ModConfig config;
    private final JsonObject palette;
    public StructureCodec(ModConfig config) {
        this.config = config;
        try (var stream = Objects.requireNonNull(getClass().getResourceAsStream("/block-palette.json"));
             var reader = new InputStreamReader(stream, StandardCharsets.UTF_8)) {
            palette = JsonParser.parseReader(reader).getAsJsonObject();
        } catch (Exception e) { throw new IllegalStateException("Paleta ausente", e); }
    }
    public Structure parse(String json) {
        if (json.length() > config.maxResponseBytes) throw new IllegalArgumentException("JSON grande demais");
        JsonObject root = JsonParser.parseString(json).getAsJsonObject();
        if (!"1.0".equals(string(root,"formatVersion")) || !"1.21.1".equals(string(root,"minecraftVersion")))
            throw new IllegalArgumentException("Versão incompatível");
        if (!"north".equals(string(root,"orientation"))) throw new IllegalArgumentException("Orientação inválida");
        String id = string(root,"id"), name = string(root,"name");
        if (!id.matches("[A-Za-z0-9_-]{1,64}") || name.isBlank() || name.length()>100)
            throw new IllegalArgumentException("ID ou nome inválido");
        JsonObject size = root.getAsJsonObject("size");
        int w = integer(size,"width"), h = integer(size,"height"), d = integer(size,"depth");
        if (w<1 || h<1 || d<1 || w>config.maxDimension || h>config.maxDimension || d>config.maxDimension)
            throw new IllegalArgumentException("Dimensões excedem o limite");
        JsonArray blocks = root.getAsJsonArray("blocks");
        if (blocks.isEmpty() || blocks.size()>config.maxBlocks) throw new IllegalArgumentException("Quantidade de blocos inválida");
        List<Structure.Cell> cells = new ArrayList<>(blocks.size());
        Set<Integer> positions = new HashSet<>();
        for (JsonElement element : blocks) {
            JsonObject b = element.getAsJsonObject();
            int x=integer(b,"x"), y=integer(b,"y"), z=integer(b,"z");
            if (x<0 || x>=w || y<0 || y>=h || z<0 || z>=d || !positions.add((y*d+z)*w+x))
                throw new IllegalArgumentException("Coordenada inválida ou duplicada");
            String block=string(b,"block");
            if (!palette.has(block)) throw new IllegalArgumentException("Bloco não permitido: " + block);
            Map<String,String> states = new HashMap<>();
            if (b.has("states")) {
                for (var entry : b.getAsJsonObject("states").entrySet()) {
                    JsonObject allowed = palette.getAsJsonObject(block);
                    String value = string(b.getAsJsonObject("states"), entry.getKey());
                    if (!allowed.has(entry.getKey()) || !allowed.getAsJsonArray(entry.getKey()).contains(new JsonPrimitive(value)))
                        throw new IllegalArgumentException("Estado inválido: " + entry.getKey());
                    states.put(entry.getKey(),value);
                }
            }
            cells.add(new Structure.Cell(x,y,z,block,Map.copyOf(states)));
        }
        // Bottom-up order places supports before stairs and other decorative blocks.
        cells.sort(Comparator.comparingInt(Structure.Cell::y));
        return new Structure(id,name,w,h,d,List.copyOf(cells));
    }
    private static String string(JsonObject obj,String key) {
        JsonElement v=obj.get(key);
        if (v==null || !v.isJsonPrimitive() || !v.getAsJsonPrimitive().isString()) throw new IllegalArgumentException("Texto inválido: "+key);
        return v.getAsString();
    }
    private static int integer(JsonObject obj,String key) {
        JsonElement v=obj.get(key);
        if (v==null || !v.isJsonPrimitive() || !v.getAsJsonPrimitive().isNumber()) throw new IllegalArgumentException("Inteiro inválido: "+key);
        try { return v.getAsBigDecimal().intValueExact(); }
        catch (ArithmeticException e) { throw new IllegalArgumentException("Inteiro inválido: "+key); }
    }
}
