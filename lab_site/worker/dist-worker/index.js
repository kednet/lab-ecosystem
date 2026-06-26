var __defProp = Object.defineProperty;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __esm = (fn, res) => function __init() {
  return fn && (res = (0, fn[__getOwnPropNames(fn)[0]])(fn = 0)), res;
};
var __export = (target, all) => {
  for (var name in all)
    __defProp(target, name, { get: all[name], enumerable: true });
};

// worker/src/lib/kv.ts
var kv_exports = {};
__export(kv_exports, {
  DEFAULT_FREE_TIER: () => DEFAULT_FREE_TIER,
  KV_KEYS: () => KV_KEYS,
  deleteAuthCode: () => deleteAuthCode,
  ensureAuthUser: () => ensureAuthUser,
  getAuthCode: () => getAuthCode,
  getAuthUser: () => getAuthUser,
  getGenerationCounts: () => getGenerationCounts,
  incrementGenerationCount: () => incrementGenerationCount,
  recordFailedAttempt: () => recordFailedAttempt,
  setAuthCode: () => setAuthCode,
  setAuthUser: () => setAuthUser,
  userIdFromEmail: () => userIdFromEmail
});
async function userIdFromEmail(email) {
  const data = new TextEncoder().encode(email.toLowerCase().trim());
  const hash = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(hash)).map((b) => b.toString(16).padStart(2, "0")).join("");
}
async function getAuthUser(kv, email) {
  const raw2 = await kv.get(KV_KEYS.authUser(email));
  if (!raw2) return null;
  return JSON.parse(raw2);
}
async function setAuthUser(kv, user) {
  await kv.put(KV_KEYS.authUser(user.email), JSON.stringify(user));
}
async function ensureAuthUser(kv, email) {
  const existing = await getAuthUser(kv, email);
  if (existing) return existing;
  const userId = await userIdFromEmail(email);
  const now = (/* @__PURE__ */ new Date()).toISOString();
  const fresh = {
    email: email.toLowerCase().trim(),
    userId,
    createdAt: now,
    ...DEFAULT_FREE_TIER
  };
  await setAuthUser(kv, fresh);
  await kv.put(KV_KEYS.userIdToEmail(userId), fresh.email);
  return fresh;
}
async function setAuthCode(kv, email, code) {
  const payload = {
    code,
    email: email.toLowerCase().trim(),
    expiresAt: Date.now() + 10 * 60 * 1e3,
    attempts: 0
  };
  await kv.put(KV_KEYS.authCode(payload.email), JSON.stringify(payload), {
    expirationTtl: 10 * 60
  });
  return payload;
}
async function getAuthCode(kv, email) {
  const raw2 = await kv.get(KV_KEYS.authCode(email));
  if (!raw2) return null;
  return JSON.parse(raw2);
}
async function deleteAuthCode(kv, email) {
  await kv.delete(KV_KEYS.authCode(email));
}
async function recordFailedAttempt(kv, email) {
  const code = await getAuthCode(kv, email);
  if (!code) return null;
  code.attempts += 1;
  if (code.attempts >= 5) {
    await deleteAuthCode(kv, email);
    return null;
  }
  await kv.put(KV_KEYS.authCode(email), JSON.stringify(code), {
    expirationTtl: Math.max(60, Math.floor((code.expiresAt - Date.now()) / 1e3))
  });
  return code;
}
async function incrementGenerationCount(kv, userId) {
  const now = /* @__PURE__ */ new Date();
  const ym = `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, "0")}`;
  const ymd = `${ym}-${String(now.getUTCDate()).padStart(2, "0")}`;
  const [monthRaw, dayRaw] = await Promise.all([
    kv.get(KV_KEYS.genMonth(userId, ym)),
    kv.get(KV_KEYS.genDay(userId, ymd))
  ]);
  const month = parseInt(monthRaw ?? "0", 10) + 1;
  const day = parseInt(dayRaw ?? "0", 10) + 1;
  await kv.put(KV_KEYS.genMonth(userId, ym), String(month), { expirationTtl: 35 * 24 * 60 * 60 });
  await kv.put(KV_KEYS.genDay(userId, ymd), String(day), { expirationTtl: 3 * 24 * 60 * 60 });
  return { month, day };
}
async function getGenerationCounts(kv, userId) {
  const now = /* @__PURE__ */ new Date();
  const ym = `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, "0")}`;
  const ymd = `${ym}-${String(now.getUTCDate()).padStart(2, "0")}`;
  const [monthRaw, dayRaw] = await Promise.all([
    kv.get(KV_KEYS.genMonth(userId, ym)),
    kv.get(KV_KEYS.genDay(userId, ymd))
  ]);
  return {
    month: parseInt(monthRaw ?? "0", 10),
    day: parseInt(dayRaw ?? "0", 10)
  };
}
var KV_KEYS, DEFAULT_FREE_TIER;
var init_kv = __esm({
  "worker/src/lib/kv.ts"() {
    "use strict";
    KV_KEYS = {
      authCode: (email) => `auth:code:${email.toLowerCase()}`,
      authUser: (email) => `auth:user:${email.toLowerCase()}`,
      // Трекер (Фаза 2)
      trackerWishes: (userId) => `tracker:wishes:${userId}`,
      // Генерации (Фаза 3)
      job: (jobId) => `job:${jobId}`,
      /** Индекс "job'ы пользователя" для листинга в /generate/jobs */
      jobUser: (userId, jobId) => `job:user:${userId}:${jobId}`,
      genMonth: (userId, ym) => `gen:month:${userId}:${ym}`,
      genDay: (userId, ymd) => `gen:day:${userId}:${ymd}`,
      // Книги (Фаза 3) — без R2
      book: (slug) => `book:${slug}`,
      bookFile: (slug, name) => `book:${slug}:file:${name}`,
      // Email-индекс по userId (для cron)
      userIdToEmail: (userId) => `userid:${userId}`,
      // Publisher (Фаза 5+) — состояние публикации и соцсети
      publish: (kind, slug) => `publish:${kind}:${slug}`,
      publishDryRun: (kind, slug) => `publish:dry-run:${kind}:${slug}`,
      socialVk: (slug) => `social:vk:${slug}`,
      socialTg: (slug) => `social:tg:${slug}`
    };
    DEFAULT_FREE_TIER = {
      plan: "free",
      subscriptionStatus: "none",
      subscriptionExpiresAt: null,
      generationsLimit: 3,
      wishesLimit: 3
    };
  }
});

// worker/src/lib/books.ts
var books_exports = {};
__export(books_exports, {
  contentTypeFor: () => contentTypeFor,
  fileBlobToBytes: () => fileBlobToBytes,
  getBook: () => getBook,
  getBookFile: () => getBookFile,
  slugify: () => slugify,
  uploadBook: () => uploadBook
});
function slugify(text) {
  const table = {
    \u0430: "a",
    \u0431: "b",
    \u0432: "v",
    \u0433: "g",
    \u0434: "d",
    \u0435: "e",
    \u0451: "e",
    \u0436: "zh",
    \u0437: "z",
    \u0438: "i",
    \u0439: "i",
    \u043A: "k",
    \u043B: "l",
    \u043C: "m",
    \u043D: "n",
    \u043E: "o",
    \u043F: "p",
    \u0440: "r",
    \u0441: "s",
    \u0442: "t",
    \u0443: "u",
    \u0444: "f",
    \u0445: "h",
    \u0446: "ts",
    \u0447: "ch",
    \u0448: "sh",
    \u0449: "shch",
    \u044A: "",
    \u044B: "y",
    \u044C: "",
    \u044D: "e",
    \u044E: "yu",
    \u044F: "ya"
  };
  const out = [];
  for (const ch of text.toLowerCase()) {
    if (table[ch]) out.push(table[ch]);
    else if (/[a-z0-9]/.test(ch) && ch.charCodeAt(0) < 128) out.push(ch);
    else if (ch === " " || ch === "-" || ch === "_") out.push("-");
  }
  return out.join("").replace(/-+/g, "-").replace(/^-|-$/g, "").slice(0, 80) || "book";
}
function contentTypeFor(filename) {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  return CONTENT_TYPES[ext] ?? "application/octet-stream";
}
function bytesToBase64(bytes) {
  const arr = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  let bin = "";
  const chunk = 32768;
  for (let i = 0; i < arr.length; i += chunk) {
    bin += String.fromCharCode.apply(null, Array.from(arr.subarray(i, i + chunk)));
  }
  return btoa(bin);
}
function base64ToBytes(b64) {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}
async function uploadBook(env, args) {
  const { slug, title, author, year, description, files } = args;
  const safeName = (n) => n.replace(/[^a-zA-Z0-9._-]/g, "_").slice(0, 80) || "file";
  const metas = [];
  const blobs = [];
  for (const f of files) {
    const name = safeName(f.name);
    const ct = contentTypeFor(name);
    const bytes = f.body instanceof Uint8Array ? f.body : new Uint8Array(f.body);
    if (bytes.byteLength > MAX_FILE_SIZE) {
      throw new Error(`\u0424\u0430\u0439\u043B ${name} \u0441\u043B\u0438\u0448\u043A\u043E\u043C \u0431\u043E\u043B\u044C\u0448\u043E\u0439 (${bytes.byteLength} > ${MAX_FILE_SIZE})`);
    }
    const blob = {
      slug,
      name,
      contentType: ct,
      dataBase64: bytesToBase64(bytes),
      size: bytes.byteLength,
      kind: f.kind
    };
    blobs.push({ key: KV_KEYS.bookFile(slug, name), blob });
    metas.push({ name, size: bytes.byteLength, contentType: ct, kind: f.kind });
  }
  const record = {
    slug,
    title,
    author,
    year: year ?? null,
    description: description ?? "",
    files: metas,
    createdAt: (/* @__PURE__ */ new Date()).toISOString(),
    generatedBy: args.generatedBy,
    generatedByJob: args.generatedByJob
  };
  await Promise.all(blobs.map((b) => env.LAB_KV.put(b.key, JSON.stringify(b.blob))));
  await env.LAB_KV.put(KV_KEYS.book(slug), JSON.stringify(record));
  return record;
}
async function getBook(env, slug) {
  const raw2 = await env.LAB_KV.get(KV_KEYS.book(slug));
  if (!raw2) return null;
  try {
    return JSON.parse(raw2);
  } catch {
    return null;
  }
}
async function getBookFile(env, slug, name) {
  if (!/^[a-zA-Z0-9._-]{1,80}$/.test(slug) || !/^[a-zA-Z0-9._-]{1,80}$/.test(name)) {
    return null;
  }
  const raw2 = await env.LAB_KV.get(KV_KEYS.bookFile(slug, name));
  if (!raw2) return null;
  try {
    return JSON.parse(raw2);
  } catch {
    return null;
  }
}
function fileBlobToBytes(blob) {
  return base64ToBytes(blob.dataBase64);
}
var CONTENT_TYPES, MAX_FILE_SIZE;
var init_books = __esm({
  "worker/src/lib/books.ts"() {
    "use strict";
    init_kv();
    CONTENT_TYPES = {
      md: "text/markdown; charset=utf-8",
      txt: "text/plain; charset=utf-8",
      jpg: "image/jpeg",
      jpeg: "image/jpeg",
      png: "image/png",
      webp: "image/webp",
      pdf: "application/pdf",
      json: "application/json; charset=utf-8"
    };
    MAX_FILE_SIZE = 5 * 1024 * 1024;
  }
});

// worker/node_modules/hono/dist/compose.js
var compose = (middleware, onError, onNotFound) => {
  return (context, next) => {
    let index = -1;
    return dispatch(0);
    async function dispatch(i) {
      if (i <= index) {
        throw new Error("next() called multiple times");
      }
      index = i;
      let res;
      let isError = false;
      let handler;
      if (middleware[i]) {
        handler = middleware[i][0][0];
        context.req.routeIndex = i;
      } else {
        handler = i === middleware.length && next || void 0;
      }
      if (handler) {
        try {
          res = await handler(context, () => dispatch(i + 1));
        } catch (err) {
          if (err instanceof Error && onError) {
            context.error = err;
            res = await onError(err, context);
            isError = true;
          } else {
            throw err;
          }
        }
      } else {
        if (context.finalized === false && onNotFound) {
          res = await onNotFound(context);
        }
      }
      if (res && (context.finalized === false || isError)) {
        context.res = res;
      }
      return context;
    }
  };
};

// worker/node_modules/hono/dist/request/constants.js
var GET_MATCH_RESULT = /* @__PURE__ */ Symbol();

// worker/node_modules/hono/dist/utils/body.js
var parseBody = async (request, options = /* @__PURE__ */ Object.create(null)) => {
  const { all = false, dot = false } = options;
  const headers = request instanceof HonoRequest ? request.raw.headers : request.headers;
  const contentType = headers.get("Content-Type");
  if (contentType?.startsWith("multipart/form-data") || contentType?.startsWith("application/x-www-form-urlencoded")) {
    return parseFormData(request, { all, dot });
  }
  return {};
};
async function parseFormData(request, options) {
  const formData = await request.formData();
  if (formData) {
    return convertFormDataToBodyData(formData, options);
  }
  return {};
}
function convertFormDataToBodyData(formData, options) {
  const form = /* @__PURE__ */ Object.create(null);
  formData.forEach((value, key2) => {
    const shouldParseAllValues = options.all || key2.endsWith("[]");
    if (!shouldParseAllValues) {
      form[key2] = value;
    } else {
      handleParsingAllValues(form, key2, value);
    }
  });
  if (options.dot) {
    Object.entries(form).forEach(([key2, value]) => {
      const shouldParseDotValues = key2.includes(".");
      if (shouldParseDotValues) {
        handleParsingNestedValues(form, key2, value);
        delete form[key2];
      }
    });
  }
  return form;
}
var handleParsingAllValues = (form, key2, value) => {
  if (form[key2] !== void 0) {
    if (Array.isArray(form[key2])) {
      ;
      form[key2].push(value);
    } else {
      form[key2] = [form[key2], value];
    }
  } else {
    if (!key2.endsWith("[]")) {
      form[key2] = value;
    } else {
      form[key2] = [value];
    }
  }
};
var handleParsingNestedValues = (form, key2, value) => {
  if (/(?:^|\.)__proto__\./.test(key2)) {
    return;
  }
  let nestedForm = form;
  const keys = key2.split(".");
  keys.forEach((key22, index) => {
    if (index === keys.length - 1) {
      nestedForm[key22] = value;
    } else {
      if (!nestedForm[key22] || typeof nestedForm[key22] !== "object" || Array.isArray(nestedForm[key22]) || nestedForm[key22] instanceof File) {
        nestedForm[key22] = /* @__PURE__ */ Object.create(null);
      }
      nestedForm = nestedForm[key22];
    }
  });
};

// worker/node_modules/hono/dist/utils/url.js
var splitPath = (path) => {
  const paths = path.split("/");
  if (paths[0] === "") {
    paths.shift();
  }
  return paths;
};
var splitRoutingPath = (routePath) => {
  const { groups, path } = extractGroupsFromPath(routePath);
  const paths = splitPath(path);
  return replaceGroupMarks(paths, groups);
};
var extractGroupsFromPath = (path) => {
  const groups = [];
  path = path.replace(/\{[^}]+\}/g, (match2, index) => {
    const mark = `@${index}`;
    groups.push([mark, match2]);
    return mark;
  });
  return { groups, path };
};
var replaceGroupMarks = (paths, groups) => {
  for (let i = groups.length - 1; i >= 0; i--) {
    const [mark] = groups[i];
    for (let j = paths.length - 1; j >= 0; j--) {
      if (paths[j].includes(mark)) {
        paths[j] = paths[j].replace(mark, groups[i][1]);
        break;
      }
    }
  }
  return paths;
};
var patternCache = {};
var getPattern = (label, next) => {
  if (label === "*") {
    return "*";
  }
  const match2 = label.match(/^\:([^\{\}]+)(?:\{(.+)\})?$/);
  if (match2) {
    const cacheKey = `${label}#${next}`;
    if (!patternCache[cacheKey]) {
      if (match2[2]) {
        patternCache[cacheKey] = next && next[0] !== ":" && next[0] !== "*" ? [cacheKey, match2[1], new RegExp(`^${match2[2]}(?=/${next})`)] : [label, match2[1], new RegExp(`^${match2[2]}$`)];
      } else {
        patternCache[cacheKey] = [label, match2[1], true];
      }
    }
    return patternCache[cacheKey];
  }
  return null;
};
var tryDecode = (str, decoder) => {
  try {
    return decoder(str);
  } catch {
    return str.replace(/(?:%[0-9A-Fa-f]{2})+/g, (match2) => {
      try {
        return decoder(match2);
      } catch {
        return match2;
      }
    });
  }
};
var tryDecodeURI = (str) => tryDecode(str, decodeURI);
var getPath = (request) => {
  const url = request.url;
  const start = url.indexOf("/", url.indexOf(":") + 4);
  let i = start;
  for (; i < url.length; i++) {
    const charCode = url.charCodeAt(i);
    if (charCode === 37) {
      const queryIndex = url.indexOf("?", i);
      const hashIndex = url.indexOf("#", i);
      const end = queryIndex === -1 ? hashIndex === -1 ? void 0 : hashIndex : hashIndex === -1 ? queryIndex : Math.min(queryIndex, hashIndex);
      const path = url.slice(start, end);
      return tryDecodeURI(path.includes("%25") ? path.replace(/%25/g, "%2525") : path);
    } else if (charCode === 63 || charCode === 35) {
      break;
    }
  }
  return url.slice(start, i);
};
var getPathNoStrict = (request) => {
  const result = getPath(request);
  return result.length > 1 && result.at(-1) === "/" ? result.slice(0, -1) : result;
};
var mergePath = (base, sub, ...rest) => {
  if (rest.length) {
    sub = mergePath(sub, ...rest);
  }
  return `${base?.[0] === "/" ? "" : "/"}${base}${sub === "/" ? "" : `${base?.at(-1) === "/" ? "" : "/"}${sub?.[0] === "/" ? sub.slice(1) : sub}`}`;
};
var checkOptionalParameter = (path) => {
  if (path.charCodeAt(path.length - 1) !== 63 || !path.includes(":")) {
    return null;
  }
  const segments = path.split("/");
  const results = [];
  let basePath = "";
  segments.forEach((segment) => {
    if (segment !== "" && !/\:/.test(segment)) {
      basePath += "/" + segment;
    } else if (/\:/.test(segment)) {
      if (/\?/.test(segment)) {
        if (results.length === 0 && basePath === "") {
          results.push("/");
        } else {
          results.push(basePath);
        }
        const optionalSegment = segment.replace("?", "");
        basePath += "/" + optionalSegment;
        results.push(basePath);
      } else {
        basePath += "/" + segment;
      }
    }
  });
  return results.filter((v, i, a) => a.indexOf(v) === i);
};
var _decodeURI = (value) => {
  if (!/[%+]/.test(value)) {
    return value;
  }
  if (value.indexOf("+") !== -1) {
    value = value.replace(/\+/g, " ");
  }
  return value.indexOf("%") !== -1 ? tryDecode(value, decodeURIComponent_) : value;
};
var _getQueryParam = (url, key2, multiple) => {
  let encoded;
  if (!multiple && key2 && !/[%+]/.test(key2)) {
    let keyIndex2 = url.indexOf("?", 8);
    if (keyIndex2 === -1) {
      return void 0;
    }
    if (!url.startsWith(key2, keyIndex2 + 1)) {
      keyIndex2 = url.indexOf(`&${key2}`, keyIndex2 + 1);
    }
    while (keyIndex2 !== -1) {
      const trailingKeyCode = url.charCodeAt(keyIndex2 + key2.length + 1);
      if (trailingKeyCode === 61) {
        const valueIndex = keyIndex2 + key2.length + 2;
        const endIndex = url.indexOf("&", valueIndex);
        return _decodeURI(url.slice(valueIndex, endIndex === -1 ? void 0 : endIndex));
      } else if (trailingKeyCode == 38 || isNaN(trailingKeyCode)) {
        return "";
      }
      keyIndex2 = url.indexOf(`&${key2}`, keyIndex2 + 1);
    }
    encoded = /[%+]/.test(url);
    if (!encoded) {
      return void 0;
    }
  }
  const results = {};
  encoded ??= /[%+]/.test(url);
  let keyIndex = url.indexOf("?", 8);
  while (keyIndex !== -1) {
    const nextKeyIndex = url.indexOf("&", keyIndex + 1);
    let valueIndex = url.indexOf("=", keyIndex);
    if (valueIndex > nextKeyIndex && nextKeyIndex !== -1) {
      valueIndex = -1;
    }
    let name = url.slice(
      keyIndex + 1,
      valueIndex === -1 ? nextKeyIndex === -1 ? void 0 : nextKeyIndex : valueIndex
    );
    if (encoded) {
      name = _decodeURI(name);
    }
    keyIndex = nextKeyIndex;
    if (name === "") {
      continue;
    }
    let value;
    if (valueIndex === -1) {
      value = "";
    } else {
      value = url.slice(valueIndex + 1, nextKeyIndex === -1 ? void 0 : nextKeyIndex);
      if (encoded) {
        value = _decodeURI(value);
      }
    }
    if (multiple) {
      if (!(results[name] && Array.isArray(results[name]))) {
        results[name] = [];
      }
      ;
      results[name].push(value);
    } else {
      results[name] ??= value;
    }
  }
  return key2 ? results[key2] : results;
};
var getQueryParam = _getQueryParam;
var getQueryParams = (url, key2) => {
  return _getQueryParam(url, key2, true);
};
var decodeURIComponent_ = decodeURIComponent;

