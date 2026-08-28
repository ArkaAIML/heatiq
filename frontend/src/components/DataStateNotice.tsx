interface DataStateNoticeProps {
  state: "loading" | "unavailable" | "stale" | "error" | "demonstration";
  title: string;
  children: React.ReactNode;
}

export function DataStateNotice({ state, title, children }: DataStateNoticeProps) {
  return (
    <div className="data-state" data-state={state} role={state === "error" ? "alert" : "status"}>
      <span className="data-state__icon" aria-hidden="true">
        {state === "loading" ? "…" : state === "error" ? "×" : "!"}
      </span>
      <div>
        <strong>{title}</strong>
        <p>{children}</p>
      </div>
    </div>
  );
}
