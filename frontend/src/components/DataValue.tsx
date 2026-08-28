interface DataValueProps {
  label: string;
  value?: string | number | null;
  unit?: string;
  detail?: string;
}

export function DataValue({ label, value, unit, detail }: DataValueProps) {
  const unavailable = value === null || value === undefined || value === "";

  return (
    <div className="data-value">
      <dt>{label}</dt>
      <dd className={unavailable ? "data-value__reading is-unavailable" : "data-value__reading"}>
        {unavailable ? "Unavailable" : value}
        {!unavailable && unit ? <span className="data-value__unit"> {unit}</span> : null}
      </dd>
      {detail ? <dd className="data-value__detail">{detail}</dd> : null}
    </div>
  );
}