// worker/node_modules/hono/dist/request.js
var tryDecodeURIComponent = (str) => tryDecode(str, decodeURIComponent_);
var HonoRequest = class {
  /**
   * `.raw` can get the raw Request object.
   *
   * @see {@link https://hono.dev/docs/api/request#raw}
   *
   * @example
   * ```ts
   * // For Cloudflare Workers
   * app.post('/', async (c) => {
   *   const metadata = c.req.raw.cf?.hostMetadata?
   *   ...
   * })
   * ```
   */
  raw;
  #validatedData;
  // Short name of validatedData
  #matchResult;
  routeIndex = 0;
  /**
   * `.path` can get the pathname of the request.
   *
   * @see {@link https://hono.dev/docs/api/request#path}
   *
   * @example
   * ```ts
   * app.get('/about/me', (c) => {
   *   const pathname = c.req.path // `/about/me`
   * })
   * ```
   */
  path;
  bodyCache = {};
  constructor(request, path = "/", matchResult = [[]]) {
    this.raw = request;
    this.path = path;
    this.#matchResult = matchResult;
    this.#validatedData = {};
  }
  param(key2) {
    return key2 ? this.#getDecodedParam(key2) : this.#getAllDecodedParams();
  }
  #getDecodedParam(key2) {
    const paramKey = this.#matchResult[0][this.routeIndex][1][key2];
    const param = this.#getParamValue(paramKey);
    return param && /\%/.test(param) ? tryDecodeURIComponent(param) : param;
  }
  #getAllDecodedParams() {
    const decoded = {};
    const keys = Object.keys(this.#matchResult[0][this.routeIndex][1]);
    for (const key2 of keys) {
      const value = this.#getParamValue(this.#matchResult[0][this.routeIndex][1][key2]);
      if (value !== void 0) {
        decoded[key2] = /\%/.test(value) ? tryDecodeURIComponent(value) : value;
      }
    }
    return decoded;
  }
  #getParamValue(paramKey) {
    return this.#matchResult[1] ? this.#matchResult[1][paramKey] : paramKey;
  }
  query(key2) {
    return getQueryParam(this.url, key2);
  }
  queries(key2) {
    return getQueryParams(this.url, key2);
  }
  header(name) {
    if (name) {
      return this.raw.headers.get(name) ?? void 0;
    }
    const headerData = {};
    this.raw.headers.forEach((value, key2) => {
      headerData[key2] = value;
    });
    return headerData;
  }
  async parseBody(options) {
    return parseBody(this, options);
  }
  #cachedBody = (key2) => {
    const { bodyCache, raw: raw2 } = this;
    const cachedBody = bodyCache[key2];
    if (cachedBody) {
      return cachedBody;
    }
    const anyCachedKey = Object.keys(bodyCache)[0];
    if (anyCachedKey) {
      return bodyCache[anyCachedKey].then((body) => {
        if (anyCachedKey === "json") {
          body = JSON.stringify(body);
        }
        return new Response(body)[key2]();
      });
    }
    return bodyCache[key2] = raw2[key2]();
  };
  /**
   * `.json()` can parse Request body of type `application/json`
   *
   * @see {@link https://hono.dev/docs/api/request#json}
   *
   * @example
   * ```ts
   * app.post('/entry', async (c) => {
   *   const body = await c.req.json()
   * })
   * ```
   */
  json() {
    return this.#cachedBody("text").then((text) => JSON.parse(text));
  }
  /**
   * `.text()` can parse Request body of type `text/plain`
   *
   * @see {@link https://hono.dev/docs/api/request#text}
   *
   * @example
   * ```ts
   * app.post('/entry', async (c) => {
   *   const body = await c.req.text()
   * })
   * ```
   */
  text() {
    return this.#cachedBody("text");
  }
  /**
   * `.arrayBuffer()` parse Request body as an `ArrayBuffer`
   *
   * @see {@link https://hono.dev/docs/api/request#arraybuffer}
   *
   * @example
   * ```ts
   * app.post('/entry', async (c) => {
   *   const body = await c.req.arrayBuffer()
   * })
   * ```
   */
  arrayBuffer() {
    return this.#cachedBody("arrayBuffer");
  }
  /**
   * `.bytes()` parses the request body as a `Uint8Array`.
   *
   * @see {@link https://hono.dev/docs/api/request#bytes}
   *
   * @example
   * ```ts
   * app.post('/entry', async (c) => {
   *   const body = await c.req.bytes()
   * })
   * ```
   */
  bytes() {
    return this.#cachedBody("arrayBuffer").then((buffer) => new Uint8Array(buffer));
  }
  /**
   * Parses the request body as a `Blob`.
   * @example
   * ```ts
   * app.post('/entry', async (c) => {
   *   const body = await c.req.blob();
   * });
   * ```
   * @see https://hono.dev/docs/api/request#blob
   */
  blob() {
    return this.#cachedBody("blob");
  }
  /**
   * Parses the request body as `FormData`.
   * @example
   * ```ts
   * app.post('/entry', async (c) => {
   *   const body = await c.req.formData();
   * });
   * ```
   * @see https://hono.dev/docs/api/request#formdata
   */
  formData() {
    return this.#cachedBody("formData");
  }
  /**
   * Adds validated data to the request.
   *
   * @param target - The target of the validation.
   * @param data - The validated data to add.
   */
  addValidatedData(target, data) {
    this.#validatedData[target] = data;
  }
  valid(target) {
    return this.#validatedData[target];
  }
  /**
   * `.url()` can get the request url strings.
   *
   * @see {@link https://hono.dev/docs/api/request#url}
   *
   * @example
   * ```ts
   * app.get('/about/me', (c) => {
   *   const url = c.req.url // `http://localhost:8787/about/me`
   *   ...
   * })
   * ```
   */
  get url() {
    return this.raw.url;
  }
  /**
   * `.method()` can get the method name of the request.
   *
   * @see {@link https://hono.dev/docs/api/request#method}
   *
   * @example
   * ```ts
   * app.get('/about/me', (c) => {
   *   const method = c.req.method // `GET`
   * })
   * ```
   */
  get method() {
    return this.raw.method;
  }
  get [GET_MATCH_RESULT]() {
    return this.#matchResult;
  }
  /**
   * `.matchedRoutes()` can return a matched route in the handler
   *
   * @deprecated
   *
   * Use matchedRoutes helper defined in "hono/route" instead.
   *
   * @see {@link https://hono.dev/docs/api/request#matchedroutes}
   *
   * @example
   * ```ts
   * app.use('*', async function logger(c, next) {
   *   await next()
   *   c.req.matchedRoutes.forEach(({ handler, method, path }, i) => {
   *     const name = handler.name || (handler.length < 2 ? '[handler]' : '[middleware]')
   *     console.log(
   *       method,
   *       ' ',
   *       path,
   *       ' '.repeat(Math.max(10 - path.length, 0)),
   *       name,
   *       i === c.req.routeIndex ? '<- respond from here' : ''
   *     )
   *   })
   * })
   * ```
   */
  get matchedRoutes() {
    return this.#matchResult[0].map(([[, route]]) => route);
  }
  /**
   * `routePath()` can retrieve the path registered within the handler
   *
   * @deprecated
   *
   * Use routePath helper defined in "hono/route" instead.
   *
   * @see {@link https://hono.dev/docs/api/request#routepath}
   *
   * @example
   * ```ts
   * app.get('/posts/:id', (c) => {
   *   return c.json({ path: c.req.routePath })
   * })
   * ```
   */
  get routePath() {
    return this.#matchResult[0].map(([[, route]]) => route)[this.routeIndex].path;
  }
};

// worker/node_modules/hono/dist/utils/html.js
var HtmlEscapedCallbackPhase = {
  Stringify: 1,
  BeforeStream: 2,
  Stream: 3
};
var raw = (value, callbacks) => {
  const escapedString = new String(value);
  escapedString.isEscaped = true;
  escapedString.callbacks = callbacks;
  return escapedString;
};
var resolveCallback = async (str, phase, preserveCallbacks, context, buffer) => {
  if (typeof str === "object" && !(str instanceof String)) {
    if (!(str instanceof Promise)) {
      str = str.toString();
    }
    if (str instanceof Promise) {
      str = await str;
    }
  }
  const callbacks = str.callbacks;
  if (!callbacks?.length) {
    return Promise.resolve(str);
  }
  if (buffer) {
    buffer[0] += str;
  } else {
    buffer = [str];
  }
  const resStr = Promise.all(callbacks.map((c) => c({ phase, buffer, context }))).then(
    (res) => Promise.all(
      res.filter(Boolean).map((str2) => resolveCallback(str2, phase, false, context, buffer))
    ).then(() => buffer[0])
  );
  if (preserveCallbacks) {
    return raw(await resStr, callbacks);
  } else {
    return resStr;
  }
};

// worker/node_modules/hono/dist/context.js
var TEXT_PLAIN = "text/plain; charset=UTF-8";
var setDefaultContentType = (contentType, headers) => {
  return {
    "Content-Type": contentType,
    ...headers
  };
};
var createResponseInstance = (body, init) => new Response(body, init);
var Context = class {
  #rawRequest;
  #req;
  /**
   * `.env` can get bindings (environment variables, secrets, KV namespaces, D1 database, R2 bucket etc.) in Cloudflare Workers.
   *
   * @see {@link https://hono.dev/docs/api/context#env}
   *
   * @example
   * ```ts
   * // Environment object for Cloudflare Workers
   * app.get('*', async c => {
   *   const counter = c.env.COUNTER
   * })
   * ```
   */
  env = {};
  #var;
  finalized = false;
  /**
   * `.error` can get the error object from the middleware if the Handler throws an error.
   *
   * @see {@link https://hono.dev/docs/api/context#error}
   *
   * @example
   * ```ts
   * app.use('*', async (c, next) => {
   *   await next()
   *   if (c.error) {
   *     // do something...
   *   }
   * })
   * ```
   */
  error;
  #status;
  #executionCtx;
  #res;
  #layout;
  #renderer;
  #notFoundHandler;
  #preparedHeaders;
  #matchResult;
  #path;
  /**
   * Creates an instance of the Context class.
   *
   * @param req - The Request object.
   * @param options - Optional configuration options for the context.
   */
  constructor(req, options) {
    this.#rawRequest = req;
    if (options) {
      this.#executionCtx = options.executionCtx;
      this.env = options.env;
      this.#notFoundHandler = options.notFoundHandler;
      this.#path = options.path;
      this.#matchResult = options.matchResult;
    }
  }
  /**
   * `.req` is the instance of {@link HonoRequest}.
   */
  get req() {
    this.#req ??= new HonoRequest(this.#rawRequest, this.#path, this.#matchResult);
    return this.#req;
  }
  /**
   * @see {@link https://hono.dev/docs/api/context#event}
   * The FetchEvent associated with the current request.
   *
   * @throws Will throw an error if the context does not have a FetchEvent.
   */
  get event() {
    if (this.#executionCtx && "respondWith" in this.#executionCtx) {
      return this.#executionCtx;
    } else {
      throw Error("This context has no FetchEvent");
    }
  }
  /**
   * @see {@link https://hono.dev/docs/api/context#executionctx}
   * The ExecutionContext associated with the current request.
   *
   * @throws Will throw an error if the context does not have an ExecutionContext.
   */
  get executionCtx() {
    if (this.#executionCtx) {
      return this.#executionCtx;
    } else {
      throw Error("This context has no ExecutionContext");
    }
  }
  /**
   * @see {@link https://hono.dev/docs/api/context#res}
   * The Response object for the current request.
   */
  get res() {
    return this.#res ||= createResponseInstance(null, {
      headers: this.#preparedHeaders ??= new Headers()
    });
  }
  /**
   * Sets the Response object for the current request.
   *
   * @param _res - The Response object to set.
   */
  set res(_res) {
    if (this.#res && _res) {
      _res = createResponseInstance(_res.body, _res);
      for (const [k, v] of this.#res.headers.entries()) {
        if (k === "content-type") {
          continue;
        }
        if (k === "set-cookie") {
          const cookies = this.#res.headers.getSetCookie();
          _res.headers.delete("set-cookie");
          for (const cookie of cookies) {
            _res.headers.append("set-cookie", cookie);
          }
        } else {
          _res.headers.set(k, v);
        }
      }
    }
    this.#res = _res;
    this.finalized = true;
  }
  /**
   * `.render()` can create a response within a layout.
   *
   * @see {@link https://hono.dev/docs/api/context#render-setrenderer}
   *
   * @example
   * ```ts
   * app.get('/', (c) => {
   *   return c.render('Hello!')
   * })
   * ```
   */
  render = (...args) => {
    this.#renderer ??= (content) => this.html(content);
    return this.#renderer(...args);
  };
  /**
   * Sets the layout for the response.
   *
   * @param layout - The layout to set.
   * @returns The layout function.
   */
  setLayout = (layout) => this.#layout = layout;
  /**
   * Gets the current layout for the response.
   *
   * @returns The current layout function.
   */
  getLayout = () => this.#layout;
  /**
   * `.setRenderer()` can set the layout in the custom middleware.
   *
   * @see {@link https://hono.dev/docs/api/context#render-setrenderer}
   *
   * @example
   * ```tsx
   * app.use('*', async (c, next) => {
   *   c.setRenderer((content) => {
   *     return c.html(
   *       <html>
   *         <body>
   *           <p>{content}</p>
   *         </body>
   *       </html>
   *     )
   *   })
   *   await next()
   * })
   * ```
   */
  setRenderer = (renderer) => {
    this.#renderer = renderer;
  };
  /**
   * `.header()` can set headers.
   *
   * @see {@link https://hono.dev/docs/api/context#header}
   *
   * @example
   * ```ts
   * app.get('/welcome', (c) => {
   *   // Set headers
   *   c.header('X-Message', 'Hello!')
   *   c.header('Content-Type', 'text/plain')
   *
   *   return c.body('Thank you for coming')
   * })
   * ```
   */
  header = (name, value, options) => {
    if (this.finalized) {
      this.#res = createResponseInstance(this.#res.body, this.#res);
    }
    const headers = this.#res ? this.#res.headers : this.#preparedHeaders ??= new Headers();
    if (value === void 0) {
      headers.delete(name);
    } else if (options?.append) {
      headers.append(name, value);
    } else {
      headers.set(name, value);
    }
  };
  status = (status) => {
    this.#status = status;
  };
  /**
   * `.set()` can set the value specified by the key.
   *
   * @see {@link https://hono.dev/docs/api/context#set-get}
   *
   * @example
   * ```ts
   * app.use('*', async (c, next) => {
   *   c.set('message', 'Hono is hot!!')
   *   await next()
   * })
   * ```
   */
  set = (key2, value) => {
    this.#var ??= /* @__PURE__ */ new Map();
    this.#var.set(key2, value);
  };
  /**
   * `.get()` can use the value specified by the key.
   *
   * @see {@link https://hono.dev/docs/api/context#set-get}
   *
   * @example
   * ```ts
   * app.get('/', (c) => {
   *   const message = c.get('message')
   *   return c.text(`The message is "${message}"`)
   * })
   * ```
   */
  get = (key2) => {
    return this.#var ? this.#var.get(key2) : void 0;
  };
  /**
   * `.var` can access the value of a variable.
   *
   * @see {@link https://hono.dev/docs/api/context#var}
   *
   * @example
   * ```ts
   * const result = c.var.client.oneMethod()
   * ```
   */
  // c.var.propName is a read-only
  get var() {
    if (!this.#var) {
      return {};
    }
    return Object.fromEntries(this.#var);
  }
  #newResponse(data, arg, headers) {
    const responseHeaders = this.#res ? new Headers(this.#res.headers) : this.#preparedHeaders ?? new Headers();
    if (typeof arg === "object" && "headers" in arg) {
      const argHeaders = arg.headers instanceof Headers ? arg.headers : new Headers(arg.headers);
      for (const [key2, value] of argHeaders) {
        if (key2.toLowerCase() === "set-cookie") {
          responseHeaders.append(key2, value);
        } else {
          responseHeaders.set(key2, value);
        }
      }
    }
    if (headers) {
      for (const [k, v] of Object.entries(headers)) {
        if (typeof v === "string") {
          responseHeaders.set(k, v);
        } else {
          responseHeaders.delete(k);
          for (const v2 of v) {
            responseHeaders.append(k, v2);
          }
        }
      }
    }
    const status = typeof arg === "number" ? arg : arg?.status ?? this.#status;
    return createResponseInstance(data, { status, headers: responseHeaders });
  }
  newResponse = (...args) => this.#newResponse(...args);
  /**
   * `.body()` can return the HTTP response.
   * You can set headers with `.header()` and set HTTP status code with `.status`.
   * This can also be set in `.text()`, `.json()` and so on.
   *
   * @see {@link https://hono.dev/docs/api/context#body}
   *
   * @example
   * ```ts
   * app.get('/welcome', (c) => {
   *   // Set headers
   *   c.header('X-Message', 'Hello!')
   *   c.header('Content-Type', 'text/plain')
   *   // Set HTTP status code
   *   c.status(201)
   *
   *   // Return the response body
   *   return c.body('Thank you for coming')
   * })
   * ```
   */
  body = (data, arg, headers) => this.#newResponse(data, arg, headers);
  /**
   * `.text()` can render text as `Content-Type:text/plain`.
   *
   * @see {@link https://hono.dev/docs/api/context#text}
   *
   * @example
   * ```ts
   * app.get('/say', (c) => {
   *   return c.text('Hello!')
   * })
   * ```
   */
  text = (text, arg, headers) => {
    return !this.#preparedHeaders && !this.#status && !arg && !headers && !this.finalized ? new Response(text) : this.#newResponse(
      text,
      arg,
      setDefaultContentType(TEXT_PLAIN, headers)
    );
  };
  /**
   * `.json()` can render JSON as `Content-Type:application/json`.
   *
   * @see {@link https://hono.dev/docs/api/context#json}
   *
   * @example
   * ```ts
   * app.get('/api', (c) => {
   *   return c.json({ message: 'Hello!' })
   * })
   * ```
   */
  json = (object, arg, headers) => {
    return this.#newResponse(
      JSON.stringify(object),
      arg,
      setDefaultContentType("application/json", headers)
    );
  };
  html = (html, arg, headers) => {
    const res = (html2) => this.#newResponse(html2, arg, setDefaultContentType("text/html; charset=UTF-8", headers));
    return typeof html === "object" ? resolveCallback(html, HtmlEscapedCallbackPhase.Stringify, false, {}).then(res) : res(html);
  };
  /**
   * `.redirect()` can Redirect, default status code is 302.
   *
   * @see {@link https://hono.dev/docs/api/context#redirect}
   *
   * @example
   * ```ts
   * app.get('/redirect', (c) => {
   *   return c.redirect('/')
   * })
   * app.get('/redirect-permanently', (c) => {
   *   return c.redirect('/', 301)
   * })
   * ```
   */
  redirect = (location, status) => {
    const locationString = String(location);
    this.header(
      "Location",
      // Multibyes should be encoded
      // eslint-disable-next-line no-control-regex
      !/[^\x00-\xFF]/.test(locationString) ? locationString : encodeURI(locationString)
    );
    return this.newResponse(null, status ?? 302);
  };
  /**
   * `.notFound()` can return the Not Found Response.
   *
   * @see {@link https://hono.dev/docs/api/context#notfound}
   *
   * @example
   * ```ts
   * app.get('/notfound', (c) => {
   *   return c.notFound()
   * })
   * ```
   */
  notFound = () => {
    this.#notFoundHandler ??= () => createResponseInstance();
    return this.#notFoundHandler(this);
  };
};

