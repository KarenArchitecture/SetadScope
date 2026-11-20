import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "",
  headers: { Accept: "application/json" },
  timeout: 15000,
});

export async function getAuctions({ search = "", page = 1, pageSize = 20 } = {}) {
  const response = await api.get("/api/auctions", {
    params: { search: search || undefined, page, page_size: pageSize },
  });
  return response.data;
}

export async function getAuctionById(auctionId) {
  const response = await api.get("/api/auctions/" + auctionId);
  return response.data;
}

export async function getTenders({ search = "", page = 1, pageSize = 20 } = {}) {
  const response = await api.get("/api/tenders", {
    params: { search: search || undefined, page, page_size: pageSize },
  });
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

export async function startCollection(kind) {
  const response = await api.post("/api/collection/" + kind + "/run");
  return response.data;
}

export async function getCollectionStatus(kind) {
  const response = await api.get("/api/collection/" + kind + "/status");
  return response.data;
}
