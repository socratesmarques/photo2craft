package dev.photo2craft;

import com.google.gson.GsonBuilder;
import net.fabricmc.loader.api.FabricLoader;
import java.nio.file.Files;
import java.io.IOException;
import java.net.URI;

public final class ModConfig {
    public String apiBaseUrl = "http://127.0.0.1:8000";
    public int blocksPerTick = 500;
    public int maxBlocks = 50000;
    public int maxDimension = 64;
    public int maxResponseBytes = 8388608;
    public int maxJobs = 4;
    public boolean replaceExisting = false;

    public static ModConfig load() {
        var path = FabricLoader.getInstance().getConfigDir().resolve("photo2craft.json");
        var gson = new GsonBuilder().setPrettyPrinting().create();
        try {
            ModConfig c;
            if (Files.exists(path)) c = gson.fromJson(Files.readString(path), ModConfig.class);
            else { c = new ModConfig(); Files.createDirectories(path.getParent()); Files.writeString(path, gson.toJson(c)); }
            if (c == null) throw new IllegalArgumentException("Configuração vazia");
            URI uri = URI.create(c.apiBaseUrl);
            if (!("http".equals(uri.getScheme()) || "https".equals(uri.getScheme())) || uri.getHost() == null
                    || uri.getUserInfo() != null || uri.getQuery() != null || uri.getFragment() != null)
                throw new IllegalArgumentException("apiBaseUrl inválida");
            c.apiBaseUrl = c.apiBaseUrl.replaceAll("/+$", "");
            if (c.blocksPerTick < 1 || c.blocksPerTick > 2000 || c.maxBlocks < 1 || c.maxBlocks > 100000
                    || c.maxDimension < 1 || c.maxDimension > 128 || c.maxResponseBytes < 1024
                    || c.maxResponseBytes > 16777216 || c.maxJobs < 1 || c.maxJobs > 8)
                throw new IllegalArgumentException("Limites fora da faixa permitida");
            return c;
        } catch (IOException | RuntimeException e) { throw new IllegalStateException("Revise config/photo2craft.json", e); }
    }
}