// worker/node_modules/hono/dist/router.js
var METHOD_NAME_ALL = "ALL";
var METHOD_NAME_ALL_LOWERCASE = "all";
var METHODS = ["get", "post", "put", "delete", "options", "patch"];
var MESSAGE_MATCHER_IS_ALREADY_BUILT = "Can not add a route since the matcher is already built.";
var UnsupportedPathError = class extends Error {
};

// worker/node_modules/hono/dist/utils/constants.js
var COMPOSED_HANDLER = "__COMPOSED_HANDLER";

// worker/node_modules/hono/dist/hono-base.js
var notFoundHandler = (c) => {
  return c.text("404 Not Found", 404);
};
var errorHandler = (err, c) => {
  if ("getResponse" in err) {
    const res = err.getResponse();
    return c.newResponse(res.body, res);
  }
  console.error(err);
  return c.text("Internal Server Error", 500);
};
var Hono = class _Hono {
  get;
  post;
  put;
  delete;
  options;
  patch;
  all;
  on;
  use;
  /*
    This class is like an abstract class and does not have a router.
    To use it, inherit the class and implement router in the constructor.
  */
  router;
  getPath;
  // Cannot use `#` because it requires visibility at JavaScript runtime.
  _basePath = "/";
  #path = "/";
  routes = [];
  constructor(options = {}) {
    const allMethods = [...METHODS, METHOD_NAME_ALL_LOWERCASE];
    allMethods.forEach((method) => {
      this[method] = (args1, ...args) => {
        if (typeof args1 === "string") {
          this.#path = args1;
        } else {
          this.#addRoute(method, this.#path, args1);
        }
        args.forEach((handler) => {
          this.#addRoute(method, this.#path, handler);
        });
        return this;
      };
    });
    this.on = (method, path, ...handlers) => {
      for (const p of [path].flat()) {
        this.#path = p;
        for (const m of [method].flat()) {
          handlers.map((handler) => {
            this.#addRoute(m.toUpperCase(), this.#path, handler);
          });
        }
      }
      return this;
    };
    this.use = (arg1, ...handlers) => {
      if (typeof arg1 === "string") {
        this.#path = arg1;
      } else {
        this.#path = "*";
        handlers.unshift(arg1);
      }
      handlers.forEach((handler) => {
        this.#addRoute(METHOD_NAME_ALL, this.#path, handler);
      });
      return this;
    };
    const { strict, ...optionsWithoutStrict } = options;
    Object.assign(this, optionsWithoutStrict);
    this.getPath = strict ?? true ? options.getPath ?? getPath : getPathNoStrict;
  }
  #clone() {
    const clone = new _Hono({
      router: this.router,
      getPath: this.getPath
    });
    clone.errorHandler = this.errorHandler;
    clone.#notFoundHandler = this.#notFoundHandler;
    clone.routes = this.routes;
    return clone;
  }
  #notFoundHandler = notFoundHandler;
  // Cannot use `#` because it requires visibility at JavaScript runtime.
  errorHandler = errorHandler;
  /**
   * `.route()` allows grouping other Hono instance in routes.
   *
   * @see {@link https://hono.dev/docs/api/routing#grouping}
   *
   * @param {string} path - base Path
   * @param {Hono} app - other Hono instance
   * @returns {Hono} routed Hono instance
   *
   * @example
   * ```ts
   * const app = new Hono()
   * const app2 = new Hono()
   *
   * app2.get("/user", (c) => c.text("user"))
   * app.route("/api", app2) // GET /api/user
   * ```
   */
  route(path, app8) {
    const subApp = this.basePath(path);
    app8.routes.map((r) => {
      let handler;
      if (app8.errorHandler === errorHandler) {
        handler = r.handler;
      } else {
        handler = async (c, next) => (await compose([], app8.errorHandler)(c, () => r.handler(c, next))).res;
        handler[COMPOSED_HANDLER] = r.handler;
      }
      subApp.#addRoute(r.method, r.path, handler, r.basePath);
    });
    return this;
  }
  /**
   * `.basePath()` allows base paths to be specified.
   *
   * @see {@link https://hono.dev/docs/api/routing#base-path}
   *
   * @param {string} path - base Path
   * @returns {Hono} changed Hono instance
   *
   * @example
   * ```ts
   * const api = new Hono().basePath('/api')
   * ```
   */
  basePath(path) {
    const subApp = this.#clone();
    subApp._basePath = mergePath(this._basePath, path);
    return subApp;
  }
  /**
   * `.onError()` handles an error and returns a customized Response.
   *
   * @see {@link https://hono.dev/docs/api/hono#error-handling}
   *
   * @param {ErrorHandler} handler - request Handler for error
   * @returns {Hono} changed Hono instance
   *
   * @example
   * ```ts
   * app.onError((err, c) => {
   *   console.error(`${err}`)
   *   return c.text('Custom Error Message', 500)
   * })
   * ```
   */
  onError = (handler) => {
    this.errorHandler = handler;
    return this;
  };
  /**
   * `.notFound()` allows you to customize a Not Found Response.
   *
   * @see {@link https://hono.dev/docs/api/hono#not-found}
   *
   * @param {NotFoundHandler} handler - request handler for not-found
   * @returns {Hono} changed Hono instance
   *
   * @example
   * ```ts
   * app.notFound((c) => {
   *   return c.text('Custom 404 Message', 404)
   * })
   * ```
   */
  notFound = (handler) => {
    this.#notFoundHandler = handler;
    return this;
  };
  /**
   * `.mount()` allows you to mount applications built with other frameworks into your Hono application.
   *
   * @see {@link https://hono.dev/docs/api/hono#mount}
   *
   * @param {string} path - base Path
   * @param {Function} applicationHandler - other Request Handler
   * @param {MountOptions} [options] - options of `.mount()`
   * @returns {Hono} mounted Hono instance
   *
   * @example
   * ```ts
   * import { Router as IttyRouter } from 'itty-router'
   * import { Hono } from 'hono'
   * // Create itty-router application
   * const ittyRouter = IttyRouter()
   * // GET /itty-router/hello
   * ittyRouter.get('/hello', () => new Response('Hello from itty-router'))
   *
   * const app = new Hono()
   * app.mount('/itty-router', ittyRouter.handle)
   * ```
   *
   * @example
   * ```ts
   * const app = new Hono()
   * // Send the request to another application without modification.
   * app.mount('/app', anotherApp, {
   *   replaceRequest: (req) => req,
   * })
   * ```
   */
  mount(path, applicationHandler, options) {
    let replaceRequest;
    let optionHandler;
    if (options) {
      if (typeof options === "function") {
        optionHandler = options;
      } else {
        optionHandler = options.optionHandler;
        if (options.replaceRequest === false) {
          replaceRequest = (request) => request;
        } else {
          replaceRequest = options.replaceRequest;
        }
      }
    }
    const getOptions = optionHandler ? (c) => {
      const options2 = optionHandler(c);
      return Array.isArray(options2) ? options2 : [options2];
    } : (c) => {
      let executionContext = void 0;
      try {
        executionContext = c.executionCtx;
      } catch {
      }
      return [c.env, executionContext];
    };
    replaceRequest ||= (() => {
      const mergedPath = mergePath(this._basePath, path);
      const pathPrefixLength = mergedPath === "/" ? 0 : mergedPath.length;
      return (request) => {
        const url = new URL(request.url);
        url.pathname = this.getPath(request).slice(pathPrefixLength) || "/";
        return new Request(url, request);
      };
    })();
    const handler = async (c, next) => {
      const res = await applicationHandler(replaceRequest(c.req.raw), ...getOptions(c));
      if (res) {
        return res;
      }
      await next();
    };
    this.#addRoute(METHOD_NAME_ALL, mergePath(path, "*"), handler);
    return this;
  }
  #addRoute(method, path, handler, baseRoutePath) {
    method = method.toUpperCase();
    path = mergePath(this._basePath, path);
    const r = {
      basePath: baseRoutePath !== void 0 ? mergePath(this._basePath, baseRoutePath) : this._basePath,
      path,
      method,
      handler
    };
    this.router.add(method, path, [handler, r]);
    this.routes.push(r);
  }
  #handleError(err, c) {
    if (err instanceof Error) {
      return this.errorHandler(err, c);
    }
    throw err;
  }
  #dispatch(request, executionCtx, env, method) {
    if (method === "HEAD") {
      return (async () => new Response(null, await this.#dispatch(request, executionCtx, env, "GET")))();
    }
    const path = this.getPath(request, { env });
    const matchResult = this.router.match(method, path);
    const c = new Context(request, {
      path,
      matchResult,
      env,
      executionCtx,
      notFoundHandler: this.#notFoundHandler
    });
    if (matchResult[0].length === 1) {
      let res;
      try {
        res = matchResult[0][0][0][0](c, async () => {
          c.res = await this.#notFoundHandler(c);
        });
      } catch (err) {
        return this.#handleError(err, c);
      }
      return res instanceof Promise ? res.then(
        (resolved) => resolved || (c.finalized ? c.res : this.#notFoundHandler(c))
      ).catch((err) => this.#handleError(err, c)) : res ?? this.#notFoundHandler(c);
    }
    const composed = compose(matchResult[0], this.errorHandler, this.#notFoundHandler);
    return (async () => {
      try {
        const context = await composed(c);
        if (!context.finalized) {
          throw new Error(
            "Context is not finalized. Did you forget to return a Response object or `await next()`?"
          );
        }
        return context.res;
      } catch (err) {
        return this.#handleError(err, c);
      }
    })();
  }
  /**
   * `.fetch()` will be entry point of your app.
   *
   * @see {@link https://hono.dev/docs/api/hono#fetch}
   *
   * @param {Request} request - request Object of request
   * @param {Env} Env - env Object
   * @param {ExecutionContext} - context of execution
   * @returns {Response | Promise<Response>} response of request
   *
   */
  fetch = (request, ...rest) => {
    return this.#dispatch(request, rest[1], rest[0], request.method);
  };
  /**
   * `.request()` is a useful method for testing.
   * You can pass a URL or pathname to send a GET request.
   * app will return a Response object.
   * ```ts
   * test('GET /hello is ok', async () => {
   *   const res = await app.request('/hello')
   *   expect(res.status).toBe(200)
   * })
   * ```
   * @see https://hono.dev/docs/api/hono#request
   */
  request = (input, requestInit, Env, executionCtx) => {
    if (input instanceof Request) {
      return this.fetch(requestInit ? new Request(input, requestInit) : input, Env, executionCtx);
    }
    input = input.toString();
    return this.fetch(
      new Request(
        /^https?:\/\//.test(input) ? input : `http://localhost${mergePath("/", input)}`,
        requestInit
      ),
      Env,
      executionCtx
    );
  };
  /**
   * `.fire()` automatically adds a global fetch event listener.
   * This can be useful for environments that adhere to the Service Worker API, such as non-ES module Cloudflare Workers.
   * @deprecated
   * Use `fire` from `hono/service-worker` instead.
   * ```ts
   * import { Hono } from 'hono'
   * import { fire } from 'hono/service-worker'
   *
   * const app = new Hono()
   * // ...
   * fire(app)
   * ```
   * @see https://hono.dev/docs/api/hono#fire
   * @see https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API
   * @see https://developers.cloudflare.com/workers/reference/migrate-to-module-workers/
   */
  fire = () => {
    addEventListener("fetch", (event) => {
      event.respondWith(this.#dispatch(event.request, event, void 0, event.request.method));
    });
  };
};

// worker/node_modules/hono/dist/router/reg-exp-router/matcher.js
var emptyParam = [];
function match(method, path) {
  const matchers = this.buildAllMatchers();
  const match2 = ((method2, path2) => {
    const matcher = matchers[method2] || matchers[METHOD_NAME_ALL];
    const staticMatch = matcher[2][path2];
    if (staticMatch) {
      return staticMatch;
    }
    const match3 = path2.match(matcher[0]);
    if (!match3) {
      return [[], emptyParam];
    }
    const index = match3.indexOf("", 1);
    return [matcher[1][index], match3];
  });
  this.match = match2;
  return match2(method, path);
}

// worker/node_modules/hono/dist/router/reg-exp-router/node.js
var LABEL_REG_EXP_STR = "[^/]+";
var ONLY_WILDCARD_REG_EXP_STR = ".*";
var TAIL_WILDCARD_REG_EXP_STR = "(?:|/.*)";
var PATH_ERROR = /* @__PURE__ */ Symbol();
var regExpMetaChars = new Set(".\\+*[^]$()");
function compareKey(a, b) {
  if (a.length === 1) {
    return b.length === 1 ? a < b ? -1 : 1 : -1;
  }
  if (b.length === 1) {
    return 1;
  }
  if (a === ONLY_WILDCARD_REG_EXP_STR || a === TAIL_WILDCARD_REG_EXP_STR) {
    return 1;
  } else if (b === ONLY_WILDCARD_REG_EXP_STR || b === TAIL_WILDCARD_REG_EXP_STR) {
    return -1;
  }
  if (a === LABEL_REG_EXP_STR) {
    return 1;
  } else if (b === LABEL_REG_EXP_STR) {
    return -1;
  }
  return a.length === b.length ? a < b ? -1 : 1 : b.length - a.length;
}
var Node = class _Node {
  #index;
  #varIndex;
  #children = /* @__PURE__ */ Object.create(null);
  insert(tokens, index, paramMap, context, pathErrorCheckOnly) {
    if (tokens.length === 0) {
      if (this.#index !== void 0) {
        throw PATH_ERROR;
      }
      if (pathErrorCheckOnly) {
        return;
      }
      this.#index = index;
      return;
    }
    const [token, ...restTokens] = tokens;
    const pattern = token === "*" ? restTokens.length === 0 ? ["", "", ONLY_WILDCARD_REG_EXP_STR] : ["", "", LABEL_REG_EXP_STR] : token === "/*" ? ["", "", TAIL_WILDCARD_REG_EXP_STR] : token.match(/^\:([^\{\}]+)(?:\{(.+)\})?$/);
    let node;
    if (pattern) {
      const name = pattern[1];
      let regexpStr = pattern[2] || LABEL_REG_EXP_STR;
      if (name && pattern[2]) {
        if (regexpStr === ".*") {
          throw PATH_ERROR;
        }
        regexpStr = regexpStr.replace(/^\((?!\?:)(?=[^)]+\)$)/, "(?:");
        if (/\((?!\?:)/.test(regexpStr)) {
          throw PATH_ERROR;
        }
      }
      node = this.#children[regexpStr];
      if (!node) {
        if (Object.keys(this.#children).some(
          (k) => k !== ONLY_WILDCARD_REG_EXP_STR && k !== TAIL_WILDCARD_REG_EXP_STR
        )) {
          throw PATH_ERROR;
        }
        if (pathErrorCheckOnly) {
          return;
        }
        node = this.#children[regexpStr] = new _Node();
        if (name !== "") {
          node.#varIndex = context.varIndex++;
        }
      }
      if (!pathErrorCheckOnly && name !== "") {
        paramMap.push([name, node.#varIndex]);
      }
    } else {
      node = this.#children[token];
      if (!node) {
        if (Object.keys(this.#children).some(
          (k) => k.length > 1 && k !== ONLY_WILDCARD_REG_EXP_STR && k !== TAIL_WILDCARD_REG_EXP_STR
        )) {
          throw PATH_ERROR;
        }
        if (pathErrorCheckOnly) {
          return;
        }
        node = this.#children[token] = new _Node();
      }
    }
    node.insert(restTokens, index, paramMap, context, pathErrorCheckOnly);
  }
  buildRegExpStr() {
    const childKeys = Object.keys(this.#children).sort(compareKey);
    const strList = childKeys.map((k) => {
      const c = this.#children[k];
      return (typeof c.#varIndex === "number" ? `(${k})@${c.#varIndex}` : regExpMetaChars.has(k) ? `\\${k}` : k) + c.buildRegExpStr();
    });
    if (typeof this.#index === "number") {
      strList.unshift(`#${this.#index}`);
    }
    if (strList.length === 0) {
      return "";
    }
    if (strList.length === 1) {
      return strList[0];
    }
    return "(?:" + strList.join("|") + ")";
  }
};

// worker/node_modules/hono/dist/router/reg-exp-router/trie.js
var Trie = class {
  #context = { varIndex: 0 };
  #root = new Node();
  insert(path, index, pathErrorCheckOnly) {
    const paramAssoc = [];
    const groups = [];
    for (let i = 0; ; ) {
      let replaced = false;
      path = path.replace(/\{[^}]+\}/g, (m) => {
        const mark = `@\\${i}`;
        groups[i] = [mark, m];
        i++;
        replaced = true;
        return mark;
      });
      if (!replaced) {
        break;
      }
    }
    const tokens = path.match(/(?::[^\/]+)|(?:\/\*$)|./g) || [];
    for (let i = groups.length - 1; i >= 0; i--) {
      const [mark] = groups[i];
      for (let j = tokens.length - 1; j >= 0; j--) {
        if (tokens[j].indexOf(mark) !== -1) {
          tokens[j] = tokens[j].replace(mark, groups[i][1]);
          break;
        }
      }
    }
    this.#root.insert(tokens, index, paramAssoc, this.#context, pathErrorCheckOnly);
    return paramAssoc;
  }
  buildRegExp() {
    let regexp = this.#root.buildRegExpStr();
    if (regexp === "") {
      return [/^$/, [], []];
    }
    let captureIndex = 0;
    const indexReplacementMap = [];
    const paramReplacementMap = [];
    regexp = regexp.replace(/#(\d+)|@(\d+)|\.\*\$/g, (_, handlerIndex, paramIndex) => {
      if (handlerIndex !== void 0) {
        indexReplacementMap[++captureIndex] = Number(handlerIndex);
        return "$()";
      }
      if (paramIndex !== void 0) {
        paramReplacementMap[Number(paramIndex)] = ++captureIndex;
        return "";
      }
      return "";
    });
    return [new RegExp(`^${regexp}`), indexReplacementMap, paramReplacementMap];
  }
};

// worker/node_modules/hono/dist/router/reg-exp-router/router.js
var nullMatcher = [/^$/, [], /* @__PURE__ */ Object.create(null)];
var wildcardRegExpCache = /* @__PURE__ */ Object.create(null);
function buildWildcardRegExp(path) {
  return wildcardRegExpCache[path] ??= new RegExp(
    path === "*" ? "" : `^${path.replace(
      /\/\*$|([.\\+*[^\]$()])/g,
      (_, metaChar) => metaChar ? `\\${metaChar}` : "(?:|/.*)"
    )}$`
  );
}
function clearWildcardRegExpCache() {
  wildcardRegExpCache = /* @__PURE__ */ Object.create(null);
}
function buildMatcherFromPreprocessedRoutes(routes) {
  const trie = new Trie();
  const handlerData = [];
  if (routes.length === 0) {
    return nullMatcher;
  }
  const routesWithStaticPathFlag = routes.map(
    (route) => [!/\*|\/:/.test(route[0]), ...route]
  ).sort(
    ([isStaticA, pathA], [isStaticB, pathB]) => isStaticA ? 1 : isStaticB ? -1 : pathA.length - pathB.length
  );
  const staticMap = /* @__PURE__ */ Object.create(null);
  for (let i = 0, j = -1, len = routesWithStaticPathFlag.length; i < len; i++) {
    const [pathErrorCheckOnly, path, handlers] = routesWithStaticPathFlag[i];
    if (pathErrorCheckOnly) {
      staticMap[path] = [handlers.map(([h]) => [h, /* @__PURE__ */ Object.create(null)]), emptyParam];
    } else {
      j++;
    }
    let paramAssoc;
    try {
      paramAssoc = trie.insert(path, j, pathErrorCheckOnly);
    } catch (e) {
      throw e === PATH_ERROR ? new UnsupportedPathError(path) : e;
    }
    if (pathErrorCheckOnly) {
      continue;
    }
    handlerData[j] = handlers.map(([h, paramCount]) => {
      const paramIndexMap = /* @__PURE__ */ Object.create(null);
      paramCount -= 1;
      for (; paramCount >= 0; paramCount--) {
        const [key2, value] = paramAssoc[paramCount];
        paramIndexMap[key2] = value;
      }
      return [h, paramIndexMap];
    });
  }
  const [regexp, indexReplacementMap, paramReplacementMap] = trie.buildRegExp();
  for (let i = 0, len = handlerData.length; i < len; i++) {
    for (let j = 0, len2 = handlerData[i].length; j < len2; j++) {
      const map = handlerData[i][j]?.[1];
      if (!map) {
        continue;
      }
      const keys = Object.keys(map);
      for (let k = 0, len3 = keys.length; k < len3; k++) {
        map[keys[k]] = paramReplacementMap[map[keys[k]]];
      }
    }
  }
  const handlerMap = [];
  for (const i in indexReplacementMap) {
    handlerMap[i] = handlerData[indexReplacementMap[i]];
  }
  return [regexp, handlerMap, staticMap];
}
function findMiddleware(middleware, path) {
  if (!middleware) {
    return void 0;
  }
  for (const k of Object.keys(middleware).sort((a, b) => b.length - a.length)) {
    if (buildWildcardRegExp(k).test(path)) {
      return [...middleware[k]];
    }
  }
  return void 0;
}
var RegExpRouter = class {
  name = "RegExpRouter";
  #middleware;
  #routes;
  constructor() {
    this.#middleware = { [METHOD_NAME_ALL]: /* @__PURE__ */ Object.create(null) };
    this.#routes = { [METHOD_NAME_ALL]: /* @__PURE__ */ Object.create(null) };
  }
  add(method, path, handler) {
    const middleware = this.#middleware;
    const routes = this.#routes;
    if (!middleware || !routes) {
      throw new Error(MESSAGE_MATCHER_IS_ALREADY_BUILT);
    }
    if (!middleware[method]) {
      ;
      [middleware, routes].forEach((handlerMap) => {
        handlerMap[method] = /* @__PURE__ */ Object.create(null);
        Object.keys(handlerMap[METHOD_NAME_ALL]).forEach((p) => {
          handlerMap[method][p] = [...handlerMap[METHOD_NAME_ALL][p]];
        });
      });
    }
    if (path === "/*") {
      path = "*";
    }
    const paramCount = (path.match(/\/:/g) || []).length;
    if (/\*$/.test(path)) {
      const re = buildWildcardRegExp(path);
      if (method === METHOD_NAME_ALL) {
        Object.keys(middleware).forEach((m) => {
          middleware[m][path] ||= findMiddleware(middleware[m], path) || findMiddleware(middleware[METHOD_NAME_ALL], path) || [];
        });
      } else {
        middleware[method][path] ||= findMiddleware(middleware[method], path) || findMiddleware(middleware[METHOD_NAME_ALL], path) || [];
      }
      Object.keys(middleware).forEach((m) => {
        if (method === METHOD_NAME_ALL || method === m) {
          Object.keys(middleware[m]).forEach((p) => {
            re.test(p) && middleware[m][p].push([handler, paramCount]);
          });
        }
      });
      Object.keys(routes).forEach((m) => {
        if (method === METHOD_NAME_ALL || method === m) {
          Object.keys(routes[m]).forEach(
            (p) => re.test(p) && routes[m][p].push([handler, paramCount])
          );
        }
      });
      return;
    }
    const paths = checkOptionalParameter(path) || [path];
    for (let i = 0, len = paths.length; i < len; i++) {
      const path2 = paths[i];
      Object.keys(routes).forEach((m) => {
        if (method === METHOD_NAME_ALL || method === m) {
          routes[m][path2] ||= [
            ...findMiddleware(middleware[m], path2) || findMiddleware(middleware[METHOD_NAME_ALL], path2) || []
          ];
          routes[m][path2].push([handler, paramCount - len + i + 1]);
        }
      });
    }
  }
  match = match;
  buildAllMatchers() {
    const matchers = /* @__PURE__ */ Object.create(null);
    Object.keys(this.#routes).concat(Object.keys(this.#middleware)).forEach((method) => {
      matchers[method] ||= this.#buildMatcher(method);
    });
    this.#middleware = this.#routes = void 0;
    clearWildcardRegExpCache();
    return matchers;
  }
  #buildMatcher(method) {
    const routes = [];
    let hasOwnRoute = method === METHOD_NAME_ALL;
    [this.#middleware, this.#routes].forEach((r) => {
      const ownRoute = r[method] ? Object.keys(r[method]).map((path) => [path, r[method][path]]) : [];
      if (ownRoute.length !== 0) {
        hasOwnRoute ||= true;
        routes.push(...ownRoute);
      } else if (method !== METHOD_NAME_ALL) {
        routes.push(
          ...Object.keys(r[METHOD_NAME_ALL]).map((path) => [path, r[METHOD_NAME_ALL][path]])
        );
      }
    });
    if (!hasOwnRoute) {
      return null;
    } else {
      return buildMatcherFromPreprocessedRoutes(routes);
    }
  }
};

// worker/node_modules/hono/dist/router/smart-router/router.js
var SmartRouter = class {
  name = "SmartRouter";
  #routers = [];
  #routes = [];
  constructor(init) {
    this.#routers = init.routers;
  }
  add(method, path, handler) {
    if (!this.#routes) {
      throw new Error(MESSAGE_MATCHER_IS_ALREADY_BUILT);
    }
    this.#routes.push([method, path, handler]);
  }
  match(method, path) {
    if (!this.#routes) {
      throw new Error("Fatal error");
    }
    const routers = this.#routers;
    const routes = this.#routes;
    const len = routers.length;
    let i = 0;
    let res;
    for (; i < len; i++) {
      const router = routers[i];
      try {
        for (let i2 = 0, len2 = routes.length; i2 < len2; i2++) {
          router.add(...routes[i2]);
        }
        res = router.match(method, path);
      } catch (e) {
        if (e instanceof UnsupportedPathError) {
          continue;
        }
        throw e;
      }
      this.match = router.match.bind(router);
      this.#routers = [router];
      this.#routes = void 0;
      break;
    }
    if (i === len) {
      throw new Error("Fatal error");
    }
    this.name = `SmartRouter + ${this.activeRouter.name}`;
    return res;
  }
  get activeRouter() {
    if (this.#routes || this.#routers.length !== 1) {
      throw new Error("No active router has been determined yet.");
    }
    return this.#routers[0];
  }
};

// worker/node_modules/hono/dist/router/trie-router/node.js
var emptyParams = /* @__PURE__ */ Object.create(null);
var hasChildren = (children) => {
  for (const _ in children) {
    return true;
  }
  return false;
};
var Node2 = class _Node2 {
  #methods;
  #children;
  #patterns;
  #order = 0;
  #params = emptyParams;
  constructor(method, handler, children) {
    this.#children = children || /* @__PURE__ */ Object.create(null);
    this.#methods = [];
    if (method && handler) {
      const m = /* @__PURE__ */ Object.create(null);
      m[method] = { handler, possibleKeys: [], score: 0 };
      this.#methods = [m];
    }
    this.#patterns = [];
  }
  insert(method, path, handler) {
    this.#order = ++this.#order;
    let curNode = this;
    const parts = splitRoutingPath(path);
    const possibleKeys = [];
    for (let i = 0, len = parts.length; i < len; i++) {
      const p = parts[i];
      const nextP = parts[i + 1];
      const pattern = getPattern(p, nextP);
      const key2 = Array.isArray(pattern) ? pattern[0] : p;
      if (key2 in curNode.#children) {
        curNode = curNode.#children[key2];
        if (pattern) {
          possibleKeys.push(pattern[1]);
        }
        continue;
      }
      curNode.#children[key2] = new _Node2();
      if (pattern) {
        curNode.#patterns.push(pattern);
        possibleKeys.push(pattern[1]);
      }
      curNode = curNode.#children[key2];
    }
    curNode.#methods.push({
      [method]: {
        handler,
        possibleKeys: possibleKeys.filter((v, i, a) => a.indexOf(v) === i),
        score: this.#order
      }
    });
    return curNode;
  }
  #pushHandlerSets(handlerSets, node, method, nodeParams, params) {
    for (let i = 0, len = node.#methods.length; i < len; i++) {
      const m = node.#methods[i];
      const handlerSet = m[method] || m[METHOD_NAME_ALL];
      const processedSet = {};
      if (handlerSet !== void 0) {
        handlerSet.params = /* @__PURE__ */ Object.create(null);
        handlerSets.push(handlerSet);
        if (nodeParams !== emptyParams || params && params !== emptyParams) {
          for (let i2 = 0, len2 = handlerSet.possibleKeys.length; i2 < len2; i2++) {
            const key2 = handlerSet.possibleKeys[i2];
            const processed = processedSet[handlerSet.score];
            handlerSet.params[key2] = params?.[key2] && !processed ? params[key2] : nodeParams[key2] ?? params?.[key2];
            processedSet[handlerSet.score] = true;
          }
        }
      }
    }
  }
  search(method, path) {
    const handlerSets = [];
    this.#params = emptyParams;
    const curNode = this;
    let curNodes = [curNode];
    const parts = splitPath(path);
    const curNodesQueue = [];
    const len = parts.length;
    let partOffsets = null;
    for (let i = 0; i < len; i++) {
      const part = parts[i];
      const isLast = i === len - 1;
      const tempNodes = [];
      for (let j = 0, len2 = curNodes.length; j < len2; j++) {
        const node = curNodes[j];
        const nextNode = node.#children[part];
        if (nextNode) {
          nextNode.#params = node.#params;
          if (isLast) {
            if (nextNode.#children["*"]) {
              this.#pushHandlerSets(handlerSets, nextNode.#children["*"], method, node.#params);
            }
            this.#pushHandlerSets(handlerSets, nextNode, method, node.#params);
          } else {
            tempNodes.push(nextNode);
          }
        }
        for (let k = 0, len3 = node.#patterns.length; k < len3; k++) {
          const pattern = node.#patterns[k];
          const params = node.#params === emptyParams ? {} : { ...node.#params };
          if (pattern === "*") {
            const astNode = node.#children["*"];
            if (astNode) {
              this.#pushHandlerSets(handlerSets, astNode, method, node.#params);
              astNode.#params = params;
              tempNodes.push(astNode);
            }
            continue;
          }
          const [key2, name, matcher] = pattern;
          if (!part && !(matcher instanceof RegExp)) {
            continue;
          }
          const child = node.#children[key2];
          if (matcher instanceof RegExp) {
            if (partOffsets === null) {
              partOffsets = new Array(len);
              let offset = path[0] === "/" ? 1 : 0;
              for (let p = 0; p < len; p++) {
                partOffsets[p] = offset;
                offset += parts[p].length + 1;
              }
            }
            const restPathString = path.substring(partOffsets[i]);
            const m = matcher.exec(restPathString);
            if (m) {
              params[name] = m[0];
              this.#pushHandlerSets(handlerSets, child, method, node.#params, params);
              if (hasChildren(child.#children)) {
                child.#params = params;
                const componentCount = m[0].match(/\//)?.length ?? 0;
                const targetCurNodes = curNodesQueue[componentCount] ||= [];
                targetCurNodes.push(child);
              }
              continue;
            }
          }
          if (matcher === true || matcher.test(part)) {
            params[name] = part;
            if (isLast) {
              this.#pushHandlerSets(handlerSets, child, method, params, node.#params);
              if (child.#children["*"]) {
                this.#pushHandlerSets(
                  handlerSets,
                  child.#children["*"],
                  method,
                  params,
                  node.#params
                );
              }
            } else {
              child.#params = params;
              tempNodes.push(child);
            }
          }
        }
      }
      const shifted = curNodesQueue.shift();
      curNodes = shifted ? tempNodes.concat(shifted) : tempNodes;
    }
    if (handlerSets.length > 1) {
      handlerSets.sort((a, b) => {
        return a.score - b.score;
      });
    }
    return [handlerSets.map(({ handler, params }) => [handler, params])];
  }
};

// worker/node_modules/hono/dist/router/trie-router/router.js
var TrieRouter = class {
  name = "TrieRouter";
  #node;
  constructor() {
    this.#node = new Node2();
  }
  add(method, path, handler) {
    const results = checkOptionalParameter(path);
    if (results) {
      for (let i = 0, len = results.length; i < len; i++) {
        this.#node.insert(method, results[i], handler);
      }
      return;
    }
    this.#node.insert(method, path, handler);
  }
  match(method, path) {
    return this.#node.search(method, path);
  }
};

// worker/node_modules/hono/dist/hono.js
var Hono2 = class extends Hono {
  /**
   * Creates an instance of the Hono class.
   *
   * @param options - Optional configuration options for the Hono instance.
   */
  constructor(options = {}) {
    super(options);
    this.router = options.router ?? new SmartRouter({
      routers: [new RegExpRouter(), new TrieRouter()]
    });
  }
};

// worker/src/types.ts
function corsOrigin(env) {
  return env.FRONTEND_ORIGIN;
}

// worker/src/middleware/cors.ts
function corsHeaders(env, request) {
  const origin = request.headers.get("Origin") ?? "";
  const allowed = corsOrigin(env);
  const headers = new Headers();
  if (origin === allowed) {
    headers.set("Access-Control-Allow-Origin", origin);
    headers.set("Vary", "Origin");
    headers.set("Access-Control-Allow-Credentials", "true");
    headers.set("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS");
    headers.set("Access-Control-Allow-Headers", "Content-Type, Authorization");
    headers.set("Access-Control-Max-Age", "86400");
  }
  return headers;
}
function applyCors(response, env, request) {
  const cors = corsHeaders(env, request);
  cors.forEach((value, key2) => response.headers.set(key2, value));
  return response;
}

// worker/src/lib/jwt.ts
var HEADER = { alg: "HS256", typ: "JWT" };
function base64urlEncode(bytes) {
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function base64urlDecode(str) {
  const padded = str + "=".repeat((4 - str.length % 4) % 4);
  const binary = atob(padded.replace(/-/g, "+").replace(/_/g, "/"));
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}
function strToBytes(s) {
  return new TextEncoder().encode(s);
}
async function importKey(secret) {
  return crypto.subtle.importKey(
    "raw",
    strToBytes(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign", "verify"]
  );
}
async function signJWT(payload, secret, expiresInSec = 30 * 24 * 60 * 60) {
  const now = Math.floor(Date.now() / 1e3);
  const fullPayload = {
    ...payload,
    iat: now,
    exp: now + expiresInSec
  };
  const headerB64 = base64urlEncode(strToBytes(JSON.stringify(HEADER)));
  const payloadB64 = base64urlEncode(strToBytes(JSON.stringify(fullPayload)));
  const signingInput = `${headerB64}.${payloadB64}`;
  const key2 = await importKey(secret);
  const sig = await crypto.subtle.sign("HMAC", key2, strToBytes(signingInput));
  const sigB64 = base64urlEncode(new Uint8Array(sig));
  return `${signingInput}.${sigB64}`;
}
async function verifyJWT(token, secret) {
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  const [headerB64, payloadB64, sigB64] = parts;
  const signingInput = `${headerB64}.${payloadB64}`;
  try {
    const key2 = await importKey(secret);
    const sigBytes = base64urlDecode(sigB64);
    const valid = await crypto.subtle.verify("HMAC", key2, sigBytes, strToBytes(signingInput));
    if (!valid) return null;
    const payloadBytes = base64urlDecode(payloadB64);
    const payload = JSON.parse(new TextDecoder().decode(payloadBytes));
    if (payload.exp < Math.floor(Date.now() / 1e3)) return null;
    return payload;
  } catch {
    return null;
  }
}
function getJWTSecret(env) {
  if (env.JWT_SECRET) return env.JWT_SECRET;
  if (env.JWT_SECRET_DEV) return env.JWT_SECRET_DEV;
  throw new Error("JWT_SECRET not configured. Set it via `wrangler secret put JWT_SECRET`.");
}

// worker/src/middleware/auth.ts
init_kv();
var optionalAuth = async (c, next) => {
  const auth = c.req.header("Authorization");
  if (!auth?.startsWith("Bearer ")) {
    c.set("user", null);
    c.set("userId", null);
    c.set("email", null);
    await next();
    return;
  }
  const token = auth.slice("Bearer ".length).trim();
  try {
    const payload = await verifyJWT(token, getJWTSecret(c.env));
    if (!payload) throw new Error("invalid token");
    const user = await getAuthUser(c.env.LAB_KV, payload.email);
    if (!user) throw new Error("user not found");
    c.set("user", user);
    c.set("userId", user.userId);
    c.set("email", user.email);
  } catch (err) {
    console.warn("[auth] invalid token", err);
    c.set("user", null);
    c.set("userId", null);
    c.set("email", null);
  }
  await next();
};
var requireAuth = async (c, next) => {
  const user = c.get("user");
  if (!user) {
    return c.json({ error: "unauthorized", message: "\u041D\u0443\u0436\u0435\u043D \u0432\u0445\u043E\u0434 \u043F\u043E email" }, 401);
  }
  await next();
};

// worker/src/routes/auth.ts
init_kv();

// worker/src/lib/email.ts
async function sendEmail(env, params) {
  if (!env.RESEND_API_KEY) {
    console.log("[email:dev]", params.subject, "\u2192", params.to);
    console.log("[email:dev]", params.text ?? params.html.replace(/<[^>]+>/g, "").slice(0, 200));
    return { ok: true, id: "dev-mode" };
  }
  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${env.RESEND_API_KEY}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      from: "\u041B\u0410\u0411\u041E\u0420\u0410\u0422\u041E\u0420\u0418\u042F \u0416\u0415\u041B\u0410\u041D\u0418\u0419 <hello@app.pulab.online>",
      to: params.to,
      subject: params.subject,
      html: params.html,
      text: params.text
    })
  });
  if (!res.ok) {
    const body = await res.text();
    console.error("[email:error]", res.status, body);
    return { ok: false, error: `Resend API error: ${res.status}` };
  }
  const data = await res.json();
  return { ok: true, id: data.id };
}
function authCodeEmail(params) {
  const subject = "\u041A\u043E\u0434 \u0432\u0445\u043E\u0434\u0430 \u0432 \u041B\u0410\u0411\u041E\u0420\u0410\u0422\u041E\u0420\u0418\u042E \u0416\u0415\u041B\u0410\u041D\u0418\u0419";
  const text = `\u0412\u0430\u0448 \u043A\u043E\u0434 \u0432\u0445\u043E\u0434\u0430: ${params.code}

\u041E\u043D \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u0442\u0435\u043B\u0435\u043D 10 \u043C\u0438\u043D\u0443\u0442.

\u0415\u0441\u043B\u0438 \u0432\u044B \u043D\u0435 \u0437\u0430\u043F\u0440\u0430\u0448\u0438\u0432\u0430\u043B\u0438 \u043A\u043E\u0434, \u043F\u0440\u043E\u0441\u0442\u043E \u043F\u0440\u043E\u0438\u0433\u043D\u043E\u0440\u0438\u0440\u0443\u0439\u0442\u0435 \u044D\u0442\u043E \u043F\u0438\u0441\u044C\u043C\u043E.`;
  const html = `<!doctype html>
<html><body style="margin:0;padding:0;background:#fff1f2;font-family:'Helvetica Neue',Arial,sans-serif;color:#1f0a14;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#fff1f2;padding:40px 20px;">
  <tr><td align="center">
    <table width="480" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:18px;border:1px solid rgba(225,29,72,0.18);overflow:hidden;">
      <tr><td style="background:linear-gradient(135deg,#e11d48 0%,#881337 100%);padding:32px 32px 24px;text-align:center;">
        <h1 style="margin:0;font-size:18px;font-weight:700;color:#ffffff;letter-spacing:0.04em;">\u041B\u0410\u0411\u041E\u0420\u0410\u0422\u041E\u0420\u0418\u042F \u0416\u0415\u041B\u0410\u041D\u0418\u0419</h1>
      </td></tr>
      <tr><td style="padding:36px 32px 16px;text-align:center;">
        <p style="margin:0 0 12px;font-size:14px;color:#6b3a4a;letter-spacing:0.04em;text-transform:uppercase;">\u0412\u0430\u0448 \u043A\u043E\u0434 \u0432\u0445\u043E\u0434\u0430</p>
        <div style="font-family:'Courier New',monospace;font-size:36px;font-weight:700;letter-spacing:0.4em;color:#881337;padding:20px 0;background:#fff5f7;border-radius:14px;margin:0 0 20px;">${params.code}</div>
        <p style="margin:0 0 8px;font-size:14px;line-height:1.5;color:#1f0a14;">\u041A\u043E\u0434 \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u0442\u0435\u043B\u0435\u043D <strong>10 \u043C\u0438\u043D\u0443\u0442</strong>.</p>
        <p style="margin:0;font-size:13px;line-height:1.5;color:#6b3a4a;">\u0415\u0441\u043B\u0438 \u0432\u044B \u043D\u0435 \u0437\u0430\u043F\u0440\u0430\u0448\u0438\u0432\u0430\u043B\u0438 \u043A\u043E\u0434 \u2014 \u043F\u0440\u043E\u0441\u0442\u043E \u043F\u0440\u043E\u0438\u0433\u043D\u043E\u0440\u0438\u0440\u0443\u0439\u0442\u0435 \u044D\u0442\u043E \u043F\u0438\u0441\u044C\u043C\u043E.</p>
      </td></tr>
      <tr><td style="padding:24px 32px 32px;text-align:center;">
        <a href="${params.frontendOrigin}/tracker/" style="display:inline-block;background:#e11d48;color:#ffffff;text-decoration:none;padding:12px 24px;border-radius:999px;font-size:14px;font-weight:600;">\u041F\u0435\u0440\u0435\u0439\u0442\u0438 \u043A \u0442\u0440\u0435\u043A\u0435\u0440\u0443</a>
      </td></tr>
    </table>
    <p style="margin:24px 0 0;font-size:12px;color:#6b3a4a;">\xA9 2024\u20132026 \u041B\u0410\u0411\u041E\u0420\u0410\u0422\u041E\u0420\u0418\u042F \u0416\u0415\u041B\u0410\u041D\u0418\u0419</p>
  </td></tr>
</table>
</body></html>`;
  return { subject, html, text };
}

