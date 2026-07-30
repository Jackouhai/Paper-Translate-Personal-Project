const DEFAULT_API_BASE_URL = "http://127.0.0.1:8002";

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL
).replace(/\/+$/, "");

async function parseApiResponse(response) {
  const contentType = response.headers.get("content-type") || "";

  let payload = null;

  if (contentType.includes("application/json")) {
    payload = await response.json();
  } else {
    const text = await response.text();
    payload = text ? { detail: text } : null;
  }

  if (!response.ok) {
    const message =
      payload?.detail ||
      payload?.message ||
      `Request failed with status ${response.status}`;

    throw new Error(message);
  }

  return payload;
}

async function request(path, options = {}) {
  let response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        Accept: "application/json",
        ...options.headers,
      },
    });
  } catch (error) {
    throw new Error(
      `Cannot connect to PaperTranslate backend at ${API_BASE_URL}.`,
      { cause: error },
    );
  }

  return parseApiResponse(response);
}

export function getModelManagerStatus() {
  return request("/pipeline/model-manager/status");
}

export function startModel(modelName) {
  validateModelName(modelName);

  return request(`/pipeline/model-manager/${modelName}/start`, {
    method: "POST",
  });
}

export function stopModel(modelName) {
  validateModelName(modelName);

  return request(`/pipeline/model-manager/${modelName}/stop`, {
    method: "POST",
  });
}

export function startOcrModel() {
  return startModel("ocr");
}

export function stopOcrModel() {
  return stopModel("ocr");
}

export function startTranslatorModel() {
  return startModel("translator");
}

export function stopTranslatorModel() {
  return stopModel("translator");
}

function validateModelName(modelName) {
  if (!["ocr", "translator"].includes(modelName)) {
    throw new Error(`Unsupported model: ${modelName}`);
  }
}

export const modelManagerApiBaseUrl = API_BASE_URL;

