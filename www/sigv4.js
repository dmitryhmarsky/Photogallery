/* Минимальный клиент S3 (Cloudflare R2) с подписью AWS Signature V4. Без внешних библиотек. */
(function (root) {
  const enc = new TextEncoder();
  const hex = (buf) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
  const sha256 = async (data) => hex(await crypto.subtle.digest("SHA-256", typeof data === "string" ? enc.encode(data) : data));
  async function hmac(key, msg) {
    const k = await crypto.subtle.importKey("raw", key, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
    return new Uint8Array(await crypto.subtle.sign("HMAC", k, enc.encode(msg)));
  }
  const uriEnc = (s) => encodeURIComponent(s).replace(/[!'()*]/g, (c) => "%" + c.charCodeAt(0).toString(16).toUpperCase());
  const encPath = (p) => p.split("/").map(uriEnc).join("/");

  /** Возвращает {url, headers} для подписанного запроса. now можно подставить в тестах. */
  async function sign(cfg, method, key, opts) {
    opts = opts || {};
    const host = (cfg.endpoint ? cfg.endpoint.replace(/^https?:\/\//, "").replace(/\/+$/, "") : cfg.account + ".r2.cloudflarestorage.com");
    const scheme = cfg.endpoint && cfg.endpoint.startsWith("http://") ? "http" : "https";
    const path = "/" + uriEnc(cfg.bucket) + (key ? "/" + encPath(key) : "");
    const now = opts.now || new Date();
    const amz = now.toISOString().replace(/[:-]|\.\d{3}/g, "");
    const day = amz.slice(0, 8);
    const payload = opts.payloadHash || "UNSIGNED-PAYLOAD";
    const hdrs = { host: host, "x-amz-content-sha256": payload, "x-amz-date": amz };
    const names = Object.keys(hdrs).sort();
    const canonHeaders = names.map((n) => n + ":" + hdrs[n] + "\n").join("");
    const signed = names.join(";");
    const query = opts.query || "";
    const canon = [method, path, query, canonHeaders, signed, payload].join("\n");
    const scope = day + "/auto/s3/aws4_request";
    const sts = ["AWS4-HMAC-SHA256", amz, scope, await sha256(canon)].join("\n");
    let k = await hmac(enc.encode("AWS4" + cfg.secret), day);
    k = await hmac(k, "auto"); k = await hmac(k, "s3"); k = await hmac(k, "aws4_request");
    const sig = hex(await hmac(k, sts));
    const headers = {
      "x-amz-content-sha256": payload,
      "x-amz-date": amz,
      Authorization: "AWS4-HMAC-SHA256 Credential=" + cfg.access + "/" + scope + ", SignedHeaders=" + signed + ", Signature=" + sig,
    };
    return { url: scheme + "://" + host + path + (query ? "?" + query : ""), headers: headers, canonical: canon };
  }

  async function request(cfg, method, key, body, contentType, query) {
    const s = await sign(cfg, method, key, { query: query });
    const h = Object.assign({}, s.headers);
    if (contentType) h["Content-Type"] = contentType;
    return fetch(s.url, { method: method, headers: h, body: body });
  }

  root.R2 = {
    sign: sign,
    async getJson(cfg, key) {
      const r = await request(cfg, "GET", key);
      if (r.status === 404) return null;
      if (!r.ok) throw new Error("R2 " + r.status);
      return r.json();
    },
    async putJson(cfg, key, obj) {
      const r = await request(cfg, "PUT", key, JSON.stringify(obj), "application/json");
      if (!r.ok) throw new Error("R2 " + r.status);
    },
    async putBlob(cfg, key, blob) {
      const r = await request(cfg, "PUT", key, blob, blob.type || "application/octet-stream");
      if (!r.ok) throw new Error("R2 " + r.status);
    },
    async getBlob(cfg, key) {
      const r = await request(cfg, "GET", key);
      if (!r.ok) throw new Error("R2 " + r.status);
      return r.blob();
    },
    async del(cfg, key) {
      const r = await request(cfg, "DELETE", key);
      if (!r.ok && r.status !== 404) throw new Error("R2 " + r.status);
    },
    async head(cfg) {                      // проверка доступа к бакету
      const r = await request(cfg, "GET", "", undefined, undefined, "list-type=2&max-keys=1");
      return r.status;
    },
  };
})(typeof window !== "undefined" ? window : globalThis);
