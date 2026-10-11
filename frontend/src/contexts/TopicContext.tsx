import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { Outlet, useParams } from "react-router-dom";

import { createTopicApi, type TopicApi } from "../api/http";
import type { Topic } from "../api/types";

type TopicContextValue = { topic: Topic; api: TopicApi };
const TopicContext = createContext<TopicContextValue | null>(null);

export function useTopicContext(): TopicContextValue {
  const value = useContext(TopicContext);
  if (!value) throw new Error("Esta página requiere un tema.");
  return value;
}

export function useTopicContextOptional(): TopicContextValue | null {
  return useContext(TopicContext);
}

export function TopicLayout() {
  const { topicSlug } = useParams();
  const [topic, setTopic] = useState<Topic | null>(null);
  const [error, setError] = useState<string | null>(null);
  const api = useMemo(
    () => createTopicApi(topicSlug ?? ""),
    [topicSlug],
  );
  useEffect(() => {
    if (!topicSlug) return;
    api.getTopic().then(setTopic).catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : String(reason));
    });
  }, [api, topicSlug]);
  if (error) return <main className="shell"><p className="banner banner--error">{error}</p></main>;
  if (!topic) return <main className="shell"><p>Cargando tema…</p></main>;
  return (
    <TopicContext.Provider value={{ topic, api }}>
      <Outlet />
    </TopicContext.Provider>
  );
}