// worker/src/routes/auth.ts
var app = new Hono2();
var EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
function generateCode() {
  const buf = new Uint8Array(4);
  crypto.getRandomValues(buf);
  const n = (buf[0] << 24 | buf[1] << 16 | buf[2] << 8 | buf[3]) >>> 0;
  return String(n % 1e6).padStart(6, "0");
}
app.post("/auth/code", async (c) => {
  let body;
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: "bad_request", message: "\u041D\u0443\u0436\u0435\u043D JSON \u0441 \u043F\u043E\u043B\u0435\u043C email" }, 400);
  }
  const email = (body.email ?? "").trim().toLowerCase();
  if (!email || !EMAIL_RE.test(email) || email.length > 254) {
    return c.json({ error: "invalid_email", message: "\u041F\u043E\u0445\u043E\u0436\u0435, email \u0443\u043A\u0430\u0437\u0430\u043D \u043D\u0435\u0432\u0435\u0440\u043D\u043E" }, 400);
  }
  const code = generateCode();
  await setAuthCode(c.env.LAB_KV, email, code);
  const tpl = authCodeEmail({ code, email, frontendOrigin: c.env.FRONTEND_ORIGIN });
  const result = await sendEmail(c.env, {
    to: email,
    subject: tpl.subject,
    html: tpl.html,
    text: tpl.text
  });
  if (!result.ok) {
    return c.json({ error: "email_send_failed", message: "\u041D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u043E\u0442\u043F\u0440\u0430\u0432\u0438\u0442\u044C \u043F\u0438\u0441\u044C\u043C\u043E. \u041F\u043E\u043F\u0440\u043E\u0431\u0443\u0439\u0442\u0435 \u043F\u043E\u0437\u0436\u0435." }, 502);
  }
  return c.json({
    ok: true,
    // В dev-режиме (без RESEND_API_KEY) возвращаем код в ответе для удобства тестирования
    devCode: c.env.RESEND_API_KEY ? void 0 : code,
    expiresInSec: 600
  });
});
app.post("/auth/verify", async (c) => {
  let body;
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: "bad_request", message: "\u041D\u0443\u0436\u0435\u043D JSON" }, 400);
  }
  const email = (body.email ?? "").trim().toLowerCase();
  const code = (body.code ?? "").trim();
  if (!email || !code) {
    return c.json({ error: "bad_request", message: "\u041D\u0443\u0436\u043D\u044B email \u0438 \u043A\u043E\u0434" }, 400);
  }
  const stored = await getAuthCode(c.env.LAB_KV, email);
  if (!stored) {
    return c.json({ error: "code_expired", message: "\u041A\u043E\u0434 \u0438\u0441\u0442\u0451\u043A \u0438\u043B\u0438 \u043D\u0435 \u0441\u0443\u0449\u0435\u0441\u0442\u0432\u0443\u0435\u0442. \u0417\u0430\u043F\u0440\u043E\u0441\u0438\u0442\u0435 \u043D\u043E\u0432\u044B\u0439." }, 410);
  }
  if (Date.now() > stored.expiresAt) {
    await deleteAuthCode(c.env.LAB_KV, email);
    return c.json({ error: "code_expired", message: "\u041A\u043E\u0434 \u0438\u0441\u0442\u0451\u043A. \u0417\u0430\u043F\u0440\u043E\u0441\u0438\u0442\u0435 \u043D\u043E\u0432\u044B\u0439." }, 410);
  }
  if (stored.code !== code) {
    const updated = await recordFailedAttempt(c.env.LAB_KV, email);
    const remaining = updated ? Math.max(0, 5 - updated.attempts) : 0;
    return c.json({
      error: "code_invalid",
      message: "\u041D\u0435\u0432\u0435\u0440\u043D\u044B\u0439 \u043A\u043E\u0434.",
      attemptsRemaining: remaining
    }, 401);
  }
  await deleteAuthCode(c.env.LAB_KV, email);
  const user = await ensureAuthUser(c.env.LAB_KV, email);
  const token = await signJWT({ sub: user.userId, email: user.email }, getJWTSecret(c.env));
  return c.json({
    ok: true,
    token,
    user: {
      email: user.email,
      userId: user.userId,
      plan: user.plan,
      subscriptionStatus: user.subscriptionStatus,
      subscriptionExpiresAt: user.subscriptionExpiresAt,
      generationsLimit: user.generationsLimit,
      wishesLimit: user.wishesLimit
    }
  });
});
app.get("/auth/me", requireAuth, async (c) => {
  const user = c.get("user");
  const counts = await getGenerationCounts(c.env.LAB_KV, user.userId);
  return c.json({
    user: {
      email: user.email,
      userId: user.userId,
      plan: user.plan,
      subscriptionStatus: user.subscriptionStatus,
      subscriptionExpiresAt: user.subscriptionExpiresAt,
      generationsLimit: user.generationsLimit,
      wishesLimit: user.wishesLimit
    },
    generations: {
      usedThisMonth: counts.month,
      usedToday: counts.day,
      limitThisMonth: user.generationsLimit,
      limitPerDay: user.plan === "free" ? 1 : user.plan === "month" ? 5 : 100
    }
  });
});
app.post("/auth/logout", (c) => c.json({ ok: true }));
var auth_default = app;

