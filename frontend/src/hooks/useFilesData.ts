"use client";

import { useState, useCallback } from "react";
import type { AlertItem, FileItem } from "@/types";
import { fetchAlerts, fetchFiles, uploadFile } from "@/api/client";

type State = {
  files: FileItem[];
  alerts: AlertItem[];
  isLoading: boolean;
  isSubmitting: boolean;
  errorMessage: string | null;
};

export function useFilesData() {
  const [state, setState] = useState<State>({
    files: [],
    alerts: [],
    isLoading: true,
    isSubmitting: false,
    errorMessage: null,
  });

  const loadData = useCallback(async () => {
    setState((s) => ({ ...s, isLoading: true, errorMessage: null }));
    try {
      const [files, alerts] = await Promise.all([fetchFiles(), fetchAlerts()]);
      setState((s) => ({ ...s, files, alerts }));
    } catch (error) {
      setState((s) => ({
        ...s,
        errorMessage: error instanceof Error ? error.message : "Произошла ошибка",
      }));
    } finally {
      setState((s) => ({ ...s, isLoading: false }));
    }
  }, []);

  const submitFile = useCallback(
    async (title: string, file: File): Promise<boolean> => {
      setState((s) => ({ ...s, isSubmitting: true, errorMessage: null }));
      try {
        await uploadFile(title, file);
        await loadData();
        return true;
      } catch (error) {
        setState((s) => ({
          ...s,
          errorMessage: error instanceof Error ? error.message : "Произошла ошибка",
        }));
        return false;
      } finally {
        setState((s) => ({ ...s, isSubmitting: false }));
      }
    },
    [loadData]
  );

  return { ...state, loadData, submitFile };
}
