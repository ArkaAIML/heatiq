import type { PresentedValue } from "../types/dashboard";

interface DataValueProps {
  label: string;
  data: PresentedValue<string | number>;
}

export function DataValue({ label, data }: DataValueProps) {
  const unavailable = data.value === null || data.value === "";
  const value = typeof data.value === "number"
    ? data.value.toLocaleString("en-IN", { maximumFractionDigits: 1 })
    : data.value;

  return (
    <div className="data-value" data-state={data.state}>
      <dt>{label}</dt>
      <dd className={unavailable ? "data-value__reading is-unavailable" : "data-value__reading"}>
        {unavailable ? "Unavailable" : value}
        {!unavailable && data.unit ? <span className="data-value__unit"> {data.unit}</span> : null}
      </dd>
      <dd className="data-value__detail">
        {data.state === "demonstration" ? "Demo · " : ""}
        {data.note ?? (unavailable ? "No value supplied" : "")}
      </dd>
    </div>
  );
}
