package dev.photo2craft;

import java.io.ByteArrayOutputStream;
import java.net.URI;
import java.net.http.*;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.List;
import java.util.concurrent.*;
import java.util.concurrent.Flow;

public final class ApiClient implements AutoCloseable {
    private final ModConfig config;
    private final StructureCodec codec;
    private final ExecutorService executor = Executors.newFixedThreadPool(2);
    private final HttpClient client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5))
            .followRedirects(HttpClient.Redirect.NEVER).build();
    public ApiClient(ModConfig config, StructureCodec codec) { this.config=config; this.codec=codec; }
    public CompletableFuture<Structure> fetch(String id) {
        if (!id.matches("[A-Za-z0-9_-]{1,64}")) return CompletableFuture.failedFuture(new IllegalArgumentException("ID inválido"));
        var req = HttpRequest.newBuilder(URI.create(config.apiBaseUrl+"/api/builds/"+id+"/structure"))
                .timeout(Duration.ofSeconds(20)).header("Accept","application/json").GET().build();
        var response = client.sendAsync(req, info -> new LimitedBody(config.maxResponseBytes));
        var result = response.thenApplyAsync(r -> {
            if (r.statusCode()!=200) throw new IllegalArgumentException("API retornou HTTP "+r.statusCode());
            Structure s=codec.parse(new String(r.body(),StandardCharsets.UTF_8));
            if (!id.equals(s.id())) throw new IllegalArgumentException("ID retornado não corresponde ao solicitado");
            return s;
        },executor).orTimeout(25,TimeUnit.SECONDS);
        result.whenComplete((value, failure) -> { if (failure != null) response.cancel(true); });
        return result;
    }
    public void close() { client.shutdownNow(); executor.shutdownNow(); }
    static final class LimitedBody implements HttpResponse.BodySubscriber<byte[]> {
        private final int limit;
        private final ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        private final CompletableFuture<byte[]> future = new CompletableFuture<>();
        private Flow.Subscription subscription;
        LimitedBody(int limit) { this.limit=limit; }
        public CompletionStage<byte[]> getBody() { return future; }
        public void onSubscribe(Flow.Subscription s) { subscription=s; s.request(1); }
        public void onNext(List<ByteBuffer> items) {
            for (ByteBuffer b:items) {
                if ((long)bytes.size()+b.remaining()>limit) {
                    subscription.cancel(); future.completeExceptionally(new IllegalArgumentException("Resposta muito grande")); return;
                }
                byte[] chunk = new byte[b.remaining()]; b.get(chunk); bytes.writeBytes(chunk);
            }
            subscription.request(1);
        }
        public void onError(Throwable e) { future.completeExceptionally(e); }
        public void onComplete() { future.complete(bytes.toByteArray()); }
    }
}