// worker/src/routes/tracker.ts
init_kv();
var app2 = new Hono2({ strict: false });
app2.use("/tracker/*", requireAuth);
function newId() {
  return crypto.randomUUID().replace(/-/g, "").slice(0, 12);
}
async function loadWishes(kv, userId) {
  const raw2 = await kv.get(KV_KEYS.trackerWishes(userId));
  if (!raw2) return [];
  try {
    return JSON.parse(raw2);
  } catch {
    return [];
  }
}
async function saveWishes(kv, userId, wishes) {
  await kv.put(KV_KEYS.trackerWishes(userId), JSON.stringify(wishes));
}
function activeWishesCount(wishes) {
  return wishes.filter((w) => !w.archivedAt).length;
}
app2.get("/tracker/wishes", async (c) => {
  const user = c.get("user");
  const wishes = await loadWishes(c.env.LAB_KV, user.userId);
  const sorted = [...wishes].sort((a, b) => {
    if (!!a.archivedAt !== !!b.archivedAt) return a.archivedAt ? 1 : -1;
    return b.createdAt.localeCompare(a.createdAt);
  });
  return c.json({
    wishes: sorted,
    quota: {
      active: activeWishesCount(wishes),
      limit: user.wishesLimit,
      remaining: Math.max(0, user.wishesLimit - activeWishesCount(wishes)),
      plan: user.plan
    }
  });
});
app2.post("/tracker/wishes", async (c) => {
  const user = c.get("user");
  let body;
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: "bad_request", message: "\u041D\u0443\u0436\u0435\u043D JSON" }, 400);
  }
  const title = (body.title ?? "").trim();
  const description = (body.description ?? "").trim() || void 0;
  if (!title) return c.json({ error: "bad_request", message: "\u041D\u0430\u0437\u0432\u0430\u043D\u0438\u0435 \u043E\u0431\u044F\u0437\u0430\u0442\u0435\u043B\u044C\u043D\u043E" }, 400);
  if (title.length > 100) return c.json({ error: "bad_request", message: "\u041D\u0430\u0437\u0432\u0430\u043D\u0438\u0435 \u0441\u043B\u0438\u0448\u043A\u043E\u043C \u0434\u043B\u0438\u043D\u043D\u043E\u0435 (\u043C\u0430\u043A\u0441. 100)" }, 400);
  if (description && description.length > 500) {
    return c.json({ error: "bad_request", message: "\u041E\u043F\u0438\u0441\u0430\u043D\u0438\u0435 \u0441\u043B\u0438\u0448\u043A\u043E\u043C \u0434\u043B\u0438\u043D\u043D\u043E\u0435 (\u043C\u0430\u043A\u0441. 500)" }, 500);
  }
  const wishes = await loadWishes(c.env.LAB_KV, user.userId);
  const active = activeWishesCount(wishes);
  if (active >= user.wishesLimit) {
    return c.json({
      error: "quota_exceeded",
      message: `\u041B\u0438\u043C\u0438\u0442 \u0430\u043A\u0442\u0438\u0432\u043D\u044B\u0445 \u0436\u0435\u043B\u0430\u043D\u0438\u0439: ${user.wishesLimit}. \u0423\u0434\u0430\u043B\u0438 \u0438\u043B\u0438 \u0437\u0430\u0430\u0440\u0445\u0438\u0432\u0438\u0440\u0443\u0439 \u0441\u0442\u0430\u0440\u044B\u0435, \u0438\u043B\u0438 \u043E\u0444\u043E\u0440\u043C\u0438 \u043F\u043E\u0434\u043F\u0438\u0441\u043A\u0443.`,
      quota: { active, limit: user.wishesLimit },
      upgradeUrl: "/pricing/"
    }, 403);
  }
  const stepInputs = Array.isArray(body.steps) ? body.steps.slice(0, 10) : [];
  const steps = stepInputs.map((s) => ({ text: (s?.text ?? "").trim() })).filter((s) => s.text.length > 0).map((s) => {
    if (s.text.length > 200) s.text = s.text.slice(0, 200);
    return { id: newId(), text: s.text, done: false };
  });
  const now = (/* @__PURE__ */ new Date()).toISOString();
  const wish = {
    id: newId(),
    title,
    description,
    steps,
    createdAt: now,
    updatedAt: now
  };
  wishes.push(wish);
  await saveWishes(c.env.LAB_KV, user.userId, wishes);
  return c.json({ ok: true, wish }, 201);
});
app2.patch("/tracker/wishes/:id", async (c) => {
  const user = c.get("user");
  const id = c.req.param("id");
  let body;
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: "bad_request", message: "\u041D\u0443\u0436\u0435\u043D JSON" }, 400);
  }
  const wishes = await loadWishes(c.env.LAB_KV, user.userId);
  const wish = wishes.find((w) => w.id === id);
  if (!wish) return c.json({ error: "not_found", message: "\u0416\u0435\u043B\u0430\u043D\u0438\u0435 \u043D\u0435 \u043D\u0430\u0439\u0434\u0435\u043D\u043E" }, 404);
  if (typeof body.title === "string") {
    const title = body.title.trim();
    if (!title) return c.json({ error: "bad_request", message: "\u041D\u0430\u0437\u0432\u0430\u043D\u0438\u0435 \u043D\u0435 \u043C\u043E\u0436\u0435\u0442 \u0431\u044B\u0442\u044C \u043F\u0443\u0441\u0442\u044B\u043C" }, 400);
    if (title.length > 100) return c.json({ error: "bad_request", message: "\u041D\u0430\u0437\u0432\u0430\u043D\u0438\u0435 \u0441\u043B\u0438\u0448\u043A\u043E\u043C \u0434\u043B\u0438\u043D\u043D\u043E\u0435" }, 400);
    wish.title = title;
  }
  if (typeof body.description === "string") {
    const desc = body.description.trim();
    if (desc.length > 500) return c.json({ error: "bad_request", message: "\u041E\u043F\u0438\u0441\u0430\u043D\u0438\u0435 \u0441\u043B\u0438\u0448\u043A\u043E\u043C \u0434\u043B\u0438\u043D\u043D\u043E\u0435" }, 400);
    wish.description = desc || void 0;
  }
  if (Array.isArray(body.steps)) {
    const newSteps = body.steps.slice(0, 10).map((s) => {
      const text = (s?.text ?? "").trim().slice(0, 200);
      const stepId = s?.id && wishes.find((w) => w.steps.some((x) => x.id === s.id)) ? s.id : newId();
      const done = !!s?.done;
      return {
        id: stepId,
        text,
        done,
        doneAt: done ? wishes.find((w) => w.steps.find((x) => x.id === stepId))?.steps.find((x) => x.id === stepId)?.doneAt ?? (/* @__PURE__ */ new Date()).toISOString() : void 0
      };
    }).filter((s) => s.text.length > 0);
    wish.steps = newSteps;
  }
  if (typeof body.archived === "boolean") {
    wish.archivedAt = body.archived ? (/* @__PURE__ */ new Date()).toISOString() : void 0;
  }
  wish.updatedAt = (/* @__PURE__ */ new Date()).toISOString();
  await saveWishes(c.env.LAB_KV, user.userId, wishes);
  return c.json({ ok: true, wish });
});
app2.delete("/tracker/wishes/:id", async (c) => {
  const user = c.get("user");
  const id = c.req.param("id");
  const wishes = await loadWishes(c.env.LAB_KV, user.userId);
  const idx = wishes.findIndex((w) => w.id === id);
  if (idx === -1) return c.json({ error: "not_found", message: "\u0416\u0435\u043B\u0430\u043D\u0438\u0435 \u043D\u0435 \u043D\u0430\u0439\u0434\u0435\u043D\u043E" }, 404);
  const [removed] = wishes.splice(idx, 1);
  await saveWishes(c.env.LAB_KV, user.userId, wishes);
  return c.json({ ok: true, removedId: removed.id });
});
app2.post("/tracker/wishes/:id/toggle", async (c) => {
  const user = c.get("user");
  const id = c.req.param("id");
  let body;
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: "bad_request", message: "\u041D\u0443\u0436\u0435\u043D JSON" }, 400);
  }
  const stepId = (body.stepId ?? "").trim();
  if (!stepId) return c.json({ error: "bad_request", message: "\u041D\u0443\u0436\u0435\u043D stepId" }, 400);
  const done = !!body.done;
  const wishes = await loadWishes(c.env.LAB_KV, user.userId);
  const wish = wishes.find((w) => w.id === id);
  if (!wish) return c.json({ error: "not_found", message: "\u0416\u0435\u043B\u0430\u043D\u0438\u0435 \u043D\u0435 \u043D\u0430\u0439\u0434\u0435\u043D\u043E" }, 404);
  const step = wish.steps.find((s) => s.id === stepId);
  if (!step) return c.json({ error: "not_found", message: "\u0428\u0430\u0433 \u043D\u0435 \u043D\u0430\u0439\u0434\u0435\u043D" }, 404);
  step.done = done;
  step.doneAt = done ? (/* @__PURE__ */ new Date()).toISOString() : void 0;
  wish.updatedAt = (/* @__PURE__ */ new Date()).toISOString();
  await saveWishes(c.env.LAB_KV, user.userId, wishes);
  return c.json({ ok: true, wish });
});
var tracker_default = app2;

