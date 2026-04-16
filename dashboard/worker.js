export default {
    async fetch(request, env) {
        const url = new URL(request.url);

        // Intercept ANY DuckDB WebAssembly file
        if (url.pathname.includes("@duckdb/duckdb-wasm") && url.pathname.endsWith(".wasm")) {
            // Translate the local Observable path to the jsDelivr CDN path
            const cdnUrl = url.pathname.replace("/_npm/", "/npm/");

            // Stream the file directly from the CDN
            return fetch(`https://cdn.jsdelivr.net${cdnUrl}`);
        }

        // For every other file, serve your local static assets seamlessly
        return env.ASSETS.fetch(request);
    }
}