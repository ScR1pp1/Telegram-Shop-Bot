import axios from "axios";

export const http = axios.create({
  baseURL: "https://telegram-shop-api.loca.lt/api"
});

let initData: string | null = null;

export function setInitData(v: string) {
  initData = v;
}

http.interceptors.request.use((config) => {
  if (initData) {
    config.headers = config.headers ?? {};
    config.headers["Authorization"] = `tma ${initData}`;
  }
  return config;
});

http.interceptors.response.use(
  response => {
    console.log('API Response:', response.config.url, response.status);
    return response;
  },
  error => {
    console.error('API Error:', error.config?.url, error.message);
    return Promise.reject(error);
  }
);