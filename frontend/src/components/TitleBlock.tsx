import { Link } from "react-router-dom";

type Props = {
  title: string;
  lede?: string;
  eyebrow?: string;
  backTo?: string;
  backLabel?: string;
  chips?: string[];
};

export default function TitleBlock({
  title,
  lede,
  eyebrow,
  backTo,
  backLabel,
  chips = [],
}: Props) {
  return (
    <header className="title-block">
      {backTo && <Link to={backTo}>← {backLabel ?? "Volver"}</Link>}
      {eyebrow && <p className="mono">{eyebrow}</p>}
      <h1>{title}</h1>
      {lede && <p>{lede}</p>}
      {chips.length > 0 && (
        <div className="row">
          {chips.map((chip) => (
            <span className="chip" key={chip}>
              {chip}
            </span>
          ))}
        </div>
      )}
    </header>
  );
}
