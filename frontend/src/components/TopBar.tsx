import { useEffect, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { useTopicContextOptional } from "../contexts/TopicContext";
import { IS_HOSTED } from "../config/runtime";

export default function TopBar() {
  const context = useTopicContextOptional();
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  const base = context ? `/t/${context.topic.slug}` : "";
  return (
    <header className={`topbar ${scrolled ? "topbar--scrolled" : ""}`}>
      <div className="topbar__inner">
        <Link className="topbar__mark" to="/" aria-label="Volver al selector de temas">
          <img className="topbar__logo" src="/learn-up-logo.webp" alt="" />
        </Link>
        {context && (
          <>
            <span className="mono topbar__topic">{context.topic.name}</span>
            <nav className="topbar__nav" aria-label="Navegación del tema">
              <NavLink to={base} end>Panel</NavLink>
              <NavLink to={`${base}/lessons`}>Lecciones</NavLink>
              {context.topic.labs_enabled && <NavLink to={`${base}/labs`}>Prácticas</NavLink>}
              {context.topic.strategy_enabled && <NavLink to={`${base}/strategy`}>Estrategia</NavLink>}
              <NavLink to={`${base}/badges`}>Insignias</NavLink>
              <NavLink to={`${base}/about`}>Acerca de</NavLink>
            </nav>
          </>
        )}
        {IS_HOSTED && (
          <a className="topbar__signout" href="/signout-with-chatgpt">
            Cerrar sesión
          </a>
        )}
      </div>
    </header>
  );
}
