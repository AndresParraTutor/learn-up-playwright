import { Link } from "react-router-dom";
import TitleBlock from "../components/TitleBlock";

export default function NotFoundPage() {
  return (
    <main className="shell shell--narrow">
      <TitleBlock title="Página inexistente" eyebrow="404" />
      <p>La ruta solicitada no forma parte de esta aplicación.</p>
      <Link className="btn btn--primary" to="/">Volver al inicio</Link>
    </main>
  );
}