// worker/src/routes/generate.ts
init_kv();
var app3 = new Hono2({ strict: false });
app3.use("/generate/*", requireAuth);
function newJobId() {
  return crypto.randomUUID().replace(/-/g, "").slice(0, 16);
}
var KOOB_URL_RE = /^https?:\/\/(www\.)?koob\.ru\/[\w\-./?=&%#]+$/i;
function publicJobView(job, env) {
  return {
    jobId: job.jobId,
    status: job.status,
    stage: job.stage,
    progress: job.progress,
    message: job.message,
    slug: job.slug,
    result: job.result,
    error: job.error,
    createdAt: job.createdAt,
    updatedAt: job.updatedAt,
    startedAt: job.startedAt,
    finishedAt: job.finishedAt,
    bookUrl: env.FRONTEND_ORIGIN.includes(job.bookUrl) ? void 0 : void 0
    // никогда не отдаём url обратно
  };
}
app3.post("/generate/jobs", async (c) => {
  const user = c.get("user");
  let body;
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: "bad_request", message: "\u041D\u0443\u0436\u0435\u043D JSON \u0441 \u043F\u043E\u043B\u0435\u043C bookUrl" }, 400);
  }
  const url = (body.bookUrl ?? "").trim();
  if (!url) {
    return c.json({ error: "bad_request", message: "\u0423\u043A\u0430\u0436\u0438\u0442\u0435 URL \u043A\u043D\u0438\u0433\u0438 \u043D\u0430 koob.ru" }, 400);
  }
  if (!KOOB_URL_RE.test(url)) {
    return c.json({ error: "bad_request", message: "\u041F\u043E\u0434\u0434\u0435\u0440\u0436\u0438\u0432\u0430\u044E\u0442\u0441\u044F \u0442\u043E\u043B\u044C\u043A\u043E \u0441\u0441\u044B\u043B\u043A\u0438 \u043D\u0430 koob.ru" }, 400);
  }
  if (url.length > 500) {
    return c.json({ error: "bad_request", message: "\u0421\u043B\u0438\u0448\u043A\u043E\u043C \u0434\u043B\u0438\u043D\u043D\u044B\u0439 URL" }, 400);
  }
  const { incrementGenerationCount: incrementGenerationCount2, getGenerationCounts: getGenerationCounts2 } = await Promise.resolve().then(() => (init_kv(), kv_exports));
  const counts = await getGenerationCounts2(c.env.LAB_KV, user.userId);
  const perDay = user.plan === "free" ? 1 : user.plan === "month" ? 5 : 100;
  if (counts.month >= user.generationsLimit) {
    return c.json({
      error: "quota_exceeded",
      message: `\u041B\u0438\u043C\u0438\u0442 \u0433\u0435\u043D\u0435\u0440\u0430\u0446\u0438\u0439 \u043D\u0430 \u043C\u0435\u0441\u044F\u0446: ${user.generationsLimit}. \u041E\u0444\u043E\u0440\u043C\u0438\u0442\u0435 \u043F\u043E\u0434\u043F\u0438\u0441\u043A\u0443.`,
      quota: { used: counts.month, limit: user.generationsLimit, plan: user.plan },
      upgradeUrl: "/pricing/"
    }, 403);
  }
  if (counts.day >= perDay) {
    return c.json({
      error: "quota_exceeded_daily",
      message: `\u0414\u043D\u0435\u0432\u043D\u043E\u0439 \u043B\u0438\u043C\u0438\u0442: ${perDay} \u0433\u0435\u043D\u0435\u0440\u0430\u0446\u0438\u0439. \u041F\u043E\u043F\u0440\u043E\u0431\u0443\u0439\u0442\u0435 \u0437\u0430\u0432\u0442\u0440\u0430.`,
      quota: { used: counts.day, limit: perDay, plan: user.plan }
    }, 429);
  }
  await incrementGenerationCount2(c.env.LAB_KV, user.userId);
  const now = (/* @__PURE__ */ new Date()).toISOString();
  const job = {
    jobId: newJobId(),
    userId: user.userId,
    bookUrl: url,
    status: "pending",
    stage: "queued",
    progress: 0,
    message: "\u0412 \u043E\u0447\u0435\u0440\u0435\u0434\u0438",
    createdAt: now,
    updatedAt: now
  };
  await c.env.LAB_KV.put(KV_KEYS.job(job.jobId), JSON.stringify(job), {
    // TTL 6 часов — за это время генерация уж точно завершится или упадёт
    expirationTtl: 6 * 60 * 60
  });
  return c.json({ ok: true, job: publicJobView(job, c.env) }, 201);
});
app3.get("/generate/jobs/:id", async (c) => {
  const user = c.get("user");
  const id = c.req.param("id");
  const raw2 = await c.env.LAB_KV.get(KV_KEYS.job(id));
  if (!raw2) {
    return c.json({ error: "not_found", message: "Job \u043D\u0435 \u043D\u0430\u0439\u0434\u0435\u043D \u0438\u043B\u0438 \u0438\u0441\u0442\u0451\u043A" }, 404);
  }
  let job;
  try {
    job = JSON.parse(raw2);
  } catch {
    return c.json({ error: "corrupt_job", message: "Job \u043F\u043E\u0432\u0440\u0435\u0436\u0434\u0451\u043D" }, 500);
  }
  if (job.userId !== user.userId) {
    return c.json({ error: "not_found", message: "Job \u043D\u0435 \u043D\u0430\u0439\u0434\u0435\u043D" }, 404);
  }
  return c.json({ ok: true, job: publicJobView(job, c.env) });
});
app3.get("/generate/jobs", async (c) => {
  const user = c.get("user");
  const list = await c.env.LAB_KV.list({ prefix: `job:user:${user.userId}:` });
  const jobs = [];
  for (const k of list.keys.slice(0, 50)) {
    const raw2 = await c.env.LAB_KV.get(k.name);
    if (!raw2) continue;
    try {
      jobs.push(JSON.parse(raw2));
    } catch {
    }
  }
  jobs.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  return c.json({
    ok: true,
    jobs: jobs.map((j) => publicJobView(j, c.env)),
    quota: {
      // Подтянем актуальные цифры
      ...await (async () => {
        const { getGenerationCounts: getGenerationCounts2 } = await Promise.resolve().then(() => (init_kv(), kv_exports));
        const counts = await getGenerationCounts2(c.env.LAB_KV, user.userId);
        return { usedThisMonth: counts.month, limitThisMonth: user.generationsLimit };
      })()
    }
  });
});
var generate_default = app3;

// worker/src/routes/internal.ts
init_kv();
init_books();
var app4 = new Hono2({ strict: false });
var requirePythonAuth = async (c, next) => {
  const auth = c.req.header("Authorization");
  const expected = c.env.PYTHON_SERVICE_TOKEN;
  if (!expected) {
    return c.json({ error: "server_misconfigured", message: "PYTHON_SERVICE_TOKEN \u043D\u0435 \u0437\u0430\u0434\u0430\u043D" }, 500);
  }
  if (auth !== `Bearer ${expected}`) {
    return c.json({ error: "unauthorized", message: "Bad token" }, 401);
  }
  await next();
};
app4.use("/internal/*", requirePythonAuth);
async function loadJob(env, jobId) {
  const raw2 = await env.LAB_KV.get(KV_KEYS.job(jobId));
  if (!raw2) return null;
  try {
    return JSON.parse(raw2);
  } catch {
    return null;
  }
}
async function saveJob(env, job) {
  job.updatedAt = (/* @__PURE__ */ new Date()).toISOString();
  await env.LAB_KV.put(KV_KEYS.job(job.jobId), JSON.stringify(job), {
    expirationTtl: 6 * 60 * 60
  });
}
async function markIndex(env, userId, jobId) {
  await env.LAB_KV.put(KV_KEYS.jobUser(userId, jobId), jobId, {
    expirationTtl: 30 * 24 * 60 * 60
  });
}
app4.get("/internal/jobs/pending", async (c) => {
  const limit = Math.min(20, Math.max(1, parseInt(c.req.query("limit") ?? "5", 10)));
  const list = await c.env.LAB_KV.list({ prefix: "job:" });
  const pending = [];
  for (const k of list.keys) {
    if (k.name.startsWith("job:user:")) continue;
    const raw2 = await c.env.LAB_KV.get(k.name);
    if (!raw2) continue;
    let job;
    try {
      job = JSON.parse(raw2);
    } catch {
      continue;
    }
    if (job.status !== "pending") continue;
    job.status = "running";
    job.startedAt = job.startedAt ?? (/* @__PURE__ */ new Date()).toISOString();
    job.stage = "starting";
    job.message = "\u041F\u0440\u0438\u043D\u044F\u043B\u0438 \u0432 \u0440\u0430\u0431\u043E\u0442\u0443";
    await saveJob(c.env, job);
    pending.push(job);
    if (pending.length >= limit) break;
  }
  return c.json({
    ok: true,
    jobs: pending.map((j) => ({
      jobId: j.jobId,
      userId: j.userId,
      bookQuery: j.bookUrl,
      queryType: "url"
    }))
  });
});
app4.post("/internal/jobs/:id/progress", async (c) => {
  const id = c.req.param("id");
  let body;
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: "bad_request", message: "\u041D\u0443\u0436\u0435\u043D JSON" }, 400);
  }
  const job = await loadJob(c.env, id);
  if (!job) {
    return c.json({ ok: true, expired: true });
  }
  const stage = body.stage ?? "starting";
  const progress = Math.max(0, Math.min(100, Math.floor(body.progress ?? 0)));
  job.stage = stage;
  job.progress = progress;
  if (typeof body.message === "string") job.message = body.message;
  if (stage === "error") {
    job.status = "error";
    job.error = body.message ?? "Unknown error";
    job.finishedAt = (/* @__PURE__ */ new Date()).toISOString();
  }
  await saveJob(c.env, job);
  return c.json({ ok: true });
});
app4.post("/internal/jobs/:id/done", async (c) => {
  const id = c.req.param("id");
  const job = await loadJob(c.env, id);
  if (!job) {
    return c.json({ error: "not_found", message: "Job \u043D\u0435 \u043D\u0430\u0439\u0434\u0435\u043D \u0438\u043B\u0438 \u0438\u0441\u0442\u0451\u043A" }, 404);
  }
  let form;
  try {
    form = await c.req.formData();
  } catch {
    return c.json({ error: "bad_request", message: "\u041E\u0436\u0438\u0434\u0430\u0435\u043C multipart/form-data" }, 400);
  }
  const resultRaw = form.get("result");
  if (typeof resultRaw !== "string") {
    return c.json({ error: "bad_request", message: "\u041D\u0435\u0442 \u043F\u043E\u043B\u044F result" }, 400);
  }
  let result;
  try {
    result = JSON.parse(resultRaw);
  } catch {
    return c.json({ error: "bad_request", message: "result \u2014 \u043D\u0435\u0432\u0430\u043B\u0438\u0434\u043D\u044B\u0439 JSON" }, 400);
  }
  const slug = (result.slug ?? "").trim();
  const title = (result.title ?? "").trim();
  const author = (result.author ?? "").trim();
  if (!slug || !title || !author) {
    return c.json({ error: "bad_request", message: "slug/title/author \u043E\u0431\u044F\u0437\u0430\u0442\u0435\u043B\u044C\u043D\u044B" }, 400);
  }
  const files = [];
  for (const [fieldName, value] of form.entries()) {
    if (!fieldName.startsWith("files[")) continue;
    if (typeof value === "string") continue;
    const fileValue = value;
    const kind = fieldName.match(/^files\[(\w+)\]$/)?.[1] ?? "other";
    const filename = fileValue.name || `${kind}.bin`;
    const body = await fileValue.arrayBuffer();
    files.push({ kind, name: filename, body });
  }
  if (files.length === 0) {
    return c.json({ error: "bad_request", message: "\u041D\u0435\u0442 \u0444\u0430\u0439\u043B\u043E\u0432 \u0432 files[]" }, 400);
  }
  try {
    const book = await uploadBook(c.env, {
      slug,
      title,
      author,
      year: result.year ?? null,
      description: result.description ?? "",
      files: files.map((f) => ({ kind: f.kind, name: f.name, body: f.body })),
      generatedBy: job.userId,
      generatedByJob: job.jobId
    });
    job.status = "done";
    job.stage = "done";
    job.progress = 100;
    job.message = `\u0413\u043E\u0442\u043E\u0432\u043E: ${title}`;
    job.slug = slug;
    job.result = {
      slug,
      title,
      author,
      year: result.year ?? null,
      description: result.description ?? ""
    };
    job.finishedAt = (/* @__PURE__ */ new Date()).toISOString();
    await saveJob(c.env, job);
    await markIndex(c.env, job.userId, job.jobId);
    return c.json({
      ok: true,
      slug,
      bookUrl: `${c.env.FRONTEND_ORIGIN}/library/${slug}/`,
      files: book.files
    });
  } catch (e) {
    console.error("[internal/done] upload failed", e);
    job.status = "error";
    job.stage = "error";
    job.error = e instanceof Error ? e.message : String(e);
    job.finishedAt = (/* @__PURE__ */ new Date()).toISOString();
    await saveJob(c.env, job);
    return c.json({ error: "upload_failed", message: job.error }, 500);
  }
});
var internal_default = app4;
var publicBooksRouter = new Hono2();
publicBooksRouter.get("/books/:slug/:filename", async (c) => {
  const slug = c.req.param("slug");
  const filename = c.req.param("filename");
  const blob = await getBookFile(c.env, slug, filename);
  if (!blob) {
    return c.json({ error: "not_found", message: "\u0424\u0430\u0439\u043B \u043D\u0435 \u043D\u0430\u0439\u0434\u0435\u043D" }, 404);
  }
  const bytes = fileBlobToBytes(blob);
  const headers = new Headers();
  headers.set("Content-Type", blob.contentType);
  headers.set("Content-Length", String(bytes.byteLength));
  headers.set("Cache-Control", "public, max-age=3600");
  return new Response(bytes, { headers });
});
publicBooksRouter.get("/books/:slug", async (c) => {
  const slug = c.req.param("slug");
  const { getBook: getBook2 } = await Promise.resolve().then(() => (init_books(), books_exports));
  const book = await getBook2(c.env, slug);
  if (!book) return c.json({ error: "not_found", message: "\u041A\u043D\u0438\u0433\u0430 \u043D\u0435 \u043D\u0430\u0439\u0434\u0435\u043D\u0430" }, 404);
  return c.json({ ok: true, book });
});

