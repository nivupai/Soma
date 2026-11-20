import { rampCss } from "./headColor";

export default function ScalarLegend({
  title,
  range,
  units,
  note,
  badge,
}: {
  title: string;
  range: [number, number];
  units: string;
  note?: string;
  badge?: string;
}) {
  const stops = [0, 0.25, 0.5, 0.75, 1]
    .map((q) => `${rampCss(q)} ${q * 100}%`)
    .join(", ");
  return (
    <figure className="scalar-legend" aria-label={`${title} legend`}>
      <figcaption>
        {title}
        {badge && <span className="badge">{badge}</span>}
      </figcaption>
      <div
        className="scalar-legend-bar"
        style={{ background: `linear-gradient(90deg, ${stops})` }}
      />
      <div className="scalar-legend-ticks">
        <span>
          {range[0].toFixed(2)} {units}
        </span>
        <span>
          {range[1].toFixed(2)} {units}
        </span>
      </div>
      {note && <p className="muted small">{note}</p>}
    </figure>
  );
}
