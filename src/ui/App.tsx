import { useEffect, useState } from "react";

type HealthStatus = "ok" | "unavailable" | "checking";

export default function App() {
  const [status, setStatus] = useState<HealthStatus>("checking");

  useEffect(() => {
    let cancelled = false;

    fetch("/api/health")
      .then((response) => response.json())
      .then((data) => {
        if (cancelled) return;
        setStatus(data.status === "ok" ? "ok" : "unavailable");
      })
      .catch(() => {
        if (cancelled) return;
        setStatus("unavailable");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  if (status === "checking") {
    return <p>Backend: checking</p>;
  }

  return <p>Backend: {status === "ok" ? "ok" : "unavailable"}</p>;
}