// worker/src/routes/social.ts
init_kv();

// worker/src/lib/publish_state.ts
init_kv();
var TTL_SECONDS = 30 * 24 * 60 * 60;
function key(kind, slug, dryRun) {
  return dryRun ? KV_KEYS.publishDryRun(kind, slug) : KV_KEYS.publish(kind, slug);
}
async function getPublish(kv, kind, slug, dryRun = false) {
  const raw2 = await kv.get(key(kind, slug, dryRun));
  if (!raw2) return null;
  try {
    return JSON.parse(raw2);
  } catch {
    return null;
  }
}
async function savePublish(kv, record) {
  record.updatedAt = (/* @__PURE__ */ new Date()).toISOString();
  await kv.put(key(record.kind, record.slug, record.dryRun), JSON.stringify(record), {
    expirationTtl: TTL_SECONDS
  });
}
async function createPublish(kv, args) {
  const now = (/* @__PURE__ */ new Date()).toISOString();
  const rec = {
    kind: args.kind,
    slug: args.slug,
    state: "NEW",
    createdAt: now,
    updatedAt: now,
    initiatedBy: args.initiatedBy,
    dryRun: args.dryRun ?? false
  };
  await savePublish(kv, rec);
  return rec;
}
async function listPublishes(kv, opts = {}) {
  const prefix = opts.dryRun ? "publish:dry-run:" : "publish:";
  const limit = Math.min(200, opts.limit ?? 100);
  const out = [];
  const list = await kv.list({ prefix, limit });
  for (const k of list.keys) {
    const raw2 = await kv.get(k.name);
    if (!raw2) continue;
    try {
      const rec = JSON.parse(raw2);
      if (opts.kind && rec.kind !== opts.kind) continue;
      if (opts.state && rec.state !== opts.state) continue;
      out.push(rec);
      if (out.length >= limit) break;
    } catch {
    }
  }
  return out;
}
var TRANSITIONS = {
  NEW: ["COPIES_GENERATED", "FAILED"],
  COPIES_GENERATED: ["VK_POSTED", "FAILED"],
  VK_POSTED: ["TG_POSTED", "FAILED"],
  TG_POSTED: ["NOTIFIED", "FAILED"],
  NOTIFIED: ["PUBLISHED", "FAILED"],
  PUBLISHED: ["FAILED"],
  // можно "откатить" вручную
  FAILED: ["NEW"]
  // можно перезапустить
};
function canTransition(from, to) {
  if (from === to) return true;
  return TRANSITIONS[from]?.includes(to) ?? false;
}
async function transitionPublish(kv, kind, slug, to, patch = {}, dryRun = false) {
  const rec = await getPublish(kv, kind, slug, dryRun);
  if (!rec) {
    throw new Error(`Publish record ${kind}:${slug} \u043D\u0435 \u043D\u0430\u0439\u0434\u0435\u043D`);
  }
  if (!canTransition(rec.state, to)) {
    throw new Error(`\u041D\u0435\u0434\u043E\u043F\u0443\u0441\u0442\u0438\u043C\u044B\u0439 \u043F\u0435\u0440\u0435\u0445\u043E\u0434 ${rec.state} \u2192 ${to} \u0434\u043B\u044F ${kind}:${slug}`);
  }
  Object.assign(rec, patch);
  rec.state = to;
  await savePublish(kv, rec);
  return rec;
}

// worker/src/lib/social_vk.ts
var VK_API_VERSION = "5.199";
var VK_TEXT_LIMIT = 16384;
var VKAdapter = class {
  constructor(env) {
    this.env = env;
  }
  /** В dev-режиме, если нет токенов — не публикуем, а возвращаем mock-результат. */
  isDevMode() {
    return !this.env.VK_GROUP_TOKEN || !this.env.VK_GROUP_ID;
  }
  /**
   * Публикует пост на стене группы.
   * @throws если превышен лимит символов, либо API вернул ошибку.
   */
  async publishPost(params) {
    if (params.message.length > VK_TEXT_LIMIT) {
      throw new Error(
        `VK message too long: ${params.message.length} > ${VK_TEXT_LIMIT}`
      );
    }
    if (this.isDevMode()) {
      const mockId = Math.floor(Math.random() * 1e6);
      console.log("[vk:dev] would publish:", {
        length: params.message.length,
        fromGroup: params.fromGroup ?? true,
        link: params.link,
        preview: params.message.slice(0, 200) + (params.message.length > 200 ? "\u2026" : "")
      });
      return {
        post_id: mockId,
        owner_id: -237295798,
        url: `https://vk.com/club237295798?w=wall-{dev}${mockId}`,
        raw: { dev: true, mock: true }
      };
    }
    const groupId = this.env.VK_GROUP_ID;
    const fromGroup = params.fromGroup ?? true;
    const ownerId = `-${groupId}`;
    const body = new URLSearchParams();
    body.set("owner_id", ownerId);
    body.set("from_group", fromGroup ? "1" : "0");
    body.set("message", params.message);
    body.set("signed", "0");
    body.set("v", VK_API_VERSION);
    if (params.link) {
      body.set("attachments", params.link.url);
    }
    const res = await fetch("https://api.vk.com/method/wall.post", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${this.env.VK_GROUP_TOKEN}`,
        "Content-Type": "application/x-www-form-urlencoded"
      },
      body: body.toString()
    });
    const data = await res.json();
    if ("error" in data) {
      console.error("[vk:error]", data.error);
      throw new Error(`VK API error: ${data.error.error_msg} (code ${data.error.error_code})`);
    }
    const owner = data.response.owner_id;
    const postId = data.response.post_id;
    const url = owner > 0 ? `https://vk.com/id${owner}?w=wall${owner}_${postId}` : `https://vk.com/club${Math.abs(owner)}?w=wall${owner}_${postId}`;
    return {
      post_id: postId,
      owner_id: owner,
      url,
      raw: data
    };
  }
  /** Редактирование уже опубликованного поста. */
  async editPost(postId, message, ownerId) {
    if (this.isDevMode()) {
      console.log("[vk:dev] would edit post", postId, "len=", message.length);
      return true;
    }
    const body = new URLSearchParams();
    body.set("owner_id", String(ownerId));
    body.set("post_id", String(postId));
    body.set("message", message);
    body.set("v", VK_API_VERSION);
    const res = await fetch("https://api.vk.com/method/wall.edit", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${this.env.VK_GROUP_TOKEN}`,
        "Content-Type": "application/x-www-form-urlencoded"
      },
      body: body.toString()
    });
    const data = await res.json();
    if (data.error) {
      console.error("[vk:edit-error]", data.error);
      return false;
    }
    return data.response === 1;
  }
  /** Удаление поста. */
  async deletePost(postId, ownerId) {
    if (this.isDevMode()) {
      console.log("[vk:dev] would delete post", postId);
      return true;
    }
    const body = new URLSearchParams();
    body.set("owner_id", String(ownerId));
    body.set("post_id", String(postId));
    body.set("v", VK_API_VERSION);
    const res = await fetch("https://api.vk.com/method/wall.delete", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${this.env.VK_GROUP_TOKEN}`,
        "Content-Type": "application/x-www-form-urlencoded"
      },
      body: body.toString()
    });
    const data = await res.json();
    if (data.error) {
      console.error("[vk:delete-error]", data.error);
      return false;
    }
    return data.response === 1;
  }
};

// worker/src/lib/social_tg.ts
var TG_API = "https://api.telegram.org/bot";
var TelegramAdapter = class {
  constructor(env) {
    this.env = env;
  }
  isDevMode() {
    return !this.env.TELEGRAM_BOT_TOKEN;
  }
  apiUrl(method) {
    return `${TG_API}${this.env.TELEGRAM_BOT_TOKEN}/${method}`;
  }
  buildReplyMarkup(buttons) {
    if (!buttons || buttons.length === 0) return void 0;
    return JSON.stringify({ inline_keyboard: buttons });
  }
  /** Отправка в произвольный чат. */
  async sendToChat(chatId, params) {
    if (this.isDevMode()) {
      const mockId = Math.floor(Math.random() * 1e6);
      console.log("[tg:dev] would send to", chatId, {
        length: params.text.length,
        buttons: params.buttons?.length ?? 0,
        preview: params.text.slice(0, 200) + (params.text.length > 200 ? "\u2026" : "")
      });
      return {
        message_id: mockId,
        chat: { id: chatId, type: typeof chatId === "string" ? "channel" : "private" },
        url: typeof chatId === "string" ? `https://t.me/${String(chatId).replace("@", "")}/${mockId}` : `https://t.me/c/${mockId}`,
        raw: { dev: true, mock: true }
      };
    }
    const body = new URLSearchParams();
    body.set("chat_id", String(chatId));
    body.set("text", params.text);
    body.set("parse_mode", params.parseMode ?? "HTML");
    body.set("disable_web_page_preview", params.linkPreview === false ? "true" : "false");
    const replyMarkup = this.buildReplyMarkup(params.buttons);
    if (replyMarkup) body.set("reply_markup", replyMarkup);
    const res = await fetch(this.apiUrl("sendMessage"), {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body.toString()
    });
    const data = await res.json();
    if (!data.ok) {
      console.error("[tg:send-error]", data);
      throw new Error(`Telegram API error: ${data.description}`);
    }
    return data.result;
  }
  /** Удобный алиас — личное сообщение админу. */
  async sendToAdmin(text, buttons) {
    if (!this.env.TELEGRAM_ADMIN_ID) {
      console.log("[tg:dev] TELEGRAM_ADMIN_ID \u043D\u0435 \u0437\u0430\u0434\u0430\u043D, \u0432\u044B\u0432\u043E\u0434 \u0432 \u043A\u043E\u043D\u0441\u043E\u043B\u044C:", text.slice(0, 200));
      return {
        message_id: 0,
        chat: { id: 0, type: "private" },
        raw: { dev: true, noAdminId: true }
      };
    }
    return this.sendToChat(this.env.TELEGRAM_ADMIN_ID, { text, buttons });
  }
  /** Алиас — в канал. */
  async sendToChannel(text, buttons) {
    if (!this.env.TELEGRAM_CHANNEL_ID) {
      console.log("[tg:dev] TELEGRAM_CHANNEL_ID \u043D\u0435 \u0437\u0430\u0434\u0430\u043D, \u0432\u044B\u0432\u043E\u0434 \u0432 \u043A\u043E\u043D\u0441\u043E\u043B\u044C:", text.slice(0, 200));
      return {
        message_id: 0,
        chat: { id: 0, type: "channel" },
        raw: { dev: true, noChannelId: true }
      };
    }
    return this.sendToChat(this.env.TELEGRAM_CHANNEL_ID, { text, buttons });
  }
  /** Редактирование сообщения. */
  async editMessage(chatId, messageId, params) {
    if (this.isDevMode()) {
      console.log("[tg:dev] would edit", chatId, messageId);
      return true;
    }
    const body = new URLSearchParams();
    body.set("chat_id", String(chatId));
    body.set("message_id", String(messageId));
    body.set("text", params.text);
    body.set("parse_mode", params.parseMode ?? "HTML");
    const replyMarkup = this.buildReplyMarkup(params.buttons);
    if (replyMarkup) body.set("reply_markup", replyMarkup);
    const res = await fetch(this.apiUrl("editMessageText"), {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body.toString()
    });
    const data = await res.json();
    if (!data.ok) {
      console.error("[tg:edit-error]", data.description);
      return false;
    }
    return true;
  }
  /** Удаление сообщения. */
  async deleteMessage(chatId, messageId) {
    if (this.isDevMode()) {
      console.log("[tg:dev] would delete", chatId, messageId);
      return true;
    }
    const body = new URLSearchParams();
    body.set("chat_id", String(chatId));
    body.set("message_id", String(messageId));
    const res = await fetch(this.apiUrl("deleteMessage"), {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body.toString()
    });
    const data = await res.json();
    if (!data.ok) {
      console.error("[tg:delete-error]", data.description);
      return false;
    }
    return true;
  }
  /**
   * Ответ на callback (нажатие inline-кнопки).
   * Telegram требует ответить в течение 30 сек, иначе таймаут.
   */
  async answerCallback(callbackQueryId, text, showAlert = false) {
    if (this.isDevMode()) {
      console.log("[tg:dev] would answer callback", callbackQueryId, text);
      return true;
    }
    const body = new URLSearchParams();
    body.set("callback_query_id", callbackQueryId);
    if (text) body.set("text", text);
    body.set("show_alert", showAlert ? "true" : "false");
    const res = await fetch(this.apiUrl("answerCallbackQuery"), {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body.toString()
    });
    const data = await res.json();
    return data.ok;
  }
};

