import { useCallback, useEffect, useRef, useState } from "react";

import {
  getModelManagerStatus,
  startModel,
  stopModel,
} from "../services/modelManagerApi";

const INITIAL_MODEL_STATUS = {
  name: "",
  process_state: "stopped",
  server_ready: false,
  owned_by_app: false,
  pid: null,
  port: null,
  health_url: "",
  log_file: "",
  last_error: null,
};

const INITIAL_STATUS = {
  ocr: {
    ...INITIAL_MODEL_STATUS,
    name: "ocr",
    port: 8000,
  },
  translator: {
    ...INITIAL_MODEL_STATUS,
    name: "translator",
    port: 8001,
  },
};

export function useModelManager({
  pollingInterval = 3000,
  enabled = true,
} = {}) {
  const [status, setStatus] = useState(INITIAL_STATUS);
  const [loading, setLoading] = useState({
    ocr: false,
    translator: false,
  });
  const [error, setError] = useState(null);

  const mountedRef = useRef(true);
  const requestInProgressRef = useRef(false);

  const refreshStatus = useCallback(async () => {
    if (requestInProgressRef.current) {
      return null;
    }

    requestInProgressRef.current = true;

    try {
      const nextStatus = await getModelManagerStatus();

      if (mountedRef.current) {
        setStatus(nextStatus);
        setError(null);
      }

      return nextStatus;
    } catch (requestError) {
      if (mountedRef.current) {
        setError(requestError.message);
      }

      return null;
    } finally {
      requestInProgressRef.current = false;
    }
  }, []);

  const runModelAction = useCallback(
    async (modelName, action) => {
      setLoading((current) => ({
        ...current,
        [modelName]: true,
      }));
      setError(null);

      try {
        const response =
          action === "start"
            ? await startModel(modelName)
            : await stopModel(modelName);

        if (mountedRef.current && response?.model) {
          setStatus((current) => ({
            ...current,
            [modelName]: response.model,
          }));
        }

        await refreshStatus();

        return response;
      } catch (actionError) {
        if (mountedRef.current) {
          setError(actionError.message);
        }

        throw actionError;
      } finally {
        if (mountedRef.current) {
          setLoading((current) => ({
            ...current,
            [modelName]: false,
          }));
        }
      }
    },
    [refreshStatus],
  );

  const start = useCallback(
    (modelName) => runModelAction(modelName, "start"),
    [runModelAction],
  );

  const stop = useCallback(
    (modelName) => runModelAction(modelName, "stop"),
    [runModelAction],
  );

  useEffect(() => {
    mountedRef.current = true;

    if (!enabled) {
      return () => {
        mountedRef.current = false;
      };
    }

    refreshStatus();

    const intervalId = window.setInterval(
      refreshStatus,
      pollingInterval,
    );

    return () => {
      mountedRef.current = false;
      window.clearInterval(intervalId);
    };
  }, [enabled, pollingInterval, refreshStatus]);

  return {
    status,
    loading,
    error,
    refreshStatus,
    startModel: start,
    stopModel: stop,
  };
}
