import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "",
  headers: { Accept: "application/json" },
  timeout: 15000,
});

export function listingQueryParams(options) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(options)) {
    for (const item of Array.isArray(value) ? value : [value]) {
      if (item !== "" && item !== undefined && item !== null) params.append(key, item);
    }
  }
  return params;
}

function listingParams(options = {}) {
  const {
    search = "",
    sortBy,
    sortDir,
    page = 1,
    pageSize = 20,
    ...filters
  } = options;
  const params = {
    ...filters,
    search: search || undefined,
    sort_by: sortBy,
    sort_dir: sortDir,
    page,
    page_size: pageSize,
  };
  return listingQueryParams(params);
}

export async function getAuctions(options = {}) {
  const response = await api.get("/api/auctions", { params: listingParams(options) });
  return response.data;
}

export async function getGlobalSearch(options = {}) {
  const response = await api.get("/api/search", { params: listingParams(options) });
  return response.data;
}

export async function getAuctionById(auctionId) {
  const response = await api.get("/api/auctions/" + auctionId);
  return response.data;
}

export async function getTenders(options = {}) {
  const response = await api.get("/api/tenders", { params: listingParams(options) });
  return response.data;
}

export async function getTenderById(tenderId) {
  const response = await api.get("/api/tenders/" + tenderId);
  return response.data;
}

export async function getApiHealth() {
  const response = await api.get("/api/health");
  return response.data;
}

export async function startCollection(
  kind,
  category = "movable",
  collectionGroup = "executive_agencies",
  categories = [],
) {
  if (kind === "tenders") {
    const response = await api.post("/api/collection/tenders/run");
    return response.data;
  }
  const response = await api.post(
    "/api/collection/auctions/" + category + "/run",
    null,
    { params: listingQueryParams({ collection_group: collectionGroup, categories }) },
  );
  return response.data;
}

export async function getCollectionStatus(
  kind,
  category = "movable",
  collectionGroup = "executive_agencies",
  categories = [],
) {
  if (kind === "tenders") {
    const response = await api.get("/api/collection/tenders/status");
    return response.data;
  }
  const response = await api.get(
    "/api/collection/auctions/" + category + "/status",
    { params: listingQueryParams({ collection_group: collectionGroup, categories }) },
  );
  return response.data;
}


export async function startGlobalCollection() {
  const response = await api.post("/api/collection/global/run");
  return response.data;
}

export async function getGlobalCollectionStatus() {
  const response = await api.get("/api/collection/global/status");
  return response.data;
}

export async function getKeywords() {
  const response = await api.get("/api/settings/keywords");
  return response.data;
}

export async function updateKeywords(keywords) {
  const response = await api.put("/api/settings/keywords", { keywords });
  return response.data;
}

export async function quickRequest(kind, action, startedAt) {
  const url = "/api/quick/" + kind + "/" + action;
  const response = action === "status" ? await api.get(url) :
    await api.post(url, null, { params: { started_at: startedAt } });
  return response.data;
}