// worker/src/routes/social.ts
var app5 = new Hono2({ strict: false });
var requirePublisherAuth = async (c, next) => {
  const auth = c.req.header("Authorization");
  if (auth && c.env.PYTHON_SERVICE_TOKEN && auth === `Bearer ${c.env.PYTHON_SERVICE_TOKEN}`) {
    await next();
    return;
  }
  const adminEmail = c.req.query("admin") ?? c.req.header("X-Admin-Email");
  if (adminEmail && c.env.LAB_KV) {
    const user = await getAuthUser(c.env.LAB_KV, adminEmail);
    if (user && user.subscriptionStatus === "active") {
      await next();
      return;
    }
  }
  return c.json({ error: "unauthorized", message: "\u041D\u0443\u0436\u0435\u043D PYTHON_SERVICE_TOKEN \u0438\u043B\u0438 admin email" }, 401);
};
app5.use("/internal/*", requirePublisherAuth);
async function callCopywriter(env, bookSlug, fallbackOnly = false) {
  if (!env.PYTHON_SERVICE_URL) {
    return {
      ok: false,
      book_slug: bookSlug,
      error: "PYTHON_SERVICE_URL \u043D\u0435 \u0437\u0430\u0434\u0430\u043D"
    };
  }
  const url = `${env.PYTHON_SERVICE_URL.replace(/\/$/, "")}/internal/copywrite`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${env.PYTHON_SERVICE_TOKEN ?? ""}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ bookSlug, fallbackOnly })
  });
  if (!res.ok) {
    return { ok: false, book_slug: bookSlug, error: `python-service ${res.status}: ${await res.text()}` };
  }
  return res.json();
}
app5.post("/internal/publish", async (c) => {
  let body;
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: "bad_request", message: "\u041D\u0443\u0436\u0435\u043D JSON" }, 400);
  }
  const kind = (body.kind ?? "").trim();
  const slug = (body.slug ?? "").trim();
  const dryRun = body.dryRun ?? false;
  const force = body.force ?? false;
  if (!["book", "expert"].includes(kind) || !slug) {
    return c.json({ error: "bad_request", message: "kind \u2208 {book,expert} \u0438 slug \u043E\u0431\u044F\u0437\u0430\u0442\u0435\u043B\u044C\u043D\u044B" }, 400);
  }
  const existing = await getPublish(c.env.LAB_KV, kind, slug, dryRun);
  if (existing && existing.state === "PUBLISHED" && !force) {
    return c.json({
      ok: true,
      skipped: true,
      message: "\u0423\u0436\u0435 \u043E\u043F\u0443\u0431\u043B\u0438\u043A\u043E\u0432\u0430\u043D\u043E. \u0418\u0441\u043F\u043E\u043B\u044C\u0437\u0443\u0439\u0442\u0435 ?force=true \u0434\u043B\u044F \u043F\u043E\u0432\u0442\u043E\u0440\u0430.",
      record: existing
    });
  }
  if (existing && existing.state === "FAILED" && !force) {
    return c.json({
      ok: false,
      message: "\u041F\u0440\u0435\u0434\u044B\u0434\u0443\u0449\u0430\u044F \u043F\u043E\u043F\u044B\u0442\u043A\u0430 \u0443\u043F\u0430\u043B\u0430. \u0418\u0441\u043F\u043E\u043B\u044C\u0437\u0443\u0439\u0442\u0435 ?force=true \u0434\u043B\u044F \u043F\u043E\u0432\u0442\u043E\u0440\u0430.",
      record: existing
    }, 409);
  }
  let record = existing ?? await createPublish(c.env.LAB_KV, {
    kind,
    slug,
    dryRun,
    initiatedBy: body.initiatedBy
  });
  if (force && existing) {
    record.state = "NEW";
    record.error = void 0;
    record.vk = void 0;
    record.tg = void 0;
    await savePublish(c.env.LAB_KV, record);
  }
  const steps = [];
  try {
    if (record.state === "NEW") {
      const copies = await callCopywriter(c.env, slug, dryRun);
      if (!copies.ok || !copies.vk || !copies.tg) {
        await transitionPublish(c.env.LAB_KV, kind, slug, "FAILED", {
          error: copies.error ?? "\u041A\u043E\u043F\u0438\u0440\u0430\u0439\u0442\u0435\u0440 \u043D\u0435 \u0432\u0435\u0440\u043D\u0443\u043B vk/tg"
        }, dryRun);
        return c.json({ ok: false, error: "copywriter_failed", message: copies.error }, 500);
      }
      record.copies = {
        vk: copies.vk,
        tg: copies.tg,
        meta_description: copies.meta_description,
        source: copies.source
      };
      record = await transitionPublish(c.env.LAB_KV, kind, slug, "COPIES_GENERATED", record, dryRun);
      steps.push("COPIES_GENERATED");
    }
    if (record.state === "COPIES_GENERATED" && record.copies?.vk) {
      const vk = new VKAdapter(c.env);
      const linkUrl = c.env.FRONTEND_ORIGIN + (kind === "book" ? `/library/${slug}/` : `/experts/${slug}/`);
      const result = await vk.publishPost({
        message: record.copies.vk,
        link: { url: linkUrl }
      });
      const vkRec = {
        post_id: result.post_id,
        owner_id: result.owner_id,
        url: result.url,
        posted_at: (/* @__PURE__ */ new Date()).toISOString(),
        status: "pending_moderation"
      };
      record.vk = vkRec;
      record = await transitionPublish(c.env.LAB_KV, kind, slug, "VK_POSTED", record, dryRun);
      if (!dryRun) {
        await c.env.LAB_KV.put(KV_KEYS.socialVk(slug), JSON.stringify(vkRec), {
          expirationTtl: 30 * 24 * 60 * 60
        });
      }
      steps.push("VK_POSTED");
    }
    if (record.state === "VK_POSTED" && record.copies?.tg) {
      const tg = new TelegramAdapter(c.env);
      const linkUrl = c.env.FRONTEND_ORIGIN + (kind === "book" ? `/library/${slug}/` : `/experts/${slug}/`);
      const result = await tg.sendToChannel(record.copies.tg);
      const tgRec = {
        message_id: result.message_id,
        chat_id: result.chat.id,
        url: result.url,
        posted_at: (/* @__PURE__ */ new Date()).toISOString()
      };
      record.tg = tgRec;
      record = await transitionPublish(c.env.LAB_KV, kind, slug, "TG_POSTED", record, dryRun);
      if (!dryRun) {
        await c.env.LAB_KV.put(KV_KEYS.socialTg(slug), JSON.stringify(tgRec), {
          expirationTtl: 30 * 24 * 60 * 60
        });
      }
      steps.push("TG_POSTED");
    }
    if (record.state === "TG_POSTED") {
      const tg = new TelegramAdapter(c.env);
      const lines = [];
      lines.push("\u2705 <b>\u041E\u043F\u0443\u0431\u043B\u0438\u043A\u043E\u0432\u0430\u043D\u043E</b>");
      lines.push("");
      lines.push(`<b>${kind === "book" ? "\u{1F4DA}" : "\u{1F464}"} ${slug}</b>`);
      if (record.copies?.meta_description) {
        lines.push(`<i>${escapeHtml(record.copies.meta_description)}</i>`);
      }
      lines.push("");
      if (record.vk?.url) lines.push(`VK: <a href="${record.vk.url}">${record.vk.url}</a>`);
      if (record.tg?.url) lines.push(`TG: <a href="${record.tg.url}">${record.tg.url}</a>`);
      const buttons = [
        [
          { text: "\u{1F5D1} \u0423\u0434\u0430\u043B\u0438\u0442\u044C VK", callback_data: `del_vk:${kind}:${slug}` },
          { text: "\u{1F5D1} \u0423\u0434\u0430\u043B\u0438\u0442\u044C TG", callback_data: `del_tg:${kind}:${slug}` }
        ],
        [
          { text: "\u2705 \u041F\u043E\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u044C", callback_data: `confirm:${kind}:${slug}` }
        ]
      ];
      await tg.sendToAdmin(lines.join("\n"), buttons);
      record = await transitionPublish(c.env.LAB_KV, kind, slug, "NOTIFIED", record, dryRun);
      steps.push("NOTIFIED");
    }
    if (dryRun && record.state === "NOTIFIED") {
      record = await transitionPublish(c.env.LAB_KV, kind, slug, "PUBLISHED", record, dryRun);
      steps.push("PUBLISHED (dry-run)");
    }
    return c.json({
      ok: true,
      dryRun,
      steps,
      record: await getPublish(c.env.LAB_KV, kind, slug, dryRun)
    });
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    console.error("[publish:error]", kind, slug, message);
    try {
      await transitionPublish(c.env.LAB_KV, kind, slug, "FAILED", { error: message }, dryRun);
    } catch {
    }
    return c.json({ ok: false, error: "publish_failed", message }, 500);
  }
});
app5.post("/internal/publish/confirm", async (c) => {
  let body;
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: "bad_request", message: "\u041D\u0443\u0436\u0435\u043D JSON" }, 400);
  }
  const { kind, slug, action } = body;
  if (!kind || !slug || !action) {
    return c.json({ error: "bad_request", message: "kind/slug/action \u043E\u0431\u044F\u0437\u0430\u0442\u0435\u043B\u044C\u043D\u044B" }, 400);
  }
  const record = await getPublish(c.env.LAB_KV, kind, slug, false);
  if (!record) {
    return c.json({ error: "not_found", message: "\u0417\u0430\u043F\u0438\u0441\u044C \u043D\u0435 \u043D\u0430\u0439\u0434\u0435\u043D\u0430" }, 404);
  }
  if (record.dryRun) {
    return c.json({ error: "conflict", message: "\u041D\u0435\u043B\u044C\u0437\u044F \u043F\u043E\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u044C dry-run \u0437\u0430\u043F\u0438\u0441\u044C" }, 409);
  }
  const results = [];
  try {
    if (action === "del_vk" && record.vk && record.vk.post_id && record.vk.owner_id) {
      const vk = new VKAdapter(c.env);
      const ok = await vk.deletePost(record.vk.post_id, record.vk.owner_id);
      results.push(`VK delete: ${ok ? "ok" : "failed"}`);
      if (ok) {
        record.vk = void 0;
        await c.env.LAB_KV.delete(KV_KEYS.socialVk(slug));
      }
    }
    if (action === "del_tg" && record.tg) {
      const tg = new TelegramAdapter(c.env);
      const ok = await tg.deleteMessage(record.tg.chat_id, record.tg.message_id);
      results.push(`TG delete: ${ok ? "ok" : "failed"}`);
      if (ok) {
        record.tg = void 0;
        await c.env.LAB_KV.delete(KV_KEYS.socialTg(slug));
      }
    }
    if (action === "confirm") {
      await transitionPublish(c.env.LAB_KV, kind, slug, "PUBLISHED", record);
      results.push("\u2192 PUBLISHED");
      return c.json({ ok: true, results, record: await getPublish(c.env.LAB_KV, kind, slug, false) });
    }
    if (!record.vk && !record.tg) {
      await transitionPublish(c.env.LAB_KV, kind, slug, "FAILED", { error: "\u0423\u0434\u0430\u043B\u0435\u043D\u043E \u0432\u0440\u0443\u0447\u043D\u0443\u044E" });
      results.push("\u2192 FAILED (\u0432\u0441\u0451 \u0443\u0434\u0430\u043B\u0435\u043D\u043E)");
    } else {
      await savePublish(c.env.LAB_KV, record);
    }
    return c.json({ ok: true, results, record: await getPublish(c.env.LAB_KV, kind, slug, false) });
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    return c.json({ ok: false, error: "confirm_failed", message }, 500);
  }
});
app5.get("/internal/publish/status", async (c) => {
  const kind = c.req.query("kind");
  const slug = c.req.query("slug");
  const dryRun = c.req.query("dryRun") === "true";
  if (!kind || !slug) {
    return c.json({ error: "bad_request", message: "kind+slug \u043E\u0431\u044F\u0437\u0430\u0442\u0435\u043B\u044C\u043D\u044B" }, 400);
  }
  const rec = await getPublish(c.env.LAB_KV, kind, slug, dryRun);
  return c.json({ ok: true, record: rec });
});
app5.get("/internal/publish/list", async (c) => {
  const kind = c.req.query("kind");
  const state = c.req.query("state");
  const dryRun = c.req.query("dryRun") === "true";
  const limit = Math.min(200, parseInt(c.req.query("limit") ?? "50", 10));
  const records = await listPublishes(c.env.LAB_KV, { kind, state, dryRun, limit });
  return c.json({ ok: true, total: records.length, records });
});
function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
var social_default = app5;

// worker/src/routes/notifications.ts
init_kv();
var app6 = new Hono2({ strict: false });
var requireInternalAuth = async (c, next) => {
  const auth = c.req.header("Authorization");
  if (auth && c.env.PYTHON_SERVICE_TOKEN && auth === `Bearer ${c.env.PYTHON_SERVICE_TOKEN}`) {
    await next();
    return;
  }
  const secret = c.req.header("X-Telegram-Bot-Api-Secret-Token");
  if (secret && secret === c.env.TELEGRAM_BOT_TOKEN?.slice(-16)) {
    await next();
    return;
  }
  return c.json({ error: "unauthorized" }, 401);
};
app6.use("/internal/*", requireInternalAuth);
app6.post("/internal/tg/callback", async (c) => {
  let update;
  try {
    update = await c.req.json();
  } catch {
    return c.json({ ok: false, error: "bad_request" }, 400);
  }
  const cb = update.callback_query;
  if (!cb || !cb.data) {
    return c.json({ ok: true, skipped: true });
  }
  const tg = new TelegramAdapter(c.env);
  const parts = cb.data.split(":");
  if (parts.length < 3) {
    await tg.answerCallback(cb.id, "\u041D\u0435\u0438\u0437\u0432\u0435\u0441\u0442\u043D\u0430\u044F \u043A\u043E\u043C\u0430\u043D\u0434\u0430", true);
    return c.json({ ok: true });
  }
  const [action, kindRaw, ...rest] = parts;
  const kind = kindRaw;
  const slug = rest.join(":");
  const record = await getPublish(c.env.LAB_KV, kind, slug, false);
  if (!record) {
    await tg.answerCallback(cb.id, `\u0417\u0430\u043F\u0438\u0441\u044C ${kind}:${slug} \u043D\u0435 \u043D\u0430\u0439\u0434\u0435\u043D\u0430`, true);
    return c.json({ ok: true });
  }
  try {
    if (action === "del_vk" && record.vk && record.vk.post_id && record.vk.owner_id) {
      const vk = new VKAdapter(c.env);
      const ok = await vk.deletePost(record.vk.post_id, record.vk.owner_id);
      if (ok) {
        record.vk = void 0;
        await c.env.LAB_KV.delete(KV_KEYS.socialVk(slug));
        await tg.answerCallback(cb.id, "VK \u043F\u043E\u0441\u0442 \u0443\u0434\u0430\u043B\u0451\u043D");
      } else {
        await tg.answerCallback(cb.id, "\u041D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u0443\u0434\u0430\u043B\u0438\u0442\u044C VK", true);
      }
    } else if (action === "del_tg" && record.tg) {
      const ok = await tg.deleteMessage(record.tg.chat_id, record.tg.message_id);
      if (ok) {
        record.tg = void 0;
        await c.env.LAB_KV.delete(KV_KEYS.socialTg(slug));
        await tg.answerCallback(cb.id, "TG \u0441\u043E\u043E\u0431\u0449\u0435\u043D\u0438\u0435 \u0443\u0434\u0430\u043B\u0435\u043D\u043E");
      } else {
        await tg.answerCallback(cb.id, "\u041D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u0443\u0434\u0430\u043B\u0438\u0442\u044C TG", true);
      }
    } else if (action === "confirm") {
      await transitionPublish(c.env.LAB_KV, kind, slug, "PUBLISHED", record);
      await tg.answerCallback(cb.id, "\u041F\u043E\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043D\u043E \u2705");
    } else {
      await tg.answerCallback(cb.id, "\u0414\u0435\u0439\u0441\u0442\u0432\u0438\u0435 \u043D\u0435 \u043F\u0440\u0438\u043C\u0435\u043D\u0438\u043C\u043E", true);
    }
    if (!record.vk && !record.tg) {
      await transitionPublish(c.env.LAB_KV, kind, slug, "FAILED", { error: "\u0423\u0434\u0430\u043B\u0435\u043D\u043E \u0432\u0440\u0443\u0447\u043D\u0443\u044E \u0447\u0435\u0440\u0435\u0437 TG callback" });
    } else {
      await savePublish(c.env.LAB_KV, record);
    }
    return c.json({ ok: true });
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    await tg.answerCallback(cb.id, `\u041E\u0448\u0438\u0431\u043A\u0430: ${message}`, true);
    return c.json({ ok: false, error: message }, 500);
  }
});
var notifications_default = app6;

// worker/src/index-assets.ts
var app7 = new Hono2();
var MIME = {
  html: "text/html; charset=utf-8",
  htm: "text/html; charset=utf-8",
  css: "text/css; charset=utf-8",
  js: "application/javascript; charset=utf-8",
  mjs: "application/javascript; charset=utf-8",
  json: "application/json; charset=utf-8",
  svg: "image/svg+xml",
  png: "image/png",
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  gif: "image/gif",
  webp: "image/webp",
  ico: "image/x-icon",
  woff: "font/woff",
  woff2: "font/woff2",
  ttf: "font/ttf",
  txt: "text/plain; charset=utf-8",
  xml: "application/xml; charset=utf-8",
  map: "application/json; charset=utf-8"
};
function mimeFor(path) {
  const m = path.toLowerCase().match(/\.([a-z0-9]+)$/);
  if (!m) return "application/octet-stream";
  return MIME[m[1]] ?? "application/octet-stream";
}
var API_PATHS = [
  "/health",
  "/api",
  "/auth/",
  "/tracker/",
  "/tracker",
  "/generate/",
  "/generate",
  "/internal/",
  "/internal",
  "/books/",
  "/social/",
  "/notifications/",
  "/checkout/",
  "/webhook/"
];
function isApiPath(path) {
  const p = path.replace(/\/+$/, "") || "/";
  for (const prefix of API_PATHS) {
    if (p === prefix.replace(/\/+$/, "") || p.startsWith(prefix)) return true;
  }
  return false;
}
app7.onError((err, c) => {
  console.error("[worker-error]", err.message, err.stack);
  return c.json({ error: "internal_error", message: "\u0427\u0442\u043E-\u0442\u043E \u043F\u043E\u0448\u043B\u043E \u043D\u0435 \u0442\u0430\u043A" }, 500);
});
app7.notFound((c) => c.json({ error: "not_found", message: "\u0420\u043E\u0443\u0442 \u043D\u0435 \u043D\u0430\u0439\u0434\u0435\u043D" }, 404));
app7.use("*", async (c, next) => {
  const path = c.req.path;
  if (c.req.method !== "GET" && c.req.method !== "HEAD") return next();
  if (isApiPath(path)) return next();
  if (!c.env.LAB_KV) return next();
  const pathname = path.replace(/\/+$/, "") || "/";
  const hasExt = /\.[a-z0-9]{1,5}$/i.test(path);
  const key2 = pathname === "/" ? "static:/index.html" : `static:${pathname}`;
  let kvValue = await c.env.LAB_KV.get(key2, { type: "arrayBuffer" });
  let servedKey = key2;
  if (!kvValue && !hasExt) {
    const indexPath = (pathname === "/" ? "/" : pathname + "/") + "index.html";
    const tryKey = `static:${indexPath}`;
    const v = await c.env.LAB_KV.get(tryKey, { type: "arrayBuffer" });
    if (v) {
      kvValue = v;
      servedKey = tryKey;
    }
  }
  if (!kvValue && !hasExt && pathname !== "/") {
    const rootKey = "static:/index.html";
    const v = await c.env.LAB_KV.get(rootKey, { type: "arrayBuffer" });
    if (v) {
      kvValue = v;
      servedKey = rootKey;
    }
  }
  if (kvValue) {
    return new Response(kvValue, {
      status: 200,
      headers: {
        "Content-Type": mimeFor(servedKey),
        "Cache-Control": "public, max-age=300"
      }
    });
  }
  return next();
});
app7.use("*", optionalAuth);
app7.use("*", async (c, next) => {
  if (c.req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: corsHeaders(c.env, c.req.raw) });
  }
  await next();
  return applyCors(c.res, c.env, c.req.raw);
});
app7.get("/health", (c) => {
  return c.json({
    status: "ok",
    environment: c.env.ENVIRONMENT,
    timestamp: (/* @__PURE__ */ new Date()).toISOString(),
    version: "0.5.0"
  });
});
app7.get("/api", (c) => {
  return c.json({
    name: "lab-site-api",
    docs: "https://app.pulab.online",
    version: "0.5.0",
    endpoints: [
      "GET  /health",
      "POST /auth/code",
      "POST /auth/verify",
      "GET  /auth/me",
      "POST /auth/logout",
      "GET    /tracker/wishes",
      "POST   /tracker/wishes",
      "PATCH  /tracker/wishes/:id",
      "DELETE /tracker/wishes/:id",
      "POST   /tracker/wishes/:id/toggle",
      "POST /generate/jobs",
      "GET  /generate/jobs",
      "GET  /generate/jobs/:id",
      "GET  /internal/jobs/pending",
      "POST /internal/jobs/:id/progress",
      "POST /internal/jobs/:id/done",
      "GET  /books/:slug",
      "GET  /books/:slug/:filename"
    ]
  });
});
app7.route("/", auth_default);
app7.route("/", tracker_default);
app7.route("/", generate_default);
app7.route("/", publicBooksRouter);
app7.route("/", internal_default);
app7.route("/", social_default);
app7.route("/", notifications_default);
app7.all("/checkout/*", (c) => c.json({ error: "not_implemented", message: "Checkout \u043F\u043E\u044F\u0432\u0438\u0442\u0441\u044F \u0432 \u0424\u0430\u0437\u0435 4" }, 501));
app7.all("/webhook/*", (c) => c.json({ error: "not_implemented", message: "Webhooks \u043F\u043E\u044F\u0432\u044F\u0442\u0441\u044F \u0432 \u0424\u0430\u0437\u0435 4" }, 501));
var index_assets_default = app7;
export {
  index_assets_default as default
};
